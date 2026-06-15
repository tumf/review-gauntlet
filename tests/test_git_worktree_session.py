import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from review_gauntlet.cli import main
from review_gauntlet.git_worktree import merge_preflight_blockers
from review_gauntlet.session_store import SessionStore


def _git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True, timeout=10
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    _git(root, "add", "app.py")
    _git(root, "commit", "-m", "initial")


def _complete_session(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    main(["init", str(root), "--all", "--git-worktree", "--format", "json"])
    init_data = json.loads(capsys.readouterr().out)
    fixture = root / ".review-gauntlet" / "fixtures" / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}", encoding="utf-8")
    while True:
        main(["review", str(root), "--fixture", str(fixture), "--budget", "50", "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        if data["coverage"].get("pending", 0) == 0:
            break
    return init_data


def test_init_git_worktree_records_metadata_and_preserves_worktree_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "changed.py").write_text("print('changed')\n", encoding="utf-8")

    main(["init", str(tmp_path), "--worktree", "--git-worktree", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    metadata = SessionStore(tmp_path).session_metadata(data["session_id"])
    git_metadata = metadata["git_worktree"]
    assert metadata["target"]["kind"] == "worktree"
    assert git_metadata["enabled"] is True
    assert git_metadata["base_branch"] in {"main", "master"}
    assert _git(tmp_path, "rev-parse", "--verify", git_metadata["base_commit"])
    assert git_metadata["session_branch"].startswith("review-gauntlet/RGS-")
    assert git_metadata["worktree_path"] == f".review-gauntlet/worktrees/{data['session_id']}"
    assert (tmp_path / git_metadata["worktree_path"]).is_dir()
    assert _git(tmp_path, "branch", "--list", git_metadata["session_branch"])
    assert git_metadata == data["git_worktree"]


def test_finalize_merge_blocks_non_git_worktree_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    main(["init", str(tmp_path), "--all", "--format", "json"])
    capsys.readouterr()

    with pytest.raises(SystemExit) as excinfo:
        main(["finalize", str(tmp_path), "--merge", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert data["merged"] is False
    assert "merge finalization requires" in "\n".join(data["finalize_blockers"])
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_finalize_merge_blocks_when_base_branch_advanced_before_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    init_data = _complete_session(tmp_path, capsys)
    git_metadata = init_data["git_worktree"]
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", "package.json")
    _git(tmp_path, "commit", "-m", "advance base")

    with pytest.raises(SystemExit):
        main(["finalize", str(tmp_path), "--merge", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["merged"] is False
    assert data["can_finalize"] is False
    assert data["next_required_action"] == "resolve_finalize_blockers"
    assert "base branch has advanced" in "\n".join(data["finalize_blockers"])
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    assert (tmp_path / git_metadata["worktree_path"]).is_dir()
    assert _git(tmp_path, "branch", "--list", git_metadata["session_branch"])
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_merge_preflight_reports_missing_and_dirty_base_blockers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    init_data = _complete_session(tmp_path, capsys)
    git_metadata = init_data["git_worktree"]
    _git(tmp_path, "branch", "-m", git_metadata["base_branch"], "renamed-base")
    _git(tmp_path, "worktree", "remove", "--force", git_metadata["worktree_path"])
    _git(tmp_path, "branch", "-D", git_metadata["session_branch"])
    (tmp_path / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    blockers = merge_preflight_blockers(tmp_path, git_metadata)

    assert f"base branch is missing: {git_metadata['base_branch']}" in blockers
    assert f"session branch is missing: {git_metadata['session_branch']}" in blockers
    assert f"session worktree is missing: {git_metadata['worktree_path']}" in blockers
    assert "base branch worktree has uncommitted files" in blockers


def test_merge_preflight_reports_conflict_without_mutating_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    init_data = _complete_session(tmp_path, capsys)
    git_metadata = init_data["git_worktree"]
    (tmp_path / "app.py").write_text("print('base')\n", encoding="utf-8")
    _git(tmp_path, "add", "app.py")
    _git(tmp_path, "commit", "-m", "base change")
    git_metadata = {**git_metadata, "base_commit": _git(tmp_path, "rev-parse", "HEAD")}
    session_worktree = tmp_path / git_metadata["worktree_path"]
    (session_worktree / "app.py").write_text("print('session')\n", encoding="utf-8")
    _git(session_worktree, "add", "app.py")
    _git(session_worktree, "commit", "-m", "session change")

    blockers = merge_preflight_blockers(tmp_path, git_metadata)

    assert "session branch would conflict with base branch" in blockers
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    assert (tmp_path / git_metadata["worktree_path"]).is_dir()
    assert _git(tmp_path, "branch", "--list", git_metadata["session_branch"])


def test_finalize_merge_commits_merges_and_cleans_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    init_data = _complete_session(tmp_path, capsys)
    git_metadata = init_data["git_worktree"]

    main(["finalize", str(tmp_path), "--merge", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["merged"] is True
    assert data["cleaned_up"] is True
    assert data["base_branch"] == git_metadata["base_branch"]
    assert data["session_branch"] == git_metadata["session_branch"]
    assert _git(tmp_path, "rev-parse", git_metadata["base_branch"]) == data["merge_commit"]
    _git(
        tmp_path, "merge-base", "--is-ancestor", data["session_commit"], git_metadata["base_branch"]
    )
    assert not (tmp_path / git_metadata["worktree_path"]).exists()
    assert not _git(tmp_path, "branch", "--list", git_metadata["session_branch"])
    assert (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").is_file()
    assert not (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_finalize_merge_reports_cleanup_failure_after_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)

    def fail_cleanup(root: Path, git_meta: dict[str, object]):
        from review_gauntlet.git_worktree import GitWorktreeCleanupResult

        return GitWorktreeCleanupResult(
            cleaned_up=False,
            removed_worktree_path=None,
            deleted_branch=None,
            cleanup_blockers=("simulated cleanup failure",),
        )

    monkeypatch.setattr("review_gauntlet.git_worktree.cleanup_session_worktree", fail_cleanup)

    main(["finalize", str(tmp_path), "--merge", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["merged"] is True
    assert data["cleaned_up"] is False
    assert data["next_required_action"] == "cleanup_git_worktree"
    assert data["cleanup_blockers"] == ["simulated cleanup failure"]
    assert data["session_state"] == "finalized"
