import json
import sys
from pathlib import Path

import pytest

from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.ocr_rules import load_ruleset
from review_gauntlet.review_adapter import CommandReviewAdapter, ReviewAdapterError
from review_gauntlet.review_cells import ReviewCell


def _cell(tmp_path: Path) -> ReviewCell:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    return ReviewCell(
        id="RGC-test",
        file_path="README.md",
        rule_id="docs",
        slice_id="docs",
        content_digest="digest",
    )


def _adapter(tmp_path: Path, config: CommandAdapterConfig) -> CommandReviewAdapter:
    return CommandReviewAdapter(
        config=config,
        root=tmp_path,
        state_dir=tmp_path / ".review-gauntlet",
        run_id=1,
        ruleset=load_ruleset(),
    )


def test_command_adapter_stdout_json_success_and_artifacts(tmp_path: Path) -> None:
    script = (
        "import json, sys; "
        "prompt=sys.stdin.read(); "
        "assert 'README.md' in prompt; "
        "print(json.dumps({'comments':[{'path':'README.md','content':'Issue','start_line':1,'end_line':1}]}))"
    )
    config = CommandAdapterConfig.model_validate(
        {"type": "command", "command": sys.executable, "args": ["-c", script]}
    )

    result = _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    assert result.comments[0].content == "Issue"
    assert (cell_dir / "prompt.md").is_file()
    assert (cell_dir / "command.json").is_file()
    assert (cell_dir / "stdout.txt").read_text(encoding="utf-8")
    assert (cell_dir / "stderr.txt").is_file()
    command = json.loads((cell_dir / "command.json").read_text(encoding="utf-8"))
    assert command["argv"][0] == sys.executable


def test_command_adapter_prompt_file_and_file_json_success(tmp_path: Path) -> None:
    script = (
        "import json, pathlib, sys; "
        "prompt=pathlib.Path(sys.argv[1]).read_text(); "
        "assert 'README.md' in prompt; "
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({'comments':[]}))"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{prompt_file}", "{output_file}"],
            "input": {"mode": "prompt-file"},
            "output": {"mode": "file-json", "path": "{output_file}"},
            "cwd": "{repo_root}",
        }
    )

    result = _adapter(tmp_path, config).review(_cell(tmp_path))

    assert result.comments == ()


@pytest.mark.parametrize(
    "config_payload, error",
    [
        ({"type": "command", "command": "missing-review-gauntlet-command"}, "command not found"),
        (
            {
                "type": "command",
                "command": sys.executable,
                "args": ["-c", "import sys; sys.exit(7)"],
            },
            "status 7",
        ),
        (
            {"type": "command", "command": sys.executable, "args": ["-c", "print('not json')"]},
            "invalid verdict JSON",
        ),
        (
            {
                "type": "command",
                "command": sys.executable,
                "args": [
                    "-c",
                    "import json; print(json.dumps({'comments':[{'path':'README.md'}]}))",
                ],
            },
            "invalid verdict JSON",
        ),
        (
            {
                "type": "command",
                "command": sys.executable,
                "args": ["-c", "pass"],
                "output": {"mode": "file-json", "path": "{output_file}"},
            },
            "missing verdict output file",
        ),
    ],
)
def test_command_adapter_failure_paths(
    tmp_path: Path, config_payload: dict[str, object], error: str
) -> None:
    config = CommandAdapterConfig.model_validate(config_payload)

    with pytest.raises(ReviewAdapterError, match=error):
        _adapter(tmp_path, config).review(_cell(tmp_path))

    failure = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test" / "failure.json"
    assert failure.is_file()


def test_command_adapter_timeout_failure(tmp_path: Path) -> None:
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", "import time; time.sleep(2)"],
            "timeout_seconds": 0.1,
        }
    )

    with pytest.raises(ReviewAdapterError, match="timed out"):
        _adapter(tmp_path, config).review(_cell(tmp_path))


def test_file_json_output_path_rejects_traversal_and_absolute(tmp_path: Path) -> None:
    for path in ("../verdict.json", str(tmp_path / "outside.json")):
        config = CommandAdapterConfig.model_validate(
            {
                "type": "command",
                "command": sys.executable,
                "args": ["-c", "pass"],
                "output": {"mode": "file-json", "path": path},
            }
        )
        with pytest.raises(ReviewAdapterError, match="unsafe output path"):
            _adapter(tmp_path, config).review(_cell(tmp_path))


def test_file_json_output_path_allows_cell_dir_template(tmp_path: Path) -> None:
    script = (
        "import json, pathlib, sys; "
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({'comments':[]}))"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{cell_dir}/custom.json"],
            "output": {"mode": "file-json", "path": "{cell_dir}/custom.json"},
        }
    )

    assert _adapter(tmp_path, config).review(_cell(tmp_path)).comments == ()
