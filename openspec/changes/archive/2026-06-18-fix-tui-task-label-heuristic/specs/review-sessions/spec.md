## ADDED Requirements

### Requirement: Run TUI SHALL derive task labels from structured action signals

`review-gauntlet run` interactive TUI SHALL determine the current task label and Activity `step_started` detail from the structured `next_required_action` signal and coverage/finding counts, not by scanning the ready prompt body text. The TUI SHALL NOT use keyword matching, substring search, or any natural-language parsing of the ready prompt to classify the task kind. When `next_required_action` is `run_review`, the TUI SHALL distinguish `REVIEW PENDING CELLS` from `REVIEW STALE CELLS` by checking whether `coverage.pending > 0` or `coverage.stale > 0` respectively. When `next_required_action` is missing or holds an unknown value, the TUI SHALL display `READY TASK` without misclassifying the task.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI to derive task labels from next_required_action and coverage counts, and will prohibit ready-prompt text parsing for task classification. -->

#### Scenario: Pending review cells display REVIEW PENDING CELLS despite prompt containing confirmed and fix

**Given**: an active review session with pending review cells and no confirmed findings
**And**: `next_required_action` is `run_review`
**And**: the ready prompt body contains the words `confirmed` and `fix` (as part of review workflow instructions)
**When**: `review-gauntlet run` renders the TUI current-task display
**Then**: the task label is `REVIEW PENDING CELLS`
**And**: the task label is not `FIX CONFIRMED FINDING`

#### Scenario: Stale review cells display REVIEW STALE CELLS

**Given**: an active review session with stale review cells, no pending cells, and no actionable findings
**And**: `next_required_action` is `run_review`
**And**: `coverage.pending` is `0` and `coverage.stale` is greater than `0`
**When**: `review-gauntlet run` renders the TUI current-task display
**Then**: the task label is `REVIEW STALE CELLS`

#### Scenario: Confirmed findings display FIX CONFIRMED FINDING only when action matches

**Given**: an active review session with confirmed findings
**And**: `next_required_action` is `fix_confirmed_findings`
**When**: `review-gauntlet run` renders the TUI current-task display
**Then**: the task label is `FIX CONFIRMED FINDING`

#### Scenario: Unknown action displays READY TASK

**Given**: a `RunSnapshot` whose `next_required_action` is `None` or an unrecognized string
**When**: the TUI renders the current-task display
**Then**: the task label is `READY TASK`
**And**: no keyword matching is performed on the ready prompt body

#### Scenario: Activity step_started detail uses action from event payload

**Given**: a `step_started` event with `next_required_action` in its payload
**When**: the Activity timeline renders the event detail
**Then**: the detail label is derived from `next_required_action`
**And**: the detail is not derived by parsing the `prompt` field of the event payload
