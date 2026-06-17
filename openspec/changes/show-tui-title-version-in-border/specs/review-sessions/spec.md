## ADDED Requirements

### Requirement: Run TUI SHALL display title and version in the header border

`review-gauntlet run` SHALL render the interactive TUI top header title as the `#session_header` border title. The border title SHALL include the Review Gauntlet brand marker, product name, and current package version sourced from the package version metadata. The TUI header body SHALL remain focused on run status and metadata, while non-TUI compact/text rendering SHALL remain self-describing with title, status, and metadata text.

<!-- Expected canonical result after archive: the canonical review-sessions spec will require the run TUI top header to use a versioned border title instead of rendering the product title as ordinary header body content. -->

#### Scenario: TUI header uses versioned border title

**Given**: `review-gauntlet run` selects the interactive TUI path
**When**: the TUI application is constructed
**Then**: the top `#session_header` panel has a border title containing the brand marker, `Review Gauntlet`, and the current package version
**And**: the header body does not render the title as a separate first-line body widget
**And**: the header body still renders run status and metadata

#### Scenario: Version comes from package metadata

**Given**: the package exposes `review_gauntlet.__about__.__version__`
**When**: the run TUI header title is rendered
**Then**: the version shown in the header title matches the package version metadata
**And**: changing the package version source changes the displayed TUI title version without editing a duplicate literal in the TUI title implementation

#### Scenario: Compact text output remains self-describing

**Given**: run dashboard text is rendered outside the interactive TUI border-title context
**When**: compact or fallback dashboard text is generated
**Then**: the text output includes the title, status, and metadata lines
**And**: the output remains readable without relying on a graphical border title
