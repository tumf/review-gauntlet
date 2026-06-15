from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass
class GitCommandError(RuntimeError):
    argv: tuple[str, ...]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str

    def __str__(self) -> str:
        detail = self.stderr.strip() or self.stdout.strip() or f"exit status {self.returncode}"
        return f"git {' '.join(self.argv)} failed in {self.cwd}: {detail}"


@dataclass(frozen=True)
class GitWorktreeMetadata:
    enabled: bool
    base_branch: str
    base_commit: str
    session_branch: str
    worktree_path: str

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "base_branch": self.base_branch,
            "base_commit": self.base_commit,
            "session_branch": self.session_branch,
            "worktree_path": self.worktree_path,
        }


@dataclass(frozen=True)
class GitWorktreeCleanupResult:
    cleaned_up: bool
    removed_worktree_path: str | None
    deleted_branch: str | None
    cleanup_blockers: tuple[str, ...]


@dataclass(frozen=True)
class GitWorktreeMergeResult:
    merged: bool
    cleaned_up: bool
    base_branch: str | None = None
    session_branch: str | None = None
    session_commit: str | None = None
    merge_commit: str | None = None
    removed_worktree_path: str | None = None
    deleted_branch: str | None = None
    finalize_blockers: tuple[str, ...] = ()
    cleanup_blockers: tuple[str, ...] = ()
    next_required_action: str | None = None


def git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, timeout=10, check=False
    )
    if check and completed.returncode != 0:
        raise GitCommandError(args, root, completed.returncode, completed.stdout, completed.stderr)
    return completed.stdout.strip()


def create_session_worktree(root: Path, session_id: str) -> GitWorktreeMetadata:
    base_branch = _current_branch(root)
    base_commit = git(root, "rev-parse", "--verify", "HEAD^{commit}")
    session_branch = _unique_session_branch(root, session_id)
    worktree_path = Path(".review-gauntlet") / "worktrees" / session_id
    absolute_worktree = root / worktree_path
    absolute_worktree.parent.mkdir(parents=True, exist_ok=True)
    git(root, "worktree", "add", "-b", session_branch, str(absolute_worktree), base_commit)
    return GitWorktreeMetadata(
        enabled=True,
        base_branch=base_branch,
        base_commit=base_commit,
        session_branch=session_branch,
        worktree_path=worktree_path.as_posix(),
    )


def merge_session_worktree(
    root: Path,
    metadata: dict[str, object],
    *,
    session_id: str,
    commit_paths: tuple[str, ...],
) -> GitWorktreeMergeResult:
    git_meta = _git_worktree_metadata(metadata)
    if git_meta is None:
        return GitWorktreeMergeResult(
            merged=False,
            cleaned_up=False,
            finalize_blockers=("merge finalization requires a Git-worktree-backed session",),
            next_required_action="resolve_finalize_blockers",
        )
    blockers = merge_preflight_blockers(root, git_meta)
    if blockers:
        return GitWorktreeMergeResult(
            merged=False,
            cleaned_up=False,
            base_branch=str(git_meta["base_branch"]),
            session_branch=str(git_meta["session_branch"]),
            finalize_blockers=tuple(blockers),
            next_required_action="resolve_finalize_blockers",
        )
    session_worktree = (root / str(git_meta["worktree_path"])).resolve()
    session_branch = str(git_meta["session_branch"])
    base_branch = str(git_meta["base_branch"])
    _commit_session_changes(session_worktree, session_id=session_id, commit_paths=commit_paths)
    session_commit = git(session_worktree, "rev-parse", "--verify", "HEAD^{commit}")
    git(root, "merge", "--ff-only", session_branch)
    merge_commit = git(root, "rev-parse", "--verify", "HEAD^{commit}")
    cleanup = cleanup_session_worktree(root, git_meta)
    return GitWorktreeMergeResult(
        merged=True,
        cleaned_up=cleanup.cleaned_up,
        base_branch=base_branch,
        session_branch=session_branch,
        session_commit=session_commit,
        merge_commit=merge_commit,
        removed_worktree_path=cleanup.removed_worktree_path,
        deleted_branch=cleanup.deleted_branch,
        cleanup_blockers=cleanup.cleanup_blockers,
        next_required_action=None if cleanup.cleaned_up else "cleanup_git_worktree",
    )


