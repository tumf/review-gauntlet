---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/run-controller/spec.md
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/run_tui.py
  - tests/test_run_tui.py
---

# Enhance run TUI Findings progress display

**Change Type**: implementation

## Problem / Context

The run TUI currently renders the Findings panel with a static `Findings` title and lists actionable findings without showing which finding IDs are actively being resolved. During Phase 1 review execution, the Findings area does not make it visually clear that findings are still being discovered. During Phase 2 resolution execution, the TUI does not identify the specific finding rows targeted by the active agent step.

The project constitution requires incomplete and undecided states to stay visible, and existing run-controller behavior already derives targeted finding IDs internally for no-progress detection. This change exposes only transient active-step metadata to the TUI and keeps durable session state unchanged.

## Proposed Solution

Update `review-gauntlet run` TUI behavior so that:

- The Findings panel title shows resolved progress as `Findings {resolved}/{total}` when not actively reviewing cells.
- While a review step is running, the Findings panel title animates as `Finding`, `Finding.`, `Finding..`, `Finding...`.
- While a resolve step is running, the Findings panel keeps the resolved/total title and shows an inline running indicator on the finding rows targeted by the active resolve process.
- `RunSnapshot` exposes transient active-step action and target finding IDs derived by `RunController`, avoiding prompt re-parsing inside TUI rendering.

## Acceptance Criteria

- Normal Findings panel titles show `Findings {resolved}/{total}` in overview and findings views.
- Resolved count is derived from non-actionable findings when projection data is available, with a fallback from finding state counts when projection data is unavailable.
- Review execution renders the title animation using the existing TUI activity frame and the singular `Finding` label.
- Resolve execution does not replace the title with the review animation.
- Resolve execution shows a spinner indicator only on rows whose finding IDs are targeted by the active step.
- Non-targeted finding rows retain aligned columns and do not show a spinner.
- When the agent step finishes, active target indicators disappear.
- Existing finalized rendering continues hiding operational panels.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `RunSnapshot` and `RunController.snapshot()` carry transient active-step action and active target finding IDs during running agent steps and clear them after step completion.
- `dashboard_state(...)`, Findings panel title rendering, and `findings_tui_lines(...)` use those transient values to render the requested title and row indicators.
- `tests/test_run_tui.py` or adjacent tests cover normal counts, review-title animation frames, resolve-title count preservation, active-row indicator rendering, and indicator clearing behavior.
- The project check command `make check` passes.

## Out of Scope

- Changing durable finding state semantics or ledger persistence.
- Changing the two-phase review/resolve workflow.
- Adding new finding states.
- Changing non-TUI `run --no-tui` output format.
