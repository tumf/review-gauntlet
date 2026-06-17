---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli.py
---

# Add session cancel command

**Change Type**: implementation

## Problem / Context

`review-gauntlet init` creates an active review session by writing `.review-gauntlet/active-session.json` and ledger rows, but the CLI does not expose an explicit way to abandon that initialized session. Developers who start the wrong target currently have to know and manually delete `.review-gauntlet/active-session.json`, which is an internal implementation detail and is easy to confuse with `finalize`.

`finalize` is not a safe substitute for cancellation because it writes checkpoint artifacts and requires coverage/finding closure. Cancellation should explicitly abandon the active-session pointer without claiming review completion, creating a checkpoint, or hiding incomplete review evidence in the ledger.

## Proposed Solution

Add a `review-gauntlet cancel` session command that cancels the current active review session by removing the active-session marker and marking the session as cancelled in durable session metadata/state.

The command should:

- require an existing active session and fail actionably when none exists;
- update the session ledger state to `cancelled` before clearing the active marker;
- avoid writing checkpoint files or review-run evidence;
- emit structured JSON/text output consistent with existing session commands;
- make subsequent `status`, `review`, and `ready` behave as no-active-session until a new `init` is run;
- document the command as the supported way to undo an accidental `init`.

## Acceptance Criteria

- Developers can run `review-gauntlet cancel` after `init` and the CLI reports the cancelled session ID.
- `.review-gauntlet/active-session.json` is removed after successful cancellation.
- The ledger records the cancelled session state instead of silently losing all evidence of the abandoned session.
- No checkpoint files, review run rows, finding decisions, or source-file changes are created by cancellation.
- Running session-scoped commands after cancellation fails with the existing actionable no-active-session guidance until a new `init` is run.
- Documentation describes `cancel` separately from `finalize` and warns that cancellation does not produce a review checkpoint.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/cli.py` exposes and dispatches a `cancel` subcommand.
- `src/review_gauntlet/session_store.py` or an equivalent session-layer helper implements durable session cancellation with row-count validation.
- Tests prove cancellation removes the active marker, persists `sessions.state = 'cancelled'`, creates no review runs/checkpoints, and makes follow-up active-session commands fail until re-init.
- README documentation includes a concise cancellation example near the review lifecycle documentation.
- `make check` passes.

## Out of Scope

- Deleting historical ledger rows for cancelled sessions.
- Cancelling or killing already-running external adapter subprocesses.
- Creating partial checkpoints for cancelled sessions.
- Adding multi-session selection or restoring cancelled sessions.
