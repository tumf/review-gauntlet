import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.cli import main


def _create_session_with_findings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    session_id = json.loads((tmp_path / ".review-gauntlet" / "active-session.json").read_text())[
        "session_id"
    ]
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        for finding_id, state, path in (
            ("RGF-open", "open", "README.md"),
            ("RGF-confirmed", "confirmed", "README.md"),
            ("RGF-dismissed", "dismissed", "src/app.py"),
        ):
            conn.execute(
                """
                insert into findings(
                    session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
                )
                values (?, ?, ?, ?, ?, 'docs-accuracy', ?, '{}')
                """,
                (session_id, finding_id, f"fp-{finding_id}", state, path, f"{state} finding"),
            )


def test_findings_suppresses_terminal_findings_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert [finding["finding_id"] for finding in data["findings"]] == ["RGF-open"]


def test_findings_all_includes_terminal_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--all", "--all-findings", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert {finding["state"] for finding in data["findings"]} == {
        "open",
        "confirmed",
        "dismissed",
    }


def test_findings_filters_by_mark_and_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(
        [
            "findings",
            str(tmp_path),
            "--all",
            "--mark",
            "dismissed",
            "--path",
            "src/",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert [finding["finding_id"] for finding in data["findings"]] == ["RGF-dismissed"]


def test_findings_rejects_limit_with_all_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    with pytest.raises(SystemExit) as exc_info:
        main(["findings", str(tmp_path), "--all-findings", "--limit", "1"])

    assert exc_info.value.code == 64
