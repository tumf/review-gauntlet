import hashlib
import subprocess
from pathlib import Path

import pytest

import review_gauntlet.targets as targets_module
from review_gauntlet.targets import (
    HeadMode,
    TargetKind,
    TargetSpec,
    changed_files_for_target,
    file_digests,
    resolve_target,
    target_digest,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "initial")


def test_default_target_is_worktree(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    target = resolve_target(root=tmp_path, base_ref=None, head_ref=None, commit=None)

    assert target.kind == TargetKind.WORKTREE
    assert target.head_mode == HeadMode.MOVING


def test_branch_target_has_moving_head(tmp_path: Path) -> None:
    target = resolve_target(root=tmp_path, base_ref="main", head_ref="HEAD", commit=None)
    assert target.kind == TargetKind.BRANCH
    assert target.head_mode == HeadMode.MOVING


def test_all_target_reviews_full_inventory(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    target = resolve_target(
        root=tmp_path, base_ref=None, head_ref=None, commit=None, all_files=True
    )

    assert target.kind == TargetKind.ALL
    assert target.head_mode == HeadMode.MOVING


def test_commit_target_has_fixed_head(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    commit = _git(tmp_path, "rev-parse", "HEAD")

    target = resolve_target(root=tmp_path, base_ref=None, head_ref=None, commit=commit)

    assert target.kind == TargetKind.COMMIT
    assert target.commit == commit
    assert target.head_mode == HeadMode.FIXED


def test_changed_files_for_all_target_uses_full_inventory(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    target = resolve_target(
        root=tmp_path, base_ref=None, head_ref=None, commit=None, all_files=True
    )

    assert changed_files_for_target(tmp_path, target) is None


@pytest.mark.parametrize(
    ("base_ref", "head_ref", "commit", "all_files"),
    [
        ("main", "HEAD", "HEAD", False),
        ("main", "HEAD", None, True),
        (None, None, "HEAD", True),
    ],
)
def test_rejects_mixed_target_modes(
    tmp_path: Path,
    base_ref: str | None,
    head_ref: str | None,
    commit: str | None,
    all_files: bool,
) -> None:
    with pytest.raises(ValueError):
        resolve_target(
            root=tmp_path,
            base_ref=base_ref,
            head_ref=head_ref,
            commit=commit,
            all_files=all_files,
        )


def test_rejects_partial_branch_options(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_target(root=tmp_path, base_ref="main", head_ref=None, commit=None)


def test_workspace_changed_files_tracks_staged_unstaged_and_untracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "staged.py").write_text("print('staged')\n", encoding="utf-8")
    (tmp_path / "unstaged.py").write_text("print('unstaged')\n", encoding="utf-8")
    (tmp_path / "untracked.py").write_text("print('untracked')\n", encoding="utf-8")
    _git(tmp_path, "add", "staged.py")
    _git(tmp_path, "add", "unstaged.py")
    (tmp_path / "unstaged.py").write_text("print('unstaged changed')\n", encoding="utf-8")
    target = resolve_target(root=tmp_path, base_ref=None, head_ref=None, commit=None)

    assert changed_files_for_target(tmp_path, target) == (
        "staged.py",
        "unstaged.py",
        "untracked.py",
    )
    assert (
        file_digests(tmp_path)["unstaged.py"]
        == hashlib.sha256(b"print('unstaged changed')\n").hexdigest()
    )


def test_branch_target_with_worktree_inclusion_returns_union(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(root: Path, *args: str) -> str:
        assert root == tmp_path
        assert args == ("diff", "--name-only", "base", "head")
        return "committed.py\noverlap.py\n"

    def fake_workspace_changed_files(root: Path) -> tuple[str, ...]:
        assert root == tmp_path
        return ("overlap.py", "staged.py", "unstaged.py", "untracked.py")

    monkeypatch.setattr(targets_module, "_git", fake_git)
    monkeypatch.setattr(
        targets_module,
        "_workspace_changed_files",
        fake_workspace_changed_files,
    )
    target = TargetSpec(
        kind=TargetKind.BRANCH,
        base_ref="base",
        head_ref="head",
        head_mode=HeadMode.MOVING,
        include_worktree=True,
    )

    assert changed_files_for_target(tmp_path, target) == (
        "committed.py",
        "overlap.py",
        "staged.py",
        "unstaged.py",
        "untracked.py",
    )


def test_explicit_branch_target_excludes_worktree_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_git(root: Path, *args: str) -> str:
        assert root == tmp_path
        return "committed.py\n"

    def fake_workspace_changed_files(root: Path) -> tuple[str, ...]:
        assert root == tmp_path
        return ("uncommitted.py",)

    monkeypatch.setattr(targets_module, "_git", fake_git)
    monkeypatch.setattr(
        targets_module,
        "_workspace_changed_files",
        fake_workspace_changed_files,
    )
    target = TargetSpec(
        kind=TargetKind.BRANCH,
        base_ref="base",
        head_ref="head",
        head_mode=HeadMode.MOVING,
    )

    assert changed_files_for_target(tmp_path, target) == ("committed.py",)


def test_target_digest_and_file_digests_skip_symlink_escape(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    outside = tmp_path.parent / "outside-target-digest.py"
    outside.write_text("print('escape v1')\n", encoding="utf-8")
    (tmp_path / "src" / "escape.py").symlink_to(outside)

    original_digest = target_digest(tmp_path)
    original_file_digests = file_digests(tmp_path)
    outside.write_text("print('escape v2')\n", encoding="utf-8")

    assert target_digest(tmp_path) == original_digest
    assert file_digests(tmp_path) == original_file_digests
    assert set(original_file_digests) == {"src/app.py"}


def test_target_digest_and_file_digests_ignore_default_review_exclusions(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "app.py"
    source.write_text("print('v1')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    excluded_test = tmp_path / "tests" / "test_app.py"
    excluded_test.write_text("def test_app(): pass\n", encoding="utf-8")
    excluded_rust_test = tmp_path / "foo_test.rs"
    excluded_rust_test.write_text("#[test]\nfn it_works() {}\n", encoding="utf-8")
    (tmp_path / "target" / "debug").mkdir(parents=True)
    excluded_artifact = tmp_path / "target" / "debug" / "app"
    excluded_artifact.write_text("binary-v1\n", encoding="utf-8")

    original_digest = target_digest(tmp_path)
    original_file_digests = file_digests(tmp_path)
    excluded_test.write_text("def test_app(): assert True\n", encoding="utf-8")
    excluded_rust_test.write_text("#[test]\nfn it_changed() {}\n", encoding="utf-8")
    excluded_artifact.write_text("binary-v2\n", encoding="utf-8")

    assert target_digest(tmp_path) == original_digest
    assert file_digests(tmp_path) == original_file_digests
    assert set(original_file_digests) == {"src/app.py"}

    source.write_text("print('v2')\n", encoding="utf-8")

    assert target_digest(tmp_path) != original_digest
    assert file_digests(tmp_path)["src/app.py"] != original_file_digests["src/app.py"]


def test_target_digest_and_file_digests_match_relative_and_absolute_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert target_digest(Path(".")) == target_digest(tmp_path.resolve())
    assert (
        file_digests(Path("."))
        == file_digests(tmp_path.resolve())
        == {"src/app.py": file_digests(tmp_path)["src/app.py"]}
    )
