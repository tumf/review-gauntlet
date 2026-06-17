## ADDED Requirements

### Requirement: Run TUI SHALL use an explicit dark background

`review-gauntlet run` SHALL render the interactive TUI with an explicitly dark dashboard background rather than relying on Textual default backgrounds. The dark styling SHALL cover the screen and the primary dashboard surfaces while preserving existing brand accents, semantic status colors, panel titles, layout, and run behavior.

#### Scenario: Run TUI renders dark dashboard surfaces

**Given**: `review-gauntlet run` selects the interactive TUI path
**When**: the TUI application is constructed
**Then**: the Textual CSS defines an explicit dark background for the screen
**And**: the header, panel, body, and controls surfaces use dark-compatible background styling
**And**: the existing brand accent and semantic status colors remain available

#### Scenario: Dark styling does not change non-TUI behavior

**Given**: `review-gauntlet run` is executed with JSON output or with TUI disabled
**When**: the run result is rendered
**Then**: output selection and non-TUI rendering behavior remain unchanged
**And**: run controller state, session state, findings state, and finalization behavior are not modified by the dark TUI styling
