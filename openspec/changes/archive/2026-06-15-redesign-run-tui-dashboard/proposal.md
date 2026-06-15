---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/run_controller.py
  - tests/test_run_tui.py
  - tests/test_run_controller.py
---

# Redesign `review-gauntlet run` TUI as a dashboard

**Change Type**: implementation

## Premise / Context

- `review-gauntlet run` already has an optional Textual TUI implemented in `src/review_gauntlet/run_tui.py`; this is not a Rich-only TUI.
- Textual is an adequate foundation for this dashboard because it provides application layout, CSS, widgets, actions, events, reactivity, and worker support.
- The canonical `review-sessions` spec already requires run TUI presentation to prioritize current-target progress and preserve run semantics.
- The current TUI renders progress, coverage, findings, current task, and events, but several areas expose raw machine-oriented values such as long ISO timestamps, prompt text, and `command n/a`.
- `openspec/CONSTITUTION.md` emphasizes that coverage, unknowns, undecided findings, and incompleteness must remain visible rather than hidden.
- This change is presentation/runtime behavior, not spec-only: it requires Textual layout/CSS changes, a dashboard view model, possible controller snapshot/event metadata changes, and regression tests.

## Problem / Context

The existing `review-gauntlet run` TUI behaves more like a log/status dump than a review execution dashboard. The problem is not that Textual is too weak; the problem is that the current design passes internal state too directly into Rich/Textual panels. Normal panels use the same accent color that should be reserved for warning or attention states, the progress summary uses unclear terms such as `current cells`, coverage hides the full state composition, findings disappear or collapse when empty, and the current task displays the agent prompt directly instead of a human task title.

The event area also renders raw ISO timestamps and `key=value` payloads, including prompt and argv details that are hard to read in a terminal. These issues make it harder for a reviewer to quickly answer whether the session is running, blocked, failed, finalized, how much coverage remains, whether findings are accumulating, and what human action is needed next.

The fix is therefore not a TUI framework migration. The fix is to keep Textual as the TUI application framework and introduce an explicit human-facing view model between `RunController` raw state/events and rendered widgets.

## Proposed Solution

Redesign the interactive `review-gauntlet run` TUI as a four-area dashboard:

1. Header / session summary
2. Metrics dashboard with Coverage and Findings
3. Current operation
4. Activity timeline

The implementation will keep run orchestration semantics unchanged while improving presentation, command labeling, task title formatting, event formatting, terminal-state display, and compact layout behavior.

The implementation will introduce or formalize a `RunViewState`-style display model that converts raw session state into human-readable dashboard fields such as status, short session ID, agent name, step label, coverage metrics, finding metrics, task title, command label, and timeline events. Textual widgets should render that view model rather than raw controller payloads.

The TUI will use semantic colors: muted blue/gray for normal borders, yellow only for pending/blocker/warning attention, red for failure, and green for running/finalized success states. Coverage and findings will stay visible even when counts are zero, and raw internal prompt/event payloads will be hidden behind human-readable labels.

## Acceptance Criteria

- The implementation continues using Textual for interactive TTY dashboard mode, with Rich renderables allowed as Textual widget content where helpful.
- Normal TUI panel borders do not use yellow or warning color.
- Coverage and Findings display as adjacent metric panels when terminal width allows.
- A compact layout remains readable around an 80x24 terminal.
- Coverage shows percent, progress bar, reviewed/total cells, reviewed, pending, stale, and superseded counts.
- Coverage does not use the wording `current cells`.
- Coverage does not render `! pending` or `! stale` markers.
- Findings is always visible, including when all counts are zero.
- Findings shows at least open, untriaged, confirmed, reopened, fixed-pending, and closed counts.
- Current task shows a human title and description rather than the full agent prompt.
- Known ready prompt intents map to stable titles such as `REVIEW PENDING CELLS`, `TRIAGE FINDINGS`, and `FINALIZE SESSION`.
- The TUI never displays `command n/a`.
- The TUI never displays `argv=[]`.
- Activity renders human-readable timeline rows with `HH:MM:SS` timestamps.
- Activity does not render ISO timestamps, full raw prompt payloads, or long unshortened session IDs.
- Header and timeline use shortened session IDs.
- Blocked, failed, and finalized terminal states have distinct wording and semantic colors.
- Footer only lists controls that are implemented.
- TUI changes do not change task selection, command execution semantics, run result semantics, interruption behavior, fallback behavior, or session finalization semantics.

## Explicit Completion Conditions

Implementation is complete when repository evidence shows:

- `src/review_gauntlet/run_tui.py` renders a dashboard-style header, metrics panels, current task panel, activity timeline, and implemented-controls footer using Textual layout/CSS and human-readable formatter functions.
- `src/review_gauntlet/run_tui.py` or supporting code defines a `RunViewState`-style display model or equivalent transformation layer so widgets render human-facing fields instead of raw controller payloads.
- `src/review_gauntlet/run_tui.py` or supporting code has tests proving no `command n/a`, `argv=[]`, raw prompt dump, raw ISO timestamp, or `current cells` text appears in normal dashboard formatter output.
- `src/review_gauntlet/run_tui.py` includes prompt-intent mapping for pending review, stale review, untriaged triage, confirmed-finding fixes, fixed-pending verification, and finalization prompts.
- `src/review_gauntlet/run_controller.py` or equivalent runtime state exposes enough display metadata for the TUI to show an agent/command label before or during command execution without depending on an empty argv list.
- `tests/test_run_tui.py` covers progress metrics, coverage display, findings zero/nonzero display, task title mapping, event formatting, session ID shortening, command placeholder behavior, terminal-state rendering, and compact layout text behavior.
- `tests/test_run_controller.py` or an equivalent test covers command metadata/event behavior if controller state is changed.
- `make check` passes.

## Out of Scope

- Changing review/finding/coverage persistence semantics.
- Changing `review-gauntlet ready` prompt content or task priority.
- Migrating from Textual to another TUI framework.
- Adding an artifact browser or prompt expansion UI unless needed for an implemented footer control.
- Changing external command adapter execution semantics.
- Changing non-TUI JSON or non-TTY output behavior except where existing fallback behavior must be preserved.
