import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main


def test_cli_inventory_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["inventory", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["files"][0]["path"] == "README.md"


def test_cli_plan_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["plan", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["slices"][0]["id"] == "docs"
    assert data["slices"][0]["checks"][0]["id"] == "docs-accuracy"


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

    assert exc.value.code == 2


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

    assert exc_info.value.code == 2


@pytest.mark.parametrize("command", ["init", "status", "mark", "finalize", "findings"])
def test_cli_rejects_audience_on_non_review_commands(command: str) -> None:
    argv = [command, ".", "--audience", "agent"]
    if command == "mark":
        argv = ["mark", ".", "RGF-0001", "confirmed", "--audience", "agent"]

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 2


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
