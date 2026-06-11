import json
import sys
from pathlib import Path

import pytest

from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.findings import normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment, load_ruleset
from review_gauntlet.review_adapter import (
    CommandReviewAdapter,
    FakeReviewAdapter,
    ReviewAdapterError,
)
from review_gauntlet.review_cells import ReviewCell

STRICT_JSON_HINT_FRAGMENT = "strict JSON"


def _command_adapter(tmp_path: Path, config: CommandAdapterConfig) -> CommandReviewAdapter:
    return CommandReviewAdapter(
        config=config,
        root=tmp_path,
        state_dir=tmp_path / ".review-gauntlet",
        run_id=1,
        ruleset=load_ruleset(),
    )


def _review_cell(tmp_path: Path) -> ReviewCell:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    return ReviewCell(
        id="RGC-test",
        file_path="README.md",
        rule_id="docs",
        slice_id="docs",
        content_digest="digest",
    )


def test_fake_adapter_emits_fixture_comments(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "README.md": [
                    {"path": "README.md", "content": "Issue", "start_line": 1, "end_line": 1}
                ]
            }
        ),
        encoding="utf-8",
    )
    adapter = FakeReviewAdapter(fixture)

    result = adapter.review(
        ReviewCell(id="RGC-1", file_path="README.md", rule_id="docs", slice_id="docs")
    )

    assert result.comments[0].content == "Issue"


def test_invalid_file_json_failure_includes_actionable_diagnostics(tmp_path: Path) -> None:
    script = (
        "import pathlib, sys; "
        "pathlib.Path(sys.argv[1]).write_text("
        "\"{'comments':[{'path':'README.md','content':'Issue','existing_code':'# docs'}]}\", "
        "encoding='utf-8')"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{output_file}"],
            "output": {"mode": "file-json", "path": "{output_file}"},
        }
    )

    with pytest.raises(ReviewAdapterError, match="invalid verdict JSON") as excinfo:
        _command_adapter(tmp_path, config).review(_review_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert excinfo.value.failure == failure
    assert failure["output_mode"] == "file-json"
    assert failure["verdict_path"] == str(cell_dir / "verdict.json")
    assert failure["raw_verdict_path"] == str(cell_dir / "verdict.raw.json")
    assert "'comments'" in failure["raw_snippet"]
    assert len(failure["raw_snippet"]) <= 501
    assert STRICT_JSON_HINT_FRAGMENT in failure["hint"]
    assert (cell_dir / "verdict.raw.json").read_text(encoding="utf-8").startswith("{")


def test_invalid_stdout_json_failure_includes_actionable_diagnostics(tmp_path: Path) -> None:
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", "print(\"{'comments': []}\")"],
            "output": {"mode": "stdout-json"},
        }
    )

    with pytest.raises(ReviewAdapterError, match="invalid verdict JSON") as excinfo:
        _command_adapter(tmp_path, config).review(_review_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert excinfo.value.failure == failure
    assert failure["output_mode"] == "stdout-json"
    assert failure["verdict_path"] == str(cell_dir / "verdict.json")
    assert failure["raw_verdict_path"] == str(cell_dir / "verdict.raw.json")
    assert "'comments'" in failure["raw_snippet"]
    assert STRICT_JSON_HINT_FRAGMENT in failure["hint"]


def test_ocr_comment_zero_lines_are_preserved_as_imprecise() -> None:
    finding = normalize_ocr_comment(
        OCRComment(
            path="src/app.py",
            content="Missing auth",
            suggestion_code="guard()",
            existing_code="handler()",
            start_line=0,
            end_line=0,
            thinking="line unavailable",
        ),
        repository_id="repo",
        base_target="main..head",
        rule_id="security",
        ruleset_digest="digest",
    )

    assert finding.imprecise is True
    assert finding.start_line == 0
    assert finding.end_line == 0


def test_shifted_line_numbers_keep_same_fingerprint() -> None:
    first = normalize_ocr_comment(
        OCRComment(
            path="a.py", content="Missing auth", existing_code="call()", start_line=1, end_line=1
        ),
        repository_id="repo",
        base_target="base",
        rule_id="security",
        ruleset_digest="digest",
    )
    shifted = normalize_ocr_comment(
        OCRComment(
            path="a.py", content="Missing auth", existing_code="call()", start_line=99, end_line=99
        ),
        repository_id="repo",
        base_target="base",
        rule_id="security",
        ruleset_digest="digest",
    )

    assert first.fingerprint == shifted.fingerprint
