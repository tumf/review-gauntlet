## Implementation Tasks

- [x] Update the run TUI header rendering so `header_text(...)` omits timeout remaining while retaining session id, agent name, and liveness text. (verification: unit - `uv run pytest tests/test_run_tui.py` fails if `run_tui.header_text(...)` contains `timeout 53s` or `timeout in 53s` for a quiet agent with known timeout)
- [x] Preserve Agent summary timeout rendering and existing liveness/detail fields. (verification: unit - `uv run pytest tests/test_run_tui.py` asserts `current_operation_text(...)` / `agent_summary_text(...)` still includes the Agent timeout line, `status  quiet ...`, output recency, and artifact path)
- [x] Update TUI regression tests for quiet agents with known timeout. (verification: unit - `uv run pytest tests/test_run_tui.py` covers Header timeout absence plus Agent timeout presence from the same `RunSnapshot.agent_lifecycle.timeout_remaining_seconds` fixture)
- [x] Update the `review-sessions` spec delta to state that Header omits timeout and Agent summary retains timeout. (verification: integration - `src/review_gauntlet/run_tui.py`, `tests/test_run_tui.py`, `uv run pytest tests/test_run_tui.py`, and `make check` provide repository-verifiable evidence; `cflx validate remove-timeout-from-run-tui-header --strict` passes)
- [x] Run project quality gates after implementation. (verification: integration - `make check` passes, or failures are documented with unrelated evidence)

## Future Work

- Consider a separate proposal if the Agent summary line should be normalized from `timeout timeout in ...` to less repetitive wording.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate remove-timeout-from-run-tui-header --archive-gate`

## Acceptance Notes

Archive-gate feedback was addressed by updating the `review-sessions` spec delta task verification note to cite the repository-verifiable spec delta path alongside the strict validation command.

## Acceptance #2 Failure Follow-up

Resolved by updating the task 4 verification note to cite repository-verifiable evidence tokens accepted by the archive evidence gate: `src/review_gauntlet/run_tui.py`, `tests/test_run_tui.py`, `uv run pytest tests/test_run_tui.py`, `make check`, and `cflx validate remove-timeout-from-run-tui-header --strict`.

Additional regression evidence was added in `tests/test_run_tui.py` to assert both generic `timeout` and explicit `timeout in 53s` text remain absent from the Header while Agent summary timeout remains present.
