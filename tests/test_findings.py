import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.findings import (
    ALLOWED_TRANSITIONS,
    TERMINAL_FINDING_STATES,
    FindingResolution,
    FindingState,
    NormalizedFinding,
    normalize_ocr_comment,
)
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


@pytest.mark.parametrize("path", ["/tmp/escape.py", "../escape.py"])
def test_normalize_ocr_comment_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match="repository path"):
        normalize_ocr_comment(
            OCRComment(path=path, content="Issue"),
            repository_id="repo",
            base_target="target",
            rule_id="security",
            ruleset_digest="rules",
        )


def test_finding_state_model_matches_checkpoint_states() -> None:
    assert tuple(FindingState) == (
        FindingState.UNTRIAGED,
        FindingState.OPEN,
        FindingState.CONFIRMED,
        FindingState.FIXED_PENDING_VERIFICATION,
        FindingState.FIXED_VERIFIED,
        FindingState.FALSE_POSITIVE,
        FindingState.ACCEPTED_RISK,
        FindingState.WAIVED,
        FindingState.DISMISSED,
    )
    assert {
        FindingState.CONFIRMED,
        FindingState.FIXED_VERIFIED,
        FindingState.FALSE_POSITIVE,
        FindingState.ACCEPTED_RISK,
        FindingState.WAIVED,
        FindingState.DISMISSED,
    } == TERMINAL_FINDING_STATES
    assert ALLOWED_TRANSITIONS[FindingState.OPEN] == {
        FindingState.CONFIRMED,
        FindingState.DISMISSED,
    }
    assert ALLOWED_TRANSITIONS[FindingState.CONFIRMED] == set()
    assert ALLOWED_TRANSITIONS[FindingState.FIXED_PENDING_VERIFICATION] == {
        FindingState.FIXED_VERIFIED,
        FindingState.DISMISSED,
    }
    for state in TERMINAL_FINDING_STATES:
        assert ALLOWED_TRANSITIONS[state] == set()


def test_normalized_finding_accepts_dismiss_reason() -> None:
    finding = NormalizedFinding.model_validate(
        {
            "fingerprint": "fp",
            "path": "app.py",
            "rule_id": "security",
            "content": "false alarm",
            "dismiss_reason": "generated code",
        }
    )

    assert finding.dismiss_reason == "generated code"


def test_finding_resolution_validates_resolution() -> None:
    resolution = FindingResolution.model_validate(
        {"finding_id": " RGF-0001 ", "state": "dismissed", "dismiss_reason": "not applicable"}
    )

    assert resolution.finding_id == "RGF-0001"
    assert resolution.state == "dismissed"
    assert resolution.dismiss_reason == "not applicable"


def test_normalize_ocr_comment_normalizes_safe_paths() -> None:
    finding = normalize_ocr_comment(
        OCRComment(path="./src/app.py", content="Issue"),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )

    assert finding.path == "src/app.py"


def test_repeated_findings_reuse_session_id_and_add_occurrences(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="app.py", rule_id="security", slice_id="src")
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (cell,),
    )
    first_run = store.create_run("RGS-test", "digest-1")
    second_run = store.create_run("RGS-test", "digest-2")
    first = normalize_ocr_comment(
        OCRComment(
            path="app.py",
            content="Missing authorization guard",
            existing_code="return secret",
            start_line=3,
            end_line=3,
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )
    shifted = normalize_ocr_comment(
        OCRComment(
            path="app.py",
            content="Missing authorization guard",
            existing_code="return secret",
            start_line=42,
            end_line=42,
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )

    first_id = store.upsert_finding("RGS-test", first_run, cell.id, first)
    second_id = store.upsert_finding("RGS-test", second_run, cell.id, shifted)

    assert first_id == "RGF-0001"
    assert second_id == first_id
    with sqlite3.connect(store.ledger_path) as conn:
        assert conn.execute("select count(*) from findings").fetchone()[0] == 1
        assert conn.execute("select count(*) from finding_occurrences").fetchone()[0] == 2
        occurrence_rows = conn.execute(
            "select finding_id, start_line from finding_occurrences order by occurrence_id"
        ).fetchall()
    assert occurrence_rows == [("RGF-0001", 3), ("RGF-0001", 42)]


def test_new_finding_id_uses_max_existing_numeric_id_not_row_count(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="app.py", rule_id="security", slice_id="src")
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (cell,),
    )
    with sqlite3.connect(store.ledger_path) as conn:
        conn.execute(
            """
            insert into findings(
              session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RGS-test",
                "RGF-0042",
                "migrated-fingerprint",
                FindingState.OPEN,
                "legacy.py",
                "security",
                "Migrated issue",
                "{}",
            ),
        )
    finding = normalize_ocr_comment(
        OCRComment(path="app.py", content="New auth issue", existing_code="guard()"),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )

    finding_id = store.upsert_finding(
        "RGS-test", store.create_run("RGS-test", "d1"), cell.id, finding
    )

    assert finding_id == "RGF-0043"


def test_finding_occurrence_preserves_imprecise_zero_line_comments(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="app.py", rule_id="security", slice_id="src")
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (cell,),
    )
    run_id = store.create_run("RGS-test", "digest")
    finding = normalize_ocr_comment(
        OCRComment(
            path="app.py",
            content="File-level security issue",
            existing_code="",
            suggestion_code="add validation",
            start_line=0,
            end_line=0,
            thinking="No exact line applies",
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )

    finding_id = store.upsert_finding("RGS-test", run_id, cell.id, finding)

    with sqlite3.connect(store.ledger_path) as conn:
        row = conn.execute(
            "select start_line, end_line, imprecise from finding_occurrences where finding_id = ?",
            (finding_id,),
        ).fetchone()
        metadata = conn.execute(
            "select metadata from findings where finding_id = ?", (finding_id,)
        ).fetchone()[0]
    assert row == (0, 0, 1)
    assert json.loads(metadata)["imprecise"] is True
    assert json.loads(metadata)["thinking"] == "No exact line applies"


def test_terminal_finding_keeps_stable_id_when_detected_again(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="app.py", rule_id="security", slice_id="src")
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}},
        (cell,),
    )
    finding = normalize_ocr_comment(
        OCRComment(path="app.py", content="Missing auth", existing_code="guard()"),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )
    first_id = store.upsert_finding(
        "RGS-test", store.create_run("RGS-test", "d1"), cell.id, finding
    )
    store.mark_finding(first_id, FindingState.CONFIRMED, "fixed", {})

    second_id = store.upsert_finding(
        "RGS-test", store.create_run("RGS-test", "d2"), cell.id, finding
    )

    assert second_id == first_id
    with sqlite3.connect(store.ledger_path) as conn:
        state = conn.execute(
            "select state from findings where finding_id = ?", (first_id,)
        ).fetchone()[0]
    assert state == FindingState.CONFIRMED
