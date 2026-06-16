---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli_session_review.py
  - openspec/specs/review-sessions/spec.md
---

# Clarify init creates an active session without starting a review run

**Change Type**: implementation

## Problem / Context

A developer running `uv run review-gauntlet init` sees output like `session_id`, `cell_count`, and `run_count: 0`. The current implementation does create durable session state and the active-session marker, but it does not create a review run. Because the output does not explicitly distinguish an active review session from a started review run, the command can look like it failed to "open" anything.

The existing architecture intentionally separates session creation from review execution: `init` builds the target-scoped cells and persists the active session, while `review` creates run rows when adapter work starts. That separation should remain intact, but the CLI contract and tests should make the lifecycle unambiguous.

## Proposed Solution

Define `review-gauntlet init` as a session-initialization command that creates an active session and review cells, but does not create a review run. Enhance the machine-readable and human-readable output so callers can see that the session is active, that no run has started yet, and which command starts review execution.

## Acceptance Criteria

- `review-gauntlet init` creates or replaces the active review session marker and persists the session/cell ledger as it does today.
- `review-gauntlet init` does not insert a row into `runs`; `run_count` remains `0` immediately after initialization.
- `review-gauntlet init --format json` includes explicit lifecycle fields that distinguish active session state from review-run state.
- Human/default output makes the same distinction without implying that a run has started.
- `review-gauntlet review` remains the command that creates the first run and increments run count.
- Existing target-selection semantics for checkpoint, `--all`, `--worktree`, `--from/--to`, `--commit`, and `--git-worktree` remain unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` emits explicit init lifecycle metadata such as `session_state`, `run_state`, and/or `next_command` from `_cmd_init`.
- `src/review_gauntlet/session_store.py` continues to create the active session marker during init and continues not to create runs from `create_session`.
- Tests prove that init creates `.review-gauntlet/active-session.json`, leaves `runs` empty, reports the lifecycle metadata in JSON, and that review still creates the first run.
- `make check` passes after implementation.

## Out of Scope

- Starting adapter execution from `init`.
- Creating empty or placeholder run records from `init`.
- Changing review target selection behavior.
- Changing finalized-session cleanup behavior.
