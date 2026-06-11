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


def test_cli_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["inventory", str(tmp_path / "missing")])
    assert exc.value.code == 64


def test_cli_init_creates_session_without_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["init", str(tmp_path), "--worktree", "--format", "json", "--audience", "agent"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_count"] == 0
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    assert (tmp_path / ".review-gauntlet" / "ledger.sqlite").exists()


def test_cli_status_json_after_init(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()

    main(["status", str(tmp_path), "--format", "json", "--audience", "agent"])

    data = json.loads(capsys.readouterr().out)
    assert data["next_required_action"] == "run_review"
    assert data["can_finalize"] is False
