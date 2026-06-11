from review_gauntlet.ocr_rules import RuleDocument
from review_gauntlet.review_adapter import PromptContext, build_review_prompt
from review_gauntlet.review_cells import ReviewCell


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
            file_content="def handler():\n    pass\n",
        )
    )

    assert "repository_root: /repo" in prompt
    assert "cell_id: RGC-test" in prompt
    assert "file_path: src/app.py" in prompt
    assert "rule_id: security" in prompt
    assert "content_digest: abc123" in prompt
    assert "Check auth boundaries" in prompt
    assert '"comments"' in prompt
    assert '"suggestion_code"' in prompt
    assert '"existing_code"' in prompt
    assert "def handler" in prompt
    assert "API_KEY" not in prompt
