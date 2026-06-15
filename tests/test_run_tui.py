from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from review_gauntlet import run_tui
from review_gauntlet.run_controller import RunController, RunSnapshot, SessionCommandResult
from review_gauntlet.run_tui import create_run_app, should_use_tui, textual_available
from review_gauntlet.session_store import SessionStore


def test_should_use_tui_selection_rules() -> None:
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=True) is True
    assert should_use_tui(output_format="json", no_tui=False, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=True, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=False) is False


def test_task_text_renders_prompt_as_plain_text() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-tui",
        coverage={},
        findings={},
        next_ready_prompt="[bold]task[/bold]\x1b[31m",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )

    task_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_task_text"])

    assert task_text(snapshot) == "Current task\n\\[bold]task\\[/bold]�\\[31m"


def test_agent_text_renders_status_and_argv_as_plain_text() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-tui",
        coverage={},
        findings={},
        next_ready_prompt=None,
        step=2,
        agent_status="[red]running[/red]\x1b[31m",
        command_argv=("agent", "[bold]arg[/bold]\x1b[32m"),
        elapsed_seconds=1.25,
    )

    agent_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_agent_text"])

    assert agent_text(snapshot) == (
        "Agent\n"
        "status=\\[red]running\\[/red]�\\[31m step=2 elapsed=1.2s\n"
        "argv=agent \\[bold]arg\\[/bold]�\\[32m"
    )


def test_create_run_app_constructs_when_textual_available(tmp_path: Path) -> None:
    if not textual_available():
        pytest.skip("Textual optional dependency is not installed")
    store = SessionStore(tmp_path)
    store.create_session(
        {
            "session_id": "RGS-tui",
            "root": str(tmp_path),
            "target": {
                "base_ref": None,
                "head_ref": None,
                "worktree": True,
                "commit": None,
                "all_files": False,
            },
        },
        (),
    )
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {"coverage": {}, "findings": {}},
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=[], cwd=None, returncode=0, stdout="", stderr=""
        ),
    )

    app = create_run_app(controller)

    assert app is not None


def test_run_app_executes_controller_in_headless_mode(tmp_path: Path) -> None:
    if not textual_available():
        pytest.skip("Textual optional dependency is not installed")
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "agent"}}), encoding="utf-8"
    )
    store = SessionStore(tmp_path)
    store.create_session(
        {
            "session_id": "RGS-tui-run",
            "root": str(tmp_path),
            "target": {
                "base_ref": None,
                "head_ref": None,
                "worktree": True,
                "commit": None,
                "all_files": False,
            },
        },
        (),
    )

    def command_runner(*_args: object) -> SessionCommandResult:
        (tmp_path / ".review-gauntlet" / "active-session.json").unlink()
        return SessionCommandResult(argv=["agent"], cwd=None, returncode=0, stdout="", stderr="")

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {"coverage": {}, "findings": {}},
        command_runner=command_runner,
    )

    result = cast(Any, create_run_app(controller)).run(headless=True)

    assert isinstance(result, dict)
    assert result["completed"] is True
