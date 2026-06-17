## ADDED Requirements

### Requirement: Run TUI SHALL display actionable finding counts

`review-gauntlet run` TUI SHALL derive visible open finding counts from actionable live finding states instead of requiring an `open` aggregate key in status output. The displayed open count SHALL equal the sum of `reopened`, `untriaged`, `confirmed`, and `fixed_pending_verification`. When the derived open count is non-zero, the Session panel SHALL include a concise action breakdown for triage, fix, and verify work.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require run TUI findings summaries to expose actionable live finding work from state counts, preventing hidden incomplete finding state when no `open` aggregate exists. -->

#### Scenario: TUI derives open findings from actionable state counts

**Given**: an active run snapshot whose finding state counts include untriaged, confirmed, reopened, or fixed-pending verification findings
**And**: the finding state counts do not include an `open` key
**When**: the run TUI renders the Session panel
**Then**: the displayed findings summary includes an open count equal to the sum of those actionable states
**And**: the summary does not display `open 0` while actionable findings exist

#### Scenario: TUI shows action-oriented finding breakdown

**Given**: an active run snapshot with actionable findings requiring triage, fixing, or verification
**When**: the run TUI renders the Session panel
**Then**: the findings summary includes the derived open count
**And**: the summary distinguishes triage work from confirmed-fix work and fixed-pending verification work

#### Scenario: TUI preserves clear state when no actionable findings exist

**Given**: an active run snapshot with no reopened, untriaged, confirmed, or fixed-pending verification findings
**When**: the run TUI renders the Session panel and findings detail text
**Then**: the displayed open finding count is `0`
**And**: the TUI does not invent triage, fix, or verification work
