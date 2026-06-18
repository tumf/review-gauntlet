from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.findings import normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment, load_ruleset
from review_gauntlet.review_adapter import (
    CommandReviewAdapter,
    FakeReviewAdapter,
    ReviewAdapterError,
    ReviewAdapterResult,
    _json_error_position,  # pyright: ignore[reportPrivateUsage]
    _line_column_position,  # pyright: ignore[reportPrivateUsage]
    _process_output_text,  # pyright: ignore[reportPrivateUsage]
    _raw_snippet,  # pyright: ignore[reportPrivateUsage]
    build_resolve_prompt,
    cancel_adapter,
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


def test_build_resolve_prompt_limits_open_finding_target_states(tmp_path: Path) -> None:
    continuation_path = tmp_path / ".review-gauntlet" / "turns" / "RGS-test" / "open.json"

    prompt = build_resolve_prompt(
        repository_root=str(tmp_path),
        file_path="README.md",
        findings=(
            {
                "finding_id": "RGF-0001",
                "state": "open",
                "rule_id": "docs",
                "content": "not a real issue",
            },
        ),
        continuation_path=str(continuation_path),
    )

    assert "allowed_target_states: confirmed, dismissed" in prompt
    assert "Each resolution.state must be one of the allowed_target_states" in prompt
    assert "use confirmed for real issues or dismissed for false positives" in prompt
    assert "false_positive, accepted_risk, waived" not in prompt


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


# ---------------------------------------------------------------------------
# Unit tests for private helpers and cancel_adapter
# ---------------------------------------------------------------------------


class TestRawSnippet:
    def test_short_value_returned_as_is(self) -> None:
        assert _raw_snippet("hello", None) == "hello"

    def test_long_value_truncated_without_position(self) -> None:
        value = "x" * 600
        result = _raw_snippet(value, None, limit=500)
        assert result == "x" * 500 + "…"

    def test_position_centered_in_middle(self) -> None:
        value = "a" * 200 + "MARKER" + "b" * 200
        pos = 200
        result = _raw_snippet(value, pos, limit=50)
        assert "…" in result
        assert len(result.replace("…", "")) <= 50

    def test_position_near_start(self) -> None:
        value = "a" * 600
        result = _raw_snippet(value, 5, limit=100)
        assert not result.startswith("…")
        assert result.endswith("…")

    def test_position_near_end(self) -> None:
        value = "a" * 600
        result = _raw_snippet(value, 595, limit=100)
        assert result.startswith("…")
        assert not result.endswith("…")

    def test_exact_limit_no_truncation(self) -> None:
        value = "a" * 500
        assert _raw_snippet(value, None, limit=500) == value


class TestJsonErrorPosition:
    def test_json_decode_error(self) -> None:
        try:
            json.loads("{bad}")
        except json.JSONDecodeError as exc:
            assert _json_error_position(exc) == exc.pos

    def test_non_json_value_error(self) -> None:
        assert _json_error_position(ValueError("something")) is None

    def test_validation_error_with_json_invalid(self) -> None:
        class Strict(BaseModel):
            x: int

        try:
            Strict.model_validate_json("{bad json}")
        except PydanticValidationError as exc:
            result = _json_error_position(exc)
            assert result is None or isinstance(result, int)


class TestLineColumnPosition:
    def test_valid_line_column(self) -> None:
        value = "line1\nline2\nline3\n"
        pos = _line_column_position(value, "error at line 2 column 3")
        assert pos == len("line1\n") + 2

    def test_no_match(self) -> None:
        assert _line_column_position("abc", "no position info") is None

    def test_line_zero_returns_none(self) -> None:
        assert _line_column_position("abc", "line 0 column 1") is None

    def test_column_zero_returns_none(self) -> None:
        assert _line_column_position("abc", "line 1 column 0") is None

    def test_line_beyond_content(self) -> None:
        assert _line_column_position("one line", "line 5 column 1") is None

    def test_single_line(self) -> None:
        assert _line_column_position("hello", "line 1 column 3") == 2


class TestProcessOutputText:
    def test_none_returns_empty(self) -> None:
        assert _process_output_text(None) == ""

    def test_str_passthrough(self) -> None:
        assert _process_output_text("hello") == "hello"

    def test_bytes_decoded(self) -> None:
        assert _process_output_text(b"hello") == "hello"

    def test_bytes_with_invalid_utf8(self) -> None:
        result = _process_output_text(b"hello\xff\xfeworld")
        assert "hello" in result
        assert "world" in result


class TestCancelAdapter:
    def test_calls_cancel_on_cancellable(self) -> None:
        class FakeCancellable:
            cancelled = False

            def review(self, cell: ReviewCell) -> ReviewAdapterResult:
                raise NotImplementedError

            def cancel(self) -> None:
                self.cancelled = True

        adapter = FakeCancellable()
        cancel_adapter(adapter)
        assert adapter.cancelled

    def test_noop_on_non_cancellable(self) -> None:
        class FakeNonCancellable:
            def review(self, cell: ReviewCell) -> ReviewAdapterResult:
                raise NotImplementedError

        cancel_adapter(FakeNonCancellable())
