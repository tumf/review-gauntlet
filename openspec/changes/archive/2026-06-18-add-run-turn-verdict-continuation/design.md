# Design: Run turn verdict continuation

## Background

`review-gauntlet run` currently treats each external-agent subprocess as the unit of progress. A prompt asks the agent to inspect, fix, mark, and stop when the target file has no actionable work. This is too optimistic for multi-finding triage turns: an agent may complete useful work, emit tool calls, or know that it should continue later, while the process remains open and the run waits for normal process exit or timeout.

Conflux has three relevant patterns:

- **JSON-primary verdict contracts** (`src/acceptance.rs`): `parse_json_verdict()` extracts structured `{"verdict": "<kind>", ...}` objects from agent output. `detect_verdict_in_line()` handles both standalone JSON lines and JSONL-wrapped variants. Review Gauntlet adapts this to file-based detection because run turns need durable handoff, not stream-only parsing.
- **Verdict grace termination** (`src/parallel/executor.rs`): `execute_acceptance_in_workspace()` monitors the agent output stream. After detecting a verdict, it sets a `verdict_deadline` (`tokio::time::Instant`) and continues draining output until the deadline expires, then calls `child.terminate()`. The default grace period is 30 seconds (`ACCEPTANCE_VERDICT_GRACE_DEFAULT_SECS`), overridable in tests via `scoped_verdict_grace_secs_for_test`.
- **Previous-attempt context injection** (`src/agent/prompt.rs`): `format_last_output_context()` formats stdout/stderr tail from the prior attempt into compact prompt context for retries.

Review Gauntlet should adapt those ideas with a repository-local JSON file, because the user's desired handoff is durable next-turn state rather than stdout-only verdict parsing.

## Proposed runtime shape

### Continuation file location

Use a repository-confined state path:

```text
.review-gauntlet/turns/<session_id>/<task_key>.json
```

`task_key` should be deterministic and collision-resistant. A safe shape is:

```text
<action>__<short-hash-of-file-path-and-target-ids>.json
```

Where `<action>` corresponds to the ready prompt `reason` field currently used by `_build_file_scoped_ready_prompt` in `cli.py`. Valid action values match `_READY_REASON_LABELS` keys: `pending_review_cell`, `stale_review_cell`, `reopened`, `untriaged`, `confirmed`, `fixed_pending_verification`.

The runtime must ensure the resolved path stays under `.review-gauntlet/turns/<session_id>/` before including it in prompts or reading it. Path traversal in task_key components must be rejected, consistent with the existing cell-ID safety checks in `review_adapter.py`.

### JSON schema

```json
{
  "schema_version": 1,
  "verdict": "continue",
  "summary": "What was accomplished this turn.",
  "completed_finding_ids": ["RGF-0904"],
  "remaining_finding_ids": ["RGF-0905"],
  "next_turn_instructions": "Start by checking _validated_comments_for_cell line range handling.",
  "error": null
}
```

Valid `verdict` values:

- `continue`: the turn made progress but intentionally leaves work for another turn.
- `finish`: the agent believes the file-scoped task is complete for the current target list.
- `error`: the agent cannot continue autonomously; `error` must be a non-empty string.

The file is not a source of truth for finding state. It is a handoff artifact. The ledger remains authoritative for finding and coverage state.

### Prompt rendering

Modify `_build_file_scoped_ready_prompt` in `cli.py` (currently at line 1516). For file-scoped actionable finding prompts, keep grouped findings. Do not split them by finding ID.

The function currently builds a list of sections: Target file, Required workflow, Completion condition, Review cells, Findings. Add two new sections at the end:

```text
## Previous turn context

(Only present when a valid continuation JSON exists for this task key)

verdict: continue
summary: ...
completed_finding_ids: ...
remaining_finding_ids: ...
next_turn_instructions: ...
```

```text
## Turn verdict / continuation file

Before ending this turn, write valid JSON to the following path:
<deterministic continuation file path>

Required schema:
{
  "schema_version": 1,
  "verdict": "continue | finish | error",
  "summary": "What was accomplished this turn.",
  "completed_finding_ids": ["RGF-0904"],
  "remaining_finding_ids": ["RGF-0905"],
  "next_turn_instructions": "Start by checking ...",
  "error": null
}
```

The continuation file path must be derived from `_ready_prompt_from_context` arguments. Since the function currently receives `store` and `context`, it already has access to `context.session_id`. The `task_key` should be computed from the `reason` and `file_path` parameters of `_build_file_scoped_ready_prompt`.

Invalid previous JSON should not crash readiness. It should be surfaced in prompt context as ignored invalid continuation state, and the runtime should overwrite it after the next valid turn.

### Subprocess monitoring

`_run_session_command_step` in `cli.py` (line 1847) should monitor the continuation JSON path while the child runs. The function's existing polling loop (lines 1983–2005) already polls `process.poll()` with 0.1-second sleeps between timeout checks. The verdict file check should be added to this same loop.

#### Integration with existing polling loop

The current loop structure:

```python
while True:
    returncode = process.poll()
    if returncode is not None:
        break
    # check overall_remaining and quiet_remaining
    # process.wait(timeout=min(overall_remaining, quiet_remaining, 0.1))
```

