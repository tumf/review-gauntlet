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
    assert data["total"] == 1
    assert data["returned"] == 1
    assert set(data) == {"session_id", "total", "returned", "findings"}


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

    assert exc_info.value.code == 64


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

    assert exc_info.value.code == 64


def test_findings_rejects_removed_audience_option() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", ".", "--audience", "agent"])

    assert exc_info.value.code == 64


def test_filtered_findings_does_not_mutate_runs_or_finding_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_findings(tmp_path, capsys)

    before = _count_runs_and_finding_events(tmp_path)
    main(["findings", str(tmp_path), "--path", "src/", "--mark", "confirmed"])
    capsys.readouterr()
    after = _count_runs_and_finding_events(tmp_path)

    assert after == before


def test_findings_default_limits_to_ten_after_filtering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_numbered_findings(tmp_path, capsys, count=12)

    main(["findings", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["total"] == 12
    assert data["returned"] == 10
    assert len(data["findings"]) == 10


def test_findings_explicit_limit_slices_sorted_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_numbered_findings(tmp_path, capsys, count=6)

    main(["findings", str(tmp_path), "--limit", "3", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["total"] == 6
    assert data["returned"] == 3
    assert [finding["finding_id"] for finding in data["findings"]] == [
        "RGF-002",
        "RGF-003",
        "RGF-001",
    ]


def test_findings_all_findings_disables_result_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_numbered_findings(tmp_path, capsys, count=12)

    main(["findings", str(tmp_path), "--all-findings", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["total"] == 12
    assert data["returned"] == 12
    assert len(data["findings"]) == 12


def test_findings_all_and_all_findings_are_independent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _create_session_with_numbered_findings(tmp_path, capsys, count=12)
    _insert_numbered_finding(tmp_path, index=99, state="fixed_verified")

    main(["findings", str(tmp_path), "--all-findings", "--format", "json"])
    all_findings_data = json.loads(capsys.readouterr().out)
    main(["findings", str(tmp_path), "--all", "--all-findings", "--format", "json"])
    all_visible_data = json.loads(capsys.readouterr().out)

    assert all_findings_data["total"] == 12
    assert "RGF-099" not in {finding["finding_id"] for finding in all_findings_data["findings"]}
    assert all_visible_data["total"] == 13
    assert "RGF-099" in {finding["finding_id"] for finding in all_visible_data["findings"]}


def test_findings_rejects_limit_with_all_findings(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", str(tmp_path), "--limit", "3", "--all-findings"])

    assert exc_info.value.code == 64


def test_findings_rejects_non_positive_limit() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["findings", ".", "--limit", "0"])

    assert exc_info.value.code == 64


def _create_session_with_numbered_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], *, count: int
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    for index in range(1, count + 1):
        _insert_numbered_finding(tmp_path, index=index, state="confirmed")


def _insert_numbered_finding(tmp_path: Path, *, index: int, state: str) -> None:
    session_id = json.loads((tmp_path / ".review-gauntlet" / "active-session.json").read_text())[
        "session_id"
    ]
    finding_id = f"RGF-{index:03d}"
    path, start_line, end_line = _numbered_finding_location(index)
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        conn.execute(
            """
            insert into findings(
                session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            )
            values (?, ?, ?, ?, ?, 'docs', 'content', '{}')
            """,
            (session_id, finding_id, f"fp-{index:03d}", state, path),
        )
        conn.execute(
            """
            insert into finding_occurrences(
                finding_id, run_id, cell_id, path, start_line, end_line, imprecise
            )
            values (?, 1, 'cell', ?, ?, ?, 0)
            """,
            (finding_id, path, start_line, end_line),
        )


def _numbered_finding_location(index: int) -> tuple[str, int, int]:
    locations = {
        1: ("a.py", 2, 2),
        2: ("a.py", 1, 1),
        3: ("a.py", 2, 1),
    }
    return locations.get(index, (f"b/{index:03d}.py", index, index))


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
