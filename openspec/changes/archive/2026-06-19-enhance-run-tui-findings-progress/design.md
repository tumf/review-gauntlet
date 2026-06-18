# Design: Run TUI Findings progress display

## Current Architecture

`RunController.snapshot()` returns a `RunSnapshot` that is transformed into a `RunViewState` by `dashboard_state(...)` in `src/review_gauntlet/run_tui.py`. The TUI then renders panels from `RunViewState` and periodically advances an `activity_frame` for lightweight animation.

The controller already derives a `ProgressTarget` from each ready prompt via `_progress_target_from_prompt(prompt)` before invoking the command adapter. That target is currently used for no-progress detection but is not included in snapshots.

## Design Decisions

### Transient active-step metadata belongs in `RunSnapshot`

The TUI should not parse prompts to determine which findings are being processed. `RunController` is the component that selects the ready task and parses its target for progress validation, so it should expose transient active-step metadata in snapshots while the command adapter is running.

Recommended fields:

```python
active_step_action: str | None = None
active_target_finding_ids: tuple[str, ...] = ()
```

These fields are runtime-only view metadata and must not change session ledger persistence.

### Resolved/total is derived display state

The title counter should be derived at render time:

- Prefer `view.coverage_projection.findings` when available.
- `total` is the number of projected findings.
- `resolved` is the number of projected findings where `actionable` is false.
- If projected findings are unavailable, fall back to `snapshot.findings` state counts with `resolved = total - open_count`.

This keeps the title consistent with the existing actionable-finding model while avoiding new finding states.

### Review animation is title-only

During active `run_review` execution, the Findings title communicates that findings are being discovered by cycling singular `Finding` with dots. The findings rows themselves remain normal because the review phase targets cells, not existing finding IDs.

### Resolve indicators are row-level

During active `resolve_findings` execution, the title remains `Findings {resolved}/{total}` because the relevant progress is row-specific. Targeted findings receive a spinner indicator at the start of their rows. Non-targeted rows receive blank indicator space so columns stay aligned.

## Compatibility

- `run --no-tui` behavior remains unchanged except for harmless additional dataclass fields with defaults.
- Existing `RunSnapshot` construction in tests remains source-compatible because new fields have defaults.
- Finalized TUI rendering still hides operational panels.
