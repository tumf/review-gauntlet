---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
  - openspec/specs/review-sessions/spec.md
---

# Change `ready` no-task exit code

**Change Type**: implementation

## Problem / Context

`review-gauntlet ready` is intended for external orchestration: it tells a caller which review-gauntlet task should be executed next. When no continuation task exists, the command currently emits `no ready task` for text output or `{"prompt": null}` for JSON output, but still exits successfully. This makes shell loops and agents treat the no-task state as another successful actionable step unless they parse stdout.

The project constitution says orchestration is external and review-gauntlet provides state and verdicts. The CLI should therefore expose the no-task verdict through its process status as well as stdout.

## Proposed Solution

Keep the existing `ready` output schema and text wording, but make the no-continuation state exit non-zero:

- If `_ready_prompt(...)` returns a prompt, emit the existing output and exit `0`.
- If `_ready_prompt(...)` returns `None`, emit the existing no-task output and exit `1`.
- Preserve JSON output as `{"prompt": null}` and text output as `no ready task`.
- Do not change ready priority ordering, prompt wording, or session ledger/checkpoint state.

## Acceptance Criteria

- Running `ready` when a continuation task exists exits `0` and emits the same prompt output as before.
- Running `ready --format text` when only blockers/no continuation remain emits `no ready task` and exits `1`.
- Running `ready --format json` when only blockers/no continuation remain emits parseable JSON with `prompt: null` and exits `1`.
- `ready` remains read-only for the session ledger and checkpoint state.
- Existing `status`, `findings`, `finalize`, and review-session state behavior remain unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` branches on the computed ready prompt and raises `SystemExit(1)` only for the no-ready-task state after emitting output.
- `tests/test_cli_ready.py` verifies both success and no-task exit codes for `ready` without relying only on stdout parsing.
- Focused ready tests pass with `uv run pytest tests/test_cli_ready.py`.
- Repository checks pass with `make check`.

## Out of Scope

- Renaming `prompt` in JSON output.
- Changing the `no ready task` text.
- Adding a new CLI flag to customize exit code behavior.
- Changing ready-task priority order or finalization blocker logic.
