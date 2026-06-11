import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main


def test_cli_inventory_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    main(["inventory", str(tmp_path), "--json"])

    data = json.loads(capsys.readouterr().out)
    assert data["files"][0]["path"] == "README.md"


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
