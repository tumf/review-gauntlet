import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from review_gauntlet.cli import main
from review_gauntlet.git_worktree import (
    _base_dirty_paths,  # pyright: ignore[reportPrivateUsage]
    _unique_session_branch,  # pyright: ignore[reportPrivateUsage]
    _validate_session_id,  # pyright: ignore[reportPrivateUsage]
    merge_preflight_blockers,
    run_worktree_setup,
)
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


def _write_setup_script(worktree_root: Path, contents: str) -> Path:
    setup = worktree_root / ".wt" / "setup"
    setup.parent.mkdir(parents=True, exist_ok=True)
    setup.write_text(contents, encoding="utf-8")
    setup.chmod(0o755)
    return setup


def test_run_worktree_setup_reports_missing_script(tmp_path: Path) -> None:
    result = run_worktree_setup(tmp_path, enabled=True, timeout_seconds=5)

    assert result.as_dict() == {
        "ran": False,
        "script_path": (tmp_path / ".wt" / "setup").as_posix(),
        "skipped_reason": "missing",
        "returncode": None,
        "warning": None,
    }


def test_run_worktree_setup_reports_disabled_script(tmp_path: Path) -> None:
    _write_setup_script(tmp_path, "#!/bin/sh\ntouch should-not-exist\n")

    result = run_worktree_setup(tmp_path, enabled=False, timeout_seconds=5)

    assert result.ran is False
    assert result.skipped_reason == "disabled"
    assert result.returncode is None
    assert result.warning is None
    assert not (tmp_path / "should-not-exist").exists()


def test_run_worktree_setup_runs_script_with_worktree_cwd(tmp_path: Path) -> None:
    _write_setup_script(tmp_path, "#!/bin/sh\npwd > setup-cwd.txt\n")

    result = run_worktree_setup(tmp_path, enabled=True, timeout_seconds=5)

    assert result.ran is True
    assert result.skipped_reason is None
    assert result.returncode == 0
    assert result.warning is None
    assert (tmp_path / "setup-cwd.txt").read_text(encoding="utf-8").strip() == str(tmp_path)


def test_run_worktree_setup_warns_on_nonzero_exit(tmp_path: Path) -> None:
    _write_setup_script(tmp_path, "#!/bin/sh\necho setup failed >&2\nexit 7\n")

    result = run_worktree_setup(tmp_path, enabled=True, timeout_seconds=5)

    assert result.ran is True
    assert result.returncode == 7
    assert result.skipped_reason is None
    assert result.warning is not None
    assert "status 7" in result.warning
    assert "setup failed" in result.warning


def test_run_worktree_setup_returns_warning_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_setup_script(tmp_path, "#!/bin/sh\nsleep 999\n")
    timeout_seconds = 3.0

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=timeout_seconds)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_worktree_setup(tmp_path, enabled=True, timeout_seconds=timeout_seconds)

    assert result.ran is True
    assert result.returncode == -1
    assert result.skipped_reason is None
    assert result.warning is not None
    assert "timed out" in result.warning
    assert "3 seconds" in result.warning


def test_run_worktree_setup_returns_warning_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_setup_script(tmp_path, "#!/bin/sh\necho ok\n")

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise OSError("Permission denied")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_worktree_setup(tmp_path, enabled=True, timeout_seconds=5)

    assert result.ran is True
    assert result.returncode is None
    assert result.skipped_reason is None
    assert result.warning is not None
    assert "could not be executed" in result.warning
    assert "Permission denied" in result.warning


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
    git_metadata: dict[str, object] = init_data["git_worktree"]
    (tmp_path / "app.py").write_text("print('base')\n", encoding="utf-8")
    _git(tmp_path, "add", "app.py")
    _git(tmp_path, "commit", "-m", "base change")
    git_metadata = {**git_metadata, "base_commit": _git(tmp_path, "rev-parse", "HEAD")}
    session_worktree = tmp_path / str(git_metadata["worktree_path"])
    (session_worktree / "app.py").write_text("print('session')\n", encoding="utf-8")
    _git(session_worktree, "add", "app.py")
    _git(session_worktree, "commit", "-m", "session change")

    blockers = merge_preflight_blockers(tmp_path, git_metadata)

    worktree_path = str(git_metadata["worktree_path"])
    session_branch = str(git_metadata["session_branch"])
    assert "session branch would conflict with base branch" in blockers
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    assert (tmp_path / worktree_path).is_dir()
    assert _git(tmp_path, "branch", "--list", session_branch)


