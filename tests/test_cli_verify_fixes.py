import json
import sqlite3
import sys
from pathlib import Path

import pytest

from review_gauntlet.cli import build_parser, main
from review_gauntlet.session_store import SessionStore


def _init_session(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()


def _cell_for_path(tmp_path: Path, path: str) -> str:
    for row in SessionStore(tmp_path).list_cells():
        if row["file_path"] == path:
            return str(row["cell_id"])
    raise AssertionError(f"missing cell for {path}")


def _python_cell_for_rule(tmp_path: Path, path: str, rule_id: str) -> str:
    for row in SessionStore(tmp_path).list_cells():
        if row["file_path"] == path and row["rule_id"] == rule_id:
            return str(row["cell_id"])
    raise AssertionError(f"missing cell for {path} rule {rule_id}")


def _fixture(tmp_path: Path, comments_by_cell: dict[str, list[dict[str, object]]]) -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(comments_by_cell), encoding="utf-8")
    return fixture


def _seed_two_fixed_findings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, str]:
    _init_session(tmp_path, capsys)
    readme_cell = _cell_for_path(tmp_path, "README.md")
    app_cell = _cell_for_path(tmp_path, "app.py")
    fixture = _fixture(
        tmp_path,
        {
            readme_cell: [
                {
                    "path": "README.md",
                    "content": "Docs issue",
                    "existing_code": "# docs",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            app_cell: [
                {
                    "path": "app.py",
                    "content": "Code issue",
                    "existing_code": "print('hello')",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
        },
    )
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "50", "--format", "json"])
    capsys.readouterr()
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        rows = conn.execute("select finding_id, path from findings order by path").fetchall()
    ids_by_path = {str(path): str(finding_id) for finding_id, path in rows}
    for finding_id in ids_by_path.values():
        main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
        capsys.readouterr()
    return ids_by_path


def _states_by_path(tmp_path: Path) -> dict[str, str]:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        rows = conn.execute("select path, state from findings order by path").fetchall()
    return {str(path): str(state) for path, state in rows}


def _cell_rows_by_path(tmp_path: Path, path: str) -> list[dict[str, object]]:
    return [dict(row) for row in SessionStore(tmp_path).list_cells() if row["file_path"] == path]


def _count_runs_and_events(tmp_path: Path) -> tuple[int, int]:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        runs = conn.execute("select count(*) from runs").fetchone()[0]
        events = conn.execute("select count(*) from finding_events").fetchone()[0]
    return int(runs), int(events)


def test_verify_fixes_parser_accepts_execution_and_focus_options() -> None:
    args = build_parser().parse_args(
        [
            "verify-fixes",
            ".",
            "--config",
            "review-gauntlet.jsonc",
            "--fixture",
            "fixture.json",
            "--budget",
            "2",
            "--concurrency",
            "3",
            "--format",
            "json",
            "--audience",
            "agent",
            "--finding",
            "RGF-0001",
            "--path",
            "src/",
        ]
    )

    assert args.command == "verify-fixes"
    assert args.budget == 2
    assert args.concurrency == 3
    assert args.format == "json"
    assert args.audience == "agent"
    assert args.finding == ["RGF-0001"]
    assert args.path == ["src/"]


def test_verify_fixes_success_json_and_filters_only_fixed_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _seed_two_fixed_findings(tmp_path, capsys)
    empty_fixture = _fixture(tmp_path, {})

    main(
        [
            "verify-fixes",
            str(tmp_path),
            "--fixture",
            str(empty_fixture),
            "--finding",
            ids["README.md"],
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert data["reviewed_cells"] == 1
    assert data["targeted_finding_ids"] == [ids["README.md"]]
    assert data["fixed_verified_ids"] == [ids["README.md"]]
    assert data["reopened_ids"] == []
    assert data["unverifiable_ids"] == []
    assert set(data) >= {
        "run_id",
        "reviewed_cells",
        "targeted_finding_ids",
        "fixed_verified_ids",
        "reopened_ids",
        "unverifiable_ids",
        "finding_ids",
        "can_finalize",
        "finalize_blockers",
    }
    assert _states_by_path(tmp_path) == {
        "README.md": "fixed_verified",
        "app.py": "fixed_pending_verification",
    }


def test_verify_fixes_resolves_fixed_pending_path_digest_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _seed_two_fixed_findings(tmp_path, capsys)
    before_rows = _cell_rows_by_path(tmp_path, "README.md")
    assert before_rows
    before_digest = str(before_rows[0]["content_digest"])
    (tmp_path / "README.md").write_text("# docs\n\nfixed content\n", encoding="utf-8")
    empty_fixture = _fixture(tmp_path, {})

    main(
        [
            "verify-fixes",
            str(tmp_path),
            "--fixture",
            str(empty_fixture),
            "--finding",
            ids["README.md"],
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    after_rows = _cell_rows_by_path(tmp_path, "README.md")
    refreshed_rows = [row for row in after_rows if row["content_digest"] != before_digest]
    assert data["reviewed_cells"] == 1
    assert data["fixed_verified_ids"] == [ids["README.md"]]
    assert len(refreshed_rows) == len(after_rows)
    assert {str(row["state"]) for row in refreshed_rows} == {"reviewed"}
    assert _states_by_path(tmp_path)["README.md"] == "fixed_verified"


def test_verify_fixes_refreshes_targeted_file_siblings_without_staling_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    target_cell = _python_cell_for_rule(tmp_path, "app.py", "data-validation")
    sibling_cell = _python_cell_for_rule(tmp_path, "app.py", "test-evidence")
    fixture = _fixture(
        tmp_path,
        {
            target_cell: [
                {
                    "path": "app.py",
                    "content": "Code issue",
                    "existing_code": "print('hello')",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            sibling_cell: [],
        },
    )
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "50", "--format", "json"])
    capsys.readouterr()
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        finding_id = str(conn.execute("select finding_id from findings").fetchone()[0])
    main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
    capsys.readouterr()
    before_rows = _cell_rows_by_path(tmp_path, "app.py")
    before_digest = str(before_rows[0]["content_digest"])
    (tmp_path / "app.py").write_text("print('fixed')\n", encoding="utf-8")
    empty_fixture = _fixture(tmp_path, {})

    main(
        [
            "verify-fixes",
            str(tmp_path),
            "--fixture",
            str(empty_fixture),
            "--finding",
            finding_id,
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    after_rows = _cell_rows_by_path(tmp_path, "app.py")
    states_by_rule = {str(row["rule_id"]): str(row["state"]) for row in after_rows}
    assert data["reviewed_cells"] == 1
    assert data["fixed_verified_ids"] == [finding_id]
    assert {str(row["content_digest"]) for row in after_rows} != {before_digest}
    assert len({str(row["content_digest"]) for row in after_rows}) == 1
    assert states_by_rule["data-validation"] == "reviewed"
    assert states_by_rule["test-evidence"] == "reviewed"
    assert {str(row["state"]) for row in after_rows} == {"reviewed"}


def test_verify_fixes_redetection_reopens_without_command_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _seed_two_fixed_findings(tmp_path, capsys)
    readme_cell = _cell_for_path(tmp_path, "README.md")
    fixture = _fixture(
        tmp_path,
        {
            readme_cell: [
                {
                    "path": "README.md",
                    "content": "Docs issue",
                    "existing_code": "# docs",
                    "start_line": 1,
                    "end_line": 1,
                }
            ]
        },
    )

    main(["verify-fixes", str(tmp_path), "--fixture", str(fixture), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert ids["README.md"] in data["reopened_ids"]
    assert _states_by_path(tmp_path)["README.md"] == "reopened"


def test_verify_fixes_failure_leaves_failed_path_unverifiable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _seed_two_fixed_findings(tmp_path, capsys)
    readme_cell = _cell_for_path(tmp_path, "README.md")
    script = (
        "import json, re, sys; "
        "cell_id = re.search(r'cell_id: (\\S+)', sys.argv[1]).group(1); "
        f"\nif cell_id == {readme_cell!r}:\n"
        "    print('not-json')\n"
        "else:\n"
        "    print(json.dumps({'comments':[]}))\n"
    )
    config = tmp_path / "review-gauntlet.jsonc"
    config.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": sys.executable,
                    "args": ["-c", script, "{prompt}"],
                    "output": {"mode": "stdout-json"},
                    "timeout_seconds": 5,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "verify-fixes",
                str(tmp_path),
                "--config",
                str(config),
                "--concurrency",
                "2",
                "--format",
                "json",
            ]
        )

    data = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 1
    assert data["failed_cell_id"] == readme_cell
    assert ids["README.md"] in data["unverifiable_ids"]
    assert ids["app.py"] in data["fixed_verified_ids"]
    assert _states_by_path(tmp_path) == {
        "README.md": "fixed_pending_verification",
        "app.py": "fixed_verified",
    }


def test_verify_fixes_budget_zero_noops_without_run_or_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _seed_two_fixed_findings(tmp_path, capsys)
    before = _count_runs_and_events(tmp_path)

    main(["verify-fixes", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] is None
    assert data["reviewed_cells"] == 0
    assert set(data["unverifiable_ids"]) == set(ids.values())
    assert _count_runs_and_events(tmp_path) == before


@pytest.mark.parametrize("unsafe_path", ["/tmp/escape.py", "../escape.py"])
def test_verify_fixes_rejects_unsafe_path_before_adapter_execution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], unsafe_path: str
) -> None:
    _seed_two_fixed_findings(tmp_path, capsys)
    before = _count_runs_and_events(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(["verify-fixes", str(tmp_path), "--path", unsafe_path, "--format", "json"])

    assert exc_info.value.code == 64
    assert _count_runs_and_events(tmp_path) == before


def test_verify_fixes_help_output(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify-fixes", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--finding FINDING" in output
    assert "--path PATH" in output
    assert "--audience {human,agent}" in output
