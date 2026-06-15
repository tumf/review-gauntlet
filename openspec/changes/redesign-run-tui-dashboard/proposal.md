---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Redesign run TUI as a checklist dashboard

**Change Type**: implementation

## Problem / Context

The current `review-gauntlet run` TUI exposes too much internal session state. The Finalize path reads like a raw state list, repeated `gate x/6` labels make it noisy, coverage and current-operation information are repeated across panels, and internal action names such as `run_review` can appear in user-facing text. This makes an active review session look blocked or stalled even when it is simply reviewing coverage.

The desired UI is a compact dashboard that closely follows this structure:

```text
Review Gauntlet
RUNNING · gate 1/6 · Review coverage
session RGS-207f…106b · agent opencode · quiet 2m53s · timeout 7m06s

Next to finalize
▶ Review coverage          running   0 / 9 reviewed, 9 pending
  Triage findings          next      waits for coverage
  Fix confirmed findings   next      no confirmed findings yet
  Verify fixes             next      no fixed-pending findings yet
  Final checks             later     checked after review/findings
  Finalize checkpoint      later     waiting

Agent | Session
Activity
```

This change preserves the review-gauntlet constitution: unknown and incomplete work remains visible, but the TUI presents it in human-facing terms instead of leaking implementation state.

## Proposed Solution

Redesign the TUI view model and rendering in `src/review_gauntlet/run_tui.py` so the dashboard is organized as:

1. `Review Gauntlet` header panel
2. `Next to finalize` checklist panel
3. side-by-side `Agent` and `Session` panels when width allows
4. `Activity` timeline panel
5. compact controls footer

The TUI SHALL map raw controller/session status into a human-facing dashboard model before rendering. It SHALL classify finalize blockers into coverage blockers, finding blockers, and finalize-only blockers. Coverage and finding blockers SHALL be represented by their dedicated checklist rows; `Final checks` SHALL only show blocked when finalize-only blockers remain after prior gates are satisfied.

The implementation SHALL keep JSON output, non-TUI output, controller task selection, command execution, finalization semantics, and persisted session status unchanged.

## Acceptance Criteria

- The TUI renders panels titled `Review Gauntlet`, `Next to finalize`, `Agent`, `Session`, and `Activity` in that order.
- The old standalone `Session metrics`, `Current operation`, and `Finalize path` panel labels are not rendered in the dashboard.
- The header uses a two-line summary with terminal status, `gate x/6`, current gate title, shortened session id, agent name, liveness, and timeout.
- `Next to finalize` renders six checklist rows: Review coverage, Triage findings, Fix confirmed findings, Verify fixes, Final checks, and Finalize checkpoint.
- Checklist rows do not render `gate x/6`; gate numbering appears only in the header.
- Checklist states are limited to `running`, `done`, `next`, `later`, `blocked`, and `failed`.
- While review coverage is incomplete, coverage-related finalize blockers do not make `Final checks` appear blocked.
- `Final checks` displays `checked after review/findings` or equivalent while earlier gates are incomplete.
- Internal action names such as `run_review` and `resolve_finalize_blockers` are not displayed in TUI text.
- `Agent` shows command, status/liveness, output recency, timeout, and artifact information when available.
- `Session` compresses coverage, findings, current gate, and agent step into a small summary.
- `Activity` mixes Review Gauntlet events with agent stdout/stderr tail rows using `event`, `stdout`, and `stderr` labels.
- A quiet running agent produces a non-flooding heartbeat row such as `event agent alive no output for 2m00s`.
- Existing sanitization, truncation, and secret redaction for displayed agent output remain in effect.
- Non-TUI, JSON, controller, and finalization behavior remain unchanged.

## Explicit Completion Conditions

This proposal is complete when repository evidence shows:

- `src/review_gauntlet/run_tui.py` renders the dashboard through a human-facing view model rather than directly dumping raw status fields.
- `tests/test_run_tui.py` covers the mock-aligned panel names, checklist rows, blocker classification, hidden internal action names, agent/session summaries, and activity output/heartbeat rows.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Project checks pass with `make check`, or any failure is documented as unrelated to this change with evidence.

## Out of Scope

- Changing review session durable state, JSON status payloads, or `finalize_blockers` semantics.
- Changing ready prompt priority or run-controller task selection.
- Changing command adapter execution behavior.
- Implementing a pixel-perfect terminal renderer independent of Textual. The requirement is faithful information structure, wording, density, and panel order within Textual constraints.
