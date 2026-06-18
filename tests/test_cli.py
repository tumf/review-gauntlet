import json
from pathlib import Path

import pytest

from review_gauntlet.__about__ import __version__
from review_gauntlet.cli import main
from review_gauntlet.review_cells import CellState
from review_gauntlet.session_store import SessionStore


def test_cli_version_outputs_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--version"])
    assert capsys.readouterr().out.strip() == f"review-gauntlet {__version__}"


def test_verify_fixes_command_is_not_registered(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify-fixes", "--help"])
    assert exc_info.value.code == 64
    assert "invalid choice" in capsys.readouterr().err


def test_review_help_mentions_parallel_not_verify_fixes(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["review", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--parallel" in output
    assert "verify-fixes" not in output


def test_review_runs_all_pending_cells_despite_legacy_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    cell_count = len(SessionStore(tmp_path).list_cells())
    assert data["reviewed_cells"] == cell_count
    assert data["coverage"] == {CellState.REVIEWED.value: cell_count}


def test_mark_accepts_confirmed_and_dismissed_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "README.md": [
                    {"path": "README.md", "content": "issue", "start_line": 1, "end_line": 1}
                ]
            }
        ),
        encoding="utf-8",
    )
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    finding_id = data["finding_ids"][0]

    main(["mark", str(tmp_path), finding_id, "dismissed", "--reason", "not applicable", "--format", "json"])

    marked = json.loads(capsys.readouterr().out)
    assert marked == {"finding_id": finding_id, "state": "dismissed"}
