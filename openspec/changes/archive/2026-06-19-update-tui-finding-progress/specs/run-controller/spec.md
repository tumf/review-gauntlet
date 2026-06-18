## ADDED Requirements

### Requirement: Run TUI SHALL render cell finding progress as resolved over total

The `review-gauntlet run` TUI cells view SHALL render per-cell finding progress as resolved findings over total findings. A resolved finding is any finding whose state is terminal according to the review-session finding model. Open or otherwise non-terminal findings SHALL NOT contribute to the resolved numerator. The total denominator SHALL remain the total findings attached to the cell.

This display requirement SHALL NOT change actionable finding counting used for queue prioritization, actionable queue selection, or explanatory `why` text.

#### Scenario: Mixed finding states render resolved-over-total progress

**Given**: a run TUI cell entry with three attached findings
**And**: two attached findings are in terminal states
**And**: one attached finding is open
**When**: the cells view renders the cell entry
**Then**: the entry displays `findings 2/3 resolved`
**And**: it does not display the actionable/open count as the progress numerator

#### Scenario: Actionable counts remain available for queue behavior

**Given**: a run TUI projection has a cell with one open finding and one resolved finding
**When**: the TUI builds priority, queue, and explanatory text from that projection
**Then**: actionable queue behavior may continue to use the open finding count
**And**: the cells view progress still renders resolved findings over total findings

<!-- Expected canonical result after archive: the run-controller spec will require run TUI cell finding progress to show resolved finding count over total finding count while preserving actionable finding counts for prioritization and explanations. -->
