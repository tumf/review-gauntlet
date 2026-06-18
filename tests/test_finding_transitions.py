import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.findings import FindingState, assert_transition_allowed
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


def test_open_allows_confirmed_and_dismissed_transitions() -> None:
    assert_transition_allowed(FindingState.OPEN, FindingState.CONFIRMED)
    assert_transition_allowed(FindingState.OPEN, FindingState.DISMISSED)


@pytest.mark.parametrize("terminal_state", [FindingState.CONFIRMED, FindingState.DISMISSED])
def test_terminal_states_reject_follow_up_transitions(terminal_state: FindingState) -> None:
    with pytest.raises(ValueError, match=f"{terminal_state} -> confirmed"):
        assert_transition_allowed(terminal_state, FindingState.CONFIRMED)


def test_invalid_regression_transition_is_rejected_in_store(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )
    _insert_finding(store, "RGF-0001", FindingState.DISMISSED)

    with pytest.raises(ValueError, match="dismissed -> confirmed"):
        store.mark_finding("RGF-0001", FindingState.CONFIRMED, "changed mind", {})


def test_transition_records_dismiss_metadata(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )
    _insert_finding(store, "RGF-0001", FindingState.OPEN)

    store.mark_finding(
        "RGF-0001",
        FindingState.DISMISSED,
        "not applicable to generated docs",
        {"dismiss_reason": "not applicable to generated docs"},
    )

    with sqlite3.connect(store.ledger_path) as conn:
        row = conn.execute(
            """
            select from_state, to_state, reason, metadata
            from finding_events
            where finding_id = ?
            """,
            ("RGF-0001",),
        ).fetchone()
        state = conn.execute(
            "select state from findings where finding_id = ?", ("RGF-0001",)
        ).fetchone()[0]
    assert state == FindingState.DISMISSED
    assert row[:3] == (FindingState.OPEN, FindingState.DISMISSED, "not applicable to generated docs")
    assert json.loads(row[3]) == {"dismiss_reason": "not applicable to generated docs"}


def _insert_finding(store: SessionStore, finding_id: str, state: FindingState) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(
                session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            )
            values ('RGS-test', ?, ?, ?, 'README.md', 'docs', 'content', '{}')
            """,
            (finding_id, f"fingerprint-{finding_id}", state),
        )
