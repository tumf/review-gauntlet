## Implementation Tasks

- [ ] Add `checkpoint` CLI parsing and dispatch without changing existing command behavior. (verification: unit - parser/command tests in `tests/test_cli.py` confirm `checkpoint` appears in help/completion metadata and accepts `--format text|json`; completion condition: parser-visible command routes to checkpoint handler)
- [ ] Implement checkpoint status serialization from the active session. (verification: integration - new `tests/test_cli_checkpoint.py` asserts `status.json` includes session metadata, target, current `target_digest`, `last_run_target_digest`, `ruleset_digest`, coverage, finding counts, run count, finalize blockers, and next action; completion condition: JSON is deterministic and parseable)
- [ ] Implement checkpoint findings serialization for all active-session findings. (verification: integration - `tests/test_cli_checkpoint.py` seeds open and terminal findings and asserts `findings.json` includes both with stable ordering and latest occurrence details; completion condition: default terminal suppression from `findings` does not apply to checkpoint output)
- [ ] Implement checkpoint event serialization with safe metadata handling. (verification: integration - `tests/test_cli_checkpoint.py` asserts valid event metadata is parsed into JSON objects and malformed metadata is represented without crashing; completion condition: event rows are emitted in deterministic order with raw fallback evidence)
- [ ] Implement deterministic `summary.md` rendering for PR review. (verification: integration - `tests/test_cli_checkpoint.py` asserts the summary includes session ID, can-finalize state, next action, coverage table, findings table, and finalize blockers; completion condition: dynamic table cells are escaped or normalized enough to preserve Markdown structure)
- [ ] Ensure checkpoint is latest-only and side-effect limited. (verification: integration - `tests/test_cli_checkpoint.py` runs `checkpoint` twice and asserts the same `checkpoints/latest` files are overwritten, no history directory is created, and counts for runs/finding events/finding states are unchanged; completion condition: no review/mark/finalize side effects occur)
- [ ] Update `.gitignore` to track checkpoint snapshots but ignore runtime state. (verification: manual - `git check-ignore -v .review-gauntlet/ledger.sqlite` reports ignored and `git check-ignore -v .review-gauntlet/checkpoints/latest/status.json` reports not ignored after creation; completion condition: only checkpoint files are intended for Git review)
- [ ] Document the checkpoint workflow in README. (verification: manual - inspect `README.md` and run `uv run review-gauntlet checkpoint --help` to confirm documented command/options match the CLI; completion condition: README shows expected generated files and explicit `git add .review-gauntlet/checkpoints/latest` without claiming automatic Git commits)
- [ ] Run project validation. (verification: manual - `make check`; completion condition: format, lint, typecheck, and tests pass)

## Future Work

- Add optional timestamped history support such as `checkpoint --keep-history` if teams later need committed checkpoint archives.
- Add an opt-in external wrapper workflow for Git commit automation if users want it outside the core CLI.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-checkpoint-snapshots --archive-gate`
