## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

The CLI SHALL expose current session state without modifying review coverage. `status` SHALL report coverage, finding counts, target freshness, finalization readiness, and the next required action. `findings` SHALL list open findings by default, support showing all findings, and support read-only filtering by finding path and triage mark.

Session commands that emit summaries SHALL use `--format text` for human-readable output and `--format json` for structured output where supported, with `text` as the default. Commands that support decorative progress or audience-specific progress output SHALL support `--audience human|agent` for progress control. Commands that only emit a final result and no intermediate progress UI SHALL NOT expose an `--audience` option.

<!-- Expected canonical result after archive: findings documents repeatable `--path` and `--mark` filters while preserving default terminal suppression, `--all`, `--format text|json`, and rejection of `--audience`. -->

#### Scenario: Status reports next action

**Given**: an active session with reviewed cells and untriaged findings
**When**: the developer runs `review-gauntlet status --format json`
**Then**: the JSON output includes `session_id`, `session_state`, coverage counts, finding state counts, `can_finalize`, and `next_required_action`
**And**: `next_required_action` is `triage_findings`

#### Scenario: Non-progress status rejects audience option

**Given**: an active session
**When**: the developer runs `review-gauntlet status --audience agent`
**Then**: the command fails with a usage error

#### Scenario: Status rejects obsolete human format option

**Given**: an active session
**When**: the developer runs `review-gauntlet status --format human`
**Then**: the command fails with a usage error

#### Scenario: Findings hides terminal findings by default

**Given**: an active session with open and terminal findings
**When**: the developer runs `review-gauntlet findings`
**Then**: the output includes open findings
**And**: terminal findings are omitted unless `--all` is provided

#### Scenario: Findings uses text output by default

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --help`
**Then**: the help output lists `--format {text,json}`
**And**: the help output lists `--path`
**And**: the help output lists `--mark`
**And**: the help output does not list `--audience`

#### Scenario: Findings emits structured JSON on request

**Given**: an active session with findings
**When**: the developer runs `review-gauntlet findings --format json`
**Then**: stdout contains parseable JSON for the final findings result

#### Scenario: Findings filters by mark

**Given**: an active session with confirmed, reopened, and false-positive findings
**When**: the developer runs `review-gauntlet findings --mark confirmed --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only confirmed findings
**And**: no finding state is modified

#### Scenario: Findings filters by path

**Given**: an active session with findings in multiple repository paths
**When**: the developer runs `review-gauntlet findings --path src/review_gauntlet/config.py --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only findings for that path
**When**: the developer runs `review-gauntlet findings --path src/review_gauntlet/ --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only findings under that path prefix

#### Scenario: Findings combines path and mark filters

**Given**: an active session with confirmed and reopened findings across multiple paths
**When**: the developer runs `review-gauntlet findings --path src/review_gauntlet/ --mark confirmed --mark reopened --format json`
**Then**: stdout contains parseable JSON whose `findings` list contains only confirmed or reopened findings under `src/review_gauntlet/`

#### Scenario: Findings filter respects terminal visibility

**Given**: an active session with a false-positive finding
**When**: the developer runs `review-gauntlet findings --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list omits the false-positive finding
**When**: the developer runs `review-gauntlet findings --all --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list includes the false-positive finding

#### Scenario: Findings rejects obsolete audience and human format options

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --audience agent`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet findings --format human`
**Then**: the command fails with a usage error
