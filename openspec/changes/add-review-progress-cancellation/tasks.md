## Implementation Tasks

- [ ] Add review-run progress reporting in `src/review_gauntlet/cli.py` before adapter execution starts, including session id, run id, selected cell count, budget, concurrency, adapter identity, timeout, and artifact directory. (verification: unit - add `tests/test_cli.py` or `tests/test_init_targets.py` assertions using `capsys.readouterr().err` to prove human-audience progress appears before final output)
- [ ] Route all review progress to stderr and preserve stdout for final command results. (verification: integration - add `tests/test_cli.py::test_review_json_stdout_is_clean_when_progress_enabled`, run with `uv run pytest tests/test_cli.py`, parse stdout with `json.loads`, and assert progress text is only in stderr)
- [ ] Suppress decorative progress when `--audience agent` is selected. (verification: unit - add `tests/test_cli.py::test_review_agent_audience_suppresses_progress`, run with `uv run pytest tests/test_cli.py`, and assert stderr has no progress banner)
- [ ] Emit per-cell progress events for start, success, adapter failure, timeout, and cancellation without changing deterministic ledger mutation order. (verification: integration - add `tests/test_cli.py` or a new review session test with fake fixtures and failing adapter config, asserting stderr cell events plus `reviewed_cells` and ledger state via `SessionStore`)
- [ ] Replace or wrap the executor shutdown path so `KeyboardInterrupt` cancels pending futures and does not block indefinitely in `ThreadPoolExecutor.__exit__`. (verification: unit - add a blocking adapter regression test in `tests/test_cli.py` or a new `tests/test_review_cancellation.py` that simulates interrupt and asserts unfinished cells remain pending via `SessionStore.list_cells`)
- [ ] Refactor command adapter subprocess execution in `src/review_gauntlet/review_adapter.py` from uncancellable `subprocess.run()` to a handle-based implementation that can terminate active child processes on timeout or cancellation. (verification: unit - add `tests/test_review_adapter.py` coverage using a local long-running Python command and assert timeout/cancel writes `failure.json` and terminates the child)
- [ ] Preserve command adapter artifact contracts for stdout, stderr, command metadata, raw verdict, parsed verdict, and failure files across success, non-zero exit, timeout, and cancellation. (verification: integration - add `tests/test_review_adapter.py` assertions inspecting `.review-gauntlet/runs/<run>/cells/<cell>/command.json`, `stdout.txt`, `stderr.txt`, `verdict.raw.json`, `verdict.json`, and `failure.json` as applicable)
- [ ] Preserve existing one-run, budget, concurrency, failure visibility, and coverage semantics. (verification: integration - keep existing tests in `tests/test_init_targets.py` passing and add regression assertions for successful cells recorded, failed/interrupted cells not marked reviewed, and `reviewed_cells` accuracy)
- [ ] Run the project check suite. (verification: manual - run `make check` from `/Users/tumf/work/review-gauntlet` and record that it passes)

## Future Work

- Consider a later, separate proposal to tune default `--budget`, default `--concurrency`, or adapter timeout defaults for LLM CLI adapters.
- Consider a later, separate proposal for richer machine-readable progress events if external orchestrators need streaming JSON lines.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-review-progress-cancellation --archive-gate`
