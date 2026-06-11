from __future__ import annotations

import hashlib
import subprocess
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class TargetKind(StrEnum):
    BRANCH = "branch"
    WORKTREE = "worktree"
    COMMIT = "commit"
    ALL = "all"


class HeadMode(StrEnum):
    MOVING = "moving"
    FIXED = "fixed"


class TargetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TargetKind
    base_ref: str | None = None
    head_ref: str | None = None
    commit: str | None = None
    head_mode: HeadMode


def resolve_target(
    *,
    root: Path,
    base_ref: str | None,
    head_ref: str | None,
    worktree: bool,
    commit: str | None,
    all_files: bool = False,
) -> TargetSpec:
    modes = sum([bool(base_ref or head_ref), worktree, bool(commit), all_files])
    if modes > 1:
        raise ValueError(
            "choose at most one target mode: --from/--to, --worktree, --commit, or --all"
        )
    if bool(base_ref) != bool(head_ref):
        raise ValueError("branch mode requires both --from and --to")
    if base_ref and head_ref:
        return TargetSpec(
            kind=TargetKind.BRANCH, base_ref=base_ref, head_ref=head_ref, head_mode=HeadMode.MOVING
        )
    if commit is not None:
        _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
        return TargetSpec(kind=TargetKind.COMMIT, commit=commit, head_mode=HeadMode.FIXED)
    if all_files:
        return TargetSpec(kind=TargetKind.ALL, head_mode=HeadMode.MOVING)
    return TargetSpec(kind=TargetKind.WORKTREE, head_mode=HeadMode.MOVING)


def changed_files_for_target(root: Path, target: TargetSpec) -> tuple[str, ...] | None:
    """Return target-scoped relative paths, or None for full inventory/fallback mode."""
    if target.kind == TargetKind.ALL:
        return None
    if target.kind == TargetKind.WORKTREE:
        return _workspace_changed_files(root)
    if target.kind == TargetKind.BRANCH:
        if target.base_ref is None or target.head_ref is None:
            raise ValueError("branch target requires base_ref and head_ref")
        output = _git(root, "diff", "--name-only", target.base_ref, target.head_ref)
        return _split_git_paths(output)
    if target.kind == TargetKind.COMMIT:
        if target.commit is None:
            raise ValueError("commit target requires commit")
        output = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", target.commit)
        return _split_git_paths(output)
    raise ValueError(f"unsupported target kind: {target.kind}")


def _workspace_changed_files(root: Path) -> tuple[str, ...] | None:
    try:
        staged = _git(root, "diff", "--name-only", "--cached")
        unstaged = _git(root, "diff", "--name-only")
        untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    except (OSError, subprocess.SubprocessError):
        return None
    return _split_git_paths("\n".join([staged, unstaged, untracked]))


def _split_git_paths(output: str) -> tuple[str, ...]:
    return tuple(sorted({line for line in output.splitlines() if line}))


def target_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        p for p in root.rglob("*") if p.is_file() and ".review-gauntlet" not in p.parts
    ):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_digests(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(
        p for p in root.rglob("*") if p.is_file() and ".review-gauntlet" not in p.parts
    ):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    return completed.stdout.strip()
