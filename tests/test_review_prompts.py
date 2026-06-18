from review_gauntlet.config import OutputMode
from review_gauntlet.ocr_rules import RuleDocument
from review_gauntlet.review_adapter import FileMetadata, PromptContext, build_review_prompt
from review_gauntlet.review_cells import ReviewCell

UNIQUE_FILE_BODY_TEXT = "def handler():\n    return 'secret-body-marker'\n"


def test_review_prompt_contains_cell_rule_context_and_verdict_contract() -> None:
    cell = ReviewCell(
        id="RGC-test",
        file_path="src/app.py",
        rule_id="security",
        slice_id="python",
        content_digest="abc123",
    )
    rule = RuleDocument(id="security", filename="security.md", content="Check auth boundaries")

    prompt = build_review_prompt(
        PromptContext(
            repository_root="/repo",
            cell=cell,
            rule=rule,
            ruleset_digest="rules-digest",
            file_metadata=FileMetadata(
                file_size_bytes=len(UNIQUE_FILE_BODY_TEXT.encode()),
                line_count=UNIQUE_FILE_BODY_TEXT.count("\n"),
            ),
            output_mode=OutputMode.FILE_JSON,
            verdict_output_file="/repo/.review-gauntlet/runs/1/cells/RGC-test/verdict.json",
            review_commit="abc123def456",
        )
    )

    assert "repository_root: /repo" in prompt
    assert "cell_id: RGC-test" in prompt
    assert "file_path: src/app.py" in prompt
    assert "rule_id: security" in prompt
    assert "content_digest: abc123" in prompt
    assert "review_commit: abc123def456" in prompt
    assert "git show abc123def456:src/app.py" in prompt
    assert f"file_size_bytes: {len(UNIQUE_FILE_BODY_TEXT.encode())}" in prompt
    assert f"line_count: {UNIQUE_FILE_BODY_TEXT.count(chr(10))}" in prompt
    assert "Source file contents are not embedded in this prompt" in prompt
    assert "repository_root plus file_path" in prompt
    assert "Only report issues whose JSON path exactly equals" in prompt
    assert "If the only issue you find is in a different file" in prompt
    assert "Every comment.path MUST equal: src/app.py" in prompt
    assert "must contain exactly one top-level key: comments" in prompt
    assert "Do not include rule_id" in prompt
    assert "path, content, suggestion_code" in prompt
    assert "review-gauntlet validate-verdict" in prompt
    assert "Check auth boundaries" in prompt
    assert '"comments"' in prompt
    assert '"suggestion_code"' in prompt
    assert '"existing_code"' in prompt
    assert "## File Content" not in prompt
    assert "```text path=src/app.py" not in prompt
    assert "secret-body-marker" not in prompt
    assert "def handler" not in prompt
    assert "API_KEY" not in prompt
