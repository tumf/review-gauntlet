---
change_type: implementation
priority: medium
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - openspec/changes/clarify-run-finalize-timeout
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/config.py
  - tests/test_run_tui.py
  - tests/test_run_controller.py
---

# Normalize run agent failure display

**Change Type**: implementation

## Problem / Context

The `review-gauntlet run` TUI and structured lifecycle presentation can make different external-agent failure modes look like the same timeout-like state. In the observed run, the agent tail clearly showed a tool-level `File not found` while the dashboard summarized the step as `READY timed_out` and the Agent panel showed `timeout timeout not set`. This makes diagnosis harder and conflicts with the constitution's requirement that failed and incomplete states stay visible rather than being hidden or misrepresented.

There is already an active change, `clarify-run-finalize-timeout`, focused on the special case where the agent times out after the session is otherwise ready to finalize. This proposal depends on that work and generalizes the display contract across agent failures: timeout, command failure, startup error, template error, interrupted, and max-step exhaustion should remain distinct from each other in both structured snapshots and TUI text.

## Proposed Solution

Normalize the run lifecycle/failure display pipeline so that the failure reason emitted by command execution remains visible through:

- run result JSON,
- run events,
- `RunSnapshot.agent_status`,
- `AgentLifecycle.status`,
- TUI header/status text,
- Agent panel details,
- Activity panel summaries.

The display should use concise, non-duplicative labels and should not invent timeout terminology for non-timeout failures. Stderr/stdout tail remains supporting evidence, not the sole source of the classified status.

Expected status families:

- `timed_out` only for actual command adapter timeout failures.
- `command_failed` or a similarly explicit failure label for non-zero adapter exits.
- `startup_error` for missing command/executable startup failures.
- `template_error` for invalid command template or cwd expansion.
- `interrupted` for user/controller interruption.
- `max_steps_exhausted` for orchestration step exhaustion.

## Acceptance Criteria

- A command adapter timeout is displayed as a timeout and includes the effective timeout duration when available.
- A command adapter non-zero exit is displayed as command failure, not timeout.
- A missing command startup failure is displayed as startup error, not timeout.
- A template/cwd validation failure is displayed as template or configuration error, not timeout.
- An interrupted run is displayed as interrupted and remains distinct from failed or timed-out states.
- Max-steps exhaustion is displayed as orchestration exhaustion and not as an agent timeout.
- TUI Agent and Activity panels use concise wording without duplicated labels such as `timeout timeout ...`.
- The existing `clarify-run-finalize-timeout` ready-to-finalize timeout behavior is preserved after this generalization.
- JSON run output remains parseable and continues to expose machine-readable reason/error fields for automation.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/run_controller.py` preserves machine-readable failure reason information in snapshots/events without collapsing non-timeout failures into generic `failed` when a more specific status is available.
- `src/review_gauntlet/run_tui.py` maps timeout, command failure, startup error, template error, interrupted, and max-step exhaustion to distinct concise display text.
- The Agent panel no longer renders duplicated timeout wording or `timeout not set` for configured command adapter failures.
- The Activity panel summarizes the actual failure reason for agent failures instead of a misleading generic or timeout label.
- `tests/test_run_controller.py` covers status derivation for timeout, command failure, startup error, template error, interrupted, and max-steps exhaustion.
- `tests/test_run_tui.py` covers display text for the same failure families and regression coverage for the ready-to-finalize timeout case from `clarify-run-finalize-timeout`.
- Focused tests `uv run pytest tests/test_run_tui.py tests/test_run_controller.py` pass.
- `make check` passes, or any failure is documented with evidence that it is unrelated.

## Out of Scope

- Changing command adapter execution semantics, retry behavior, or timeout duration defaults.
- Parsing arbitrary agent stderr to infer business logic beyond the command execution failure reason already produced by Review Gauntlet.
- Automatically recovering from failures, auto-finalizing, or retrying failed agent steps.
- Changing Git-worktree execution cwd; that is covered by `run-agents-in-session-worktree`.
- Replacing the existing TUI layout or changing panel titles unrelated to failure reason clarity.