Add verdict file polling inside this loop, between the process poll and the timeout checks:

1. If the prompt declared a continuation file path, check `continuation_path.exists()` on each iteration.
2. When the file exists and has been modified since the last check, attempt to read and validate it.
3. Handle partial writes: if the file exists but `json.loads()` fails, treat it as not-yet-written and continue polling. Do not treat a partial write as an invalid verdict.
4. When the file validates with `verdict` in `continue|finish|error`, record `verdict_detected_at = time.monotonic()`.
5. Once `verdict_detected_at` is set, replace the timeout comparison with a grace deadline: `grace_remaining = verdict_grace_seconds - (now - verdict_detected_at)`.
6. If the child exits before the grace deadline, process normally.
7. If the grace deadline expires while the child is still running, call `process.kill()` then `process.wait()`, matching the existing `kill_and_persist_timeout` pattern.
8. Persist stdout/stderr/activity artifacts and include verdict metadata in `SessionCommandResult`.

#### Grace period configuration

Add `verdict_grace_seconds: float = 30.0` to `CommandAdapterConfig` in `config.py`, with the same `@field_validator` pattern used for `timeout_seconds` and `quiet_timeout_seconds`. The default of 30 seconds matches Conflux's `ACCEPTANCE_VERDICT_GRACE_DEFAULT_SECS`.

#### SessionCommandResult extension

Add an optional `verdict_metadata` field to `SessionCommandResult` in `run_controller.py`:

```python
@dataclass(frozen=True)
class SessionCommandResult:
    # ... existing fields ...
    verdict_metadata: dict[str, object] | None = None
```

This field carries the parsed continuation verdict so the run controller can distinguish verdict-finalized steps from normal completions without re-reading the file.

#### New failure reasons

Add these to `_agent_status_from_failure_reason` in `run_controller.py`:

- `step_verdict_error` → agent status `"verdict_error"`
- `invalid_step_verdict` → agent status `"verdict_invalid"`
- `missing_step_verdict` → agent status `"verdict_missing"`
- `no_progress` → agent status `"no_progress"`

This avoids waiting for the full quiet timeout after a machine-readable handoff is already available.

### Progress detection

Before the command starts, the run controller already calls `self._ready_prompt(self.store, self.root)` to get the prompt (line 339 in `run_controller.py`). The targeted actionable IDs can be extracted from the prompt text or passed alongside it.

The recommended approach: extend `_build_file_scoped_ready_prompt` to return both the prompt text and the set of targeted finding IDs and cell IDs. The run controller can then capture these as pre-turn state.

After a `continue` or `finish` verdict, call `self.store.list_cells(session_id)` and `self.store.list_findings(session_id)` to refresh states. Compare against the captured pre-turn state.

If none changed, return a structured failure:

```json
{
  "reason": "no_progress",
  "error": "step verdict reported continue but no targeted state changed",
  "task_key": "...",
  "target_ids": ["RGF-0904", "RGF-0905"]
}
```

This prevents infinite loops where the same continuation file is repeatedly written without durable ledger progress.

### Error handling

- `error` verdict: fail the step with `reason: step_verdict_error`. The `SessionCommandResult.failure` dict should include the verdict file path and error message from the JSON.
- malformed JSON after child exit: fail with `reason: invalid_step_verdict`. This applies only after the child has exited and the file exists but fails `json.loads()` or schema validation. Partial writes during child execution are not malformed verdicts.
- missing JSON after child exit for a continuation-required prompt: fail with `reason: missing_step_verdict`. This is distinct from `quiet_timeout` — the child exited normally but did not write the expected verdict file.
- non-zero command exit before verdict: preserve existing `command_failed` semantics from `_run_session_command_step` (line 2027).
- non-zero command exit after a valid verdict and runtime-initiated grace termination: let the verdict drive the result, matching Conflux's verdict-finalized handling in `execute_acceptance_in_workspace`. The `returncode_after_kill` from grace termination should not override the verdict outcome.

### Compatibility

This change applies to `run` file-scoped actionable finding turns. It does not change:

- `review-gauntlet review` OCR verdict JSON.
- `verify-fixes` command adapter verdict parsing.
- session ledger authority.
- finalization requirements.
- review-cell coverage semantics.

### Artifact persistence

`_persist_session_command_artifacts` in `cli.py` (line 2047) currently persists stdout, stderr, and activity JSONL under `.review-gauntlet/runs/<uuid>/`. When a verdict file was detected, the function should also:

1. Copy the verdict JSON file to `<run_dir>/verdict.json` for diagnostic access.
2. Include the verdict file path and parsed verdict in the activity JSONL as a `verdict_detected` event entry.

The continuation file itself under `.review-gauntlet/turns/` remains the handoff artifact for the next prompt; the copy under `runs/` is for diagnosis only.

## Open design choices for implementation

- Whether continuation verdict monitoring should initially cover only actionable-finding prompts, or all file-scoped `run` prompts including stale review-cell prompts. **Recommendation**: start with all file-scoped prompts, since the monitoring is the same regardless of prompt reason.
- Whether invalid previous continuation JSON should be shown in the prompt as a warning or only recorded in run artifacts. **Recommendation**: show a one-line warning in the prompt context so the agent knows its previous output was invalid, but do not include the raw malformed content.
