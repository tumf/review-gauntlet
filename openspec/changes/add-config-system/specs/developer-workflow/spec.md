## ADDED Requirements

### Requirement: Clone-free config preset initialization SHALL be available

The `review-gauntlet` CLI SHALL provide a top-level `config` command group. The only configuration-generation command SHALL be `config init`; no top-level `setup` command SHALL be introduced. Built-in starter presets SHALL be bundled with the installed package so users do not need to clone the repository to create a starter config.

#### Scenario: Project config is initialized from a bundled preset

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config init --preset opencode`
**Then**: `.review-gauntlet/config.jsonc` is created from the bundled `opencode` preset
**And**: the command exits `0`
**And**: no repository clone or source-tree `configs/` path is required

#### Scenario: Global config is initialized from a bundled preset

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config init --global --preset opencode`
**Then**: a global config is created at `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` when `XDG_CONFIG_HOME` is set and non-empty
**And**: otherwise the global config is created at `~/.config/review-gauntlet/config.jsonc`
**And**: the command exits `0`

#### Scenario: Config init refuses accidental overwrite

**Given**: the target config path already exists
**When**: the developer runs `review-gauntlet config init --preset opencode`
**Then**: the command fails with an actionable usage error
**And**: the existing file is not overwritten

#### Scenario: Config init can force overwrite

**Given**: the target config path already exists
**When**: the developer runs `review-gauntlet config init --preset opencode --force`
**Then**: the target config is overwritten with the bundled preset contents
**And**: the command exits `0`

#### Scenario: Config init dry run has no side effects

**Given**: no project config exists
**When**: the developer runs `review-gauntlet config init --preset opencode --dry-run`
**Then**: stdout shows the target path and preset contents that would be written
**And**: no config file or parent directory is created

#### Scenario: Config init supports explicit output

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config init --preset opencode --output custom.jsonc`
**Then**: `custom.jsonc` is created from the bundled `opencode` preset
**And**: `.review-gauntlet/config.jsonc` is not created solely because of this command

### Requirement: Config presets SHALL be inspectable

The `review-gauntlet config` command group SHALL expose bundled preset names and contents without requiring repository state, active review session state, or access to the source repository's `configs/` directory.

#### Scenario: Preset names are listed

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config list`
**Then**: stdout lists exactly the preset names `claude`, `opencode`, and `codex`, one per line
**And**: the command exits `0`

#### Scenario: Preset contents are shown

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config show opencode`
**Then**: stdout contains the bundled `opencode` JSONC config contents
**And**: the command exits `0`
**And**: no config file is written

#### Scenario: Unknown preset is rejected

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config show custom`
**Then**: the command fails with the existing CLI usage-error behavior
**And**: stdout does not contain a fallback or dummy preset

### Requirement: Quick start documentation SHALL not require repository clone for config

Repository documentation SHALL describe a clone-free quick start where users can create starter configuration from bundled presets using the installed or `uvx` CLI. Source installation guidance MAY remain for contributors, but it SHALL NOT be required merely to obtain starter configuration.

#### Scenario: README documents clone-free quick start

**Given**: a developer reads the repository README
**When**: they follow the quick start section
**Then**: the guidance starts with `uvx review-gauntlet config init --preset opencode`
**And**: continues with `uvx review-gauntlet init`, `uvx review-gauntlet review`, and `uvx review-gauntlet status`
**And**: the quick start does not require `git clone` or `cp configs/...` merely to create starter config

#### Scenario: README documents global setup

**Given**: a developer reads the repository README
**When**: they follow the global setup guidance
**Then**: the guidance shows `uvx review-gauntlet config init --global --preset opencode`
**And**: the guidance explains that this creates user-specific defaults separate from project review configuration
