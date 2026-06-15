## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`review-gauntlet run` SHALL continue to expose the existing Textual dashboard behavior for interactive text executions, with panel section names rendered as Textual border titles rather than as the first line of each panel's body text. Titled dashboard panels SHALL assign concise section labels such as `Finalize path`, `Session metrics`, `Findings`, `Current operation`, and `Activity` through `border_title` or an equivalent Textual border-title mechanism on bordered widgets or containers. Body content for those panels SHALL start with the panel's actual data rows or empty-state content, not a repeated heading row. Non-Textual compact summaries MAY still include explicit section labels through separate titled-section formatting helpers, but those helpers SHALL NOT force heading rows back into the interactive TUI body widgets.

<!-- Expected canonical result after archive: the canonical review-sessions spec will additionally require Textual run TUI dashboard panel labels to be rendered via border titles, with section body text kept free of duplicated heading rows while compact non-Textual summaries retain explicit labels through separate formatting. -->

#### Scenario: Run TUI renders panel section names as border titles

**Given**: an interactive `review-gauntlet run` execution is eligible for the Textual TUI
**When**: the TUI renders the dashboard panels for finalize path, session metrics, findings, current operation, and activity
**Then**: each panel's section name is assigned through a Textual border title on the bordered panel widget or container
**And**: the panel body begins with the panel content rather than repeating the section name as the first body row
**And**: normal, active, blocked, failed, and finalized panel states retain semantic border and border-title styling

#### Scenario: Compact non-Textual summaries retain explicit section labels

**Given**: a non-Textual compact dashboard summary is constructed from run TUI helper functions
**When**: the summary is rendered for tests or fallback text output
**Then**: the summary can still include section labels such as `Finalize path`, `Session metrics`, `Findings`, `Current operation`, and `Activity`
**And**: those labels are added by explicit titled-section formatting rather than by the interactive TUI body helpers embedding heading rows
