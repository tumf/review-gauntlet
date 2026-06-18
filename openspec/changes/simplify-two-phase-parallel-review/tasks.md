# Implementation Tasks

## Phase 1: Data Model Simplification

- [ ] Task 1: Simplify `CellState` enum — remove `STALE`, `SUPERSEDED`; keep `PENDING`, `REVIEWED` (file: `src/review_gauntlet/review_cells.py`; verification: unit — assert enum members)

- [ ] Task 2: Update `TERMINAL_CELL_STATES` — set to `{CellState.REVIEWED}` only (file: `src/review_gauntlet/review_cells.py`; verification: unit — assert set contents)

- [ ] Task 3: Simplify `FindingState` enum — replace all states with `OPEN`, `CONFIRMED`, `DISMISSED` (file: `src/review_gauntlet/findings.py`; verification: unit — verify 3 enum members)

- [ ] Task 4: Update `TERMINAL_FINDING_STATES` — `{FindingState.CONFIRMED, FindingState.DISMISSED}` (file: `src/review_gauntlet/findings.py`; verification: unit — assert terminal set)

- [ ] Task 5: Update `ALLOWED_TRANSITIONS` — `OPEN → {CONFIRMED, DISMISSED}`, terminal states have no outgoing transitions (file: `src/review_gauntlet/findings.py`; verification: unit — verify transition map)

- [ ] Task 6: Add `dismiss_reason: str | None = None` field to `NormalizedFinding` (file: `src/review_gauntlet/findings.py`; verification: unit — verify model_validate accepts field)

- [ ] Task 7: Add `FindingResolution` Pydantic model with `finding_id`, `state: Literal["confirmed","dismissed"]`, `dismiss_reason` (file: `src/review_gauntlet/findings.py`; verification: unit — verify model validation)

## Phase 2: ContinuationVerdict Changes

- [ ] Task 8: Rename `error` verdict to `abort` in `ContinuationVerdict` (file: `src/review_gauntlet/continuation.py`; verification: unit — validate verdict with `abort` value)

- [ ] Task 9: Bump `schema_version` to `2` in `ContinuationVerdict` (file: `src/review_gauntlet/continuation.py`; verification: unit — verify default schema_version)

- [ ] Task 10: Add `resolutions: tuple[FindingResolution, ...]` field to `ContinuationVerdict` (file: `src/review_gauntlet/continuation.py`; verification: unit — verify verdict accepts resolutions)

## Phase 3: Store Layer Cleanup

- [ ] Task 11: Remove `stale_to_pending` parameter from `refresh_file_digest` (file: `src/review_gauntlet/session_store.py`; verification: integration — `uv run pytest tests/test_session_store.py`)

- [ ] Task 12: Remove `list_fixed_pending_findings` method (file: `src/review_gauntlet/session_store.py`; verification: unit — verify method removed, no callers)

- [ ] Task 13: Update `_TERMINAL_FINDING_STATES_CLAUSE` for new states (file: `src/review_gauntlet/session_store.py`; verification: integration — `uv run pytest tests/test_session_store.py -k terminal`)

- [ ] Task 14: Update `count_terminally_complete_cells` for new finding states (file: `src/review_gauntlet/session_store.py`; verification: integration — `uv run pytest tests/test_session_store.py -k complete`)

## Phase 4: CLI Changes

- [ ] Task 15: Modify `review` command to run all PENDING cells in parallel — Phase 1 (file: `src/review_gauntlet/cli.py`; verification: integration — `uv run pytest tests/test_cli.py -k review`)

- [ ] Task 16: Add `--parallel N` option to `review` command (file: `src/review_gauntlet/cli.py`; verification: integration — verify parallel execution)

- [ ] Task 17: Add `resolve` command — group open findings by file, run resolution agents in parallel — Phase 2 (file: `src/review_gauntlet/cli.py`; verification: integration — `uv run review-gauntlet resolve --format json`)

- [ ] Task 18: Add `--parallel N` option to `resolve` command (file: `src/review_gauntlet/cli.py`; verification: integration — verify parallel execution)

- [ ] Task 19: Remove `verify-fixes` command and all related code paths (file: `src/review_gauntlet/cli.py`; verification: unit — no references remain; command exits with usage error)

- [ ] Task 20: Update `run` command to support two-phase execution — Phase 1 → Phase 2 (files: `src/review_gauntlet/cli.py`, `src/review_gauntlet/run_controller.py`; verification: integration — `uv run pytest tests/test_run_controller.py`)

