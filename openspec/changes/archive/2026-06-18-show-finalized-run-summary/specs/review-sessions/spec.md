## ADDED Requirements

### Requirement: Run TUI SHALL show a finalized work summary

`review-gauntlet run` interactive TUI SHALL replace operational next-action panels with a completion-oriented work summary when the run reaches finalized status. The finalized summary SHALL preserve and display the final coverage percentage, reviewed/total cell counts, elapsed runtime, run step count, checkpoint commit metadata when available, resolved finding totals, resolved files, associated rule IDs, and finding IDs. The summary SHALL use explicit zero or none wording for categories that have no values, and SHALL NOT infer success for unknown categories.

The finalized summary SHALL be derived from system-recorded session state, final run result metadata, and checkpoint metadata rather than from an LLM self-report. The normal running, idle, blocked, and failed TUI views SHALL continue to show their operational panels.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the finalized run TUI to present preserved final session outcomes and achievements instead of actionable review-operation panels. -->

#### Scenario: Finalized TUI preserves final progress

**Given**: a run TUI snapshot whose agent status is `finalized`
**And**: the final preserved session coverage is 174 terminal cells out of 200 total cells
**When**: the TUI renders the finalized header and summary
**Then**: the visible progress shows the final non-zero coverage derived from 174/200 cells
**And**: the TUI does not render `0%` solely because the active session file no longer exists

#### Scenario: Finalized TUI highlights completed work

**Given**: a finalized run with resolved findings across multiple files and rules
**And**: the run result includes checkpoint commit metadata
**When**: the TUI renders the finalized summary
**Then**: the summary includes elapsed time and run step count
**And**: the summary includes the checkpoint commit short SHA or an explicit commit-unavailable reason
**And**: the summary includes resolved finding count, resolved file paths, associated rule IDs, and finding IDs

#### Scenario: Finalized TUI hides operational panels

**Given**: a run TUI view whose state class is finalized
**When**: the TUI render sections are built
**Then**: queue, rule coverage, file hotlist, findings projection, and activity content are not rendered as active operational panels
**And**: the finalized summary is the primary body content

#### Scenario: Non-finalized TUI keeps operational panels

**Given**: a run TUI view whose state is running, idle, blocked, or failed
**When**: the TUI render sections are built
**Then**: the existing queue, rule coverage, file hotlist, findings, and activity render paths remain available according to the current active view
**And**: no finalized work summary replaces those panels

#### Scenario: Empty finalized summary categories are explicit

**Given**: a finalized run with no resolved findings and no checkpoint commit SHA
**When**: the TUI renders the finalized summary
**Then**: the summary explicitly reports zero resolved findings or equivalent none wording
**And**: the summary explicitly reports that no checkpoint commit is available or why it was skipped
**And**: it does not omit those categories silently
