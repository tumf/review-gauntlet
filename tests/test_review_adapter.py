import json
from pathlib import Path

from review_gauntlet.findings import normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.review_adapter import FakeReviewAdapter
from review_gauntlet.review_cells import ReviewCell


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
