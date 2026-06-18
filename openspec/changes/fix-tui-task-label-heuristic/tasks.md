# Tasks: Fix TUI task label heuristic

## Implementation Tasks

- [x] 1. Define `ReadyTask` dataclass in `run_controller.py`. Fields: `prompt: str`, `next_required_action: str`. Add `@dataclass(frozen=True)`. (verification: unit — `tests/test_run_controller.py` imports `ReadyTask`.)

- [x] 2. Change `ReadyPrompt` type alias in `run_controller.py` from `Callable[[SessionStore, Path], str | None]` to `Callable[[SessionStore, Path], ReadyTask | None]`. (verification: unit — `make typecheck` passes with the new return type.)

- [x] 3. Update `RunController.run()` in `run_controller.py` (~line 354) to unpack `ReadyTask` from the callable. Store `prompt` and `next_required_action` separately. Emit `step_started` with `step`, `prompt`, and `next_required_action` in the payload (~line 375). (verification: integration — `tests/test_run_controller.py` — `step_started` event payload includes `next_required_action`.)

- [x] 4. Update `RunController.snapshot()` in `run_controller.py` (~line 249) to handle `ReadyTask | None` from the callable. Extract `next_ready_prompt` from `ReadyTask.prompt` for `RunSnapshot.next_ready_prompt`. `RunSnapshot.next_required_action` continues to come from status snapshot — no change needed. (verification: unit — `make typecheck` passes with the new unpacking logic.)

- [x] 5. Update `RunSnapshotReadinessProvider.ready_prompt` in `cli.py` (~line 1427) to return `ReadyTask | None`. Derive `next_required_action` from the same `_StatusContext` via `_next_action(context.effective_cell_counts, context.finding_counts, context.finalize_reasons)` or `_status_from_context(context)["next_required_action"]`. Return `ReadyTask(prompt=prompt_text, next_required_action=action)`. (verification: unit — `tests/test_cli.py` or `tests/test_run_controller.py` — ready_prompt returns ReadyTask with correct action.)

- [x] 6. Replace `format_task_title(prompt)` in `run_tui.py` (~line 612) with `format_task_title_from_action(next_required_action, coverage, findings)`. Use the action-to-title mapping table from the proposal. For `run_review`, check `coverage.get("pending", 0) > 0` → `REVIEW PENDING CELLS`; else `coverage.get("stale", 0) > 0` → `REVIEW STALE CELLS`. Missing/unknown → `READY TASK`. Remove all keyword-scan mappings. (verification: unit — `tests/test_run_tui.py::test_task_title_mapping_for_ready_prompt_intents` updated to use action-based inputs.)

- [x] 7. Update `dashboard_state` in `run_tui.py` (~line 673) to call `format_task_title_from_action(snapshot.next_required_action, snapshot.coverage, snapshot.findings)` instead of `format_task_title(snapshot.next_ready_prompt)`. (verification: unit — `tests/test_run_tui.py` — dashboard task display uses action.)

- [x] 8. Update `_event_detail` for `step_started` in `run_tui.py` (~line 2034) to use `event.payload.get("next_required_action")` with `format_task_title_from_action` instead of `format_task_title(str(event.payload.get("prompt") or ""))`. (verification: unit — `tests/test_run_tui.py` — step_started detail uses action.)

- [x] 9. Remove the old `format_task_title(prompt)` function body and its keyword-mapping tuples from `run_tui.py`. If no callers remain, delete the function entirely. (verification: manual — `rg "format_task_title" src/review_gauntlet/run_tui.py` shows no prompt-text parsing remains.)

- [x] 10. Add regression test in `tests/test_run_tui.py`: construct a `RunSnapshot` with `next_required_action="run_review"`, `coverage={"pending": 3, "stale": 0}`, `next_ready_prompt` containing the words `confirmed` and `fix` (simulating a real pending-review prompt). Assert `format_task_title_from_action(...)` returns `REVIEW PENDING CELLS`, not `FIX CONFIRMED FINDING`. (verification: unit — `uv run pytest tests/test_run_tui.py::test_task_title_ignores_prompt_keywords` passes and would fail if prompt parsing were restored.)

- [x] 11. Add test in `tests/test_run_controller.py`: run one step with a mock ready_task provider returning `ReadyTask(prompt="...", next_required_action="run_review")`. Assert the `step_started` event payload contains `next_required_action == "run_review"`. (verification: integration — `uv run pytest tests/test_run_controller.py::test_step_started_carries_next_required_action` passes.)

- [x] 12. Update existing `test_task_title_mapping_for_ready_prompt_intents` in `tests/test_run_tui.py` (~line 523) to test `format_task_title_from_action` with action + coverage + findings inputs instead of prompt strings. (verification: unit — `uv run pytest tests/test_run_tui.py::test_task_title_mapping_for_ready_prompt_intents` passes with new signature.)

- [x] 13. Update any tests in `tests/test_run_tui.py` or `tests/test_run_controller.py` that construct `RunSnapshot` or call `format_task_title` and break due to the signature change. (verification: unit — `make test` passes with all updated test expectations.)

- [x] 14. Run full CI: `make check`. (verification: manual — `make check` passes, covering format-check, lint, typecheck, and test.)

## Future Work

- `review-gauntlet ready --format json` could include `next_required_action` alongside the prompt for external orchestrators (separate proposal).
- The `ready` command text output could show the action label.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-tui-task-label-heuristic --archive-gate`