def merge_preflight_blockers(root: Path, git_meta: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    base_branch = str(git_meta.get("base_branch", ""))
    base_commit = str(git_meta.get("base_commit", ""))
    session_branch = str(git_meta.get("session_branch", ""))
    worktree_path = str(git_meta.get("worktree_path", ""))
    session_worktree = (root / worktree_path).resolve()
    if not _ref_exists(root, base_branch):
        blockers.append(f"base branch is missing: {base_branch}")
    if not _ref_exists(root, session_branch):
        blockers.append(f"session branch is missing: {session_branch}")
    if not session_worktree.is_dir():
        blockers.append(f"session worktree is missing: {worktree_path}")
    if _base_dirty_paths(root):
        blockers.append("base branch worktree has uncommitted files")
    if _ref_exists(root, base_branch):
        current_base = git(root, "rev-parse", "--verify", f"{base_branch}^{{commit}}")
        if current_base != base_commit:
            blockers.append("base branch has advanced from recorded base_commit")
    if not blockers:
        merge_tree_result = subprocess.run(
            ["git", "merge-tree", "--write-tree", base_branch, session_branch],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        merge_tree_output = f"{merge_tree_result.stdout}\n{merge_tree_result.stderr}"
        if merge_tree_result.returncode != 0 or "<<<<<<<" in merge_tree_output:
            blockers.append("session branch would conflict with base branch")
    return blockers


def cleanup_session_worktree(root: Path, git_meta: dict[str, object]) -> GitWorktreeCleanupResult:
    worktree_path = str(git_meta["worktree_path"])
    session_branch = str(git_meta["session_branch"])
    blockers: list[str] = []
    removed: str | None = None
    deleted: str | None = None
    try:
        git(root, "worktree", "remove", worktree_path)
        removed = worktree_path
    except GitCommandError as exc:
        blockers.append(str(exc))
    try:
        git(root, "branch", "-d", session_branch)
        deleted = session_branch
    except GitCommandError as exc:
        blockers.append(str(exc))
    return GitWorktreeCleanupResult(
        cleaned_up=not blockers,
        removed_worktree_path=removed,
        deleted_branch=deleted,
        cleanup_blockers=tuple(blockers),
    )


def _current_branch(root: Path) -> str:
    branch = git(root, "branch", "--show-current")
    if not branch:
        raise ValueError("init --git-worktree requires a named base branch, not detached HEAD")
    return branch


def _unique_session_branch(root: Path, session_id: str) -> str:
    base = f"review-gauntlet/{session_id}"
    branch = base
    suffix = 1
    while _ref_exists(root, branch):
        suffix += 1
        branch = f"{base}-{suffix}"
    return branch


def _ref_exists(root: Path, ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        ).returncode
        == 0
    )


def _base_dirty_paths(root: Path) -> tuple[str, ...]:
    output = git(root, "status", "--porcelain", check=True)
    paths: list[str] = []
    for line in output.splitlines():
        path = line[3:]
        if not path.startswith(".review-gauntlet/"):
            paths.append(path)
    return tuple(paths)


def _git_worktree_metadata(metadata: dict[str, object]) -> dict[str, object] | None:
    raw = metadata.get("git_worktree")
    if not isinstance(raw, dict):
        return None
    git_meta = cast(dict[str, Any], raw)
    if git_meta.get("enabled") is not True:
        return None
    required = ("base_branch", "base_commit", "session_branch", "worktree_path")
    for key in required:
        value = git_meta.get(key)
        if not isinstance(value, str) or not value:
            return None
    return cast(dict[str, object], git_meta)


def _commit_session_changes(
    session_worktree: Path, *, session_id: str, commit_paths: tuple[str, ...]
) -> None:
    git(session_worktree, "add", "--", *commit_paths)
    dirty = git(session_worktree, "diff", "--cached", "--name-only")
    if not dirty:
        return
    git(session_worktree, "commit", "-m", f"Finalize review-gauntlet session {session_id}")
