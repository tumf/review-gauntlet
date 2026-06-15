# Design: Run TUI checklist dashboard

## Context

The current TUI derives `RunViewState` from `RunSnapshot`, but several rendering functions still expose internal concepts directly: gate states such as `active`/`waiting`, the `Resolve finalize blockers` row, raw `next_required_action`, and repeated liveness labels. The redesign keeps controller data unchanged and moves presentation responsibility into the TUI view-model layer.

## Dashboard view model

Introduce or evolve the TUI view model into a structure equivalent to:

```text
RunDashboardView
  header
  finalize_path[]
  agent_summary
  session_summary
  activity[]
```

The view model is the only input to render functions. Raw `RunSnapshot` fields can be used to build the view model, but should not be concatenated directly into dashboard text unless first normalized.

## Panel layout

The Textual app should compose these regions:

1. `#session_header` rendering `Review Gauntlet`
2. `#finalize_path` rendering `Next to finalize`
3. horizontal `#summary` containing `#agent_panel` and `#session_panel`
4. `#activity_timeline`
5. compact controls

On narrow terminals, Textual may stack summary cards if needed, but the content order remains Agent before Session.

## Checklist state model

TUI checklist states are intentionally fewer and more human-facing than durable session states:

- `running`
- `done`
- `next`
- `later`
- `blocked`
- `failed`

Internal states such as `pending`, `stale`, `untriaged`, `confirmed`, and `fixed_pending_verification` remain available in details but are not used as primary TUI state labels.

## Blocker classification

`snapshot.finalize_blockers` remains an API/status concern. The TUI classifies blocker strings for display:

- Coverage blockers:
  - `review cells are still pending`
  - `review cells are stale after target changes`
- Finding blockers:
  - strings indicating untriaged, reopened, confirmed, or fixed-pending findings
  - `fixed findings require verification`
- Finalize-only blockers:
  - uncommitted or dirty working tree blockers
  - target digest drift blockers
  - expired waived or accepted-risk findings
  - `no review run has been completed`
  - anything not classified as coverage/finding blocker

Coverage and finding blockers should influence their dedicated rows. `Final checks` is blocked only when earlier checklist rows are complete and finalize-only blockers remain.

## Gate derivation rules

### Review coverage

- `running` if pending or stale coverage exists
- `done` when pending and stale are zero
- `failed` if the run failed while this is the active unresolved row

### Triage findings

- `next` while coverage is incomplete
- `running` when untriaged or reopened findings remain
- `done` otherwise

### Fix confirmed findings

- `next` while triage is incomplete
- `running` when confirmed findings remain
- `done` otherwise

### Verify fixes

- `next` while confirmed fixes remain
- `running` when fixed-pending verification remains
- `done` otherwise

### Final checks

- `later` while any prior row is incomplete
- `blocked` when finalize-only blockers remain
- `done` when prior rows are complete and no finalize-only blockers remain

### Finalize checkpoint

- `later` while Final checks is not done
- `running` when `can_finalize` is true and the session is not finalized
- `done` after finalization

## Activity rows

Activity rows should use normalized columns:

```text
HH:MM:SS  event   run started     session RGS-...
HH:MM:SS  stdout  Reading prompt
HH:MM:SS  stderr  Analyzing review cell RGC-...
```

The TUI may synthesize display-only rows such as `gate started` and `agent alive` from the current view model. These synthetic rows do not need to be persisted as durable events.

Agent output display remains bounded, line-oriented, sanitized, truncated, and redacted. Full output artifacts remain the audit source of truth.

## Compatibility

This is a presentation-only redesign. It must not alter:

- `RunController` task selection
- ready prompt generation
- durable session status
- JSON output
- finalization rules
- output artifact persistence
- non-TUI fallback behavior
