from __future__ import annotations

import subprocess
from pathlib import Path
from typing import cast

import pytest

from review_gauntlet.checkpoint import commit_latest_checkpoint, write_latest_checkpoint
from review_gauntlet.review_cells import CellState, ReviewCell
from review_gauntlet.session_store import SessionStore


def _git(root: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=check, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "initial")


def _write_checkpoint(root: Path, content: str = "{}\n") -> tuple[str, ...]:
    checkpoints_dir = root / ".review-gauntlet" / "checkpoints"
    checkpoint_dir = checkpoints_dir / "RGC-test-RGS-test"
    checkpoint_dir.mkdir(parents=True)
    generated_files: list[str] = []
    for name in ("status.json", "findings.json", "events.json", "summary.md"):
        path = checkpoint_dir / name
        path.write_text(content if name == "status.json" else f"{name}\n", encoding="utf-8")
        generated_files.append(path.relative_to(root).as_posix())
    (checkpoints_dir / "latest").write_text("RGC-test-RGS-test\n", encoding="utf-8")
    return tuple(generated_files)


def _write_real_checkpoint(root: Path) -> tuple[str, dict[str, object]]:
    store = SessionStore(root)
    session_id = store.create_session(
        {
            "session_id": "RGS-test",
            "root": str(root),
            "target": {"all_files": True},
        },
        (
            ReviewCell(
                id="cell-1",
                file_path="README.md",
                rule_id="docs-accuracy",
                slice_id="docs",
                state=CellState.REVIEWED,
                content_digest="digest",
            ),
        ),
    )
    _git(root, "add", ".review-gauntlet/active-session.json", ".review-gauntlet/ledger.sqlite")
    _git(root, "commit", "-m", "session state")
    checkpoint = write_latest_checkpoint(
        store,
        root,
        session_id,
        {"coverage": {"reviewed": 1}, "finding_state_counts": {}, "run_count": 1},
    )
    return session_id, checkpoint


