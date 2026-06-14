## MODIFIED Requirements

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

Command adapter configuration validation SHALL reject invalid environment variable names and SHALL define how literal braces are represented in template-bearing strings. Configuration errors SHALL be reported before adapter execution. Adapter `cwd` settings SHALL resolve under the reviewed repository root and cwd values that resolve outside the repository SHALL be rejected before executing any adapter command.

Review execution SHALL resolve configuration using deterministic precedence: built-in defaults, then global config, then project config, then explicit CLI config/options. Global config SHALL be discovered from `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` or fallback `~/.config/review-gauntlet/config.jsonc`. Project config SHALL prefer `.review-gauntlet/config.jsonc` and support `review-gauntlet.jsonc` for compatibility. Existing JSON config discovery MAY remain supported for backward compatibility. When multiple configuration layers are combined, objects SHALL deep merge, scalars SHALL use the last writer, and arrays SHALL replace earlier arrays.

Explicit `--config` SHALL accept both absolute paths and repository-relative paths. Relative explicit config paths SHALL resolve under the reviewed repository root. Absolute explicit config paths MAY point outside the repository, but the resolved path SHALL exist and be a regular file. Explicit config SHALL take precedence over global and project discovery.

Command adapter output path templates SHALL be deterministic before prompt construction. `adapter.output.path` SHALL reject `{prompt}` because the prompt itself can contain the output path and would make prompt-time and read-time path resolution diverge. The `{prompt}` template variable SHALL remain supported for adapter `args` and `env`.

#### Scenario: Adapter env keys are validated

**Given**: a command adapter config whose `env` contains an invalid key such as `BAD-NAME` or an empty string
**When**: the review command loads the config
**Then**: the config is rejected with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Output path rejects prompt template

**Given**: a command adapter config whose `adapter.output.path` contains `{prompt}`
**When**: the review command loads the config
**Then**: the config is rejected with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Prompt template remains available for argv and env

**Given**: a command adapter config whose `args` or `env` contains `{prompt}`
**When**: the review command loads the config
**Then**: the config remains valid
**And**: review execution expands `{prompt}` through the existing adapter prompt transport

#### Scenario: Template literal brace behavior is explicit

**Given**: a command adapter config string containing a literal brace sequence
**When**: the config is loaded
**Then**: review-gauntlet either accepts the documented literal escaping form or rejects the string with an actionable unsupported-template error
**And**: supported variables such as `{prompt}` continue to validate successfully

#### Scenario: Explicit absolute config path outside repository is accepted

**Given**: an active review session
**And**: `/tmp/review-gauntlet.jsonc` exists and contains a valid command adapter config
**When**: the developer runs `review-gauntlet review --config /tmp/review-gauntlet.jsonc`
**Then**: the review command loads the explicit config file
**And**: no configuration error is raised solely because the config path is outside the repository

#### Scenario: Explicit missing config path is rejected

**Given**: an active review session
**When**: the developer runs `review-gauntlet review --config /tmp/missing-review-gauntlet.jsonc`
**Then**: the command fails with an actionable configuration error
**And**: no external adapter command is executed

#### Scenario: Global and project configs are merged deterministically

**Given**: a global config with nested object fields and an array field
**And**: a project config with overlapping nested object fields and an overlapping array field
**When**: the review command resolves effective configuration
**Then**: nested object fields are deep-merged
**And**: scalar values from the project config override global scalar values
**And**: array values from the project config replace global array values rather than appending

#### Scenario: Missing config guidance is actionable

**Given**: no fixture, explicit config, project config, or global config is available
**When**: the developer runs `review-gauntlet review`
**Then**: the command fails with a usage error explaining that no Review Gauntlet config was found
**And**: the message shows how to create a project config with `review-gauntlet config init --preset opencode`
**And**: the message shows how to create a global config with `review-gauntlet config init --global --preset opencode`
**And**: the message points to `review-gauntlet config list` for available presets

#### Scenario: Adapter cwd outside repository is rejected

**Given**: an active review session with a command adapter config whose `cwd` resolves outside the repository
**When**: `review-gauntlet review` evaluates a cell
**Then**: the selected cell fails with a structured adapter failure
**And**: no command is executed from the out-of-repository working directory

## ADDED Requirements

### Requirement: Config validation and effective config inspection SHALL be available

The `review-gauntlet config` command group SHALL validate configuration files and SHOULD expose the resolved effective configuration for debugging and automation.

#### Scenario: Discovered configuration validates successfully

**Given**: a repository or user environment with a valid discoverable Review Gauntlet config
**When**: the developer runs `review-gauntlet config validate`
**Then**: the command validates JSONC parsing and schema constraints
**And**: the command exits `0`

#### Scenario: Explicit configuration validates successfully

**Given**: `/tmp/review-gauntlet.jsonc` exists and contains a valid Review Gauntlet config
**When**: the developer runs `review-gauntlet config validate --config /tmp/review-gauntlet.jsonc`
**Then**: the command validates that explicit config file
**And**: the command exits `0`

#### Scenario: Invalid configuration fails validation before adapter execution

**Given**: a config file whose command adapter command contains whitespace as a shell string
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: the command fails with an actionable validation error
**And**: no external adapter command is executed

#### Scenario: Effective config is displayed

**Given**: a global config and a project config are both present
**When**: the developer runs `review-gauntlet config effective`
**Then**: stdout displays the final merged configuration
**And**: the output reflects project config precedence over global config
