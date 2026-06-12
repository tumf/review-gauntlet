import json
from pathlib import Path

import pytest

from review_gauntlet.__about__ import __version__
from review_gauntlet.cli import main
from review_gauntlet.models import MatrixRow, ReviewCheck, ReviewMatrix, ReviewPlan, ReviewSlice
from review_gauntlet.report import render_markdown_report


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
        "findings",
        "mark",
        "finalize",
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


@pytest.mark.parametrize("command", ["init", "status", "mark", "finalize", "findings"])
def test_cli_rejects_audience_on_non_review_commands(command: str) -> None:
    argv = [command, ".", "--audience", "agent"]
    if command == "mark":
        argv = ["mark", ".", "RGF-0001", "confirmed", "--audience", "agent"]

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 64


def test_cli_review_help_exposes_audience(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["review", "--help"])

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "--format {text,json}" in output
    assert "--audience {human,agent}" in output


def test_cli_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["inventory", str(tmp_path / "missing")])
    assert exc.value.code == 64


def test_cli_init_creates_session_without_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["init", str(tmp_path), "--worktree", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_count"] == 0
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    assert (tmp_path / ".review-gauntlet" / "ledger.sqlite").exists()


def test_cli_status_json_after_init(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["next_required_action"] == "run_review"
    assert data["can_finalize"] is False
