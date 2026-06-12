import json
import sqlite3
import sys
from pathlib import Path

import pytest

from review_gauntlet.cli import build_parser, main
from review_gauntlet.findings import normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.session_store import SessionStore


def _init_session(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()


def _cell_for_path(tmp_path: Path, path: str) -> str:
    store = SessionStore(tmp_path)
    rows = store.list_cells()
    for row in rows:
        if row["file_path"] == path:
            return str(row["cell_id"])
    raise AssertionError(f"missing review cell for {path}")


def _fixture(tmp_path: Path, cell_id: str, content: str = "Missing auth") -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                cell_id: [
                    {
                        "path": "README.md",
                        "content": content,
                        "existing_code": "# docs",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return fixture


def _run_count(tmp_path: Path) -> int:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return int(conn.execute("select count(*) from runs").fetchone()[0])


def _finding_state(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select state from findings").fetchone()[0])


def _finding_id(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select finding_id from findings").fetchone()[0])


def _finding_states_by_path(tmp_path: Path) -> dict[str, str]:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        rows = conn.execute("select path, state from findings order by path").fetchall()
    return {str(path): str(state) for path, state in rows}


def _coverage_for_cell(tmp_path: Path, cell_id: str) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(
            conn.execute("select state from review_cells where cell_id = ?", (cell_id,)).fetchone()[
                0
            ]
        )


def _cell_states(tmp_path: Path) -> dict[str, str]:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        rows = conn.execute("select cell_id, state from review_cells order by cell_id").fetchall()
    return {str(cell_id): str(state) for cell_id, state in rows}


def _reviewed_cell_ids(tmp_path: Path) -> list[str]:
    return [cell_id for cell_id, state in _cell_states(tmp_path).items() if state == "reviewed"]


def _command_config(
    tmp_path: Path, script: str, *, name: str = "review-gauntlet.jsonc", legacy_input: bool = False
) -> Path:
    config = tmp_path / name
    config.parent.mkdir(parents=True, exist_ok=True)
    adapter: dict[str, object] = {
        "type": "command",
        "command": sys.executable,
        "args": ["-c", script, "{prompt}"],
        "output": {"mode": "stdout-json"},
        "timeout_seconds": 5,
    }
    if legacy_input:
        adapter["input"] = {"mode": "stdin"}
    config.write_text(json.dumps({"adapter": adapter}), encoding="utf-8")
    return config


def test_review_default_concurrency_is_eight() -> None:
    args = build_parser().parse_args(["review", "."])

    assert args.concurrency == 8


def test_review_rejects_invalid_concurrency_before_adapter_work(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "review",
                str(tmp_path),
                "--fixture",
                str(fixture),
                "--concurrency",
                "0",
                "--format",
                "json",
            ]
        )

    captured = capsys.readouterr()
    assert excinfo.value.code == 64
    assert "concurrency" in captured.err
    assert _run_count(tmp_path) == 0
    assert _coverage_for_cell(tmp_path, _cell_for_path(tmp_path, "README.md")) == "pending"


def test_review_advances_once_with_limited_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)

    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(
        [
            "review",
            str(tmp_path),
            "--fixture",
            str(fixture),
            "--budget",
            "1",
            "--concurrency",
            "8",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert data["run_count"] == 1
    assert data["reviewed_cells"] == 1
    assert data["coverage"]["pending"] > 0
    assert len(_reviewed_cell_ids(tmp_path)) == 1


def test_mark_updates_finding_without_creating_review_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)

    main(
        [
            "mark",
            str(tmp_path),
            finding_id,
            "confirmed",
            "--reason",
            "real issue",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert data["state"] == "confirmed"
    assert _finding_state(tmp_path) == "confirmed"
    assert _run_count(tmp_path) == 1


def test_fixed_finding_is_verified_only_when_relevant_path_is_reviewed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)
    main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])
    capsys.readouterr()
    assert _finding_state(tmp_path) == "fixed_pending_verification"

    empty_fixture = tmp_path / "empty-fixture.json"
    empty_fixture.write_text("{}", encoding="utf-8")
    main(["review", str(tmp_path), "--fixture", str(empty_fixture), "--format", "json"])
    capsys.readouterr()
    assert _finding_state(tmp_path) == "fixed_verified"


def test_partial_failure_verifies_fixed_findings_only_for_successful_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    _init_session(tmp_path, capsys)
    readme_cell = _cell_for_path(tmp_path, "README.md")
    app_cell = _cell_for_path(tmp_path, "app.py")
    fixture = tmp_path / ".review-gauntlet" / "findings.json"
    fixture.write_text(
        json.dumps(
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
            }
        ),
        encoding="utf-8",
    )
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "3", "--format", "json"])
    capsys.readouterr()

    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        finding_ids = [str(row[0]) for row in conn.execute("select finding_id from findings")]
    for finding_id in finding_ids:
        main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
        capsys.readouterr()

    script = (
        "import json, re, sys; "
        "match = re.search(r'cell_id: (\\S+)', sys.argv[1]); "
        "cell_id = match.group(1) if match else 'missing'; "
        f"\nif cell_id == {readme_cell!r}:\n"
        "    print('not-json')\n"
        "else:\n"
        "    print(json.dumps({'comments':[]}))\n"
    )
    config = _command_config(tmp_path, script, name=".review-gauntlet/partial-review.json")

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "review",
                str(tmp_path),
                "--config",
                str(config),
                "--budget",
                "3",
                "--concurrency",
                "2",
                "--format",
                "json",
            ]
        )

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert data["reviewed_cells"] == 2
    assert data["failed_cell_id"] == readme_cell
    assert _finding_states_by_path(tmp_path) == {
        "README.md": "fixed_pending_verification",
        "app.py": "fixed_verified",
    }


