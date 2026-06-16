import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from review_gauntlet.cli import main, run_session_command_step_for_testing
from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.review_cells import CellState
from review_gauntlet.run_controller import AgentOutputProgress, SessionCommandResult
from review_gauntlet.session_store import SessionStore


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_git_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")


def _write_config(
    root: Path, command: str, args: list[str], *, timeout: float = 5.0, cwd: str | None = None
) -> Path:
    config = root / "review-gauntlet.json"
    adapter: dict[str, object] = {
        "type": "command",
        "command": command,
        "args": args,
        "timeout_seconds": timeout,
    }
    if cwd is not None:
        adapter["cwd"] = cwd
    config.write_text(json.dumps({"adapter": adapter}), encoding="utf-8")
    return config


def _init_session(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(root), "--worktree", "--format", "json"])
    capsys.readouterr()


def _ready_prompt(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    main(["ready", str(root), "--format", "json"])
    prompt = json.loads(capsys.readouterr().out)["prompt"]
    assert isinstance(prompt, str)
    return prompt


def _mark_cells_reviewed(root: Path) -> None:
    store = SessionStore(root)
    session_id = store.active_session_id()
    with store.connect() as conn:
        conn.execute(
            """
            update review_cells
            set state = ?, content_digest = content_digest
            where session_id = ?
            """,
            (CellState.REVIEWED.value, session_id),
        )


def test_run_help_and_completion_expose_command_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--help"])
    assert exc_info.value.code == 0
    help_output = capsys.readouterr().out
    assert "--max-steps" in help_output
    assert "--config" in help_output
    assert "--format {text,json}" in help_output
    assert "Repository root (default: .)" in help_output

    main(["completion", "bash"])
    completion = capsys.readouterr().out
    assert "run" in completion
    assert "--max-steps" in completion
    assert "--config" in completion


def test_run_passes_same_prompt_as_ready_and_completes_when_active_session_removed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    expected_prompt = _ready_prompt(tmp_path, capsys)
    observed = tmp_path / "observed.json"
    script = tmp_path / "agent.py"
    script.write_text(
        """
import json
import os
import sys
from pathlib import Path

prompt = sys.argv[1]
root = Path(os.environ['RG_ROOT'])
state_dir = Path(os.environ['RG_STATE'])
observed = Path(os.environ['RG_OBSERVED'])
observed.write_text(json.dumps({
    'prompt': prompt,
    'cwd': os.getcwd(),
    'state_dir': str(state_dir),
}), encoding='utf-8')
(state_dir / 'active-session.json').unlink()
print('agent finished')
""".strip(),
        encoding="utf-8",
    )
    config = tmp_path / "review-gauntlet.json"
    config.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": sys.executable,
                    "args": [str(script), "{prompt}"],
                    "cwd": "{repo_root}",
                    "env": {
                        "RG_ROOT": "{repo_root}",
                        "RG_STATE": "{state_dir}",
                        "RG_OBSERVED": str(observed),
                    },
                    "timeout_seconds": 5,
                    "output": {"mode": "file-json", "path": "{output_file}"},
                }
            }
        ),
        encoding="utf-8",
    )

    main(["run", str(tmp_path), "--config", str(config), "--format", "json"])

    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is True
    assert result["reason"] == "completed"
    assert result["step_count"] == 1
    assert result["steps"][0]["prompt"] == expected_prompt
    assert result["steps"][0]["stdout"] == "agent finished\n"
    observation = json.loads(observed.read_text(encoding="utf-8"))
    assert observation["prompt"] == expected_prompt
    assert observation["cwd"] == str(tmp_path)
    assert observation["state_dir"] == str(tmp_path / ".review-gauntlet")
    assert not (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_run_does_not_mask_primary_exception_with_none_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_cmd_run(_args: object, _root: Path, _store: object) -> None:
        return None

    monkeypatch.setattr("review_gauntlet.cli._cmd_run", fake_cmd_run)

    with pytest.raises(RuntimeError) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    assert "run command did not return a result dictionary" in str(exc_info.value)
    assert "not subscriptable" not in str(exc_info.value)


def test_run_json_emits_checkpoint_commit_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(tmp_path, "fake-agent", [])

    def fake_run(_self: object) -> dict[str, object]:
        return {
            "completed": True,
            "reason": "completed",
            "steps": [],
            "step_count": 0,
            "session_id": "RGS-test",
            "checkpoint_commit_attempted": True,
            "checkpoint_committed": False,
            "checkpoint_commit": None,
            "checkpoint_commit_reason": "no_checkpoint_diff",
        }

    monkeypatch.setattr("review_gauntlet.cli.RunController.run", fake_run)

    main(["run", str(tmp_path), "--format", "json"])

    result = json.loads(capsys.readouterr().out)
    assert result["checkpoint_commit_attempted"] is True
    assert result["checkpoint_committed"] is False
    assert result["checkpoint_commit"] is None
    assert result["checkpoint_commit_reason"] == "no_checkpoint_diff"


def test_run_reports_no_ready_task_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_git_repo(tmp_path)
    _init_session(tmp_path, capsys)
    _write_config(tmp_path, sys.executable, ["-c", "print('should not run')"])
    _git(tmp_path, "add", "README.md", "review-gauntlet.json")
    _git(tmp_path, "commit", "-m", "initial")
    _mark_cells_reviewed(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is False
    assert result["reason"] == "no_ready_task"
    assert result["steps"] == []


def test_run_reports_command_failure_and_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _write_config(
        tmp_path,
        sys.executable,
        ["-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)", "{prompt}"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is False
    assert result["reason"] == "command_failed"
    step = result["steps"][0]
    assert step["returncode"] == 7
    assert step["stdout"] == "out\n"
    assert step["stderr"] == "err\n"
    assert step["failure"]["returncode"] == 7


def test_run_reports_startup_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _init_session(tmp_path, capsys)
    _write_config(tmp_path, "review-gauntlet-command-that-does-not-exist", ["{prompt}"])

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is False
    assert result["reason"] == "startup_error"
    assert "command not found" in result["error"]


def test_run_reports_timeout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _init_session(tmp_path, capsys)
    _write_config(tmp_path, sys.executable, ["-c", "import time; time.sleep(2)"], timeout=0.1)

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is False
    assert result["reason"] == "timeout"
    assert result["steps"][0]["failure"]["timeout_seconds"] == 0.1


def test_run_reports_max_steps_exhaustion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _write_config(tmp_path, sys.executable, ["-c", "print('still active')", "{prompt}"])

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--max-steps", "1", "--format", "json"])

    assert exc_info.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is False
    assert result["reason"] == "max_steps_exhausted"
    assert result["step_count"] == 1
    assert result["max_steps"] == 1


def test_run_session_command_expands_repo_root_state_dir_and_defaults_cwd(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    state_dir.mkdir()
    config = CommandAdapterConfig(
        type="command",
        command=sys.executable,
        args=(
            "-c",
            "import json, os, sys; "
            "print(json.dumps({'cwd': os.getcwd(), 'repo': sys.argv[1], "
            "'state': sys.argv[2]}))",
            "{repo_root}",
            "{state_dir}",
        ),
        timeout_seconds=5,
    )

    result = run_session_command_step_for_testing(
        config=config,
        root=tmp_path,
        state_dir=state_dir,
        prompt="prompt",
    )

    assert result.failure is None
    payload = json.loads(result.stdout)
    assert payload == {
        "cwd": str(tmp_path),
        "repo": str(tmp_path),
        "state": str(state_dir),
    }
    assert result.cwd == str(tmp_path)
    assert result.stdout_artifact is not None
    assert Path(result.stdout_artifact).is_relative_to(state_dir)


def test_run_session_command_streams_output_progress_before_process_exit(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    state_dir.mkdir()
    script = tmp_path / "slow_agent.py"
    script.write_text(
        """
import sys
import time

print('first line', flush=True)
time.sleep(0.3)
print('second line', flush=True)
print('error line', file=sys.stderr, flush=True)
""".strip(),
        encoding="utf-8",
    )
    config = CommandAdapterConfig(
        type="command",
        command=sys.executable,
        args=(str(script),),
        timeout_seconds=5,
    )
    progress = AgentOutputProgress()
    result_holder: list[SessionCommandResult] = []

    def run_command() -> None:
        result_holder.append(
            run_session_command_step_for_testing(
                config=config,
                root=tmp_path,
                state_dir=state_dir,
                prompt="prompt",
                output_progress=progress,
            )
        )

    thread = threading.Thread(target=run_command)
    thread.start()
    deadline = time.monotonic() + 1.0
    live_tail: tuple[str, ...] = ()
    while time.monotonic() < deadline:
        _age, tail = progress.snapshot()
        live_tail = tuple(entry.text for entry in tail)
        if "first line" in live_tail:
            break
        time.sleep(0.01)

    assert "first line" in live_tail
    assert thread.is_alive()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert len(result_holder) == 1
    result = result_holder[0]
    assert result.failure is None
    assert result.stdout == "first line\nsecond line\n"
    assert result.stderr == "error line\n"
    assert tuple(entry.text for entry in result.output_tail) == (
        "first line",
        "error line",
        "second line",
    )


def test_run_session_command_resolves_nested_cwd_and_rejects_escape(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    state_dir.mkdir()
    nested = tmp_path / "nested"
    nested.mkdir()
    valid = CommandAdapterConfig(
        type="command",
        command=sys.executable,
        args=("-c", "import os; print(os.getcwd())"),
        cwd="nested",
        timeout_seconds=5,
    )

    valid_result = run_session_command_step_for_testing(
        config=valid,
        root=tmp_path,
        state_dir=state_dir,
        prompt="prompt",
    )

    assert valid_result.failure is None
    assert valid_result.cwd == str(nested.resolve())
    assert valid_result.stdout == f"{nested.resolve()}\n"

    escaping = CommandAdapterConfig(
        type="command",
        command=sys.executable,
        args=("-c", "print('bad')"),
        cwd="..",
        timeout_seconds=5,
    )

    escaped_result = run_session_command_step_for_testing(
        config=escaping,
        root=tmp_path,
        state_dir=state_dir,
        prompt="prompt",
    )

    assert escaped_result.failure is not None
    assert escaped_result.failure["reason"] == "template_error"
    assert "adapter.cwd must stay inside repository root" in str(escaped_result.failure["error"])


def test_run_rejects_cell_level_template_variables_for_session_runner(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _write_config(tmp_path, sys.executable, ["-c", "print('bad')", "{cell_id}"])

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["completed"] is False
    assert result["reason"] == "template_error"
    assert "not available for run" in result["error"]
