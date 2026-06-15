## Implementation Tasks

- [x] Replace the current static-panel `run` TUI layout with a compact progress-first dashboard in `src/review_gauntlet/run_tui.py`. Completion condition: the first visible dashboard area contains percent complete, completed/total current cells, elapsed time, step number, and agent status. (verification: unit - `uv run pytest tests/test_run_tui.py`)

- [x] Implement deterministic progress metric helpers for current-target coverage. Completion condition: helpers treat `pending` and `stale` as incomplete, exclude `superseded` from the progress denominator, and handle zero-cell sessions without division errors. (verification: unit - `uv run pytest tests/test_run_tui.py`)

- [x] Render coverage and finding-state details as compact high-density visual summaries. Completion condition: coverage is displayed with graphical bars or equivalent dense visual text, pending and stale are visually emphasized, and finding counts are shown as compact state badges/chips rather than a plain sorted key/value list. (verification: unit - `uv run pytest tests/test_run_tui.py`; manual - run `uv run review-gauntlet run` in a TTY-backed local session and observe that the dashboard emphasizes progress and remaining work.)

- [x] Remove default Textual `Header` and `Footer` chrome from the run TUI. Completion condition: `create_run_app()` no longer imports or yields `Header` or `Footer`, and the default `RunApp` title/icon is not part of the app-rendered chrome. (verification: unit - `uv run pytest tests/test_run_tui.py`)

- [x] Add visible activity animation while the session-level agent is running. Completion condition: when `RunSnapshot.agent_status == "running"`, the status line includes a changing spinner/pulse indicator across refresh intervals; idle and terminal states render without the running animation. (verification: unit - `uv run pytest tests/test_run_tui.py`; manual - run a configured command that sleeps during `review-gauntlet run` and observe the animated running indicator.)

- [x] Fix run snapshot finding-count propagation for status payloads that expose `finding_state_counts`. Completion condition: `RunController.snapshot()` populates `RunSnapshot.findings` from `status["findings"]` when present, otherwise from `status["finding_state_counts"]`. (verification: unit - `uv run pytest tests/test_run_controller.py tests/test_run_tui.py`)

- [x] Preserve existing run behavior and TUI selection/fallback semantics. Completion condition: existing CLI tests for `--no-tui`, JSON output, non-TTY output, Textual fallback, interruption, and headless TUI execution continue to pass. (verification: integration - `uv run pytest tests/test_cli.py tests/test_run_tui.py`)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate run-tui-coverage-dashboard --archive-gate`
Project verification command: `make check`

## Future Work

- Real OS CPU utilization display, if a future UX requirement needs host-level resource monitoring rather than session-level agent activity.
