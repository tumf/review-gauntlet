import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.cli import main


def test_findings_suppresses_terminal_findings_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert [finding["finding_id"] for finding in data["findings"]] == ["RGF-open"]
    assert data["findings"][0]["state"] == "confirmed"


def test_findings_all_includes_terminal_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--all", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-open",
        "RGF-fixed",
        "RGF-false",
        "RGF-waived",
        "RGF-risk",
    }


def test_findings_human_output_respects_all_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path)])
    default_output = capsys.readouterr().out
    main(["findings", str(tmp_path), "--all"])
    all_output = capsys.readouterr().out

    assert "RGF-open" in default_output
    assert "RGF-fixed" not in default_output
    assert "RGF-fixed" in all_output
    assert "RGF-risk" in all_output


def _create_session_with_findings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    session_id = json.loads((tmp_path / ".review-gauntlet" / "active-session.json").read_text())[
        "session_id"
    ]
    rows = [
        ("RGF-open", "fp-open", "confirmed"),
        ("RGF-fixed", "fp-fixed", "fixed_verified"),
        ("RGF-false", "fp-false", "false_positive"),
        ("RGF-waived", "fp-waived", "waived"),
        ("RGF-risk", "fp-risk", "accepted_risk"),
    ]
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        conn.executemany(
            """
            insert into findings(session_id, finding_id, fingerprint, state, path, rule_id, content, metadata)
            values (?, ?, ?, ?, 'README.md', 'docs', 'content', '{}')
            """,
            [
                (session_id, finding_id, fingerprint, state)
                for finding_id, fingerprint, state in rows
            ],
        )
