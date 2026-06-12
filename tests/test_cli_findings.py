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
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-open",
        "RGF-config",
        "RGF-cli",
        "RGF-test",
        "RGF-pending",
    }
    assert {finding["state"] for finding in data["findings"]} == {
        "confirmed",
        "fixed_pending_verification",
        "reopened",
    }


def test_findings_all_includes_terminal_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--all", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-open",
        "RGF-config",
        "RGF-cli",
        "RGF-test",
        "RGF-fixed",
        "RGF-false",
        "RGF-waived",
        "RGF-risk",
        "RGF-pending",
    }


def test_findings_text_output_respects_all_flag(
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


@pytest.mark.parametrize("path", ["/tmp/escape.py", "../escape.py"])
def test_findings_rejects_unsafe_path_filters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], path: str
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    with pytest.raises(SystemExit) as exc_info:
        main(["findings", str(tmp_path), "--path", path])

    assert exc_info.value.code == 64


def test_findings_filters_by_single_file_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--path", "src/review_gauntlet/config.py", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert [finding["finding_id"] for finding in data["findings"]] == ["RGF-config"]
    assert set(data) == {"session_id", "findings"}


def test_findings_filters_by_directory_style_path_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--path", "src/review_gauntlet/", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-config",
        "RGF-cli",
    }


def test_findings_or_filters_repeated_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(
        [
            "findings",
            str(tmp_path),
            "--path",
            "src/review_gauntlet/config.py",
            "--path",
            "tests/",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-config",
        "RGF-test",
    }


def test_findings_filters_by_mark(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--mark", "confirmed", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-open",
        "RGF-config",
        "RGF-test",
    }
    assert {finding["state"] for finding in data["findings"]} == {"confirmed"}


def test_findings_or_filters_repeated_marks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(
        [
            "findings",
            str(tmp_path),
            "--mark",
            "confirmed",
            "--mark",
            "reopened",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-open",
        "RGF-config",
        "RGF-test",
        "RGF-cli",
    }


def test_findings_combines_path_and_mark_filters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(
        [
            "findings",
            str(tmp_path),
            "--path",
            "src/review_gauntlet/",
            "--mark",
            "confirmed",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert [finding["finding_id"] for finding in data["findings"]] == ["RGF-config"]


def test_findings_applies_terminal_suppression_before_mark_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(["findings", str(tmp_path), "--mark", "false-positive", "--format", "json"])
    default_data = json.loads(capsys.readouterr().out)
    main(
        [
            "findings",
            str(tmp_path),
            "--all",
            "--mark",
            "false-positive",
            "--format",
            "json",
        ]
    )
    all_data = json.loads(capsys.readouterr().out)

    assert default_data["findings"] == []
    assert [finding["finding_id"] for finding in all_data["findings"]] == ["RGF-false"]


def test_findings_matches_hyphenated_public_marks_to_persisted_states(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    main(
        [
            "findings",
            str(tmp_path),
            "--all",
            "--mark",
            "false-positive",
            "--mark",
            "accepted-risk",
            "--mark",
            "fixed-pending-verification",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert {finding["finding_id"] for finding in data["findings"]} == {
        "RGF-false",
        "RGF-risk",
        "RGF-pending",
    }
    assert {finding["state"] for finding in data["findings"]} == {
        "false_positive",
        "accepted_risk",
        "fixed_pending_verification",
    }


def test_findings_rejects_invalid_mark_value() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", ".", "--mark", "not-a-mark"])

    assert exc_info.value.code != 0


def test_findings_help_uses_command_specific_output_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--format {text,json}" in output
    assert "--path PATH" in output
    assert "--mark" in output
    assert "--audience" not in output


def test_findings_rejects_removed_human_format() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", ".", "--format", "human"])

    assert exc_info.value.code != 0


def test_findings_rejects_removed_audience_option() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", ".", "--audience", "agent"])

    assert exc_info.value.code != 0


def test_filtered_findings_does_not_mutate_runs_or_finding_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    before = _count_runs_and_finding_events(tmp_path)
    main(["findings", str(tmp_path), "--path", "src/", "--mark", "confirmed"])
    capsys.readouterr()
    after = _count_runs_and_finding_events(tmp_path)

    assert after == before


def _create_session_with_findings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    session_id = json.loads((tmp_path / ".review-gauntlet" / "active-session.json").read_text())[
        "session_id"
    ]
    rows = [
        ("RGF-open", "fp-open", "confirmed", "README.md"),
        ("RGF-config", "fp-config", "confirmed", "src/review_gauntlet/config.py"),
        ("RGF-cli", "fp-cli", "reopened", "src/review_gauntlet/cli.py"),
        ("RGF-test", "fp-test", "confirmed", "tests/test_cli.py"),
        ("RGF-fixed", "fp-fixed", "fixed_verified", "README.md"),
        ("RGF-false", "fp-false", "false_positive", "README.md"),
        ("RGF-waived", "fp-waived", "waived", "README.md"),
        ("RGF-risk", "fp-risk", "accepted_risk", "README.md"),
        ("RGF-pending", "fp-pending", "fixed_pending_verification", "README.md"),
    ]
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        conn.executemany(
            """
            insert into findings(
                session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            )
            values (?, ?, ?, ?, ?, 'docs', 'content', '{}')
            """,
            [
                (session_id, finding_id, fingerprint, state, path)
                for finding_id, fingerprint, state, path in rows
            ],
        )


def _count_runs_and_finding_events(tmp_path: Path) -> tuple[int, int]:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        run_count = conn.execute("select count(*) from runs").fetchone()[0]
        event_count = conn.execute("select count(*) from finding_events").fetchone()[0]
    return int(run_count), int(event_count)