def test_commit_latest_checkpoint_commits_only_checkpoint_paths(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is True
    assert result.commit == _git(tmp_path, "rev-parse", "--verify", "HEAD^{commit}")
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed_paths == [
        ".review-gauntlet/checkpoints/RGC-test-RGS-test/events.json",
        ".review-gauntlet/checkpoints/RGC-test-RGS-test/findings.json",
        ".review-gauntlet/checkpoints/RGC-test-RGS-test/status.json",
        ".review-gauntlet/checkpoints/RGC-test-RGS-test/summary.md",
        ".review-gauntlet/checkpoints/latest",
    ]
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_commit_latest_checkpoint_commits_real_write_latest_checkpoint_layout(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    session_id, checkpoint = _write_real_checkpoint(tmp_path)

    generated_files = tuple(cast(list[str], checkpoint["generated_files"]))
    result = commit_latest_checkpoint(
        tmp_path,
        session_id=session_id,
        generated_files=generated_files,
    )

    assert result.committed is True
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed_paths == [
        f"{checkpoint['checkpoint_dir']}/events.json",
        f"{checkpoint['checkpoint_dir']}/findings.json",
        f"{checkpoint['checkpoint_dir']}/status.json",
        f"{checkpoint['checkpoint_dir']}/summary.md",
        ".review-gauntlet/checkpoints/latest",
    ]
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_commit_latest_checkpoint_commits_real_layout_with_empty_generated_files(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    session_id, checkpoint = _write_real_checkpoint(tmp_path)

    result = commit_latest_checkpoint(tmp_path, session_id=session_id, generated_files=())

    assert result.committed is True
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed_paths == [
        f"{checkpoint['checkpoint_dir']}/events.json",
        f"{checkpoint['checkpoint_dir']}/findings.json",
        f"{checkpoint['checkpoint_dir']}/status.json",
        f"{checkpoint['checkpoint_dir']}/summary.md",
        ".review-gauntlet/checkpoints/latest",
    ]
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_commit_latest_checkpoint_commits_real_layout_with_incomplete_generated_files(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    session_id, checkpoint = _write_real_checkpoint(tmp_path)
    generated_files = (f"{checkpoint['checkpoint_dir']}/status.json",)

    result = commit_latest_checkpoint(
        tmp_path,
        session_id=session_id,
        generated_files=generated_files,
    )

    assert result.committed is True
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed_paths == [
        f"{checkpoint['checkpoint_dir']}/events.json",
        f"{checkpoint['checkpoint_dir']}/findings.json",
        f"{checkpoint['checkpoint_dir']}/status.json",
        f"{checkpoint['checkpoint_dir']}/summary.md",
        ".review-gauntlet/checkpoints/latest",
    ]
    assert _git(tmp_path, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "pointer_value",
    ["", "../RGC-test-RGS-test", "nested/RGC-test-RGS-test", "/tmp/RGC-test", "RGC-ä"],
)
def test_commit_latest_checkpoint_blocks_fallback_for_unsafe_latest_pointer_values(
    tmp_path: Path, pointer_value: str
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").write_text(
        f"{pointer_value}\n", encoding="utf-8"
    )

    result = commit_latest_checkpoint(tmp_path, session_id="RGS-test", generated_files=())

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == tuple(sorted(generated_files))
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_blocks_fallback_when_latest_pointer_is_missing(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").unlink()

    result = commit_latest_checkpoint(tmp_path, session_id="RGS-test", generated_files=())

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == tuple(sorted(generated_files))
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_blocks_fallback_when_latest_pointer_is_directory(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    latest = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    latest.unlink()
    latest.mkdir()

    result = commit_latest_checkpoint(tmp_path, session_id="RGS-test", generated_files=())

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == tuple(sorted(generated_files))
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_blocks_fallback_when_latest_pointer_is_symlink(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    latest = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    latest.unlink()
    latest.symlink_to("RGC-test-RGS-test")

    result = commit_latest_checkpoint(tmp_path, session_id="RGS-test", generated_files=())

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == tuple(sorted(generated_files))
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_blocks_fallback_when_latest_directory_is_symlink(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _write_checkpoint(tmp_path)
    checkpoint_dir = tmp_path / ".review-gauntlet" / "checkpoints" / "RGC-test-RGS-test"
    outside = tmp_path / ".review-gauntlet" / "outside-checkpoint"
    checkpoint_dir.rename(outside)
    checkpoint_dir.symlink_to(outside, target_is_directory=True)

    result = commit_latest_checkpoint(tmp_path, session_id="RGS-test", generated_files=())

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert checkpoint_dir.relative_to(tmp_path).as_posix() in result.blocked_paths
    assert tuple(sorted(outside.glob("*")))
    assert all(
        path.relative_to(tmp_path).as_posix() in result.blocked_paths for path in outside.glob("*")
    )
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_reports_noop_when_checkpoint_has_no_diff(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    _git(tmp_path, "add", ".review-gauntlet/checkpoints")
    _git(tmp_path, "commit", "-m", "checkpoint: existing")

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is False
    assert result.reason == "no_checkpoint_diff"
    assert result.commit is None


def test_commit_latest_checkpoint_blocks_unrelated_dirty_paths(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    (tmp_path / "src.py").write_text("print('dirty')\n", encoding="utf-8")

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == ("src.py",)
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_blocks_stale_checkpoint_artifacts_not_generated(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    stale_path = tmp_path / ".review-gauntlet" / "checkpoints" / "RGC-stale" / "status.json"
    stale_path.parent.mkdir(parents=True)
    stale_path.write_text("stale\n", encoding="utf-8")

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == (stale_path.relative_to(tmp_path).as_posix(),)
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


@pytest.mark.parametrize(
    "checkpoint_id",
    [".tmp", "checkpoint", "RGC-"],
)
def test_commit_latest_checkpoint_blocks_generated_files_with_invalid_checkpoint_id(
    tmp_path: Path, checkpoint_id: str
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    generated_file = f".review-gauntlet/checkpoints/{checkpoint_id}/status.json"
    generated_path = tmp_path / generated_file
    generated_path.parent.mkdir(parents=True)
    generated_path.write_text("generated\n", encoding="utf-8")

    result = commit_latest_checkpoint(
        tmp_path,
        session_id="RGS-test",
        generated_files=(*generated_files, generated_file),
    )

    assert result.committed is False
    assert result.reason == "blocked_by_non_checkpoint_changes"
    assert result.blocked_paths == (generated_file,)
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_commits_preexisting_staged_checkpoint_paths(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    _git(tmp_path, "add", generated_files[0])

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is True
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert generated_files[0] in committed_paths
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_commit_latest_checkpoint_blocks_dual_state_checkpoint_paths(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    staged_path = tmp_path / generated_files[0]
    _git(tmp_path, "add", generated_files[0])
    staged_path.write_text("newer unstaged checkpoint\n", encoding="utf-8")

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is False
    assert result.reason == "blocked_by_staged_and_unstaged_checkpoint_changes"
    assert result.blocked_paths == (generated_files[0],)
    assert _git(tmp_path, "diff", "--cached", "--name-only") == generated_files[0]


def test_commit_latest_checkpoint_reports_git_failure_without_staging_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)

    def fake_git(root: Path, *args: str) -> str:
        if args and args[0] == "commit":
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=["git", *args],
                stderr="commit failed",
            )
        return _git(root, *args)

    monkeypatch.setattr("review_gauntlet.checkpoint._git", fake_git)

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is False
    assert result.reason == "git_failure"
    assert result.failed_error == "commit failed"
    assert _git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_commit_latest_checkpoint_preserves_preexisting_staged_paths_on_git_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    _git(tmp_path, "add", generated_files[0])

    def fake_git(root: Path, *args: str) -> str:
        if args and args[0] == "commit":
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=["git", *args],
                stderr="commit failed",
            )
        return _git(root, *args)

    monkeypatch.setattr("review_gauntlet.checkpoint._git", fake_git)

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is False
    assert result.reason == "git_failure"
    assert _git(tmp_path, "diff", "--cached", "--name-only") == generated_files[0]
