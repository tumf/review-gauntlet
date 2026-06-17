# Design: Add session cancel command

## Overview

The cancellation behavior should be a lifecycle transition for the active session, not a filesystem-only cleanup. The active marker is the current session pointer, while the ledger is the durable evidence store. Cancelling should clear the pointer but preserve a durable record that the abandoned session existed and was intentionally cancelled.

## Lifecycle Semantics

`cancel` introduces a terminal session state distinct from `finalized`:

- `active`: current review session may be reviewed, triaged, verified, or finalized.
- `finalized`: session completed coverage/finding closure and wrote checkpoint evidence.
- `cancelled`: session was intentionally abandoned before completion and wrote no checkpoint.

A cancelled session must not satisfy future `init` checkpoint defaults, finalization evidence, or coverage claims. It remains in the ledger only as historical lifecycle evidence.

## Command Behavior

`review-gauntlet cancel` should:

1. Resolve the active session via `SessionStore.active_session_id()`.
2. Update `sessions.state` for that session to `cancelled` with row-count validation.
3. Remove `.review-gauntlet/active-session.json` after the state transition succeeds.
4. Return output containing at least `session_id` and `session_state: cancelled`.

If no active marker exists, the command should fail consistently with other active-session commands and should not create `.review-gauntlet/` state.

## Failure and Atomicity

The state transition should happen before marker removal. If marker removal fails, the command should fail rather than reporting success. If the marker is already missing between lookup and removal, the command should still avoid pretending an active session remains; tests should pin the intended behavior chosen by implementation.

Cancellation should not write to checkpoint directories, create `runs` rows, mutate finding states, or refresh review cells.

## Verification Strategy

Use CLI-level integration tests because the command is primarily user-facing and depends on the ledger plus marker file. Add lower-level tests only if the cancellation helper contains non-trivial branching.
