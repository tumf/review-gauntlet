---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
  - openspec/specs/run-controller/spec.md
  - openspec/changes/archive/2026-06-19-add-tui-color-legend
---

# Fix TUI Coverage Ratio Labels

**Change Type**: implementation

## Premise / Context

- The archived `2026-06-19-add-tui-color-legend` change addressed the wrong problem by adding a global color legend.
- The actual usability issue is that `Rule coverage` and `File hotlist` display compact ratios whose meaning is not self-evident.
- The TUI has tight horizontal space, so long repeated labels like `cells reviewed` or `findings resolved` are not acceptable.
- The preferred fix is compact, panel-local column headers such as `prio`, `target`, `cells`, and `fix`.
- The added footer/global legend should be removed; the existing controls footer may remain.

## Requested Artifact

Implementation.

## Problem / Context

`review-gauntlet run` currently renders coverage rows in a compact form such as `P0 rule-id 2/3 · 1/2` and `P1 path/to/file.py 4/5 · 0/3`. These ratios are space-efficient, but users cannot tell from the row alone whether `2/3` means reviewed cells, pending work, finding progress, or something else.

The prior color legend solution does not solve this because the ambiguity is semantic, not visual. Adding more footer legend text also consumes scarce TUI space and makes the display noisier.

## Proposed Solution

Replace the mistaken global/footer legend approach with compact column headers inside the `Rule coverage` and `File hotlist` panels.

Recommended row shape:

```text
prio target             cells fix
P0   RG-001             2/3   1/2
P1   src/foo.py         4/5   0/3
```

Column meanings:

- `prio`: priority label.
- `target`: rule id in `Rule coverage`, file path in `File hotlist`.
- `cells`: reviewed cells / total cells.
- `fix`: resolved findings / total findings.

The implementation should keep rows compact, use the same column vocabulary in both panels, and remove the added legend display path. Existing color styling may remain where already used by body fields, but the UI must not depend on a footer/global color legend for comprehension.

## Acceptance Criteria

- `Rule coverage` renders a compact header that explains the following data rows without requiring a footer/global legend.
- `File hotlist` renders the same compact header vocabulary as `Rule coverage`.
- The `cells` column means reviewed cells / total cells.
- The `fix` column means resolved findings / total findings.
- Data rows remain compact enough for the existing side-by-side coverage row layout.
- The added color legend/footer display path is removed from the active TUI.
- Existing run-controller behavior, session state, adapter invocation, and coverage computation semantics do not change.

## Explicit Completion Conditions

The change is complete when:

- `src/review_gauntlet/run_tui.py` renders compact column headers for both `rules_tui_lines()` and `files_tui_lines()` output.
- Plain-text summary helpers in `src/review_gauntlet/run_tui.py` use the same compact header/column semantics as the Rich/TUI rendering path.
- The TUI no longer updates or displays the added `color_legend_tui_lines()` footer/global legend path.
- `tests/test_run_tui.py` verifies the compact headers, the meaning of `cells` and `fix` ratios, and removal of the mistaken legend behavior.
- Focused TUI tests pass with `uv run pytest tests/test_run_tui.py`.
- Repository checks pass with `make check`.
- `cflx openspec validate fix-tui-coverage-ratio-labels --strict --evidence warn` passes.

## Out of Scope

- Redesigning the overall TUI layout.
- Changing coverage projection calculations or finding state semantics.
- Adding user-configurable columns, themes, or wider help overlays.
- Removing the existing controls footer text such as `q stop | r refresh | 1-5 views | Ctrl-C interrupt`.
- Changing non-TUI run-controller execution behavior.
