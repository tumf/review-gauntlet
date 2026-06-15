---
change_type: implementation
priority: high
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - openspec/changes/remove-timeout-from-run-tui-header
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/config.py
  - tests/test_run_tui.py
  - tests/test_run_controller.py
---

# Clarify run finalize timeout handling

**Change Type**: implementation

## Problem / Context

A `review-gauntlet run` session can reach a state where all review cells are reviewed, no findings remain open, final checks are ready, and `review-gauntlet status` reports `can_finalize=true`, but the command adapter step still times out before the agent performs the final `review-gauntlet finalize` action.

In the observed session:

- `opencode run` timed out after the command adapter timeout.
- All 13 review cells were already `reviewed`.
- `review-gauntlet status . --format json` reported `can_finalize=true`, `finalize_blockers=[]`, and `next_required_action=finalize`.
- The TUI showed `Finalize checkpoint` as `failed` with detail `ready to finalize`, which made a recoverable manual-finalize state look like a failed review result.
- The Agent summary showed `timeout timeout not set`, even though the command adapter enforces the default timeout from `CommandAdapterConfig.timeout_seconds`.

This conflicts with the constitution's principles that unknown or incomplete states must stay visible, but should not be misrepresented: a timed-out external agent is incomplete orchestration, not failed coverage or failed finalization eligibility.

## Proposed Solution

Update `review-gauntlet run` TUI/controller presentation so an adapter timeout at the finalize checkpoint distinguishes between:

1. **Ready but not finalized**: the external agent timed out, but the session remains eligible to finalize with no blockers.
2. **Blocked finalization**: finalize blockers still exist.
3. **Failed agent step before readiness**: the timeout occurred before the checklist reached finalize readiness.

When the first case occurs, the TUI SHALL surface an explicit manual-finalize recovery cue instead of presenting the finalize checkpoint as a generic failed gate. The CLI/controller SHALL preserve the timeout lifecycle status for auditability and structured result data, but the checklist detail must make clear that the next action is still `review-gauntlet finalize`.

Also ensure timeout presentation uses the configured/effective adapter timeout. If the adapter timeout is the default value, the Agent summary must not report `timeout not set` or duplicate wording such as `timeout timeout not set`.

## Acceptance Criteria

- If an external command adapter times out while `status.can_finalize=true` and `status.finalize_blockers=[]`, the run TUI indicates that the agent timed out but the session is ready for manual finalization.
- In the same ready-timeout state, the checklist does not imply review coverage, finding triage, fix verification, or final checks failed.
- The current checklist title remains `Finalize checkpoint`, and its detail includes a clear recovery action such as `run review-gauntlet finalize` or equivalent concise wording.
- If the adapter times out before `can_finalize=true`, the TUI continues to show an appropriate failed/running checklist state for the first incomplete gate.
- If finalize blockers exist, the TUI continues to show blocked final checks rather than a manual-finalize-ready cue.
- Agent summary timeout wording uses the effective configured timeout, including the default timeout from `CommandAdapterConfig`, and never renders `timeout not set` for configured command adapters.
- The change preserves command execution semantics, timeout enforcement, coverage calculation, finding state transitions, JSON result parseability, non-TUI behavior, and standalone `review-gauntlet finalize` behavior.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/run_controller.py` or its snapshot construction path carries enough effective adapter timeout/finalize-ready information for the TUI to render accurate timeout and recovery state after an adapter timeout.
- `src/review_gauntlet/run_tui.py` distinguishes finalize-ready adapter timeout from true checklist failure and renders a manual-finalize recovery cue.
- `src/review_gauntlet/run_tui.py` Agent summary timeout wording no longer duplicates the word `timeout` and no longer displays `timeout not set` when a command adapter default timeout is active.
- `tests/test_run_tui.py` covers finalize-ready adapter timeout, pre-ready adapter timeout, blocked-finalize timeout, and default timeout display behavior.
- `tests/test_run_controller.py` covers propagation or synthesis of effective command adapter timeout into run snapshots after command steps.
- Focused tests `uv run pytest tests/test_run_tui.py tests/test_run_controller.py` pass.
- `make check` passes, or any failure is documented with evidence that it is unrelated.

## Out of Scope

- Changing the actual timeout duration defaults or validation rules.
- Automatically running `review-gauntlet finalize` after an adapter timeout.
- Changing standalone `review-gauntlet finalize` semantics.
- Changing review coverage, finding lifecycle, checkpoint file format, or checkpoint commit behavior.
- Changing non-TUI command adapter execution behavior beyond structured state needed for accurate presentation.
- Reworking panel titles covered by `rename-run-tui-finalize-checklist` or header timeout removal covered by `remove-timeout-from-run-tui-header`.
