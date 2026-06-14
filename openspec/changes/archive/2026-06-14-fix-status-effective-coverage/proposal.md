---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - tests/test_cli_ready.py
  - openspec/specs/review-sessions/spec.md
---

# Fix Status Effective Coverage

**Change Type**: implementation

## Premise / Context

- `review-gauntlet status` currently reads persisted `review_cells` counts from `ledger.sqlite` and returns them as `coverage`.
- `review` and `verify-fixes` reconcile current target cells before operating, but `status` does not reconcile or compute a current-target effective coverage view before reporting.
- Existing status logic already computes current target freshness for `next_required_action`, which can make `coverage` look older than `next_required_action` and `finalize_blockers`.
- The project constitution requires stale and unknown coverage to remain visible, and old review results must not be treated as current truth after target/code changes.

## Problem / Context

`review-gauntlet status` can report a stale persisted coverage snapshot even when the current target has changed. For example, a previously reviewed cell whose content digest no longer matches the current file may still appear under `coverage.reviewed`, while the same status result indicates target digest drift or review-required next action. This mixed view makes `status` less reliable for agents and humans deciding what to do next.

## Proposed Solution

Make `status` report an effective coverage view for the current target without mutating durable ledger state. The command should derive current review cells from the active session target and current file digests, compare them with persisted cells, and return `coverage` based on effective current state:

- current cells missing from the ledger count as `pending`
- current cells with matching persisted `reviewed` state and matching digest count as `reviewed`
- current cells with digest mismatch or non-reviewed persisted state count according to the actionable effective state, including `stale` when prior coverage is invalidated by content changes
- persisted cells no longer present in the current target remain visible as superseded coverage, without hiding current-target gaps

Keep `status` read-only: it must not insert cells, update cell states, write checkpoints, write runs, or modify findings.

## Acceptance Criteria

- `review-gauntlet status --format json` returns `coverage` that reflects the effective state of the active session's current target, not only the persisted ledger snapshot.
- If a current target cell has changed since being reviewed, `coverage` reports it as stale and `next_required_action` remains `run_review` unless live finding work has higher priority under existing rules.
- If a current target cell is missing from persisted `review_cells`, `coverage` reports pending review work without mutating the ledger.
- If the only mismatch is whole-target digest drift and every current target cell is present, reviewed, and digest-matching, existing behavior remains: `status` does not force review work solely due to whole-target digest drift.
- `status` continues to expose finding state counts, finalize blockers, run count, and session metadata consistently with the effective coverage view.
- `status` remains read-only and does not mutate review cells, findings, runs, checkpoints, active-session metadata, or git state.

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` computes status coverage through a current-target effective coverage helper shared by `status` and status-like decision paths where appropriate.
- Regression tests cover reviewed-to-stale effective coverage, missing-current-cell effective pending coverage, and the whole-target-digest-drift-only case.
- Existing status priority tests continue to pass with updated expectations only where the persisted/effective distinction was previously masking current target state.
- `uv run pytest tests/test_cli_ready.py` or a narrower focused test command covering the changed status behavior passes.
- `make check` passes before the change is considered complete.

## Out of Scope

- Automatically mutating ledger state from `status`.
- Changing `review` to process more than one step per invocation.
- Changing finding triage states or mark semantics.
- Changing checkpoint finalization format except where existing status fields are consumed unchanged.
