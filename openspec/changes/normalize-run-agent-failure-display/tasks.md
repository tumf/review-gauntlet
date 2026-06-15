## Implementation Tasks

- [ ] Preserve specific command execution failure reasons through run controller snapshots and events for timeout, command failure, startup error, template error, interrupted, and max-step exhaustion. (verification: unit - `uv run pytest tests/test_run_controller.py` fails if distinct failure inputs collapse to an indistinguishable status before TUI rendering)
- [ ] Normalize `RunSnapshot.agent_status` and `AgentLifecycle.status` mapping so `timed_out` is used only for actual timeout failures and non-timeout failures keep explicit labels. (verification: unit - `uv run pytest tests/test_run_controller.py` includes timeout and non-zero exit cases and fails if both render as timeout-like states)
- [ ] Update Agent panel text in `src/review_gauntlet/run_tui.py` to render distinct concise labels for timeout, command failure, startup error, template error, interrupted, and max-step exhaustion. (verification: unit - `uv run pytest tests/test_run_tui.py` asserts each failure family has distinct display text)
- [ ] Remove duplicated or unset timeout wording from TUI display when an effective command adapter timeout is configured. (verification: unit - `uv run pytest tests/test_run_tui.py` fails if text such as `timeout timeout` or `timeout not set` appears for configured adapters)
- [ ] Update Activity panel failure summaries to use the actual controller failure reason while retaining stdout/stderr tail evidence separately. (verification: unit - `uv run pytest tests/test_run_tui.py` covers activity rendering for a command failure with stderr evidence and fails if it is labeled as timeout)
- [ ] Preserve the ready-to-finalize timeout recovery behavior from `clarify-run-finalize-timeout`. (verification: unit - `uv run pytest tests/test_run_tui.py` includes the `can_finalize=true`, no-blocker timeout case and fails if the recovery cue disappears)
- [ ] Keep run JSON output parseable and machine-readable for automation. (verification: integration - `uv run pytest tests/test_cli_run.py tests/test_run_controller.py` validates reason/error fields for representative failures)
- [ ] Run focused verification and full checks after implementation. (verification: integration - `uv run pytest tests/test_run_tui.py tests/test_run_controller.py tests/test_cli_run.py` and `make check` pass, or failures are documented with unrelated evidence)

## Future Work

- Consider richer agent stderr classification in a separate proposal if users need automatic diagnosis of tool-level errors. This proposal only preserves and displays Review Gauntlet's own command execution failure reason.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate normalize-run-agent-failure-display --archive-gate`
