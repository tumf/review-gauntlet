import sqlite3
from pathlib import Path

from review_gauntlet.review_cells import CellState, ReviewCell
from review_gauntlet.session_store import SessionStore


def test_session_store_creates_ledger_inside_tmp_path(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    session_id = store.create_session(
        {"session_id": "RGS-test", "target_digest": "abc", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )

    assert session_id == "RGS-test"
    assert store.ledger_path == tmp_path / ".review-gauntlet" / "ledger.sqlite"
    assert store.active_session_id() == "RGS-test"
    with sqlite3.connect(store.ledger_path) as conn:
        assert conn.execute("select count(*) from sessions").fetchone()[0] == 1
        assert conn.execute("select count(*) from review_cells").fetchone()[0] == 1


def test_session_store_updates_cell_state(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "abc", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )

    store.update_cell_state("RGC-1", CellState.REVIEWED)

    assert store.list_cells()[0]["state"] == "reviewed"
