---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py:_status
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Fix TUI findings summary counts

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` TUI currently renders the Session panel findings summary from `snapshot.findings.get("open", 0)`. The run controller populates `RunSnapshot.findings` from `status.finding_state_counts`, and `_status()` returns counts grouped by actual finding states such as `untriaged`, `confirmed`, `reopened`, and `fixed_pending_verification`; it does not derive an `open` key.

As a result, the Session panel can show `Findings  open 0` even when actionable live findings exist. This hides the same incomplete state that finalize blockers, ready prompt ordering, and the project constitution require to remain visible.

## Proposed Solution

Make the TUI derive its displayed open finding count from actionable non-terminal states instead of relying on a persisted `open` key. The derived open count SHALL equal:

`reopened + untriaged + confirmed + fixed_pending_verification`

The Session panel SHALL show the total open count and, when non-zero, a concise action-oriented breakdown:

- `triage = reopened + untriaged`
- `fix = confirmed`
- `verify = fixed_pending_verification`

The detailed findings helper SHALL use the same derived `open` value so compact/dashboard text and panel details agree.

## Acceptance Criteria

- `review-gauntlet run` TUI Session panel no longer displays `open 0` solely because no `open` key exists in `finding_state_counts`.
- The displayed open count equals the sum of actionable live finding states: reopened, untriaged, confirmed, and fixed-pending verification.
- When actionable findings exist, the Session panel includes a concise breakdown for triage, fix, and verify work.
- When no actionable findings exist, the Session panel still reports `open 0` and does not invent work.
- Existing coverage, agent lifecycle, finalize checklist, and ready-prompt behavior remain unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` contains a shared helper or equivalent single calculation for actionable/open finding counts that is used by Session summary rendering and detailed findings rendering.
- `build_session_summary()` no longer directly depends on `snapshot.findings.get("open", 0)` for the visible open count.
- `findings_text()` uses the derived open value while preserving useful per-state counts for actual finding states.
- `tests/test_run_tui.py` includes regression coverage proving a snapshot with no `open` key but actionable states renders the expected non-zero open count and breakdown.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Repository quality gates remain available through `make check` after implementation.

## Out of Scope

- Changing database schema or `_status()` JSON shape.
- Changing finding state transitions, terminal-state semantics, finalization rules, or ready prompt priority.
- Changing checkpoint contents or persisted finding ledgers.
- Adding new CLI flags or changing non-TUI output formats.
