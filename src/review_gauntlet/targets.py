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
    *, root: Path, base_ref: str | None, head_ref: str | None, worktree: bool, commit: str | None
) -> TargetSpec:
    modes = sum([bool(base_ref or head_ref), worktree, bool(commit)])
    if modes != 1:
        raise ValueError("choose exactly one target mode: --from/--to, --worktree, or --commit")
    if bool(base_ref) != bool(head_ref):
        raise ValueError("branch mode requires both --from and --to")
    if base_ref and head_ref:
        return TargetSpec(
            kind=TargetKind.BRANCH, base_ref=base_ref, head_ref=head_ref, head_mode=HeadMode.MOVING
        )
    if worktree:
        return TargetSpec(kind=TargetKind.WORKTREE, head_mode=HeadMode.MOVING)
    if commit is None:
        raise ValueError("commit mode requires --commit")
    _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
    return TargetSpec(kind=TargetKind.COMMIT, commit=commit, head_mode=HeadMode.FIXED)


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
