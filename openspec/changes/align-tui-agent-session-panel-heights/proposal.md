---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Align TUI Agent and Session panel heights

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` renders the Agent and Session summary panels side by side in the TUI `#summary` horizontal container. The two panels share equal width, but their heights are content-driven because the common `.panel` style uses `height: auto`.

The Agent panel may include an additional `artifact` row while the Session panel has a shorter fixed summary. When this happens, the side-by-side boxes render with different heights, making the dashboard look uneven even though the panels are visually paired.

## Proposed Solution

Make the Agent and Session panel containers stretch to the same height within their horizontal summary row while preserving the rest of the dashboard layout.

The implementation should keep the shared `.panel` behavior for other panels, and scope the height alignment to `#agent_panel_container` and `#session_panel_container` so the finalize checklist, activity panel, header, and footer keep their existing sizing behavior.

## Acceptance Criteria

- The `review-gauntlet run` TUI renders the side-by-side Agent and Session panel boxes with equal height.
- Height alignment holds whether the Agent summary has the optional artifact row or not.
- The Agent and Session panels continue to share equal horizontal width.
- The finalize checklist, activity panel, header, footer, panel titles, semantic state classes, and text content remain unchanged except for the intended panel height behavior.
- The change is covered by a focused source/CSS contract test or an equivalent TUI layout test in `tests/test_run_tui.py`.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` scopes a height alignment rule to `#agent_panel_container` and `#session_panel_container`, or otherwise implements an equivalent Textual layout rule for only the summary pair.
- The common `.panel` style is not changed in a way that forces all TUI panels to use the summary-pair height behavior.
- `tests/test_run_tui.py` contains regression coverage that would fail if either the Agent or Session panel container lost the summary height alignment rule.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Repository quality gates remain available through `make check` after implementation.

## Out of Scope

- Changing the textual content of the Agent or Session summaries.
- Changing run controller state, session state, finding state, or finalization behavior.
- Changing non-TUI or JSON output.
- Reworking the overall dashboard layout beyond the Agent/Session summary row height alignment.
