## Implementation Tasks

- [x] Update `src/review_gauntlet/cli.py::_next_action()` so `pending` review cells return `run_review` before finding work, but `stale` review cells are considered after untriaged/reopened, confirmed, and fixed-pending finding states. (verification: unit - status JSON tests assert pending plus findings selects `run_review`, while stale plus findings selects the relevant finding action)
- [x] Update `src/review_gauntlet/cli.py::_ready_prompt()` to mirror the pending-first priority order used by `_next_action()`. (verification: unit - ready prompt tests assert pending plus findings prompts pending review, while stale plus findings prompts triage/fix/verification before stale review)
- [x] Preserve stale-only review reachability after finding work is exhausted. (verification: unit - ready/status tests assert stale-only sessions still select review work and stale review prompt)
- [x] Preserve conservative blocker visibility for mixed states. (verification: unit - status JSON tests assert blockers still include both stale/pending coverage blockers and live finding blockers regardless of which next action is selected)
- [x] Run the project quality gate. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate prioritize-pending-before-findings --archive-gate`
