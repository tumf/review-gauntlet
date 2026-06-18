# Design: Fix TUI task label heuristic

## Architecture

### New dataclass: `ReadyTask`

```python
# run_controller.py
@dataclass(frozen=True)
class ReadyTask:
    prompt: str
    next_required_action: str
```

Carries both the agent-facing prompt text and the structured action signal from the same readiness context. This prevents drift between what the agent receives and what the TUI displays.

### Callable type change

```python
# BEFORE
ReadyPrompt = Callable[[SessionStore, Path], str | None]

# AFTER
ReadyPrompt = Callable[[SessionStore, Path], ReadyTask | None]
```

### Readiness provider change

`RunSnapshotReadinessProvider` in `cli.py` already caches `_StatusContext` between `status_snapshot()` and `ready_prompt()` calls. The change makes `ready_prompt()` return `ReadyTask`:

```python
def ready_prompt(self, store: SessionStore, root: Path) -> ReadyTask | None:
    context = self._status_context  # cached from status_snapshot()
    if context is None or ...:
        context = _build_status_context(store, root, allow_non_review_dirty=True)
    prompt = _ready_prompt_from_context(store, context)
    if prompt is None:
        return None
    action = _next_action(
        context.effective_cell_counts,
        context.finding_counts,
        context.finalize_reasons,
    )
    return ReadyTask(prompt=prompt, next_required_action=action)
```

The `ready` CLI command (`_ready_prompt(store, root)`) continues to return prompt text only — it does not use `RunSnapshotReadinessProvider` and is unaffected. If the `ready` command needs the action later, it can call `_next_action` independently (Future Work).

### RunController.run() change

```python
# BEFORE
prompt = self._ready_prompt(self.store, self.root)
...
self._emit("step_started", step=step_number, prompt=prompt)

# AFTER
ready_task = self._ready_prompt(self.store, self.root)
if ready_task is None:
    ...  # same blocked/no_ready_task path
prompt = ready_task.prompt
next_required_action = ready_task.next_required_action
...
self._emit(
    "step_started",
    step=step_number,
    prompt=prompt,
    next_required_action=next_required_action,
)
```

### RunController.snapshot() change

`snapshot()` calls `self._ready_prompt()` for `next_ready_prompt`. With the new return type:

```python
ready_task = self._ready_prompt(self.store, self.root)
ready = ready_task.prompt if ready_task is not None else None
```

`RunSnapshot.next_required_action` continues to come from `status.get("next_required_action")` — no change needed. This is intentional: the snapshot's action comes from the status snapshot (which may be cached), while the step_started event's action comes from the readiness provider. Both derive from `_next_action` over the same status context, so they agree.

### TUI task title: action-based mapping

```python
# run_tui.py

_ACTION_TASK_TITLES: dict[str, str] = {
    "triage_findings": "TRIAGE FINDINGS",
    "fix_confirmed_findings": "FIX CONFIRMED FINDING",
    "run_verify_fixes": "VERIFY FIXES",
    "resolve_finalize_blockers": "RESOLVE FINALIZE BLOCKERS",
    "finalize": "FINALIZE SESSION",
}

def format_task_title_from_action(
    next_required_action: str | None,
    coverage: dict[str, object],
    findings: dict[str, object],
) -> TaskDisplay:
    if next_required_action == "run_review":
        if int(coverage.get("pending", 0)) > 0:
            return TaskDisplay("REVIEW PENDING CELLS", "Review cells that have not received coverage yet.")
        if int(coverage.get("stale", 0)) > 0:
            return TaskDisplay("REVIEW STALE CELLS", "Refresh reviews whose coverage is stale.")
        return TaskDisplay("REVIEW CELLS", "Review cells need coverage.")
    if next_required_action is not None:
        title = _ACTION_TASK_TITLES.get(next_required_action)
        if title is not None:
            return TaskDisplay(title, _ACTION_TASK_DESCRIPTIONS[title])
    return TaskDisplay("READY TASK", "An actionable ready task is available.")
```

### TUI Activity step_started detail

```python
# run_tui.py _event_detail
if event.type == "step_started":
    action = event.payload.get("next_required_action")
    if action is not None:
        return format_task_title_from_action(
            str(action),
            {},  # coverage not in payload; action alone is enough for label
            {},
        ).title
    return "step started"
```

The Activity timeline does not need coverage counts for the label — the action string alone determines the title for all actions except `run_review`. For `run_review`, the step_started payload could optionally include coverage counts, but the label `REVIEW CELLS` (without pending/stale disambiguation) is acceptable for the Activity timeline. The current-task display in `dashboard_state` uses the full snapshot with coverage counts, so it gets the precise pending/stale distinction.

### What is removed

The entire `mappings` tuple in the old `format_task_title`:

```python
# REMOVED — no longer in run_tui.py
mappings = (
    (("untriaged",), "TRIAGE FINDINGS", ...),
    (("confirmed", "fix"), "FIX CONFIRMED FINDING", ...),
    (("fixed_pending",), "VERIFY FIXES", ...),
    (("fixed-pending",), "VERIFY FIXES", ...),
    (("finalize",), "FINALIZE SESSION", ...),
    (("pending", "review"), "REVIEW PENDING CELLS", ...),
    (("stale", "review"), "REVIEW STALE CELLS", ...),
)
```

## Migration

- `ReadyPrompt` callable type changes return type. The only implementation is `RunSnapshotReadinessProvider.ready_prompt` in `cli.py`, which is updated in the same change.
- `RunSnapshot` structure is unchanged (`next_required_action` already exists).
- `step_started` event payload gains a new key `next_required_action`; existing consumers that ignore unknown keys are unaffected.
- No database migration, no session format change.

## Backward compatibility

- Sessions without `next_required_action` in status (impossible in current code — `_status_from_context` always sets it) would show `READY TASK`. This is safe because `_next_action` always returns a value.
- The `ready` CLI command output is unchanged (still prompt text only).
