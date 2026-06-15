## Implementation Tasks

- [x] Add CLI parser and dispatch for `review-gauntlet run` with `ROOT`, `--max-steps`, `--config`, and `--format` (completion condition: `review-gauntlet run --help` lists the command options and parser-visible shell completion includes `run`; verification: unit - extend CLI parser/help tests or add `tests/test_cli_run.py` assertions for help/default behavior).

- [x] Implement the run loop using the existing ready prompt function as the only task-selection source (completion condition: the loop calls the same ready computation used by `review-gauntlet ready` and contains no independent finding/cell priority decision table; verification: integration - a test initializes a session, captures `ready`, runs `run` with a fake command, and asserts the fake command received the same prompt).

- [x] Add a session-level configured command runner for ready prompts without OCR verdict parsing (completion condition: `run` expands adapter command/args/env/cwd/timeout from effective config, passes `{prompt}` as the ready prompt, and does not call the review-cell verdict JSON validator for the agent result; verification: integration - fake command writes its argv/env/cwd observations and exits `0`; test asserts prompt expansion and no verdict file is required).

- [x] Persist or expose run-step diagnostics without introducing new durable session state (completion condition: command stdout/stderr/return code are available in command output or temporary artifacts for debugging, while Session Store schema and active-session semantics remain unchanged; verification: unit - tests inspect JSON/text failure payloads and confirm no new ledger tables or session metadata are required).

- [x] Implement completion detection based on active-session disappearance after agent execution (completion condition: if the agent finalizes the session and `.review-gauntlet/active-session.json` is removed, `run` exits `0` with a completed result; verification: integration - fake command invokes or simulates successful finalization/removal and `run --format json` returns `completed: true` with exit `0`).

- [x] Implement failure handling for no ready task, agent command failure, command startup failure, timeout, and max-step exhaustion (completion condition: each failure mode exits `1` and emits structured information in JSON format without a traceback as the final user-facing result; verification: integration - `tests/test_cli_run.py` covers no-ready-task, non-zero fake command, missing command or equivalent startup error, timeout if feasible with a short configured timeout, and `--max-steps 1` when the active session remains).

- [x] Keep `review`, `verify-fixes`, `ready`, `status`, and `finalize` behavior unchanged except where `run` calls them indirectly through the external agent (completion condition: existing tests for those commands continue to pass without changed expectations unrelated to `run`; verification: integration - `make check` passes).

- [x] Update README quick start and basic usage to recommend `review-gauntlet run` for normal progression and reposition `ready` as an advanced/custom-orchestrator API (completion condition: recommended usage no longer tells users to maintain a shell loop, and the former loop appears only as legacy/advanced context if retained) (verification: manual - intentional documentation review because this task changes prose examples; inspect `README.md` and run `uv run pytest tests/test_cli.py` if documentation-adjacent CLI examples need parser verification).

## Future Work

- Richer multi-agent orchestration, daemonized execution, notifications, HITL UI, and automatic VCS operations remain explicitly out of scope for this change.

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-run-command --archive-gate`
