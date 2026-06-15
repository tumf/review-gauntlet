---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - tests/test_run_tui.py
  - tests/test_cli.py
  - openspec/specs/review-sessions/spec.md
---

# Redesign run TUI around finalize path

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` is a session-completion orchestrator, not only a coverage review command.
- The active run flow advances ready tasks for pending/stale review coverage, reopened/untriaged finding triage, confirmed finding fixes, fixed-pending verification, finalize blocker resolution, and checkpoint finalization.
- The current Textual TUI exits immediately after `RunController.run()` returns, so terminal users cannot inspect the final dashboard state.
- The current TUI gives Coverage primary visual weight and labels loop iterations as `step`, which obscures the distance to checkpoint finalization.
- Long-running `run` invocations can appear idle because Activity shows Review Gauntlet events but not the underlying agent process stdout/stderr tail or liveness state.
- Existing `_status()` data already exposes coverage, `finding_state_counts`, `finalize_blockers`, `can_finalize`, `session_state`, `run_count`, and `next_required_action`; `RunSnapshot` currently forwards only part of this data.
- Session-level command execution currently captures stdout/stderr only after process completion via `subprocess.run`, so streaming tail, heartbeat, and per-step agent-output artifacts require command-runner/controller changes.
- The existing canonical `review-sessions` spec already defines TUI presentation requirements, so this proposal modifies that requirement rather than adding an unrelated capability.

## Problem / Context

The TUI currently presents `Coverage` as the main dashboard progress and shows `step N` as the primary progress label. This is misleading for `run`, because a session is not complete after coverage alone. After coverage, findings may still require triage, confirmed findings may need fixes, fixed-pending findings may need verification, finalize-only blockers may remain, and the checkpoint still needs finalization.

The TUI also automatically exits after the controller completes. This hides the most important terminal states: finalized, blocked, failed, or stopped-after-current-step. Users need to see the final gate and the next action without rerunning status commands.

During long-running agent steps, users also need proof that the agent process is alive. Review Gauntlet may simply be waiting for the configured command adapter, but the current Activity panel cannot show whether the agent is producing output, quiet-but-alive, approaching timeout, or finished and being reconciled.

## Proposed Solution

Rework the interactive `run` TUI into a finalize-path dashboard and keep it visible after the controller finishes until the user explicitly quits.

The dashboard SHALL render a six-gate `Finalize path` as its primary panel:

1. Review coverage
2. Triage findings
3. Fix confirmed findings
4. Verify fixes
5. Resolve finalize blockers
6. Finalize checkpoint

Each gate SHALL display one of `active`, `done`, `waiting`, `blocked`, `skipped`, or `failed`, along with a concise status detail derived from current session status. The header SHALL prioritize `gate x/6` and the current gate title. Agent loop iteration count SHALL move to `agent step` in secondary panels.

Coverage and finding counts SHALL remain visible but become session metrics rather than the largest/primary progress surface. Activity rows SHALL describe gate transitions, agent lifecycle events, and recent agent stdout/stderr output instead of raw run events or coverage-first labels.

The session-level command runner SHALL persist complete stdout/stderr artifacts and structured activity entries for each agent step. The TUI SHALL display only a sanitized, redacted, bounded tail of that output, while preserving raw logs for audit/debug artifacts. Header and Current operation SHALL show agent liveness using last-output, quiet, timeout, and artifact-path information where available.

When the run worker completes, the TUI SHALL store the result, render the final dashboard state, switch the footer to quit-oriented controls, and return the stored result only when the user quits.

## Acceptance Criteria

- Interactive `review-gauntlet run` TUI does not auto-exit when `RunController.run()` completes.
- After run completion, `q` exits the TUI and returns the stored run result to the CLI path.
- During an active run, `q` continues to request stop-after-current-step instead of immediately quitting.
- `Ctrl-C` interrupts an active run without traceback; after completion it behaves as an explicit quit of the final dashboard.
- The largest dashboard panel is `Finalize path`, not standalone `Coverage`.
- Header displays `gate x/6` and the current finalize gate title.
- Agent loop count is labeled `agent step` and is visually separate from finalize gate progress.
- Coverage appears inside `Session metrics` with percent and reviewed/total cells.
- Finding triage, confirmed-fix, and fixed-verification gates are always visible even when their counts are zero.
- Resolve blockers and Finalize checkpoint gates are always visible.
- Ready prompt full text is not shown as the primary UI text.
- Current operation describes the active finalize gate and uses stable titles/descriptions.
- Activity output emphasizes gate activation, gate completion/blocking/failure, agent step starts/finishes, and agent stdout/stderr tail.
- Review Gauntlet events and agent output rows are visually distinguishable.
- Agent output tail has bounded line count, bounded line length, sanitized control characters, and TUI-only redaction of common secret-looking environment assignments.
- Header or Current operation displays `last output` or `quiet` liveness information while the agent is running.
- Quiet-but-alive agent processes produce non-flooding heartbeat/status information.
- stderr output is distinguishable but does not by itself mark the agent failed.
- Agent command completion displays return code, timeout, cancellation, or failure status as appropriate.
- Complete agent stdout/stderr and structured activity entries are persisted as artifacts.
- Blocked state makes the blocked gate and next action obvious.
- Finalized state renders all six gates complete and shows checkpoint completion.
- JSON output, `--no-tui`, non-TTY text mode, and missing-Textual fallback behavior remain semantically unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` contains a finalize-path view model and rendering functions that replace Coverage as the primary panel.
- `src/review_gauntlet/run_controller.py` exposes enough status snapshot fields for the TUI to classify gates and agent liveness without querying raw session state from widgets.
- Session-level command execution persists full agent stdout/stderr and activity artifacts while surfacing sanitized bounded output tails to the TUI.
- The TUI app stores the completed run result and only calls `exit(result)` after an explicit post-completion quit action.
- Unit tests cover gate classification for coverage, triage, fix, verify, blocker, finalized, failed, and zero-work cases.
- Unit/integration tests cover agent output tailing, stdout/stderr distinction, quiet heartbeat, timeout/lifecycle display, redaction/sanitization, truncation, and artifact persistence.
- TUI text-rendering tests assert the new header, `Finalize path`, `Session metrics`, `agent step`, liveness display, activity tail, and prompt-summarization behavior.
- A headless or equivalent Textual test verifies that controller completion does not immediately return until the quit action is invoked.
- CLI tests continue to verify non-TUI and fallback modes.
- `make check` passes.

## Out of Scope

- Changing `review-gauntlet run` task-selection priority.
- Changing command adapter execution semantics or run result JSON structure.
- Changing durable coverage or finding state definitions.
- Adding a new CLI flag for this behavior.
- Implementing configurable redacted-vs-raw artifact storage; initial artifact storage remains raw while TUI display is redacted.
- Implementing Activity display-mode keybindings if a fixed mixed view is sufficient for the first implementation.
- Implementing rich coverage-delta activity events beyond what can be derived from existing snapshots and events in this change.
