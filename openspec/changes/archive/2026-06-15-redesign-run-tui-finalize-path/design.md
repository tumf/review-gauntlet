# Design: Finalize-path run TUI

## Goals

- Make `review-gauntlet run` visually communicate progress toward checkpoint finalization, not only review coverage.
- Preserve existing run orchestration semantics while improving the interactive presentation layer.
- Keep final terminal states visible until explicit user dismissal.
- Show bounded agent stdout/stderr tail and liveness state during long-running agent steps.
- Persist complete agent output artifacts for audit/debug while keeping TUI output safe and concise.

## Current Architecture

`cli._cmd_run()` creates a `RunController` and either runs it directly or wraps it in a Textual app from `run_tui.create_run_app()`.

`RunController.snapshot()` currently gathers:

- active session ID
- effective coverage
- finding counts
- ready prompt
- agent loop step
- agent status
- command display metadata

`cli._status()` already computes additional data needed for gate rendering:

- `session_state`
- `can_finalize`
- `finalize_blockers`
- `next_required_action`
- `run_count`

The TUI should use the controller snapshot as its data boundary and should not perform its own raw database/status queries from widgets.

Session-level command execution currently uses `subprocess.run(..., capture_output=True)`, which only exposes stdout/stderr after process exit. To show live agent activity, the session-level command runner needs an incremental output path analogous to the review adapter's `Popen`-based execution, while preserving existing result payload semantics.

## Proposed View Model

Add a TUI-specific finalize gate model in `run_tui.py`:

```python
@dataclass(frozen=True)
class FinalizeGate:
    index: int
    key: str
    title: str
    state: str
    detail: str
```

Gate order is fixed:

1. `review_coverage`
2. `triage_findings`
3. `fix_confirmed_findings`
4. `verify_fixes`
5. `resolve_blockers`
6. `finalize_checkpoint`

`RunViewState` should include:

- `gates: tuple[FinalizeGate, ...]`
- `active_gate: FinalizeGate`
- `gate_label: str`
- `agent_step_label: str`
- `session_metrics` data or enough fields to render it
- `agent_liveness` data such as lifecycle state, last-output age, quiet duration, timeout remaining, and artifact path
- `activity_rows` combining Review Gauntlet events, agent lifecycle events, and sanitized stdout/stderr tail entries
- stored terminal result indicator when the run has completed

## Gate Classification

Gate classification should be deterministic and derived from snapshot fields.

### Coverage

- Count `pending` and `stale` as incomplete.
- Exclude `superseded` from total denominator.
- Treat total zero as `skipped` or complete-equivalent so later gates can proceed.
- Use active state when current prompt is review-related and pending/stale work exists.

### Findings

- Triage gate uses `untriaged` and `reopened`.
- Fix gate uses `confirmed`.
- Verify gate uses `fixed_pending_verification`.
- Zero-count gates remain visible and may render as `skipped` or `done` depending on surrounding state, but they must not disappear.

### Blockers

`finalize_blockers` includes coverage/finding blockers and finalize-only blockers. The TUI should classify these strings so the Resolve blockers gate only displays finalize-only blockers.

Coverage/finding blockers currently include:

- `review cells are still pending`
- `review cells are stale after target changes`
- `findings remain untriaged`
- `findings remain confirmed`
- `findings remain reopened`
- `fixed findings require verification`

Everything else is treated as finalize-only unless future code exposes structured blocker categories.

### Finalization

The Finalize checkpoint gate is active when earlier gates are complete and `can_finalize` is true while the session remains active. It is done when the run result indicates completion or the snapshot/session state indicates finalization.

## Agent Output and Liveness Design

The command runner should surface agent output through an append-only per-step activity stream while also writing complete raw stdout/stderr artifacts. The TUI uses the stream tail, not the full logs.

Suggested artifact files per session-level agent step:

- `.review-gauntlet/runs/<run-id>/agent-stdout.log`
- `.review-gauntlet/runs/<run-id>/agent-stderr.log`
- `.review-gauntlet/runs/<run-id>/activity.jsonl`

If the implementation does not yet have a durable run ID for session-level `run` steps, it must introduce an equivalent deterministic per-step artifact directory under `.review-gauntlet/runs/` or document and test the exact existing run ID it uses.

Activity entries should represent:

- Review Gauntlet events
- agent lifecycle events
- stdout lines
- stderr lines
- heartbeat / quiet status
- timeout approaching when timeout is known
- artifact path hints on failure or completion

The TUI-visible output should be sanitized and bounded:

- latest 100 lines by default
- 160 display characters per line by default
- strip ANSI/control characters
- collapse excessive blank lines
- handle carriage-return progress as updates instead of flooding
- redact common secret-like assignments such as `*_TOKEN=`, `*_SECRET=`, and `*_KEY=`

Artifacts should preserve raw output in the initial implementation; redacted artifact mode is future work.

Agent lifecycle display states:

- `starting`
- `running`
- `quiet`
- `finishing`
- `completed`
- `failed`
- `timed_out`
- `cancelled`

`stderr` output is progress/warning information for many tools and must not by itself imply failure. Failure requires command non-zero, timeout, startup failure, cancellation, or equivalent runner failure metadata.

## Lifecycle Design

The worker thread currently calls `exit(result)` immediately after `controller.run()`. Replace this with stored completion state:

- `self._run_result: dict[str, object] | None`
- `self._run_finished: bool`
- optional `self._final_snapshot: RunSnapshot | None`

When `controller.run()` returns:

1. Store result.
2. Capture or refresh the final snapshot when possible.
3. Mark the app as finished.
4. Refresh visible widgets.
5. Do not exit.

Control behavior:

- active `q`: request stop after current step
- finished `q`: exit with stored result
- active `Ctrl-C`: interrupt as today
- finished `Ctrl-C`: exit with stored result

This preserves the CLI result contract while making interactive dismissal explicit.

## Layout Design

Suggested Textual regions:

- `#session_header`
- `#finalize_path`
- `#detail_row`
  - `#task_panel`
  - `#session_metrics`
- `#activity_timeline`
- `#controls`

Coverage and findings remain visible in metrics but are not the primary panel.

## Compatibility

This change must not alter:

- ready task selection
- command adapter invocation
- JSON result payloads
- non-TUI text output
- TUI eligibility rules
- missing optional dependency fallback
- durable session, coverage, finding, or checkpoint state transitions
- raw run result stdout/stderr availability for non-TUI callers
- stderr treatment as non-failure unless command failure metadata says otherwise

## Verification Strategy

Most behavior should be covered by pure text/view-model unit tests because Textual UI tests can be fragile and optional-dependency-dependent. A minimal headless or equivalent lifecycle test should cover the key regression: controller completion no longer immediately returns from the app before explicit quit.
