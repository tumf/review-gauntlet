## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

The CLI SHALL expose current session state without modifying review coverage. `status` SHALL report coverage, finding counts, target freshness, finalization readiness, and the next required action. `findings` SHALL list open findings by default and support showing all findings.

Session commands that emit summaries SHALL use `--format json` for structured output where supported. Commands that support decorative progress or audience-specific human output SHALL support `--audience agent` for automation-safe output. Because `findings` emits only a final result and no intermediate progress UI, `findings` SHALL NOT expose an `--audience` option. `findings` SHALL use `--format text` for human-readable output and `--format json` for structured output, with `text` as the default.

#### Scenario: Status reports next action

**Given**: an active session with reviewed cells and untriaged findings
**When**: the developer runs `review-gauntlet status --format json --audience agent`
**Then**: the JSON output includes `session_id`, `session_state`, coverage counts, finding state counts, `can_finalize`, and `next_required_action`
**And**: `next_required_action` is `triage_findings`

#### Scenario: Agent audience suppresses decorative output

**Given**: an active session
**When**: the developer runs `review-gauntlet status --format json --audience agent`
**Then**: stdout contains only parseable JSON for the final status result
**And**: stdout does not include progress bars, spinners, markdown headings, or explanatory prose

#### Scenario: Findings hides terminal findings by default

**Given**: an active session with open and terminal findings
**When**: the developer runs `review-gauntlet findings`
**Then**: the output includes open findings
**And**: terminal findings are omitted unless `--all` is provided

#### Scenario: Findings uses text output by default

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --help`
**Then**: the help output lists `--format {text,json}`
**And**: the help output does not list `--audience`

#### Scenario: Findings emits structured JSON on request

**Given**: an active session with findings
**When**: the developer runs `review-gauntlet findings --format json`
**Then**: stdout contains parseable JSON for the final findings result

#### Scenario: Findings rejects obsolete audience and human format options

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --audience agent`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet findings --format human`
**Then**: the command fails with a usage error
