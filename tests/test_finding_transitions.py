import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from review_gauntlet.findings import FindingState, assert_transition_allowed
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


def test_allowed_human_triage_transitions_from_untriaged() -> None:
    for desired in (
        FindingState.CONFIRMED,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
        FindingState.FIXED_PENDING_VERIFICATION,
    ):
        assert_transition_allowed(FindingState.UNTRIAGED, desired)


def test_allowed_reopened_triage_transitions() -> None:
    for desired in (
        FindingState.CONFIRMED,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
        FindingState.FIXED_PENDING_VERIFICATION,
    ):
        assert_transition_allowed(FindingState.REOPENED, desired)


def test_fixed_pending_verification_allows_only_review_verdicts() -> None:
    assert_transition_allowed(FindingState.FIXED_PENDING_VERIFICATION, FindingState.FIXED_VERIFIED)
    assert_transition_allowed(FindingState.FIXED_PENDING_VERIFICATION, FindingState.REOPENED)
    with pytest.raises(ValueError, match="fixed_pending_verification -> confirmed"):
        assert_transition_allowed(FindingState.FIXED_PENDING_VERIFICATION, FindingState.CONFIRMED)


@pytest.mark.parametrize(
    "terminal_state",
    [
        FindingState.FIXED_VERIFIED,
        FindingState.FALSE_POSITIVE,
        FindingState.WAIVED,
        FindingState.ACCEPTED_RISK,
    ],
)
def test_terminal_states_reject_follow_up_transitions(terminal_state: FindingState) -> None:
    with pytest.raises(ValueError, match=f"{terminal_state} -> confirmed"):
        assert_transition_allowed(terminal_state, FindingState.CONFIRMED)


def test_invalid_regression_transition_is_rejected_in_store(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )
    _insert_finding(store, "RGF-0001", FindingState.FALSE_POSITIVE)

    with pytest.raises(ValueError, match="false_positive -> confirmed"):
        store.mark_finding("RGF-0001", FindingState.CONFIRMED, "changed mind", {})


def test_transition_records_expiry_metadata_for_waiver(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs"),),
    )
    _insert_finding(store, "RGF-0001", FindingState.UNTRIAGED)
    until = (datetime.now(UTC).date() + timedelta(days=7)).isoformat()

    store.mark_finding(
        "RGF-0001",
        FindingState.WAIVED,
        "known acceptable for MVP",
        {"owner": "security", "until": until},
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
    assert state == FindingState.WAIVED
    assert row[:3] == (FindingState.UNTRIAGED, FindingState.WAIVED, "known acceptable for MVP")
    assert json.loads(row[3]) == {"owner": "security", "until": until}


def _insert_finding(store: SessionStore, finding_id: str, state: FindingState) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(session_id, finding_id, fingerprint, state, path, rule_id, content, metadata)
            values ('RGS-test', ?, ?, ?, 'README.md', 'docs', 'content', '{}')
            """,
            (finding_id, f"fingerprint-{finding_id}", state),
        )
