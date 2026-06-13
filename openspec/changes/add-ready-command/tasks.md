## Implementation Tasks

- [ ] Add parser and dispatch support for `review-gauntlet ready [root] --format text|json` in `src/review_gauntlet/cli.py` without changing existing `status` output. (verification: unit - add or update `tests/test_cli.py` and/or `tests/test_cli_ready.py` so `main(["ready", ...])` is accepted, supports text/json formats, and `main(["status", ..., "--format", "json"])` retains its existing key set without a `prompt` field)
- [ ] Implement read-only ready prompt selection from the active session ledger using deterministic priority order: reopened, untriaged, confirmed, fixed-pending verification, stale review cell, pending review cell, finalize. (verification: unit - add `tests/test_cli_ready.py` cases that construct sessions with each state and assert the selected prompt category follows the required priority order)
- [ ] Emit only the prompt contract for `ready`: JSON as exactly `{ "prompt": string|null }`, text as the prompt body or `no ready task`. (verification: integration - add `tests/test_cli_ready.py` assertions that parse `main(["ready", ..., "--format", "json"])`, assert the sole key is `prompt`, and assert text output has no additional labels or task metadata)
- [ ] Keep every non-null ready prompt skill-directed and short, beginning with `Use the review-gauntlet task execution skill.` and containing the work category plus stop condition rather than detailed command procedures. (verification: unit - add `tests/test_cli_ready.py` assertions that generated prompt templates share the prefix and do not contain task IDs, claim language, release language, or queue metadata)
- [ ] Include git-commit-before-finalize guidance in the finalize prompt while keeping `ready` non-mutating. (verification: unit - add `tests/test_cli_ready.py` finalize-ready coverage asserting the prompt mentions committing intended git changes before finalizing, and that `.review-gauntlet/checkpoints/latest/` is not written by `ready`)
- [ ] Preserve read-only behavior for ready invocations across findings, review cells, runs, events, checkpoints, and git state. (verification: integration - add `tests/test_cli_ready.py` checks that snapshot SQLite counts for `runs`, `finding_events`, `findings`, and `review_cells` before/after `main(["ready", ...])`, then assert no counts or states changed)
- [ ] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Future Work

- Create or update the external review-gauntlet task execution skill so agents know the concrete procedures for each short ready prompt.
- Consider a separate proposal for focused `review --cell <cell_id>` execution if future ready prompts need cell-specific targeting.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate add-ready-command --strict`
Expected archive gate: `cflx openspec validate add-ready-command --archive-gate`
