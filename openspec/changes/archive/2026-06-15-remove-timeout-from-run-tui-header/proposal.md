---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
---

# Remove timeout from run TUI header

**Change Type**: implementation

## Problem / Context

The `review-gauntlet run` TUI header currently repeats timeout information that is already available in the Agent summary panel. The header is intended to be a concise at-a-glance status line, while timeout remaining is detailed agent execution metadata.

The current behavior makes the header noisier than necessary:

- Header shows liveness, such as `quiet 7s`.
- Header also shows timeout remaining, such as `timeout 53s`.
- Agent summary separately shows status/liveness, output recency, timeout remaining, and artifact path.

Users want the header to keep the live/quiet signal but omit timeout details, leaving timeout in the Agent panel only.

## Proposed Solution

Update the run TUI presentation so the header second line includes only:

- shortened session id
- agent or command display name
- concise liveness label, including `quiet <duration>` when applicable

Timeout remaining SHALL no longer appear in the header. Timeout remaining SHALL continue to appear in the Agent summary panel when known.

## Acceptance Criteria

- The run TUI header does not render `timeout <duration>` or `timeout in <duration>` when timeout remaining is known.
- The run TUI header still renders quiet/liveness information such as `quiet 7s` for a quiet running agent.
- The Agent summary panel still renders timeout remaining when known.
- The Agent summary panel still renders status/liveness, output recency, and artifact path when available.
- Task selection, command execution, timeout enforcement, run lifecycle state, JSON output, non-TUI behavior, and session finalization semantics remain unchanged.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/run_tui.py` renders `header_text(...)` without using `view.agent_summary.timeout` or equivalent timeout text.
- `tests/test_run_tui.py` includes regression coverage proving a quiet agent with known timeout keeps `quiet` in the header, removes timeout from the header, and keeps timeout in the Agent summary.
- The `review-sessions` OpenSpec delta updates the canonical header requirement so timeout is no longer required in the header and is explicitly retained in the Agent summary.
- `uv run pytest tests/test_run_tui.py` passes.
- `make check` passes, or any failure is unrelated and documented with evidence.

## Out of Scope

- Changing how command adapter timeout is configured or enforced.
- Removing timeout from the Agent summary panel.
- Removing quiet/liveness labels from the header.
- Redesigning the Agent summary wording, including the existing `timeout timeout in ...` phrasing.
- Changing quiet threshold, heartbeat behavior, Activity timeline behavior, or command execution semantics.
