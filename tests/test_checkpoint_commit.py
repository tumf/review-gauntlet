from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from review_gauntlet.checkpoint import commit_latest_checkpoint


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
    checkpoint_dir = root / ".review-gauntlet" / "checkpoints" / "latest"
    checkpoint_dir.mkdir(parents=True)
    status = checkpoint_dir / "status.json"
    status.write_text(content, encoding="utf-8")
    return (".review-gauntlet/checkpoints/latest/status.json",)


def test_commit_latest_checkpoint_commits_only_checkpoint_paths(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)

    result = commit_latest_checkpoint(
        tmp_path, session_id="RGS-test", generated_files=generated_files
    )

    assert result.committed is True
    assert result.commit == _git(tmp_path, "rev-parse", "--verify", "HEAD^{commit}")
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed_paths == [".review-gauntlet/checkpoints/latest/status.json"]
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_commit_latest_checkpoint_reports_noop_when_checkpoint_has_no_diff(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    generated_files = _write_checkpoint(tmp_path)
    _git(tmp_path, "add", ".review-gauntlet/checkpoints/latest/status.json")
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
