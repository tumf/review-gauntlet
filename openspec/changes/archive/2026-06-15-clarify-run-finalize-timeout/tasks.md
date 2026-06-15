## Implementation Tasks

- [x] Preserve effective command adapter timeout in run lifecycle snapshots after command steps complete or time out, including the default `CommandAdapterConfig.timeout_seconds`. (verification: unit - `uv run pytest tests/test_run_controller.py` fails if a command-adapter snapshot cannot expose the effective timeout for TUI rendering)
- [x] Update Agent summary timeout rendering in `src/review_gauntlet/run_tui.py` so it uses concise wording and never renders `timeout not set` for configured command adapters. (verification: unit - `uv run pytest tests/test_run_tui.py` fails if default adapter timeout renders as unset or duplicate `timeout timeout ...` wording)
- [x] Teach finalize checklist rendering to distinguish an adapter timeout with `can_finalize=true` and no finalize blockers from a real blocked or pre-ready failure. (verification: unit - `uv run pytest tests/test_run_tui.py` includes a snapshot where `agent_status=timed_out`, `can_finalize=true`, and `finalize_blockers=[]`, and fails if coverage/finding/final-check gates are marked failed)
- [x] Render a concise manual-finalize recovery cue for the ready-timeout state while retaining the timeout lifecycle/audit status. (verification: unit - `uv run pytest tests/test_run_tui.py` asserts the Finalize checkpoint row or current-operation text includes a concrete manual `review-gauntlet finalize` action or equivalent recovery wording)
- [x] Preserve failure/blocker behavior for non-ready timeout states. (verification: unit - `uv run pytest tests/test_run_tui.py` covers timeout before `can_finalize=true` and timeout with finalize blockers, and fails if either incorrectly displays the manual-finalize-ready cue)
- [x] Update `openspec/changes/clarify-run-finalize-timeout/specs/review-sessions/spec.md` scenarios for ready-timeout, pre-ready timeout, blocked-finalize timeout, and effective timeout display, aligned with `tests/test_run_tui.py` and `tests/test_run_controller.py` coverage. (verification: integration - `cflx openspec validate clarify-run-finalize-timeout --strict --evidence warn` and `uv run pytest tests/test_run_tui.py tests/test_run_controller.py`)
- [x] Run focused verification and full checks after implementation. (verification: integration - `uv run pytest tests/test_run_tui.py tests/test_run_controller.py` and `make check` pass, or failures are documented with unrelated evidence)

## Future Work

- Decide separately whether `review-gauntlet run` should offer an explicit non-interactive auto-finalize-on-timeout mode. This proposal only clarifies state and recovery guidance; it does not auto-finalize.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate clarify-run-finalize-timeout --archive-gate`
