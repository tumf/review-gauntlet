import errno
import json
import sqlite3
from pathlib import Path
from typing import NoReturn

import pytest

from review_gauntlet.__about__ import __version__
from review_gauntlet.cli import (
    RunSnapshotReadinessProvider,
    _finalize_reasons,  # pyright: ignore[reportPrivateUsage]
    _run_session_command_step,  # pyright: ignore[reportPrivateUsage]
    main,
)
from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.models import MatrixRow, ReviewCheck, ReviewMatrix, ReviewPlan, ReviewSlice
from review_gauntlet.report import render_markdown_report
from review_gauntlet.review_adapter import VERDICT_OUTPUT_SIZE_LIMIT_BYTES


def test_cli_version_flag_outputs_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--version"])

    assert capsys.readouterr().out == f"review-gauntlet {__version__}\n"


def test_cli_inventory_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["inventory", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["files"][0]["path"] == "README.md"


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_cli_completion_outputs_script_for_supported_shells(
    shell: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    main(["completion", shell])

    output = capsys.readouterr().out
    assert output
    assert "review-gauntlet" in output
    for command in (
        "inventory",
        "plan",
        "report",
        "init",
        "review",
        "verify-fixes",
        "status",
        "ready",
        "findings",
        "mark",
        "finalize",
        "cancel",
        "validate-verdict",
        "completion",
    ):
        assert command in output
    for option in (
        "--format",
        "--budget",
        "--concurrency",
        "--fixture",
        "--config",
        "--audience",
        "--finding",
        "--path",
        "--mark",
        "--reason",
        "--owner",
        "--until",
    ):
        assert option in output or option.removeprefix("--") in output
    assert not (tmp_path / ".review-gauntlet").exists()


@pytest.mark.parametrize(
    "argv", [["completion", "powershell"], ["completion", "bash", "--format", "json"]]
)
def test_cli_completion_uses_usage_error_code(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 64


def _assert_usage_error(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 64


def test_cli_init_worktree_flags_rejected() -> None:
    _assert_usage_error(["init", ".", "--worktree"])
    _assert_usage_error(["init", ".", "--git-worktree"])


def test_cli_init_no_setup_rejected() -> None:
    _assert_usage_error(["init", ".", "--no-setup"])


def test_cli_finalize_merge_rejected() -> None:
    _assert_usage_error(["finalize", ".", "--merge"])


def test_validate_verdict_accepts_valid_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verdict = tmp_path / "verdict.json"
    verdict.write_text(json.dumps({"comments": []}), encoding="utf-8")

    main(["validate-verdict", str(verdict), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data == {"comment_count": 0, "path": str(verdict), "valid": True}


def test_validate_verdict_rejects_oversized_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verdict = tmp_path / "verdict.json"
    verdict.write_bytes(b"{" + b" " * VERDICT_OUTPUT_SIZE_LIMIT_BYTES + b"}")

    with pytest.raises(SystemExit) as exc_info:
        main(["validate-verdict", str(verdict), "--format", "json"])

    assert exc_info.value.code == 64
    assert "verdict file exceeds size limit" in capsys.readouterr().err


def test_validate_verdict_rejects_extra_comment_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verdict = tmp_path / "verdict.json"
    verdict.write_text(
        json.dumps({"comments": [{"path": "app.py", "content": "x", "rule_id": "bad"}]}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-verdict", str(verdict), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert data["valid"] is False
    assert "Extra inputs are not permitted" in data["error"]


def test_validate_verdict_rejects_unexpected_comment_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    verdict = tmp_path / "verdict.json"
    verdict.write_text(
        json.dumps({"comments": [{"path": "other.py", "content": "x"}]}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "validate-verdict",
                str(verdict),
                "--expected-path",
                "app.py",
                "--format",
                "json",
            ]
        )

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert data["valid"] is False
    assert "comment paths must match expected path app.py: other.py" in data["error"]


@pytest.mark.parametrize(
    "comment",
    [
        {"path": "app.py", "content": "x", "start_line": 0, "end_line": 5},
        {"path": "app.py", "content": "x", "start_line": 5, "end_line": 4},
    ],
)
def test_validate_verdict_rejects_invalid_precise_line_ranges(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], comment: dict[str, object]
) -> None:
    verdict = tmp_path / "verdict.json"
    verdict.write_text(json.dumps({"comments": [comment]}), encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-verdict", str(verdict), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert data["valid"] is False
    assert "comment has an invalid line range" in data["error"]


def test_cli_config_preset_list_outputs_text(capsys: pytest.CaptureFixture[str]) -> None:
    main(["config", "preset", "list"])

    assert capsys.readouterr().out == "claude\nopencode\ncodex\n"


def test_cli_config_preset_list_outputs_json(capsys: pytest.CaptureFixture[str]) -> None:
    main(["config", "preset", "list", "--format", "json"])

    assert json.loads(capsys.readouterr().out) == {"presets": ["claude", "opencode", "codex"]}


def test_cli_config_preset_show_outputs_contents(capsys: pytest.CaptureFixture[str]) -> None:
    main(["config", "preset", "show", "opencode"])

    output = capsys.readouterr().out
    assert '"type": "command"' in output
    assert "opencode" in output


def test_cli_config_preset_show_rejects_unknown_preset() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["config", "preset", "show", "custom"])

    assert exc_info.value.code == 64


def test_readme_documents_canonical_shell_completion_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "review-gauntlet completion bash" in readme
    assert "review-gauntlet completion zsh" in readme
    assert "review-gauntlet completion fish" in readme
    assert "review-guantlet" not in readme


def test_cli_plan_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["plan", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["slices"][0]["id"] == "docs"
    assert data["slices"][0]["checks"][0]["id"] == "docs-accuracy"


def test_cli_plan_applies_review_exclusions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    included = ["src/app.py", "README.md"]
    excluded = [
        "docs/usage.md",
        "openspec/specs/review-sessions/spec.md",
        "tests/test_app.py",
        "app.test.ts",
        "package.json",
        "uv.lock",
    ]
    for relative in [*included, *excluded]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content\n", encoding="utf-8")

    main(["plan", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    planned_paths = {
        file_path for review_slice in data["slices"] for file_path in review_slice["files"]
    }
    assert set(included) <= planned_paths
    assert not (set(excluded) & planned_paths)


def test_cli_report_applies_review_exclusions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for relative in ["src/app.py", "docs/usage.md", "openspec/specs/app/spec.md", "package.json"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content\n", encoding="utf-8")

    main(["report", str(tmp_path)])

    output = capsys.readouterr().out
    assert "python-runtime" in output
    assert "docs-accuracy" not in output
    assert "dependency-audit" not in output
    assert "docs/usage.md" not in output
    assert "openspec/specs/app/spec.md" not in output
    assert "package.json" not in output


def test_cli_inventory_defaults_to_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["inventory", str(tmp_path)])

    output = capsys.readouterr().out
    assert "Inventory\n" in output
    assert "Files: 1\n" in output
    assert "- README.md [docs] risks=-\n" in output
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


def test_cli_plan_defaults_to_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["plan", str(tmp_path)])

    output = capsys.readouterr().out
    assert "Review Plan\n" in output
    assert "Slices: 1\n" in output
    assert "- docs: Documentation files=1 checks=docs-accuracy\n" in output
    assert "  - README.md\n" in output
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


@pytest.mark.parametrize("command", ["inventory", "plan"])
def test_cli_rejects_legacy_json_flag(command: str, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main([command, str(tmp_path), "--json"])

    assert exc.value.code == 64


def test_cli_report_outputs_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["report", str(tmp_path)])

    output = capsys.readouterr().out
    assert "# Review Gauntlet Report" in output
    assert "docs-accuracy" in output
    assert "NEEDS_REVIEW" in output


def test_cli_report_format_text_outputs_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["report", str(tmp_path), "--format", "text"])

    output = capsys.readouterr().out
    assert "# Review Gauntlet Report" in output
    assert "docs-accuracy" in output
    assert "NEEDS_REVIEW" in output


def test_markdown_report_escapes_table_cell_pipes_and_newlines() -> None:
    plan = ReviewPlan(
        root="/repo",
        slices=(
            ReviewSlice(
                id="docs|api",
                title="Docs",
                files=("README.md",),
                checks=(ReviewCheck(id="docs|accuracy", title="Docs", why="Evidence"),),
            ),
        ),
    )
    matrix = ReviewMatrix(
        root="/repo",
        rows=(
            MatrixRow(
                slice_id="docs|api",
                check_id="docs|accuracy",
                evidence="finding RGF|0001\r\nline two\npath C:\\tmp",
            ),
        ),
    )

    output = render_markdown_report(plan, matrix)

    assert "`docs\\|api`" in output
    assert "docs\\|accuracy" in output
    assert "finding RGF\\|0001<br>line two<br>path C:\\\\tmp" in output


@pytest.mark.parametrize(
    ("command", "obsolete_format"),
    [
        ("init", "human"),
        ("review", "human"),
        ("status", "human"),
        ("mark", "human"),
        ("finalize", "human"),
        ("report", "markdown"),
    ],
)
def test_cli_rejects_obsolete_format_choices(command: str, obsolete_format: str) -> None:
    argv = [command, ".", "--format", obsolete_format]
    if command == "mark":
        argv = ["mark", ".", "RGF-0001", "confirmed", "--format", obsolete_format]

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 64


@pytest.mark.parametrize("command", ["init", "status", "mark", "finalize", "cancel", "findings"])
def test_cli_rejects_audience_on_non_review_commands(command: str) -> None:
    argv = [command, ".", "--audience", "agent"]
    if command == "mark":
        argv = ["mark", ".", "RGF-0001", "confirmed", "--audience", "agent"]

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 64


def _help_output(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exc_info:
        main([*argv, "--help"])

    assert exc_info.value.code == 0
    return capsys.readouterr().out


def test_cli_review_help_exposes_audience(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help_output(["review"], capsys)

    assert "--format {text,json}" in output
    assert "--audience {human,agent}" in output


@pytest.mark.parametrize("command", ["inventory", "plan", "report", "status", "ready"])
def test_cli_help_shows_optional_root_and_format_defaults(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _help_output([command], capsys)

    assert "Repository root (default: .)" in output
    assert "Output format (default: text)" in output


def test_cli_review_help_shows_numeric_and_audience_defaults(
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = _help_output(["review"], capsys)

    assert "Maximum review budget (default: 50)" in output
    assert "Review concurrency (default: 3)" in output
    assert "Output format (default: text)" in output
    assert "Progress output audience (default: human)" in output
    assert "--fixture" in output
    assert "default:" not in output.split("--fixture", maxsplit=1)[1].splitlines()[0]
    assert "--config" in output
    assert "default:" not in output.split("--config", maxsplit=1)[1].splitlines()[0]


def test_cli_verify_fixes_help_shows_repeatable_filter_defaults(
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = _help_output(["verify-fixes"], capsys)

    assert "Filter by finding ID (default: none)" in output
    assert "Filter by finding path (default: none)" in output
    assert "Maximum review budget (default: 50)" in output
    assert "Review concurrency (default: 3)" in output
    assert "Progress output audience (default: human)" in output


def test_cli_findings_help_shows_boolean_repeatable_and_mark_defaults(
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = _help_output(["findings"], capsys)

    assert "Include terminal findings (default: false)" in output
    assert "Filter by finding path (default: none)" in output
    assert "Filter by finding state marker (default: none)" in output


def test_cli_mark_help_shows_metadata_string_defaults(
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = _help_output(["mark"], capsys)

    assert "Decision reason (default: none)" in output
    assert "Decision owner (default: none)" in output
    assert "Decision expiry date, YYYY-MM-DD (default: none)" in output
    assert "finding_id" in output
    finding_line = next(line for line in output.splitlines() if "finding_id" in line)
    assert "default:" not in finding_line


def test_cli_status_help_shows_boolean_default(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help_output(["status"], capsys)

    assert "Allow uncommitted non-review files in the working tree" in output
    assert "(default: false)" in output


def test_cli_finalize_help_omits_merge(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help_output(["finalize"], capsys)

    assert "--merge" not in output
    assert "Merge and clean up" not in output
    assert "Allow uncommitted non-review files in the working tree" in output


def test_cli_init_help_shows_boolean_defaults(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help_output(["init"], capsys)

    assert "Review workspace/worktree changes as the target" not in output
    assert "--worktree" not in output
    assert "Create an isolated Git linked worktree" not in output
    assert "--git-worktree" not in output
    assert "--no-setup" not in output
    assert "(default: false)" in output
    assert "Review all files (default: false)" in output
    assert "--from" in output
    assert "--to" in output
    assert "--commit" in output


def test_cli_validate_verdict_help_does_not_force_path_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = _help_output(["validate-verdict"], capsys)

    path_line = next(line for line in output.splitlines() if "path" in line)
    assert "default:" not in path_line
    assert "Output format (default: text)" in output


def test_cli_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["inventory", str(tmp_path / "missing")])
    assert exc.value.code == 64


def test_cli_init_creates_session_without_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["init", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_count"] == 0
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    assert (tmp_path / ".review-gauntlet" / "ledger.sqlite").exists()


def test_cli_cancel_removes_active_marker_and_records_cancelled_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    session_id = json.loads(capsys.readouterr().out)["session_id"]

    main(["cancel", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data == {"session_id": session_id, "session_state": "cancelled"}
    state_dir = tmp_path / ".review-gauntlet"
    assert not (state_dir / "active-session.json").exists()
    with sqlite3.connect(state_dir / "ledger.sqlite") as conn:
        assert (
            conn.execute(
                "select state from sessions where session_id = ?", (session_id,)
            ).fetchone()[0]
            == "cancelled"
        )


@pytest.mark.parametrize("command", ["status", "review", "ready"])
def test_cli_session_commands_fail_after_cancel_until_reinit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    main(["cancel", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        main([command, str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    assert "no active review session; run review-gauntlet init" in capsys.readouterr().err


def test_cli_cancel_creates_no_review_runs_or_checkpoints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    session_id = json.loads(capsys.readouterr().out)["session_id"]

    main(["cancel", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    state_dir = tmp_path / ".review-gauntlet"
    assert not (state_dir / "runs").exists()
    assert not (state_dir / "checkpoints").exists()
    with sqlite3.connect(state_dir / "ledger.sqlite") as conn:
        assert (
            conn.execute(
                "select count(*) from runs where session_id = ?", (session_id,)
            ).fetchone()[0]
            == 0
        )
        assert conn.execute("select count(*) from finding_occurrences").fetchone()[0] == 0
        assert conn.execute("select count(*) from finding_events").fetchone()[0] == 0
        assert (
            conn.execute(
                "select count(*) from review_cells where session_id = ? and state != 'pending'",
                (session_id,),
            ).fetchone()[0]
            == 0
        )


def test_cli_cancel_requires_active_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["cancel", str(tmp_path), "--format", "json"])

    assert exc_info.value.code == 1
    assert "no active review session; run review-gauntlet init" in capsys.readouterr().err
    assert not (tmp_path / ".review-gauntlet").exists()


def test_cli_mark_json_outputs_string_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from review_gauntlet.findings import FindingState
    from review_gauntlet.session_store import SessionStore

    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    store = SessionStore(tmp_path)
    session_id = store.active_session_id()
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(
              session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            ) values (?, ?, ?, ?, 'README.md', 'docs-accuracy', 'finding', '{}')
            """,
            (session_id, "RGF-0001", "fp-1", FindingState.UNTRIAGED.value),
        )

    main(
        [
            "mark",
            str(tmp_path),
            "RGF-0001",
            "confirmed",
            "--format",
            "json",
            "--reason",
            "true issue",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert data["state"] == "confirmed"
    assert data["finding_id"] == "RGF-0001"


def test_review_enforces_budget_with_multiple_cells_per_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("print('hi')\n", encoding="utf-8")

    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({}), encoding="utf-8")

    main(["init", str(tmp_path)])

    main(
        [
            "review",
            str(tmp_path),
            "--concurrency",
            "1",
            "--budget",
            "1",
            "--fixture",
            str(fixture),
        ]
    )

    assert capsys.readouterr().err
    main(["status", str(tmp_path), "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert data["coverage"]["reviewed"] == 1


def test_cli_status_json_after_init(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["next_required_action"] == "run_review"
    assert data["can_finalize"] is False


def test_run_snapshot_readiness_provider_returns_ready_task_with_next_action(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from review_gauntlet.session_store import SessionStore

    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    store = SessionStore(tmp_path)
    provider = RunSnapshotReadinessProvider()

    provider.status_snapshot(store, tmp_path)
    ready_task = provider.ready_prompt(store, tmp_path)

    assert ready_task is not None
    assert ready_task.next_required_action == "run_review"
    assert "confirmed" in ready_task.prompt
    assert "fix" in ready_task.prompt


def _raise_emfile_git(_root: Path, *args: str) -> str:
    raise OSError(errno.EMFILE, "Too many open files")


def test_finalize_reasons_blocks_when_git_status_check_hits_emfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from review_gauntlet import checkpoint as checkpoint_module
    from review_gauntlet.session_store import SessionStore
    from review_gauntlet.targets import HeadMode, TargetKind, TargetSpec

    (tmp_path / ".git").mkdir()
    store = SessionStore(tmp_path)
    session_id = store.create_session(
        {
            "session_id": "RGS-test",
            "root": str(tmp_path),
            "target": TargetSpec(
                kind=TargetKind.COMMIT, commit="HEAD", head_mode=HeadMode.FIXED
            ).model_dump(mode="json"),
        },
        (),
    )
    monkeypatch.setattr(checkpoint_module, "_git", _raise_emfile_git)

    reasons = _finalize_reasons({}, {}, store, session_id, tmp_path)

    assert any("git status checks unavailable" in reason for reason in reasons)
    assert any("startup_error_reason=resource_exhaustion" in reason for reason in reasons)
    assert any(f"errno={errno.EMFILE}" in reason for reason in reasons)


def test_cli_status_json_blocks_when_git_status_check_hits_emfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from review_gauntlet import checkpoint as checkpoint_module

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr(checkpoint_module, "_git", _raise_emfile_git)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is False
    assert data["next_required_action"] == "run_review"
    blockers = data["finalize_blockers"]
    assert any("git status checks unavailable" in blocker for blocker in blockers)
    assert any("startup_error_reason=resource_exhaustion" in blocker for blocker in blockers)


def test_cli_finalize_emfile_blocks_without_writing_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from review_gauntlet import checkpoint as checkpoint_module
    from review_gauntlet.review_cells import CellState
    from review_gauntlet.session_store import SessionStore
    from review_gauntlet.targets import target_digest

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    session_id = json.loads(capsys.readouterr().out)["session_id"]
    store = SessionStore(tmp_path)
    for row in store.list_cells(str(session_id)):
        store.update_cell_state(str(session_id), str(row["cell_id"]), CellState.REVIEWED)
    store.create_run(str(session_id), target_digest(tmp_path))
    monkeypatch.setattr(checkpoint_module, "_git", _raise_emfile_git)

    with pytest.raises(SystemExit) as exc_info:
        main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 1
    assert data["can_finalize"] is False
    assert data["session_state"] == "active"
    assert any(
        "startup_error_reason=resource_exhaustion" in blocker
        for blocker in data["finalize_blockers"]
    )
    assert not (tmp_path / ".review-gauntlet" / "checkpoints").exists()
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def _successful_run_result() -> dict[str, object]:

    return {
        "completed": True,
        "reason": "completed",
        "steps": [],
        "step_count": 0,
        "session_id": None,
    }


def _fake_cmd_run(_args: object, _root: Path, _store: object) -> dict[str, object]:
    return _successful_run_result()


def _fake_controller_run(_self: object) -> dict[str, object]:
    return _successful_run_result()


def _raise_controller_keyboard_interrupt(_self: object) -> dict[str, object]:
    raise KeyboardInterrupt


def test_run_session_command_persists_agent_output_artifacts(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    script.write_text(
        "import sys\nprint('out-line')\nprint('err-line', file=sys.stderr)\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / ".review-gauntlet"
    config = CommandAdapterConfig(type="command", command="python", args=(str(script),))

    result = _run_session_command_step(
        config=config, root=tmp_path, state_dir=state_dir, prompt="review pending cells"
    )

    assert result.returncode == 0
    assert result.stdout == "out-line\n"
    assert result.stderr == "err-line\n"
    assert result.stdout_artifact is not None
    assert result.stderr_artifact is not None
    assert result.activity_artifact is not None
    assert Path(result.stdout_artifact).read_text(encoding="utf-8") == result.stdout
    assert Path(result.stderr_artifact).read_text(encoding="utf-8") == result.stderr
    activity = Path(result.activity_artifact).read_text(encoding="utf-8")
    assert '"stream": "stdout"' in activity
    assert '"stream": "stderr"' in activity
    assert tuple((entry.stream, entry.text) for entry in result.output_tail) == (
        ("stdout", "out-line"),
        ("stderr", "err-line"),
    )


def test_cli_run_help_exposes_no_tui(capsys: pytest.CaptureFixture[str]) -> None:
    output = _help_output(["run"], capsys)

    assert "--no-tui" in output


def test_cli_run_without_active_session_exits_with_actionable_guidance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err == "no active review session; run review-gauntlet init\n"
    assert captured.out == ""


def test_cli_run_without_active_session_preflights_before_config_tui_or_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_load_config(_root: Path, _config_path: Path | None = None) -> NoReturn:
        raise AssertionError("load_config should not run without an active session")

    def fail_should_use_tui(*, output_format: str, no_tui: bool, stdout_is_tty: bool) -> NoReturn:
        raise AssertionError("should_use_tui should not run without an active session")

    def fail_create_run_app(_controller: object) -> NoReturn:
        raise AssertionError("create_run_app should not run without an active session")

    def fail_controller_init(_self: object, *args: object, **kwargs: object) -> None:
        raise AssertionError("RunController should not be constructed without an active session")

    monkeypatch.setattr("review_gauntlet.cli.load_config", fail_load_config)
    monkeypatch.setattr("review_gauntlet.cli.should_use_tui", fail_should_use_tui)
    monkeypatch.setattr("review_gauntlet.cli.create_run_app", fail_create_run_app)
    monkeypatch.setattr("review_gauntlet.cli.RunController.__init__", fail_controller_init)

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err == "no active review session; run review-gauntlet init\n"
    assert captured.out == ""


def test_cli_run_no_tui_accepts_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr("review_gauntlet.cli.sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("review_gauntlet.cli._cmd_run", _fake_cmd_run)

    main(["run", str(tmp_path), "--no-tui", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["completed"] is True


def test_cli_run_rejects_non_integer_max_steps_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--max-steps", "abc"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 64
    assert "must be an integer" in captured.err
    assert "Traceback" not in captured.err


def test_cli_run_json_keyboard_interrupt_emits_parseable_json_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr(
        "review_gauntlet.cli.RunController.run", _raise_controller_keyboard_interrupt
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--format", "json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exc_info.value.code == 1
    assert data["completed"] is False
    assert data["reason"] == "interrupted"
    assert data["error"] == "run interrupted by user"
    assert data["step_count"] == 0
    assert data["steps"] == []
    assert data["session_id"].startswith("RGS-")
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_cli_run_text_keyboard_interrupt_emits_concise_failure_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr(
        "review_gauntlet.cli.RunController.run", _raise_controller_keyboard_interrupt
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["run", str(tmp_path), "--no-tui"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "completed: False" in captured.out
    assert "reason: interrupted" in captured.out
    assert "error: run interrupted by user" in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_cli_run_json_does_not_emit_tui_fallback_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "fake-agent"}}), encoding="utf-8"
    )
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr("review_gauntlet.cli.sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("review_gauntlet.cli.textual_available", lambda: False)
    monkeypatch.setattr("review_gauntlet.cli.RunController.run", _fake_controller_run)

    main(["run", str(tmp_path), "--format", "json"])

    captured = capsys.readouterr()
    assert "TUI support is not installed" not in captured.out
    assert "TUI support is not installed" not in captured.err
    assert json.loads(captured.out)["completed"] is True


def test_cli_run_interactive_text_missing_textual_falls_back_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "fake-agent"}}), encoding="utf-8"
    )
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr("review_gauntlet.cli.sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("review_gauntlet.cli.textual_available", lambda: False)
    monkeypatch.setattr("review_gauntlet.cli.RunController.run", _fake_controller_run)

    main(["run", str(tmp_path)])

    captured = capsys.readouterr()
    assert "TUI support is not installed; falling back to text mode." in captured.err
    assert "Reinstall review-gauntlet to restore bundled TUI dependencies." in captured.err
    assert "completed: True" in captured.out


def test_cli_run_interactive_text_with_tui_available_chooses_tui_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "fake-agent"}}), encoding="utf-8"
    )
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr("review_gauntlet.cli.sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("review_gauntlet.cli.textual_available", lambda: True)

    class FakeApp:
        def run(self) -> dict[str, object]:
            return {
                "completed": True,
                "reason": "completed",
                "steps": [],
                "step_count": 0,
                "session_id": None,
            }

    def fake_create_run_app(_controller: object) -> FakeApp:
        return FakeApp()

    monkeypatch.setattr("review_gauntlet.cli.create_run_app", fake_create_run_app)

    main(["run", str(tmp_path)])

    assert capsys.readouterr().out == ""


def test_cli_run_non_tty_text_chooses_text_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "fake-agent"}}), encoding="utf-8"
    )
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    monkeypatch.setattr("review_gauntlet.cli.sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("review_gauntlet.cli.textual_available", lambda: True)
    monkeypatch.setattr("review_gauntlet.cli.RunController.run", _fake_controller_run)

    main(["run", str(tmp_path)])

    assert "completed: True" in capsys.readouterr().out
