## Implementation Tasks

- [ ] Classify turn verdict finding resolutions into valid transitions, idempotent terminal no-ops, unknown IDs, and invalid transitions in `src/review_gauntlet/cli.py` without changing the existing `ALLOWED_TRANSITIONS` table semantics (verification: unit - focused tests in `tests/test_cli_run.py` assert each classification path from `validate-turn-verdict`).
- [ ] Preserve hard failures for meaning-changing terminal transitions and non-terminal invalid transitions, including diagnostics with finding ID, current state, requested state, and allowed/terminal context (verification: unit - `tests/test_cli_run.py` includes `confirmed -> dismissed`, `false_positive -> dismissed`, and `open -> false_positive` regression cases).
- [ ] Ignore idempotent terminal no-op resolutions during verdict application while preserving structured evidence of ignored finding IDs and requested states in CLI output, run metadata, or continuation metadata (verification: integration - add `tests/test_cli_run.py` coverage that writes a continuation verdict containing `dismissed -> dismissed` or `false_positive -> false_positive`, runs `validate-turn-verdict --format json`, and asserts success plus visible ignored-resolution metadata in stdout).
- [ ] Support mixed verdicts containing both valid state changes and idempotent terminal no-ops so valid changes are persisted and no-op resolutions do not block progress (verification: integration - add `tests/test_cli_run.py` coverage using `SessionStore` fixture data with one `open -> dismissed` resolution and one terminal idempotent no-op, then assert the open finding changed in `findings` and the terminal finding has no extra `finding_events` transition).
- [ ] Preserve run-controller `no_progress` behavior for stale-only successful verdicts so a verdict with only ignored no-op resolutions halts with actionable context rather than repeating the ready task (verification: integration - add `tests/test_run_controller.py` coverage that runs a stale-only verdict step and asserts `reason: no_progress`, targeted ID/task evidence, preserved verdict artifact path, and no immediate repeated step).
- [ ] Add diagnostics for stale session/verdict context when available, including the verdict path session ID and active session ID when they differ or when a stale artifact is suspected (verification: unit - add `tests/test_cli_run.py` coverage that validates a mismatched `.review-gauntlet/turns/<session_id>/...json` path against an active session and asserts output contains both session identifiers or equivalent artifact context).
- [ ] Run focused regression checks and the CI-equivalent suite after implementation (verification: manual - run `uv run pytest tests/test_cli_run.py tests/test_run_controller.py` for focused coverage and `make check` for full format/lint/typecheck/test coverage).

## Future Work

- Consider a future explicit command for reopening or reclassifying terminal findings if users need intentional terminal decision changes. That is not part of this change.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate ignore-idempotent-terminal-resolutions --archive-gate`
