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
        "prompt=sys.argv[1]; "
        "assert sys.stdin.read() == ''; "
        "assert 'README.md' in prompt; "
        "assert 'file_size_bytes: 7' in prompt; "
        "assert 'line_count: 1' in prompt; "
        "assert '# docs' not in prompt; "
        "print(json.dumps({'comments':[{'path':'README.md','content':'Issue','start_line':1,'end_line':1}]}))"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{prompt}"],
            "output": {"mode": "stdout-json"},
        }
    )

    result = _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    assert result.comments[0].content == "Issue"
    assert "README.md" in (cell_dir / "prompt.md").read_text(encoding="utf-8")
    assert (cell_dir / "stdout.txt").read_text(encoding="utf-8")
    assert (cell_dir / "stderr.txt").is_file()
    command = json.loads((cell_dir / "command.json").read_text(encoding="utf-8"))
    assert command["argv"][0] == sys.executable
    assert "README.md" in command["argv"][3]
    assert command["cwd"] is None
    assert command["cwd_mode"] == "inherited"
    assert command["env_overrides"] == []
    assert command["output_mode"] == "stdout-json"
    assert command["timeout_seconds"] == 600
    assert "input_mode" not in command


def test_command_adapter_accepts_imprecise_and_precise_verdict_comments(
    tmp_path: Path,
) -> None:
    script = (
        "import json, sys; "
        "comments=["
        "{'path':'README.md','content':'file-level','start_line':0,'end_line':0},"
        "{'path':'README.md','content':'precise','start_line':1,'end_line':1}]; "
        "print(json.dumps({'comments': comments}))"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script],
            "output": {"mode": "stdout-json"},
        }
    )

    result = _adapter(tmp_path, config).review(_cell(tmp_path))

    assert [comment.content for comment in result.comments] == ["file-level", "precise"]


@pytest.mark.parametrize(
    ("comment", "message"),
    [
        (
            {"path": "other.py", "content": "cross", "start_line": 1, "end_line": 1},
            "different review cell path",
        ),
        (
            {"path": "README.md", "content": "bad-order", "start_line": 2, "end_line": 1},
            "invalid line range",
        ),
        (
            {"path": "README.md", "content": "too-large", "start_line": 2, "end_line": 2},
            "exceeds review cell line count",
        ),
    ],
)
def test_command_adapter_rejects_out_of_scope_verdict_comments(
    tmp_path: Path, comment: dict[str, object], message: str
) -> None:
    script = f"import json; print(json.dumps({{'comments': [{comment!r}]}}))"
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script],
            "output": {"mode": "stdout-json"},
        }
    )

    with pytest.raises(ReviewAdapterError, match=message) as excinfo:
        _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert excinfo.value.failure == failure
    assert failure["comment_path"] == comment["path"]
    assert failure["comment_index"] == 0


def test_command_adapter_prompt_argv_and_file_json_success(tmp_path: Path) -> None:
    script = (
        "import json, pathlib, sys; "
        "prompt=sys.argv[1]; "
        "assert 'README.md' in prompt; "
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({'comments':[]}))"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{prompt}", "{output_file}"],
            "output": {"mode": "file-json", "path": "{output_file}"},
        }
    )

    result = _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    assert result.comments == ()
    assert json.loads((cell_dir / "verdict.json").read_text(encoding="utf-8")) == {"comments": []}


def test_command_adapter_defaults_to_file_json_output_file_with_stdout_audit(
    tmp_path: Path,
) -> None:
    script = (
        "import json, pathlib, sys; "
        "prompt=sys.argv[1]; "
        "output_file=sys.argv[2]; "
        "assert 'Write the final verdict JSON to this file:' in prompt; "
        "assert output_file in prompt; "
        "assert 'Stdout and stderr are audit/progress channels only' in prompt; "
        "pathlib.Path(output_file).write_text(json.dumps({'comments':[]})); "
        "print('progress: not json')"
    )
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{prompt}", "{output_file}"],
        }
    )

    result = _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    command = json.loads((cell_dir / "command.json").read_text(encoding="utf-8"))
    assert result.comments == ()
    assert command["output_mode"] == "file-json"
    assert command["output_path"] == str(cell_dir / "verdict.json")
    assert (cell_dir / "stdout.txt").read_text(encoding="utf-8") == "progress: not json\n"