def test_fixed_finding_reopens_when_fingerprint_is_seen_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)
    main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()

    assert _finding_state(tmp_path) == "reopened"


def test_command_adapter_review_with_explicit_config_creates_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    script = (
        "import json, re, sys; "
        "prompt=sys.argv[1]; "
        "match = re.search(r'file_path: (\\S+)', prompt); "
        "path = match.group(1) if match else 'custom.json'; "
        "print(json.dumps({'comments':[{'path':path,'content':'Command issue',"
        "'existing_code':'source omitted from prompt','start_line':1,'end_line':1}]}))"
    )
    config = _command_config(tmp_path, script, name="custom.json")

    main(["review", str(tmp_path), "--config", str(config), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["reviewed_cells"] == 1
    assert data["finding_ids"] == ["RGF-0001"]
    assert data["run_count"] == 1
    assert _finding_state(tmp_path) == "untriaged"


def test_command_adapter_review_with_discovered_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _command_config(tmp_path, "import json; print(json.dumps({'comments':[]}))")

    main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["reviewed_cells"] == 1
    assert data["run_count"] == 1


def test_command_adapter_reviews_selected_cells_concurrently_with_isolated_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    starts_dir = tmp_path / "starts"
    script = (
        "import json, pathlib, re, sys, time; "
        f"starts = pathlib.Path({str(starts_dir)!r}); starts.mkdir(exist_ok=True); "
        "match = re.search(r'cell_id: (\\S+)', sys.argv[1]); "
        "cell_id = match.group(1) if match else 'missing'; "
        "(starts / cell_id).write_text('started', encoding='utf-8'); "
        "deadline = time.time() + 2; "
        "\nwhile len(list(starts.iterdir())) < 2 and time.time() < deadline:\n"
        "    time.sleep(0.01)\n"
        "\nif len(list(starts.iterdir())) < 2:\n    sys.exit(7)\n"
        "print(json.dumps({'comments':[]}))"
    )
    _command_config(tmp_path, script)

    main(["review", str(tmp_path), "--budget", "2", "--concurrency", "2", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    reviewed_cell_ids = _reviewed_cell_ids(tmp_path)
    assert data["reviewed_cells"] == 2
    assert len(reviewed_cell_ids) == 2
    assert sorted(path.name for path in starts_dir.iterdir()) == reviewed_cell_ids
    for cell_id in reviewed_cell_ids:
        cell_dir = tmp_path / ".review-gauntlet" / "runs" / str(data["run_id"]) / "cells" / cell_id
        assert (cell_dir / "prompt.md").is_file()
        assert (cell_dir / "stdout.txt").is_file()
        assert (cell_dir / "stderr.txt").is_file()
        assert (cell_dir / "command.json").is_file()
        assert (cell_dir / "verdict.json").is_file()


def test_concurrent_review_failure_persists_later_successes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    _init_session(tmp_path, capsys)
    ordered_cells = [str(row["cell_id"]) for row in SessionStore(tmp_path).list_cells()]
    failing_cell = ordered_cells[0]
    script = (
        "import json, re, sys; "
        "match = re.search(r'cell_id: (\\S+)', sys.argv[1]); "
        "cell_id = match.group(1) if match else 'missing'; "
        f"\nif cell_id == {failing_cell!r}:\n"
        "    print('not-json')\n"
        "else:\n"
        "    print(json.dumps({'comments':[]}))\n"
    )
    _command_config(tmp_path, script)

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(tmp_path), "--budget", "3", "--concurrency", "2", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert data["reviewed_cells"] == 2
    assert data["finding_ids"] == []
    assert data["failed_cell_id"] == failing_cell
    assert "invalid verdict JSON" in data["error"]
    assert data["coverage"]["reviewed"] == 2
    assert _coverage_for_cell(tmp_path, failing_cell) == "pending"
    assert len(_reviewed_cell_ids(tmp_path)) == 2

    _command_config(tmp_path, "import json; print(json.dumps({'comments':[]}))")
    main(["review", str(tmp_path), "--budget", "1", "--format", "json"])
    retry_data = json.loads(capsys.readouterr().out)
    assert retry_data["reviewed_cells"] == 1
    assert _coverage_for_cell(tmp_path, failing_cell) == "reviewed"


def test_legacy_command_adapter_config_fails_clearly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    before_runs = _run_count(tmp_path)
    _command_config(tmp_path, "print('unused')", legacy_input=True)

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    err = capsys.readouterr().err
    assert excinfo.value.code == 64
    assert "invalid review config" in err
    assert "input" in err
    assert _run_count(tmp_path) <= before_runs + 1


def test_review_with_no_selected_cells_does_not_create_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    empty_fixture = tmp_path / "empty-fixture.json"
    empty_fixture.write_text("{}", encoding="utf-8")
    main(["review", str(tmp_path), "--fixture", str(empty_fixture), "--format", "json"])
    capsys.readouterr()
    before_runs = _run_count(tmp_path)

    main(["review", str(tmp_path), "--fixture", str(empty_fixture), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] is None
    assert data["reviewed_cells"] == 0
    assert _run_count(tmp_path) == before_runs


def test_review_budget_zero_does_not_create_finalization_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    before_runs = _run_count(tmp_path)

    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_id"] is None
    assert data["reviewed_cells"] == 0
    assert _run_count(tmp_path) == before_runs


def test_review_without_fixture_or_config_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(tmp_path), "--format", "json"])

    assert excinfo.value.code == 64
    assert "requires --fixture or a command adapter config" in capsys.readouterr().err


def test_command_adapter_invalid_verdict_cli_failure_includes_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _command_config(tmp_path, "print(\"{'comments': []}\")")

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    failed_cell_id = data["failed_cell_id"]
    failure = data["failure"]
    assert excinfo.value.code == 1
    assert failure["output_mode"] == "stdout-json"
    assert failure["verdict_path"].endswith(f"/cells/{failed_cell_id}/verdict.json")
    assert failure["raw_verdict_path"].endswith(f"/cells/{failed_cell_id}/verdict.raw.json")
    assert "'comments'" in failure["raw_snippet"]
    assert "strict JSON" in failure["hint"]
    assert _coverage_for_cell(tmp_path, failed_cell_id) == "pending"


@pytest.mark.parametrize(
    "script, expected",
    [
        ("import sys; sys.exit(9)", "status 9"),
        ("print('not-json')", "invalid verdict JSON"),
    ],
)
def test_command_adapter_failure_keeps_cell_pending_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], script: str, expected: str
) -> None:
    _init_session(tmp_path, capsys)
    cell_id = _cell_for_path(tmp_path, "README.md")
    _command_config(tmp_path, script)

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    assert excinfo.value.code == 1
    data = json.loads(capsys.readouterr().out)
    assert expected in data["error"]
    assert data["run_count"] == 1
    assert data["reviewed_cells"] == 0
    assert _coverage_for_cell(tmp_path, cell_id) == "pending"


def test_command_adapter_success_and_failure_create_one_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _command_config(tmp_path, "import json; print(json.dumps({'comments':[]}))")
    main(["review", str(tmp_path), "--budget", "1", "--format", "json"])
    capsys.readouterr()
    assert _run_count(tmp_path) == 1

    _command_config(tmp_path, "print('not-json')")
    with pytest.raises(SystemExit):
        main(["review", str(tmp_path), "--budget", "1", "--format", "json"])
    capsys.readouterr()
    assert _run_count(tmp_path) == 2


def test_finding_fingerprint_deduplicates_shifted_line_numbers() -> None:
    first = normalize_ocr_comment(
        OCRComment(
            path="app.py", content="Missing auth", existing_code="guard()", start_line=3, end_line=3
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="digest",
    )
    shifted = normalize_ocr_comment(
        OCRComment(
            path="app.py",
            content="Missing auth",
            existing_code="guard()",
            start_line=90,
            end_line=90,
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="digest",
    )

    assert first.fingerprint == shifted.fingerprint
