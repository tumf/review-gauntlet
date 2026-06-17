## ADDED Requirements

### Requirement: Run TUI SHALL align Agent and Session summary panel heights

`review-gauntlet run` TUI SHALL render the side-by-side Agent and Session summary panel boxes at equal height within the summary row, even when one panel has more rows of content than the other. The equal-height behavior SHALL be scoped to the Agent/Session summary pair and SHALL NOT force unrelated dashboard panels to adopt the same sizing rule.

#### Scenario: Summary panels remain equal height when Agent has artifact row

**Given**: the run TUI renders the Agent and Session summary panels side by side
**And**: the Agent summary includes an optional artifact row
**When**: the summary row is laid out
**Then**: the Agent panel box height equals the Session panel box height
**And**: both panels continue to share equal horizontal width

#### Scenario: Equal-height rule is scoped to summary pair

**Given**: the run TUI renders the header, finalize checklist, Agent panel, Session panel, Activity panel, and footer
**When**: the dashboard CSS/layout is applied
**Then**: equal-height stretching applies to the Agent and Session panel containers
**And**: the common panel style does not force the finalize checklist or Activity panel to use the summary-pair sizing behavior
