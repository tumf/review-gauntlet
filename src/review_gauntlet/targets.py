from __future__ import annotations

import hashlib
import subprocess
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from review_gauntlet.inventory import (
    UnsafeRepositoryPathError,
    resolve_under_root,
    should_include_review_relative_path,
)


class TargetKind(StrEnum):
    BRANCH = "branch"
    COMMIT = "commit"


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
    commit: str | None,
    all_files: bool = False,
) -> TargetSpec:
    modes = sum([bool(base_ref or head_ref), bool(commit), all_files])
    if modes > 1:
        raise ValueError("choose at most one target mode: --from/--to, --commit, or --all")
    if bool(base_ref) != bool(head_ref):
        raise ValueError("branch mode requires both --from and --to")
    if base_ref and head_ref:
        return TargetSpec(
            kind=TargetKind.BRANCH, base_ref=base_ref, head_ref=head_ref, head_mode=HeadMode.MOVING
        )
    target_commit = commit
    if all_files or target_commit is None:
        try:
            target_commit = _git(root, "rev-parse", "HEAD^{commit}")
        except (OSError, subprocess.SubprocessError):
            target_commit = "HEAD"
    else:
        _git(root, "rev-parse", "--verify", f"{target_commit}^{{commit}}")
    return TargetSpec(
        kind=TargetKind.COMMIT,
        base_ref="__all__" if all_files else None,
        commit=target_commit,
        head_mode=HeadMode.FIXED,
    )


def changed_files_for_target(root: Path, target: TargetSpec) -> tuple[str, ...] | None:
    """Return target-scoped relative paths, or None for full inventory/fallback mode."""
    if target.kind == TargetKind.BRANCH:
        if target.base_ref is None or target.head_ref is None:
            raise ValueError("branch target requires base_ref and head_ref")
        output = _git(root, "diff", "--name-only", target.base_ref, target.head_ref)
        return _split_git_paths(output)
    if target.kind == TargetKind.COMMIT:
        if target.commit is None:
            raise ValueError("commit target requires commit")
        if target.base_ref == "__all__":
            try:
                return tuple(file_digests_at_commit(root, target.commit))
            except (OSError, subprocess.SubprocessError):
                return None
        try:
            output = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", target.commit)
            return _split_git_paths(output)
        except (OSError, subprocess.SubprocessError):
            return None
    raise ValueError(f"unsupported target kind: {target.kind}")


def _split_git_paths(output: str) -> tuple[str, ...]:
    return tuple(sorted({line for line in output.splitlines() if line}))


def review_universe_files(root: Path) -> tuple[Path, ...]:
    repo_root = root.resolve()
    paths: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(repo_root).as_posix()
        if not should_include_review_relative_path(relative):
            continue
        try:
            resolved = resolve_under_root(repo_root, relative)
        except UnsafeRepositoryPathError:
            continue
        if resolved != path.resolve():
            continue
        paths.append(path)
    return tuple(sorted(paths))


def target_digest(root: Path) -> str:
    repo_root = root.resolve()
    digest = hashlib.sha256()
    for path in review_universe_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_digests(root: Path) -> dict[str, str]:
    repo_root = root.resolve()
    result: dict[str, str] = {}
    for path in review_universe_files(repo_root):
        result[path.relative_to(repo_root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return result


def file_digests_at_commit(root: Path, commit: str) -> dict[str, str]:
    repo_root = root.resolve()
    result: dict[str, str] = {}
    for relative in _review_universe_files_at_commit(repo_root, commit):
        try:
            content = _git_bytes(repo_root, "show", f"{commit}:{relative}")
        except subprocess.CalledProcessError:
            continue
        result[relative] = hashlib.sha256(content).hexdigest()
    return result


def _review_universe_files_at_commit(root: Path, commit: str) -> tuple[str, ...]:
    output = _git_bytes(root, "ls-tree", "-r", "-z", commit)
    paths: list[str] = []
    for record in output.split(b"\0"):
        if not record:
            continue
        header, separator, raw_path = record.partition(b"\t")
        if not separator or b" blob " not in header:
            continue
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        if not should_include_review_relative_path(relative):
            continue
        try:
            normalize_repository_relative_path = relative.replace("\\", "/")
            resolve_under_root(root, normalize_repository_relative_path)
        except UnsafeRepositoryPathError:
            continue
        paths.append(relative)
    return tuple(sorted(paths))


def _git(root: Path, *args: str) -> str:
    return _git_bytes(root, *args).decode("utf-8").strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        timeout=10,
        check=True,
    )
    return completed.stdout
