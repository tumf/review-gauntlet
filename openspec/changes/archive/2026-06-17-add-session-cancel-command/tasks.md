## Implementation Tasks

- [x] Add a durable session cancellation API in the session layer (completion: repository code can mark the active session state as `cancelled`, validate exactly one session row changed, and remove `.review-gauntlet/active-session.json` only after the state update succeeds; verification: unit - add focused tests around `SessionStore` cancellation behavior or CLI-observable ledger state in `tests/test_cli.py` / a session-store test).

- [x] Expose `review-gauntlet cancel` in the CLI parser and dispatch path (completion: `review-gauntlet cancel [root] --format json` is accepted by the parser, invokes the session cancellation API, and returns `session_id` plus `session_state: cancelled` without creating review work; verification: integration - add CLI tests that run `init`, then `cancel --format json`, and assert output fields plus exit code success).

- [x] Preserve explicit no-active-session behavior after cancellation (completion: after `cancel`, `status`, `review`, and `ready` without a new `init` fail through the same actionable no-active-session path used when no active marker exists; verification: integration - add tests that cancel a session and then assert follow-up session commands exit non-zero with the existing no-active-session guidance).

- [x] Prove cancellation does not masquerade as finalization or review execution (completion: cancellation creates no run rows, writes no checkpoint artifacts, and does not mark coverage or findings as reviewed/finalized; verification: integration - add assertions against `.review-gauntlet/ledger.sqlite` and `.review-gauntlet/checkpoints/` after `cancel`).

- [x] Document cancellation in the review lifecycle docs (completion: `README.md` and `README.ja.md` describe `review-gauntlet cancel` as the supported way to abandon an accidental `init`, distinct from `finalize`; verification: manual - inspect docs to confirm the command appears near lifecycle guidance and does not imply checkpoint creation).

- [x] Run the project quality gate (verification: integration - execute `make check` and confirm it exits 0; completion: formatting, linting, type checking, and tests all pass using the repository CI-equivalent command).

## Future Work

- Support cancellation of actively running external adapter processes if review execution is later made long-lived or daemonized.
- Add multi-session administration commands if cancelled-session history needs human-facing inspection beyond the ledger.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-session-cancel-command --archive-gate`
