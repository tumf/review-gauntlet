from __future__ import annotations

from pathlib import Path

import pytest

from review_gauntlet.run_controller import RunController, SessionCommandResult
from review_gauntlet.run_tui import create_run_app, should_use_tui, textual_available
from review_gauntlet.session_store import SessionStore


def test_should_use_tui_selection_rules() -> None:
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=True) is True
    assert should_use_tui(output_format="json", no_tui=False, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=True, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=False) is False


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
