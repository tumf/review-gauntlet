## ADDED Requirements

### Requirement: Run TUI finalized summary SHALL show changed-file fixed outcomes

When `review-gauntlet run` reaches finalized state, the finalized TUI summary SHALL distinguish changed-file fix outcomes from general review completion. The summary SHALL list only files detected as changed since review, SHALL count and list only findings on those changed files whose state is `fixed_pending_verification` or `fixed_verified`, and SHALL NOT include findings closed by confirmation, dismissal, false-positive classification, accepted risk, waiver, or other non-fixed states in the fixed-finding summary.

The finalized summary SHALL continue to display final coverage, run metadata, checkpoint summary, and replace operational panels in finalized mode. Empty changed-file or fixed-finding sets SHALL be rendered explicitly rather than inferred from fully reviewed coverage.

<!-- Expected canonical result after archive: the run-controller spec will require the finalized run TUI summary to report changed files and fixed findings only, preserving finalized panel behavior while avoiding broad resolved/decision terminology. -->

#### Scenario: Finalized summary lists only changed files

**Given**: a finalized run TUI snapshot whose coverage projection contains queue entries for `src/changed.py` and `src/unchanged.py`
**And**: only the `src/changed.py` queue entry has `changed_since_review == True`
**When**: the finalized summary renders
**Then**: the summary lists `src/changed.py` under changed files
**And**: the summary does not list `src/unchanged.py` as a changed or resolved file

#### Scenario: Finalized summary shows explicit empty changed files

**Given**: a finalized run TUI snapshot whose coverage projection has no queue entries with `changed_since_review == True`
**When**: the finalized summary renders
**Then**: the changed files value is an explicit empty value such as `none`
**And**: fully reviewed but unchanged files are not shown as changed files

#### Scenario: Finalized summary lists only fixed findings on changed files

**Given**: a finalized run TUI snapshot with changed file `src/changed.py`
**And**: findings on that file include states `fixed_pending_verification`, `fixed_verified`, `confirmed`, `dismissed`, `false_positive`, `accepted_risk`, `waived`, `open`, and `untriaged`
**When**: the finalized summary renders finding count, rules, and finding IDs
**Then**: only the `fixed_pending_verification` and `fixed_verified` finding IDs appear
**And**: the fixed finding count equals the number of displayed fixed finding IDs
**And**: the rule list includes only rules represented by those displayed fixed findings

#### Scenario: Finalized summary excludes fixed findings from unchanged files

**Given**: a finalized run TUI snapshot with changed file `src/changed.py` and unchanged file `src/unchanged.py`
**And**: `src/unchanged.py` has a finding in state `fixed_verified`
**When**: the finalized summary renders finding IDs
**Then**: the fixed finding from `src/unchanged.py` does not appear

#### Scenario: Compact finalized output uses the same filtered summary

**Given**: a finalized run TUI snapshot with changed and unchanged files and mixed finding states
**When**: compact dashboard text renders the finalized summary
**Then**: the compact output uses the same changed-file and fixed-finding filters as the finalized TUI summary section
