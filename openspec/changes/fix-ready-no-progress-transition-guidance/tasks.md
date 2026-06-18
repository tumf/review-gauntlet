## Implementation Tasks

- [ ] Update resolve ready prompt state guidance in `src/review_gauntlet/cli.py` so each active finding lists only its currently allowed target states and open findings explain that false positives/non-issues must be recorded as `dismissed` with `dismiss_reason`. (completion: generated open-finding ready prompts no longer contain the static invalid state list and include `confirmed` / `dismissed` guidance for open findings; verification: unit - add or update CLI prompt tests covering open finding ready prompt text)

- [ ] Make invalid transition diagnostics actionable in `src/review_gauntlet/cli.py` by ensuring validation errors include the active session, finding ID, current state, requested state, and a concise allowed-transition hint. (completion: invalid resolution verdict validation fails with a structured/actionable message that identifies the attempted invalid transition; verification: unit - add or update turn verdict validation tests for `open -> false_positive`)

- [ ] Preserve `RunController.run()` no-progress protection while improving returned failure context for successful-looking verdicts that leave the targeted state unchanged. (completion: no-progress failures still stop the run, include `reason: no_progress`, and expose the task key, target IDs, and artifact context needed to inspect the rejected/no-op verdict; verification: unit - update `tests/test_run_controller.py` to assert no-progress failure metadata for unchanged targeted state)

- [ ] Verify valid open finding resolution still progresses through the existing ledger and finalize gate behavior. (completion: `dismissed` and `confirmed` resolutions from open findings update finding state and reduce open finding counts as before; verification: integration - add or update CLI/session tests that process a valid resolution verdict and assert changed status output)

- [ ] Run the project quality gate. (verification: integration - `make check`; completion: formatting, linting, type checking, and tests all pass)

## Future Work

- Consider a separate product decision on whether the historical terminal states `false_positive`, `accepted_risk`, and `waived` should remain in the public resolution schema or be hidden from resolve-phase agents entirely.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate fix-ready-no-progress-transition-guidance --archive-gate`
