## Implementation Tasks

- [ ] Define a typed run-turn continuation schema and validators for JSON files under `.review-gauntlet/turns/`.
  Completion condition: repository code exposes a schema with `schema_version`, `verdict`, `summary`, `completed_finding_ids`, `remaining_finding_ids`, `next_turn_instructions`, and optional `error`, rejecting invalid verdicts and unsafe paths.
  verification: unit - add focused tests in `tests/test_cli.py` or a dedicated run-turn test module validating accepted and rejected JSON shapes without invoking an external agent.

- [ ] Render continuation-file instructions into file-scoped actionable finding prompts while preserving grouped findings.
  Completion condition: `triage_findings`, reopened, confirmed, and fixed-pending file-scoped prompts include all actionable findings for the selected file plus a deterministic continuation file path and schema instructions.
  verification: unit - extend ready-prompt tests in `tests/test_cli.py` to assert multiple findings for the same file remain present and the continuation path/schema is present.

- [ ] Inject compact previous-turn context from an existing continuation JSON file into the next prompt for the same session/action/file key.
  Completion condition: when a valid prior continuation file exists, the next matching prompt includes its summary, completed/remaining finding IDs, next-turn instructions, and previous verdict without embedding unrelated task state.
  verification: unit - extend prompt generation tests in `tests/test_cli.py` to cover existing valid continuation context, absent continuation context, and invalid JSON fallback behavior.

- [ ] Add run subprocess monitoring for continuation verdict files with a bounded verdict grace period.
  Completion condition: `review-gauntlet run` detects a valid continuation JSON verdict while the child is still running, starts a grace timer, and terminates the child if it has not exited by the deadline while preserving stdout/stderr artifacts.
  verification: integration - add a `tests/test_cli.py` or `tests/test_run_controller.py` fake-command case where the command writes a valid continuation JSON file and sleeps; `review-gauntlet run` completes before the sleep duration and records a verdict-finalized result rather than waiting for quiet timeout.

- [ ] Map continuation verdict outcomes to run control semantics.
  Completion condition: `continue` and `finish` are successful command-step outcomes that cause the run controller to refresh readiness; `error`, malformed JSON, and missing required verdict files become structured failures with distinct reasons.
  verification: unit - extend command-step tests in `tests/test_cli.py` or `tests/test_run_controller.py` to cover `continue`, `finish`, `error`, malformed JSON, missing file, and command non-zero interactions.

- [ ] Detect no-progress continuation outcomes for targeted actionable work.
  Completion condition: when a step reports `continue` or `finish` but none of the targeted actionable finding/cell states changed, the run stops with a structured `no_progress` failure that includes the task key and target IDs.
  verification: integration - add a fake-command case in `tests/test_cli.py` or `tests/test_run_controller.py` where the command writes `continue` without marking any finding, and `review-gauntlet run` fails with `reason: no_progress`.

- [ ] Preserve existing review adapter and timeout behavior outside continuation-aware run turns.
  Completion condition: `review-gauntlet review`, `verify-fixes`, existing command adapter file-json verdict handling, overall timeout, quiet timeout, and TUI failure labels continue to satisfy existing tests.
  verification: integration - run `uv run pytest tests/test_cli.py tests/test_review_adapter.py tests/test_run_tui.py` plus the new continuation tests.

## Final Validation

Expected archive gate: `cflx openspec validate add-run-turn-verdict-continuation --archive-gate`

Recommended implementation validation: `make check` plus focused tests around run continuation behavior.

## Future Work

- Consider exposing continuation/grace settings in command adapter config after the default behavior proves stable.
- Consider adding a diagnostic command to inspect `.review-gauntlet/turns/` continuation files if operators need visibility beyond run artifacts.
