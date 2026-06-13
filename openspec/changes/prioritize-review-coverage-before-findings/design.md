# Design: Coverage-First Continuation Priority

## Current Behavior

The CLI currently computes continuation priority from independent review-cell and finding-state counts. Live findings are selected before review coverage work, so a partial review pass that produces untriaged findings can cause orchestrators to triage those findings while many review cells remain pending.

## Target Behavior

Continuation priority should reflect phase completion:

1. Finish the review coverage phase for the current target.
2. Then process the finding phase using the existing finding-state priority order.
3. Then resolve finalization blockers and finalize.

This does not change the durability model. Review cell states and finding states remain independent ledger facts; only the actionable next step exposed through `status` and `ready` changes.

## Integration Points

- `_next_action()` controls `status --format json` and review command result summaries that include status fields.
- `_ready_prompt()` controls orchestration prompts and exit status behavior for `ready`.
- `_finalize_reasons()` remains unchanged so blockers continue to expose all incomplete work, not only the selected next action.

## Verification Strategy

Unit tests should exercise mixed states directly because the regression is a priority-order issue rather than adapter behavior. The key regression state is:

- `coverage.pending > 0`
- `finding_state_counts.untriaged > 0`

The expected result is review work as the next action while blockers still list both incomplete coverage and untriaged findings.
