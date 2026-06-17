import json
import sqlite3
from pathlib import Path

import pytest

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


def test_session_store_cancel_active_session_updates_ledger_before_removing_marker(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-cancel", "target_digest": "abc", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )

    session_id = store.cancel_active_session()

    assert session_id == "RGS-cancel"
    assert not store.active_path.exists()
    with sqlite3.connect(store.ledger_path) as conn:
        assert (
            conn.execute(
                "select state from sessions where session_id = ?", ("RGS-cancel",)
            ).fetchone()[0]
            == "cancelled"
        )


def test_session_store_cancel_active_session_rejects_unknown_session_marker(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path)
    store.initialize()
    store.active_path.write_text(json.dumps({"session_id": "RGS-missing"}), encoding="utf-8")

    with pytest.raises(LookupError, match="unknown session: RGS-missing"):
        store.cancel_active_session()

    assert store.active_path.exists()


def test_session_store_allows_duplicate_cell_ids_in_different_sessions(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs")

    store.create_session({"session_id": "RGS-one", "target_digest": "abc", "target": {}}, (cell,))
    store.create_session({"session_id": "RGS-two", "target_digest": "def", "target": {}}, (cell,))

    with sqlite3.connect(store.ledger_path) as conn:
        rows = conn.execute(
            "select session_id, cell_id from review_cells order by session_id"
        ).fetchall()
    assert rows == [("RGS-one", "RGC-1"), ("RGS-two", "RGC-1")]


def test_session_store_updates_cell_state_for_one_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs")
    store.create_session({"session_id": "RGS-one", "target_digest": "abc", "target": {}}, (cell,))
    store.create_session({"session_id": "RGS-two", "target_digest": "def", "target": {}}, (cell,))

    store.update_cell_state("RGS-one", "RGC-1", CellState.REVIEWED)

    assert store.list_cells("RGS-one")[0]["state"] == "reviewed"
    assert store.list_cells("RGS-two")[0]["state"] == "pending"


def test_session_store_update_cell_state_rejects_unknown_cell(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs")
    store.create_session({"session_id": "RGS-one", "target_digest": "abc", "target": {}}, (cell,))

    with pytest.raises(LookupError, match="unknown review cell"):
        store.update_cell_state("RGS-one", "RGC-missing", CellState.REVIEWED)


def test_session_store_marks_reviewed_and_refreshes_digest_for_one_session(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path)
    old_cell = ReviewCell(
        id="RGC-1",
        file_path="README.md",
        rule_id="docs",
        slice_id="docs",
        content_digest="old-digest",
    )
    refreshed_cell = old_cell.model_copy(update={"content_digest": "current-digest"})
    store.create_session(
        {"session_id": "RGS-one", "target_digest": "abc", "target": {}}, (old_cell,)
    )
    store.create_session(
        {"session_id": "RGS-two", "target_digest": "def", "target": {}}, (old_cell,)
    )

    store.mark_cell_reviewed("RGS-one", refreshed_cell)

    first = store.list_cells("RGS-one")[0]
    second = store.list_cells("RGS-two")[0]
    assert first["state"] == "reviewed"
    assert first["content_digest"] == "current-digest"
    assert second["state"] == "pending"
    assert second["content_digest"] == "old-digest"
