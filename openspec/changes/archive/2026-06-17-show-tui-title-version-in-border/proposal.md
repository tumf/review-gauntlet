---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - src/review_gauntlet/__about__.py
  - tests/test_run_tui.py
  - openspec/specs/review-sessions/spec.md
---

# Show TUI title and version in header border

**Change Type**: implementation

## Problem/Context

`review-gauntlet run` renders an interactive Textual TUI whose top `#session_header` panel currently displays `✻ Review Gauntlet` as the first line inside the panel body. The project already uses `border_title` for other dashboard panels and keeps the package version in `src/review_gauntlet/__about__.py`.

Keeping the product title as body content makes the top header less consistent with the rest of the TUI panel model, and the TUI does not currently expose the running Review Gauntlet version in the header.

## Proposed Solution

Move the `✻ Review Gauntlet` title from the `#session_header` body into the `#session_header` border title and append the current package version to that border title.

The implementation should source the version from `review_gauntlet.__about__.__version__`, prefer a compact title such as `✻ Review Gauntlet v0.1.1`, and keep the header body focused on status and metadata. Non-TUI compact/text output may continue to use `header_text()` with the title line so text fallback remains self-describing.

## Acceptance Criteria

- `review-gauntlet run` TUI displays the top header title in the `#session_header` border title instead of as the first body line.
- The TUI header border title includes the brand sparkle, `Review Gauntlet`, and the current package version from `__version__`.
- The TUI header body still displays run status and metadata, including agent liveness information, without duplicating the title as body content.
- Existing panel border titles, semantic state colors, brand accent styling, activity/finalize/session content, and run behavior remain unchanged except for the title relocation/version text.
- Non-TUI compact/text rendering remains self-describing and continues to include the title, status, and metadata.
- The change is covered by focused tests in `tests/test_run_tui.py` that would fail if the title stayed only in the body, the border title was not set, or the version was omitted.

## Explicit Completion Conditions

- `src/review_gauntlet/run_tui.py` imports or otherwise references `review_gauntlet.__about__.__version__` for the TUI title/version text.
- The `#session_header` `Vertical` has `border_title` set to the versioned `header_title_text()` result or an equivalent helper result.
- The `#session_header` body no longer yields a `Static(header_title_text(), id="header_title")` title row.
- Header styling is updated so the top header border title receives the intended brand/bold styling without relying on a removed `#header_title` widget.
- `tests/test_run_tui.py` includes assertions for versioned title text, session-header border-title wiring, no title body widget, and preserved text fallback header behavior.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Repository quality gates remain available through `make check` after implementation.

## Out of Scope

- Changing the package version value or release process.
- Adding a new CLI flag, configuration option, or theme preference for header title formatting.
- Changing run controller state, agent lifecycle tracking, finding/coverage/finalization behavior, JSON output, or checkpoint output.
- Changing unrelated TUI panel ordering, sizing, or content beyond the header title relocation/version display.
