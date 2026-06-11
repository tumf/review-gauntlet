import subprocess
from pathlib import Path

import pytest

from review_gauntlet.targets import HeadMode, TargetKind, resolve_target


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "initial")


def test_default_target_is_workspace_diff(tmp_path: Path) -> None:
    target = resolve_target(
        root=tmp_path, base_ref=None, head_ref=None, worktree=False, commit=None
    )
    assert target.kind == TargetKind.WORKTREE
    assert target.head_mode == HeadMode.MOVING


def test_branch_target_has_moving_head(tmp_path: Path) -> None:
    target = resolve_target(
        root=tmp_path, base_ref="main", head_ref="HEAD", worktree=False, commit=None
    )
    assert target.kind == TargetKind.BRANCH
    assert target.head_mode == HeadMode.MOVING


def test_worktree_target_has_moving_head(tmp_path: Path) -> None:
    target = resolve_target(root=tmp_path, base_ref=None, head_ref=None, worktree=True, commit=None)
    assert target.kind == TargetKind.WORKTREE
    assert target.head_mode == HeadMode.MOVING


def test_all_target_has_moving_head(tmp_path: Path) -> None:
    target = resolve_target(
        root=tmp_path, base_ref=None, head_ref=None, worktree=False, commit=None, all_files=True
    )
    assert target.kind == TargetKind.ALL
    assert target.head_mode == HeadMode.MOVING


def test_commit_target_has_fixed_head(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    target = resolve_target(
        root=tmp_path, base_ref=None, head_ref=None, worktree=False, commit=commit
    )

    assert target.kind == TargetKind.COMMIT
    assert target.commit == commit
    assert target.head_mode == HeadMode.FIXED


@pytest.mark.parametrize(
    ("base_ref", "head_ref", "worktree", "commit", "all_files"),
    [
        ("main", "HEAD", True, None, False),
        (None, None, True, None, True),
        ("main", "HEAD", False, "HEAD", False),
    ],
)
def test_rejects_mixed_target_modes(
    tmp_path: Path,
    base_ref: str | None,
    head_ref: str | None,
    worktree: bool,
    commit: str | None,
    all_files: bool,
) -> None:
    with pytest.raises(ValueError):
        resolve_target(
            root=tmp_path,
            base_ref=base_ref,
            head_ref=head_ref,
            worktree=worktree,
            commit=commit,
            all_files=all_files,
        )


def test_rejects_partial_branch_options(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_target(root=tmp_path, base_ref="main", head_ref=None, worktree=False, commit=None)
