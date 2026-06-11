from pathlib import Path

import pytest

from review_gauntlet.targets import HeadMode, TargetKind, resolve_target


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


def test_rejects_mixed_target_modes(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_target(root=tmp_path, base_ref="main", head_ref="HEAD", worktree=True, commit=None)


def test_rejects_partial_branch_options(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_target(root=tmp_path, base_ref="main", head_ref=None, worktree=False, commit=None)
