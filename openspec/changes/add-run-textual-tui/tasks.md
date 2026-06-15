## Implementation Tasks

- [ ] Add optional TUI dependencies to `pyproject.toml` under `[project.optional-dependencies]` with `textual>=0.89` and `rich>=13`. (verification: unit - inspect package metadata or dependency configuration in `pyproject.toml` and run `uv sync --all-groups` without requiring the TUI extra for base development checks; completion condition: base package installation remains possible without Textual while `review-gauntlet[tui]` exposes the TUI dependencies.)

- [ ] Add `--no-tui` parsing for the `run` subcommand in `src/review_gauntlet/cli.py`. (verification: integration - add or update CLI help tests in `tests/test_cli.py` proving `review-gauntlet run --help` includes `--no-tui` and accepts the flag; completion condition: CLI argument parsing routes `--no-tui` into the run command without affecting other subcommands.)

- [ ] Extract the existing `_cmd_run` orchestration semantics into a `RunController` abstraction that emits structured run events and returns the existing run result shape. (verification: unit - add controller tests in `tests/test_run_controller.py` using fake session state and fake command execution to prove ready prompt reuse, completed run, command failure, no-ready-task, and max-step behavior still match existing expectations; completion condition: non-TUI `run` and JSON `run` use the controller instead of duplicating run-loop logic.)

- [ ] Implement controller operations for `refresh`, `stop after current step`, and `interrupt` request handling without allowing UI code to mutate session state directly. (verification: unit - add tests in `tests/test_run_controller.py` proving a stop request made during a fake successful step prevents the next step and reports an incomplete active session when the active-session marker remains; completion condition: UI-facing operations are represented as controller requests or methods and do not update findings, cells, or session ledger rows directly.)

- [ ] Implement optional Textual `RunApp` and widgets for header, coverage, findings, current task, agent status, event log, and footer/help. (verification: unit - add tests in `tests/test_run_tui.py` that skip when Textual is unavailable or use dependency injection to validate the app can be constructed from a controller snapshot without running a real terminal session; completion condition: the TUI renders controller snapshots/events and keeps all state mutation delegated to the controller.)

- [ ] Add TUI selection and fallback logic for `review-gauntlet run`. (verification: integration - add CLI tests in `tests/test_cli.py` for these matrix cases: interactive text with TUI available chooses TUI path, `--no-tui` chooses text path, `--format json` chooses JSON/non-TUI path, non-TTY chooses text/non-TUI path, and missing Textual falls back with the documented warning; completion condition: JSON stdout remains parseable and no warning or TUI control text is emitted to JSON stdout.)

- [ ] Preserve and update existing run tests for non-TUI behavior. (verification: integration - run focused CLI tests covering existing `run --format json` scenarios from `tests/test_cli.py` and any new controller tests; completion condition: existing run result fields (`completed`, `reason`, `steps`, `step_count`, `session_id`, errors) remain compatible.)

- [ ] Add user-facing text and help behavior for missing TUI support. (verification: integration - add `tests/test_cli.py` coverage proving missing Textual fallback emits `TUI support is not installed; falling back to text mode.` plus install guidance outside JSON stdout; completion condition: users can recover by either installing `uv tool install "review-gauntlet[tui]"` or running `review-gauntlet run --no-tui`.)

- [ ] Run repository verification. (verification: integration - `make check`; completion condition: format, lint, typecheck, and tests pass under the repository's standard check command.)

## Future Work

- Implement `o` to open the artifact directory once artifact-directory semantics are defined for session-level run steps.
- Add finding list/detail panes and keyboard-driven triage after initial read-only TUI behavior is stable.
- Add live command output streaming if the controller later supports incremental subprocess output events.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-run-textual-tui --archive-gate`
