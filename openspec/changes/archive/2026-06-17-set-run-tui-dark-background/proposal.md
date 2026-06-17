---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Set run TUI dark background

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` can render an interactive Textual TUI when text output is selected and stdout is a TTY. The TUI currently defines layout, panel borders, brand color, and semantic status colors in `src/review_gauntlet/run_tui.py`, but it does not explicitly set a dark background for the screen or primary containers.

Because background colors are left to Textual defaults or the active terminal/theme, the visual result can vary between environments and may not consistently match the requested dark dashboard appearance.

## Proposed Solution

Make the run TUI explicitly use a dark background palette while preserving the existing dashboard structure and semantic colors.

The implementation should add dark background CSS tokens or equivalent explicit color values to `RunApp.CSS`, apply them to `Screen`, and cover the primary containers that visually define the dashboard: `#body`, `#session_header`, `.panel`, and `#controls`. Existing brand, success, warning, error, muted text, border titles, panel state classes, and layout behavior should remain intact.

A minimal implementation is preferred: this change should not introduce a new CLI flag, configuration surface, or theme selection mechanism.

## Acceptance Criteria

- `review-gauntlet run` TUI renders with an explicitly dark screen background.
- Header, panel, activity, and footer/container surfaces use dark-compatible backgrounds rather than depending solely on Textual defaults.
- Existing brand accent, semantic status colors, border titles, panel state classes, layout structure, and text content remain unchanged except for background styling.
- The change is covered by a focused TUI CSS/source contract test or equivalent TUI rendering test in `tests/test_run_tui.py`.
- Non-TUI output modes, JSON output, run controller behavior, session state, findings state, and finalization behavior are unchanged.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` defines an explicit dark background for `Screen` in `RunApp.CSS`.
- The primary TUI dashboard containers (`#body`, `#session_header`, `.panel`, and `#controls`) have explicit dark-compatible background styling or an equivalent inherited dark surface behavior that is visible from the CSS contract.
- The existing `$brand: #d97757;` accent and semantic state color rules remain present.
- `tests/test_run_tui.py` contains regression coverage that would fail if the explicit dark background styling were removed from the TUI CSS.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Repository quality gates remain available through `make check` after implementation.

## Out of Scope

- Adding theme selection, user-configurable colors, CLI flags, or persistent preferences.
- Changing textual TUI content, panel ordering, panel sizing, or run workflow behavior.
- Changing non-TUI text output, JSON output, checkpoint output, or OpenSpec validation behavior.
- Changing review coverage, finding state, agent lifecycle, or finalization semantics.