## Phase 5: Ready Prompt and Status

- [ ] Task 21: Update ready prompt priorities — PENDING cells → OPEN findings → finalize; remove stale branches (file: `src/review_gauntlet/cli.py`; verification: integration — `uv run pytest tests/test_cli_ready.py`)

- [ ] Task 22: Remove all stale-related logic from `_build_status_context` and `_ready_prompt_from_context` (file: `src/review_gauntlet/cli.py`; verification: unit — grep for STALE in ready/status code returns empty)

- [ ] Task 23: Update `_ACTIONABLE_FINDING_STATES` for new model — only `OPEN` is actionable (file: `src/review_gauntlet/cli.py`; verification: unit — assert only open state)

- [ ] Task 24: Remove stale-related cell state handling from `_ready_review_cells_by_state` (file: `src/review_gauntlet/cli.py`; verification: unit — verify only PENDING bucket exists)

## Phase 6: TUI Updates

- [ ] Task 25: Update `FINDING_STATES` constant in run_tui.py for new states (file: `src/review_gauntlet/run_tui.py`; verification: unit — verify constants reflect open/confirmed/dismissed)

- [ ] Task 26: Update finding state color mapping for new states (file: `src/review_gauntlet/run_tui.py`; verification: manual — visual inspection of TUI rendering)

- [ ] Task 27: Update `actionable_finding_summary` for new state model (file: `src/review_gauntlet/run_tui.py`; verification: unit — verify summary counts match new states)

- [ ] Task 28: Update `findings_text` for new finding states (file: `src/review_gauntlet/run_tui.py`; verification: unit — verify text output uses new state names)

- [ ] Task 29: Add phase display to TUI — review vs resolve progress (file: `src/review_gauntlet/run_tui.py`; verification: manual — visual inspection of TUI with two-phase run)

## Phase 7: Review Adapter Updates

- [ ] Task 30: Update verdict validation in `review_adapter.py` for `abort` verdict and schema v2 (file: `src/review_gauntlet/review_adapter.py`; verification: integration — `uv run pytest tests/test_command_review_adapter.py`)

- [ ] Task 31: Create resolve prompt template — file path + open findings list → resolution instructions (file: `src/review_gauntlet/review_adapter.py` or new module; verification: unit — verify prompt includes file path, finding IDs, resolution instructions)

## Phase 8: Constitution Update

- [ ] Task 32: Update Principle 4 — remove "stale" from enumerated states (file: `openspec/CONSTITUTION.md`; verification: manual — read and verify stale is removed)

- [ ] Task 33: Update Principle 5 — "advances exactly one step" to "advances exactly one phase" (file: `openspec/CONSTITUTION.md`; verification: manual — read and verify wording)

- [ ] Task 34: Update Principle 9 — replace fixed-pending-verification with unified judgment+fix (file: `openspec/CONSTITUTION.md`; verification: manual — read and verify new principle)

- [ ] Task 35: Update Principle 11 — remove stale reference, describe deterministic per-session review (file: `openspec/CONSTITUTION.md`; verification: manual — read and verify stale concept removed)

## Phase 9: Test Suite Migration

- [ ] Task 36: Update `tests/test_findings.py` — all transitions and state tests for new model (verification: integration — `uv run pytest tests/test_findings.py`)

- [ ] Task 37: Update `tests/test_finding_transitions.py` — new transition map tests (verification: integration — `uv run pytest tests/test_finding_transitions.py`)

- [ ] Task 38: Update `tests/test_review_cells.py` — remove stale/superseded tests (verification: integration — `uv run pytest tests/test_review_cells.py`)

- [ ] Task 39: Update `tests/test_cli.py` — remove verify-fixes tests, add resolve tests (verification: integration — `uv run pytest tests/test_cli.py`)

- [ ] Task 40: Update `tests/test_session_store.py` — remove stale-related tests (verification: integration — `uv run pytest tests/test_session_store.py`)

- [ ] Task 41: Update `tests/test_run_controller.py` — two-phase model tests (verification: integration — `uv run pytest tests/test_run_controller.py`)

- [ ] Task 42: Update `tests/test_cli_ready.py` — new ready prompt priorities (verification: integration — `uv run pytest tests/test_cli_ready.py`)

- [ ] Task 43: Full test suite pass — `make check` exits 0 (verification: integration — `make check`)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate simplify-two-phase-parallel-review --archive-gate`
