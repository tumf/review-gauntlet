## Implementation Tasks

- [ ] Define a typed run-turn continuation schema and validators in a new module `src/review_gauntlet/continuation.py`.
  Completion condition: the module exposes a `ContinuationVerdict` dataclass or Pydantic model with `schema_version`, `verdict`, `summary`, `completed_finding_ids`, `remaining_finding_ids`, `next_turn_instructions`, and optional `error`. A `validate_continuation_verdict(path: Path) -> ContinuationVerdict` function rejects invalid verdicts, unsafe paths (traversal outside `.review-gauntlet/turns/<session_id>/`), and partial writes (file exists but is not valid JSON). A `compute_task_key(reason: str, file_path: str) -> str` function produces deterministic collision-resistant keys matching `<action>__<short-hash>.json`.
  verification: unit - add `tests/test_continuation.py` with tests for accepted JSON shapes, rejected shapes, partial-write handling, path traversal rejection, and task_key determinism.

- [ ] Add `verdict_grace_seconds` field to `CommandAdapterConfig` in `src/review_gauntlet/config.py`.
  Completion condition: `CommandAdapterConfig` has a `verdict_grace_seconds: float = 30.0` field with a `@field_validator` rejecting non-finite or non-positive values, matching the existing pattern for `timeout_seconds` and `quiet_timeout_seconds`.
  verification: unit - extend `tests/test_config.py` to cover valid and invalid `verdict_grace_seconds` values and effective-config merging.

- [ ] Render continuation-file instructions into file-scoped ready prompts in `_build_file_scoped_ready_prompt` (`src/review_gauntlet/cli.py`, line 1516).
  Completion condition: the function accepts a `continuation_path: Path | None` parameter. When provided, it appends "## Turn verdict / continuation file" with the deterministic path and schema instructions. All actionable findings for the selected file remain grouped in the prompt; findings are not split into separate one-finding turns.
  verification: unit - extend `tests/test_cli_ready.py` to assert multiple findings for the same file remain present and the continuation path/schema section is present when a session exists.

- [ ] Inject compact previous-turn context from an existing continuation JSON file into the next prompt.
  Completion condition: `_build_file_scoped_ready_prompt` reads the continuation file at the computed task_key path. When a valid prior continuation file exists, the prompt includes a "## Previous turn context" section before "## Turn verdict / continuation file" with summary, completed/remaining finding IDs, next-turn instructions, and previous verdict. When the file is absent, no section is added. When the file has invalid JSON, a one-line warning is included instead of crashing.
  verification: unit - extend `tests/test_cli_ready.py` to cover existing valid continuation context, absent continuation context, and invalid JSON fallback behavior.

- [ ] Add continuation verdict file monitoring to the subprocess polling loop in `_run_session_command_step` (`src/review_gauntlet/cli.py`, line 1983).
  Completion condition: when a continuation file path is passed, the polling loop checks for the file on each 0.1-second iteration. When a valid verdict JSON is detected, `verdict_detected_at` is recorded and the loop switches to grace-period countdown using `config.verdict_grace_seconds`. When the grace period expires with the child still running, the child is killed (matching the existing `kill_and_persist_timeout` pattern). Partial writes (file exists, `json.loads()` fails) are treated as not-yet-written, not as errors. `SessionCommandResult` includes `verdict_metadata` with the parsed verdict.
  verification: integration - add `tests/test_cli_run.py` fake-command case where the command writes a valid continuation JSON file and sleeps; `review-gauntlet run` completes before the sleep duration and records a verdict-finalized result rather than waiting for quiet timeout.

- [ ] Extend `SessionCommandResult` in `src/review_gauntlet/run_controller.py` with `verdict_metadata: dict[str, object] | None = None`.
  Completion condition: the dataclass has the new field with a default of `None`. `_run_step_payload` includes verdict metadata in the step payload when present. `_lifecycle_status_from_result` recognizes the new verdict failure reasons.
  verification: unit - extend `tests/test_run_controller.py` to cover verdict metadata propagation through step payload and lifecycle status derivation for new failure reasons.

- [ ] Add verdict failure reasons to `_agent_status_from_failure_reason` in `src/review_gauntlet/run_controller.py` (line 620).
  Completion condition: `step_verdict_error` maps to `"verdict_error"`, `invalid_step_verdict` maps to `"verdict_invalid"`, `missing_step_verdict` maps to `"verdict_missing"`, and `no_progress` maps to `"no_progress"`. These are distinct from existing `timeout`, `quiet_timeout`, `command_failed`, and `startup_error` statuses.
  verification: unit - extend `tests/test_run_controller.py` to cover each new reason mapping.

- [ ] Map continuation verdict outcomes to run control semantics in `RunController.run()` (`src/review_gauntlet/run_controller.py`, line 307).
  Completion condition: `continue` and `finish` verdicts with progress are successful command-step outcomes that cause the run controller to call `self.refresh()` and proceed. `error`, malformed JSON, and missing required verdict files become structured failures with distinct reasons (`step_verdict_error`, `invalid_step_verdict`, `missing_step_verdict`). The run result preserves the verdict metadata.
  verification: unit - extend `tests/test_run_controller.py` to cover `continue` (with progress), `finish`, `error`, malformed JSON, missing file, and command non-zero interactions with verdict detection.

- [ ] Detect no-progress continuation outcomes for targeted actionable work.
  Completion condition: when a step reports `continue` or `finish` but none of the targeted finding or review-cell states changed in the ledger, the run stops with `reason: no_progress`, `task_key`, and `target_ids`. Pre-turn state is captured from `_ready_prompt_from_context` arguments. Post-turn state is checked via `store.list_cells()` and `store.list_findings()`.
  verification: integration - add a `tests/test_cli_run.py` fake-command case where the command writes `continue` without marking any finding, and `review-gauntlet run` fails with `reason: no_progress`.

- [ ] Persist verdict artifacts in `_persist_session_command_artifacts` (`src/review_gauntlet/cli.py`, line 2047).
  Completion condition: when a verdict file was detected, the function copies it to `<run_dir>/verdict.json` and includes a `verdict_detected` entry in the activity JSONL. The original continuation file under `.review-gauntlet/turns/` remains for next-turn handoff.
  verification: unit - extend artifact persistence tests to verify verdict.json copy and activity JSONL entry when verdict metadata is present.

- [ ] Preserve existing review adapter, timeout, and TUI behavior outside continuation-aware run turns.
  Completion condition: `review-gauntlet review`, `verify-fixes`, existing command adapter file-json verdict handling, overall timeout, quiet timeout, and TUI failure labels continue to satisfy existing tests. The new `verdict_grace_seconds` field does not affect non-continuation prompts.
  verification: integration - run `uv run pytest tests/test_cli_run.py tests/test_review_adapter.py tests/test_run_tui.py tests/test_run_controller.py tests/test_cli_ready.py tests/test_config.py` plus the new continuation tests.

## Final Validation

Expected archive gate: `cflx openspec validate add-run-turn-verdict-continuation --archive-gate`

Recommended implementation validation: `make check` plus focused tests around run continuation behavior.

## Future Work

- Consider exposing continuation/grace settings in command adapter config documentation and `review-gauntlet config effective` output after the default behavior proves stable.
- Consider adding a diagnostic command to inspect `.review-gauntlet/turns/` continuation files if operators need visibility beyond run artifacts.
- Consider TUI display enhancements to show verdict-detected status and grace countdown in the Agent panel.
