import hashlib
import subprocess
from pathlib import Path

import pytest

from review_gauntlet.targets import (
    HeadMode,
    TargetKind,
    file_digests,
    file_digests_at_commit,
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


def test_default_target_is_head_commit(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    head = _git(tmp_path, "rev-parse", "HEAD")

    target = resolve_target(root=tmp_path, base_ref=None, head_ref=None, commit=None)

    assert target.kind == TargetKind.COMMIT
    assert target.commit == head
    assert target.head_mode == HeadMode.FIXED


def test_branch_target_has_moving_head(tmp_path: Path) -> None:
    target = resolve_target(root=tmp_path, base_ref="main", head_ref="HEAD", commit=None)
    assert target.kind == TargetKind.BRANCH
    assert target.head_mode == HeadMode.MOVING


def test_all_target_is_head_commit(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    head = _git(tmp_path, "rev-parse", "HEAD")

    target = resolve_target(
        root=tmp_path, base_ref=None, head_ref=None, commit=None, all_files=True
    )

    assert target.kind == TargetKind.COMMIT
    assert target.commit == head
    assert target.head_mode == HeadMode.FIXED


def test_commit_target_has_fixed_head(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    commit = _git(tmp_path, "rev-parse", "HEAD")

    target = resolve_target(root=tmp_path, base_ref=None, head_ref=None, commit=commit)

    assert target.kind == TargetKind.COMMIT
    assert target.commit == commit
    assert target.head_mode == HeadMode.FIXED


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


def test_file_digests_at_commit_reads_committed_content(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "app.py"
    source.write_text("print('committed')\n", encoding="utf-8")
    _git(tmp_path, "add", "src/app.py")
    _git(tmp_path, "commit", "-m", "add app")
    commit = _git(tmp_path, "rev-parse", "HEAD")

    source.write_text("print('working tree')\n", encoding="utf-8")

    assert (
        file_digests_at_commit(tmp_path, commit)["src/app.py"]
        == hashlib.sha256(b"print('committed')\n").hexdigest()
    )
    assert (
        file_digests(tmp_path)["src/app.py"]
        == hashlib.sha256(b"print('working tree')\n").hexdigest()
    )


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
