from pathlib import Path

import pytest

from review_gauntlet.continuation import (
    ContinuationVerdictError,
    compute_task_key,
    continuation_path_for_task,
    validate_continuation_verdict,
)


def _write_verdict(path: Path, *, verdict: str = "continue") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
{
  "schema_version": 2,
  "verdict": "%s",
  "summary": "completed useful work",
  "completed_finding_ids": ["RGF-0001", "RGF-0001"],
  "remaining_finding_ids": ["RGF-0002"],
  "resolutions": [{"finding_id": "RGF-0001", "state": "confirmed", "dismiss_reason": null}],
  "next_turn_instructions": "continue with the remaining finding",
  "error": %s
}
""".strip()
        % (verdict, '"agent error"' if verdict == "abort" else "null"),
        encoding="utf-8",
    )


def test_validate_continuation_verdict_accepts_schema(tmp_path: Path) -> None:
    path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )
    _write_verdict(path)

    verdict = validate_continuation_verdict(path)

    assert verdict.schema_version == 2
    assert verdict.verdict == "continue"
    assert verdict.completed_finding_ids == ("RGF-0001",)
    assert verdict.remaining_finding_ids == ("RGF-0002",)


@pytest.mark.parametrize(
    "content, message",
    [
        ("{}", "invalid continuation verdict schema"),
        ("[]", "must be an object"),
        ("{", "not valid JSON"),
        (
            """{
              "schema_version": 2,
              "verdict": "abort",
              "summary": "bad",
              "completed_finding_ids": [],
              "remaining_finding_ids": [],
              "next_turn_instructions": "retry",
              "error": null
            }""",
            "abort verdicts require",
        ),
    ],
)
def test_validate_continuation_verdict_rejects_invalid_shapes(
    tmp_path: Path, content: str, message: str
) -> None:
    path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ContinuationVerdictError, match=message):
        validate_continuation_verdict(path)


def test_validate_continuation_verdict_rejects_path_traversal(tmp_path: Path) -> None:
    path = (
        tmp_path / ".review-gauntlet" / "turns" / "RGS-test" / ".." / "untriaged__aaaaaaaaaaaa.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ContinuationVerdictError, match="escapes session turn directory"):
        validate_continuation_verdict(path)


def test_compute_task_key_is_deterministic_and_action_prefixed() -> None:
    first = compute_task_key("open", "src/example.py")
    second = compute_task_key("open", "src/example.py")
    other = compute_task_key("confirmed", "src/example.py")

    assert first == second
    assert first.startswith("open__")
    assert first.endswith(".json")
    assert first != other
    assert len(first.removesuffix(".json").rpartition("__")[2]) == 12


@pytest.mark.parametrize("reason", ["../bad", "bad/action", "bad action"])
def test_compute_task_key_rejects_unsafe_actions(reason: str) -> None:
    with pytest.raises(ContinuationVerdictError, match="invalid continuation action"):
        compute_task_key(reason, "src/example.py")
