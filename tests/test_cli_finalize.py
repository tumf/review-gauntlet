import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.review_cells import CellState
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import target_digest


def _init_reviewed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> SessionStore:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    store = SessionStore(tmp_path)
    session_id = store.active_session_id()
    for row in store.list_cells(session_id):
        store.update_cell_state(session_id, str(row["cell_id"]), CellState.REVIEWED)
    store.create_run(session_id, target_digest(tmp_path))
    return store


def test_finalize_blocks_on_open_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _init_reviewed(tmp_path, capsys)
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(
                session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            )
            values (?, 'RGF-0001', 'fp', 'open', 'README.md', 'docs', 'issue', '{}')
            """,
            (store.active_session_id(),),
        )

    with pytest.raises(SystemExit):
        main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is False
    assert "findings remain open" in data["finalize_blockers"]


def test_finalize_succeeds_when_reviewed_and_findings_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_reviewed(tmp_path, capsys)

    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["session_state"] == "finalized"
    assert data["can_finalize"] is True


def test_finalize_includes_terminal_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _init_reviewed(tmp_path, capsys)
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(
                session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            )
            values (?, 'RGF-0001', 'fp', 'dismissed', 'README.md', 'docs', 'issue', '{}')
            """,
            (store.active_session_id(),),
        )

    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        assert conn.execute("select state from sessions").fetchone()[0] == "finalized"