def test_run_git_worktree_session_executes_agent_in_session_worktree_and_keeps_state_in_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    main(["init", str(tmp_path), "--all", "--git-worktree", "--format", "json"])
    init_data = json.loads(capsys.readouterr().out)
    git_metadata = init_data["git_worktree"]
    session_worktree = tmp_path / git_metadata["worktree_path"]
    observed = tmp_path / ".review-gauntlet" / "observed.json"
    script = tmp_path / ".review-gauntlet" / "agent.py"
    script.write_text(
        """
import json
import os
from pathlib import Path

repo_root = Path(os.environ['RG_REPO_ROOT'])
state_dir = Path(os.environ['RG_STATE_DIR'])
observed = Path(os.environ['RG_OBSERVED'])
(repo_root / 'agent-marker.txt').write_text('session worktree\\n', encoding='utf-8')
observed.write_text(json.dumps({
    'cwd': os.getcwd(),
    'repo_root': str(repo_root),
    'state_dir': str(state_dir),
}), encoding='utf-8')
(state_dir / 'active-session.json').unlink()
print('done')
""".strip(),
        encoding="utf-8",
    )
    config = tmp_path / ".review-gauntlet" / "config.json"
    config.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": "python",
                    "args": [str(script)],
                    "env": {
                        "RG_REPO_ROOT": "{repo_root}",
                        "RG_STATE_DIR": "{state_dir}",
                        "RG_OBSERVED": str(observed),
                    },
                    "timeout_seconds": 5,
                }
            }
        ),
        encoding="utf-8",
    )

    main(["run", str(tmp_path), "--config", str(config), "--format", "json"])

    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is True
    step = result["steps"][0]
    assert step["cwd"] == str(session_worktree.resolve())
    assert (session_worktree / "agent-marker.txt").read_text(
        encoding="utf-8"
    ) == "session worktree\n"
    assert not (tmp_path / "agent-marker.txt").exists()
    observation = json.loads(observed.read_text(encoding="utf-8"))
    assert observation == {
        "cwd": str(session_worktree.resolve()),
        "repo_root": str(session_worktree.resolve()),
        "state_dir": str(tmp_path / ".review-gauntlet"),
    }
    assert Path(step["stdout_artifact"]).is_relative_to(tmp_path / ".review-gauntlet")
    assert not Path(step["stdout_artifact"]).is_relative_to(session_worktree)


def test_run_git_worktree_session_changes_can_finalize_merge(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    main(["init", str(tmp_path), "--all", "--git-worktree", "--format", "json"])
    init_data = json.loads(capsys.readouterr().out)
    git_metadata = init_data["git_worktree"]
    session_worktree = tmp_path / git_metadata["worktree_path"]
    script = tmp_path / ".review-gauntlet" / "agent.py"
    script.write_text(
        """
from pathlib import Path
import os
Path('agent-merge-marker.txt').write_text('merge me\\n', encoding='utf-8')
print('marker written')
""".strip(),
        encoding="utf-8",
    )
    config = tmp_path / ".review-gauntlet" / "config.json"
    config.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": "python",
                    "args": [str(script)],
                    "env": {"RG_STATE_DIR": "{state_dir}"},
                    "timeout_seconds": 5,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as run_exit:
        main(
            ["run", str(tmp_path), "--config", str(config), "--max-steps", "1", "--format", "json"]
        )
    run_data = json.loads(capsys.readouterr().out)
    assert run_exit.value.code == 1
    assert run_data["reason"] == "max_steps_exhausted"
    assert (session_worktree / "agent-merge-marker.txt").exists()

    fixture = tmp_path / ".review-gauntlet" / "fixtures" / "fixture.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("{}", encoding="utf-8")
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "50", "--format", "json"])
    review_data = json.loads(capsys.readouterr().out)
    assert review_data["coverage"].get("pending", 0) == 0

    main(["finalize", str(tmp_path), "--merge", "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["merged"] is True
    assert (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").is_file()


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


# --- RGF-0407: _validate_session_id rejection ---


class TestValidateSessionId:
    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValueError):
            _validate_session_id("../../etc")

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError):
            _validate_session_id("a b")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError):
            _validate_session_id("")

    def test_accepts_valid_id(self) -> None:
        _validate_session_id("valid-id_123")


# --- RGF-0408: _unique_session_branch collision dedup ---


class TestUniqueSessionBranch:
    def test_appends_suffix_on_collision(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _git(tmp_path, "branch", "review-gauntlet/test-session")

        result = _unique_session_branch(tmp_path, "test-session")

        assert result == "review-gauntlet/test-session-2"

    def test_increments_suffix_on_repeated_collision(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _git(tmp_path, "branch", "review-gauntlet/test-session")
        _git(tmp_path, "branch", "review-gauntlet/test-session-2")

        result = _unique_session_branch(tmp_path, "test-session")

        assert result == "review-gauntlet/test-session-3"


# --- RGF-0409: rename handling in _base_dirty_paths ---


class TestBaseDirtyPathsRename:
    def test_includes_renamed_file(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "old_name.py").write_text("content\n", encoding="utf-8")
        _git(tmp_path, "add", "old_name.py")
        _git(tmp_path, "commit", "-m", "add old_name")
        _git(tmp_path, "mv", "old_name.py", "new_name.py")

        dirty = _base_dirty_paths(tmp_path)

        assert "new_name.py" in dirty
