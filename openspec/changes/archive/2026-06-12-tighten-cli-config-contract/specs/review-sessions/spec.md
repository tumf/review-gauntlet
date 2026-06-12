## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

#### Scenario: Findings mark filter matches hyphenated public state

**Given**: an active session with a `false_positive` finding
**When**: the developer runs `review-gauntlet findings --all --mark false-positive --format json`
**Then**: stdout contains parseable JSON whose `findings` list includes that false-positive finding
**And**: no finding state is modified

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

Command adapter configuration validation SHALL reject invalid environment variable names and SHALL define how literal braces are represented in template-bearing strings. Configuration errors SHALL be reported before adapter execution.

#### Scenario: Adapter env keys are validated

**Given**: a command adapter config whose `env` contains an invalid key such as `BAD-NAME` or an empty string
**When**: the review command loads the config
**Then**: the config is rejected with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Template literal brace behavior is explicit

**Given**: a command adapter config string containing a literal brace sequence
**When**: the config is loaded
**Then**: review-gauntlet either accepts the documented literal escaping form or rejects the string with an actionable unsupported-template error
**And**: supported variables such as `{prompt}` continue to validate successfully

## ADDED Requirements

### Requirement: CI runtime SHALL be pinned to the project Python version

Repository CI SHALL install the Python runtime declared by project guidance rather than the latest interpreter available to the package manager.

#### Scenario: CI installs Python 3.11

**Given**: the GitHub Actions workflow for repository checks
**When**: CI sets up Python with `uv`
**Then**: the workflow installs Python 3.11 explicitly
**And**: dependency resolution, linting, type checking, and tests run against that runtime