def test_stdout_json_rejects_output_path() -> None:
    with pytest.raises(ValueError, match="only supported for file-json"):
        CommandAdapterConfig.model_validate(
            {
                "type": "command",
                "command": sys.executable,
                "output": {"mode": "stdout-json", "path": "verdict.json"},
            }
        )


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
        _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert excinfo.value.failure == failure
    assert failure["output_mode"] == "file-json"
    assert failure["verdict_path"] == str(cell_dir / "verdict.json")
    assert failure["raw_verdict_path"] == str(cell_dir / "verdict.raw.json")
    assert "'comments'" in failure["raw_snippet"]
    assert len(failure["raw_snippet"]) <= 501
    assert "strict JSON" in failure["hint"]
    assert not (cell_dir / "verdict.json").read_text(encoding="utf-8").startswith('{"comments"')


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
        _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert excinfo.value.failure == failure
    assert failure["output_mode"] == "stdout-json"
    assert failure["verdict_path"] == str(cell_dir / "verdict.json")
    assert failure["raw_verdict_path"] == str(cell_dir / "verdict.raw.json")
    assert "'comments'" in failure["raw_snippet"]
    assert "strict JSON" in failure["hint"]


def test_command_adapter_default_file_json_fails_when_output_file_missing(
    tmp_path: Path,
) -> None:
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", "print('{\\\"comments\\\": []}')"],
        }
    )

    with pytest.raises(ReviewAdapterError, match="missing verdict output file"):
        _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    assert (cell_dir / "stdout.txt").read_text(encoding="utf-8").strip() == '{"comments": []}'


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
            {
                "type": "command",
                "command": sys.executable,
                "args": ["-c", "print('not json')"],
                "output": {"mode": "stdout-json"},
            },
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
                "output": {"mode": "stdout-json"},
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
            "args": ["-c", "import time; print('before', flush=True); time.sleep(2)"],
            "timeout_seconds": 0.1,
        }
    )

    with pytest.raises(ReviewAdapterError, match="timed out"):
        _adapter(tmp_path, config).review(_cell(tmp_path))

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["timeout_seconds"] == 0.1
    assert (cell_dir / "stdout.txt").read_text(encoding="utf-8") == "before\n"
    assert (cell_dir / "stderr.txt").is_file()


def test_command_adapter_cancel_writes_failure_and_terminates_child(tmp_path: Path) -> None:
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", "import time; print('started', flush=True); time.sleep(10)"],
            "timeout_seconds": 30,
        }
    )
    adapter = _adapter(tmp_path, config)
    cell = _cell(tmp_path)

    import concurrent.futures
    import time

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(adapter.review, cell)
        time.sleep(0.2)
        adapter.cancel()
        with pytest.raises(ReviewAdapterError, match="cancelled"):
            future.result(timeout=2)

    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    failure = json.loads((cell_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["cancelled"] is True
    assert (cell_dir / "stdout.txt").read_text(encoding="utf-8") == "started\n"
    assert (cell_dir / "stderr.txt").is_file()


def test_command_adapter_rejects_cell_id_artifact_escape(tmp_path: Path) -> None:
    config = CommandAdapterConfig.model_validate(
        {"type": "command", "command": sys.executable, "args": ["-c", "pass"]}
    )
    cell = _cell(tmp_path).model_copy(update={"id": "../escape"})

    with pytest.raises(ReviewAdapterError, match="unsafe review cell id"):
        _adapter(tmp_path, config).review(cell)


@pytest.mark.parametrize("cwd", ["..", "/"])
def test_command_adapter_rejects_cwd_outside_repo(tmp_path: Path, cwd: str) -> None:
    config = CommandAdapterConfig.model_validate(
        {"type": "command", "command": sys.executable, "args": ["-c", "pass"], "cwd": cwd}
    )

    with pytest.raises(ReviewAdapterError, match="inside repository root"):
        _adapter(tmp_path, config).review(_cell(tmp_path))


def test_command_adapter_rejects_invalid_cwd(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist"
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", "print('ok')"],
            "cwd": str(non_existent),
        }
    )

    with pytest.raises(ReviewAdapterError, match="not a directory"):
        _adapter(tmp_path, config).review(_cell(tmp_path))


def test_command_adapter_rejects_cell_paths_outside_repo_without_invoking_command(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "invoked.txt"
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", f"import pathlib; pathlib.Path({str(marker)!r}).write_text('yes')"],
        }
    )
    cell = ReviewCell(
        id="RGC-test",
        file_path="../outside.md",
        rule_id="docs",
        slice_id="docs",
        content_digest="digest",
    )

    with pytest.raises(ReviewAdapterError, match="outside repository"):
        _adapter(tmp_path, config).review(cell)

    assert not marker.exists()


