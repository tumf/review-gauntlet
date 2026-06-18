import json
from pathlib import Path

from review_gauntlet.cli import run_session_command_step_for_testing
from review_gauntlet.config import CommandAdapterConfig


def test_run_detects_v2_continue_verdict(tmp_path: Path) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    verdict = state_dir / "turns" / "RGS-test" / "open__aaaaaaaaaaaa.json"
    prompt = "\n".join(
        [
            "Before ending this turn, write valid JSON to the following path:",
            str(verdict),
        ]
    )
    script = (
        "import json, pathlib, sys; "
        "p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text(json.dumps({'schema_version':2,'verdict':'continue','summary':'more',"
        "'completed_finding_ids':[],'remaining_finding_ids':['RGF-0001'],'resolutions':[],"
        "'next_turn_instructions':'continue','error':None}))"
    )

    result = run_session_command_step_for_testing(
        config=CommandAdapterConfig(type="command", command="python", args=("-c", script, str(verdict))),
        root=tmp_path,
        state_dir=state_dir,
        prompt=prompt,
    )

    assert result.failure is None
    assert result.verdict_metadata is not None
    assert result.verdict_metadata["verdict"] == "continue"


def test_run_treats_abort_verdict_as_failure(tmp_path: Path) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    verdict = state_dir / "turns" / "RGS-test" / "open__aaaaaaaaaaaa.json"
    prompt = "\n".join(
        [
            "Before ending this turn, write valid JSON to the following path:",
            str(verdict),
        ]
    )
    payload = {
        "schema_version": 2,
        "verdict": "abort",
        "summary": "blocked",
        "completed_finding_ids": [],
        "remaining_finding_ids": ["RGF-0001"],
        "resolutions": [],
        "next_turn_instructions": None,
        "error": "blocked",
    }
    script = "import json, pathlib, sys; p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(sys.argv[2])"

    result = run_session_command_step_for_testing(
        config=CommandAdapterConfig(type="command", command="python", args=("-c", script, str(verdict), json.dumps(payload))),
        root=tmp_path,
        state_dir=state_dir,
        prompt=prompt,
    )

    assert result.failure is not None
    assert result.failure["reason"] == "step_verdict_abort"
