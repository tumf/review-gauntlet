import json
import sqlite3
from pathlib import Path

from review_gauntlet.findings import FindingState, normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


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


def test_reopened_finding_keeps_stable_id_when_detected_again(tmp_path: Path) -> None:
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
    store.mark_finding(first_id, FindingState.FIXED_PENDING_VERIFICATION, "fixed", {})

    second_id = store.upsert_finding(
        "RGS-test", store.create_run("RGS-test", "d2"), cell.id, finding
    )

    assert second_id == first_id
    with sqlite3.connect(store.ledger_path) as conn:
        state = conn.execute(
            "select state from findings where finding_id = ?", (first_id,)
        ).fetchone()[0]
        event = conn.execute(
            "select from_state, to_state, reason from finding_events order by event_id desc limit 1"
        ).fetchone()
    assert state == FindingState.REOPENED
    assert event == (
        FindingState.FIXED_PENDING_VERIFICATION,
        FindingState.REOPENED,
        "review_detected_again",
    )
