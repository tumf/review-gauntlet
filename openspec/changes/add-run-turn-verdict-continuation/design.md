# Design: Run turn verdict continuation

## Background

`review-gauntlet run` currently treats each external-agent subprocess as the unit of progress. A prompt asks the agent to inspect, fix, mark, and stop when the target file has no actionable work. This is too optimistic for multi-finding triage turns: an agent may complete useful work, emit tool calls, or know that it should continue later, while the process remains open and the run waits for normal process exit or timeout.

Conflux has two relevant patterns:

- JSON-primary verdict contracts (`src/acceptance.rs`) make the machine-readable outcome explicit.
- Verdict grace termination (`src/parallel/executor.rs`) stops waiting for lingering child processes after a canonical verdict is observed.
- Previous-attempt context injection (`src/agent/prompt.rs`) lets later turns avoid repeating earlier investigation.

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

The runtime must ensure the resolved path stays under `.review-gauntlet/turns/<session_id>/` before including it in prompts or reading it.

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

For file-scoped actionable finding prompts, keep grouped findings. Do not split them by finding ID.

Add a section:

```text
## Turn verdict / continuation file

Read previous continuation context from this file if it exists:
<path>

Before ending this turn, write valid JSON to the same path using this schema:
...
```

If a valid previous file exists, inject a compact context block before the workflow instructions:

```text
## Previous turn context

verdict: continue
summary: ...
completed_finding_ids: ...
remaining_finding_ids: ...
next_turn_instructions: ...
```

Invalid previous JSON should not crash readiness. It should be surfaced in prompt context as ignored invalid continuation state, and the runtime should overwrite it after the next valid turn.

### Subprocess monitoring

`_run_session_command_step` should monitor the continuation JSON path while the child runs.

Suggested behavior:

1. Start child and stdout/stderr reader threads as today.
2. If the prompt declares a continuation file, poll that file at a bounded interval while waiting for the child.
3. When the file exists and validates with `verdict` in `continue|finish|error`, mark the step as verdict-detected.
4. Start a short grace period.
5. If the child exits before the grace deadline, process normally.
6. If the grace deadline expires while the child is still running, terminate then kill if necessary.
7. Persist stdout/stderr/activity artifacts and include verdict metadata in the command result failure/success payload.

This avoids waiting for the full quiet timeout after a machine-readable handoff is already available.

### Progress detection

Before the command starts, capture the targeted actionable IDs and states from the prompt/task metadata. After a `continue` or `finish` verdict, refresh those states from the ledger.

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

- `error` verdict: fail the step with `reason: step_verdict_error`.
- malformed JSON after child exit: fail with `reason: invalid_step_verdict`.
- missing JSON after child exit for a continuation-required prompt: fail with `reason: missing_step_verdict`.
- non-zero command exit before verdict: preserve existing `command_failed` semantics.
- non-zero command exit after a valid verdict and runtime-initiated termination: let the verdict drive the result, matching Conflux's verdict-finalized handling.

### Compatibility

This change applies to `run` file-scoped actionable finding turns. It does not change:

- `review-gauntlet review` OCR verdict JSON.
- `verify-fixes` command adapter verdict parsing.
- session ledger authority.
- finalization requirements.
- review-cell coverage semantics.

## Open design choices for implementation

- Whether continuation verdict monitoring should initially cover only actionable-finding prompts, or all file-scoped `run` prompts including stale review-cell prompts.
- Whether the verdict grace period should be fixed internally first or exposed in adapter configuration.
- Whether invalid previous continuation JSON should be shown in the prompt as a warning or only recorded in run artifacts.