def test_command_adapter_rejects_missing_cell_file_without_invoking_command(tmp_path: Path) -> None:
    marker = tmp_path / "invoked.txt"
    config = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", f"import pathlib; pathlib.Path({str(marker)!r}).write_text('yes')"],
        }
    )
    cell = ReviewCell(
        id="RGC-test",
        file_path="missing.md",
        rule_id="docs",
        slice_id="docs",
        content_digest="digest",
    )

    with pytest.raises(ReviewAdapterError, match="not a file"):
        _adapter(tmp_path, config).review(cell)

    assert not marker.exists()


def test_command_adapter_inherits_and_configures_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir()
    configured_cwd = tmp_path / "configured"
    configured_cwd.mkdir()
    monkeypatch.chdir(caller_cwd)
    script = (
        "import json, pathlib, sys; "
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({'comments': []})); "
        "print(json.dumps({'cwd': pathlib.Path.cwd().name}))"
    )

    inherited = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{output_file}"],
            "output": {"mode": "file-json", "path": "{output_file}"},
        }
    )
    _adapter(tmp_path, inherited).review(_cell(tmp_path))
    inherited_cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    inherited_stdout = json.loads((inherited_cell_dir / "stdout.txt").read_text())
    inherited_command = json.loads((inherited_cell_dir / "command.json").read_text())
    assert inherited_stdout["cwd"] == "caller"
    assert inherited_command["cwd"] is None
    assert inherited_command["cwd_mode"] == "inherited"

    configured = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{output_file}"],
            "output": {"mode": "file-json", "path": "{output_file}"},
            "cwd": "configured",
        }
    )
    _adapter(tmp_path, configured).review(_cell(tmp_path))
    configured_cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    configured_stdout = json.loads((configured_cell_dir / "stdout.txt").read_text())
    configured_command = json.loads((configured_cell_dir / "command.json").read_text())
    assert configured_stdout["cwd"] == "configured"
    assert configured_command["cwd"] == str(configured_cwd)
    assert configured_command["cwd_mode"] == "explicit"


def test_command_adapter_env_inheritance_and_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PARENT_ONLY", "visible")
    monkeypatch.delenv("REVIEW_GAUNTLET", raising=False)
    script = (
        "import json, os, pathlib, sys; "
        "payload={'parent': os.environ.get('PARENT_ONLY'), "
        "'marker': os.environ.get('REVIEW_GAUNTLET'), 'custom': os.environ.get('CUSTOM_PROMPT')}; "
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({'comments': []})); "
        "print(json.dumps(payload))"
    )

    inherited = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{output_file}"],
            "output": {"mode": "file-json", "path": "{output_file}"},
        }
    )
    _adapter(tmp_path, inherited).review(_cell(tmp_path))
    cell_dir = tmp_path / ".review-gauntlet" / "runs" / "1" / "cells" / "RGC-test"
    stdout = json.loads((cell_dir / "stdout.txt").read_text())
    command = json.loads((cell_dir / "command.json").read_text())
    assert stdout["parent"] == "visible"
    assert stdout["marker"] is None
    assert stdout["custom"] is None
    assert command["env_overrides"] == []

    overridden = CommandAdapterConfig.model_validate(
        {
            "type": "command",
            "command": sys.executable,
            "args": ["-c", script, "{output_file}"],
            "output": {"mode": "file-json", "path": "{output_file}"},
            "env": {"CUSTOM_PROMPT": "{prompt}", "PARENT_ONLY": "overridden"},
        }
    )
    _adapter(tmp_path, overridden).review(_cell(tmp_path))
    overridden_stdout = json.loads((cell_dir / "stdout.txt").read_text())
    overridden_command = json.loads((cell_dir / "command.json").read_text())
    assert overridden_stdout["parent"] == "overridden"
    assert "README.md" in overridden_stdout["custom"]
    assert overridden_command["env_overrides"] == ["CUSTOM_PROMPT", "PARENT_ONLY"]


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
