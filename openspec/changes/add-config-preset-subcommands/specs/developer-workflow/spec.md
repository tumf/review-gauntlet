## MODIFIED Requirements

### Requirement: Config presets SHALL be inspectable

The `review-gauntlet config preset` command group SHALL expose bundled preset names and contents without requiring repository state, active review session state, or access to the source repository's `configs/` directory.

<!-- Expected canonical result after archive: preset inspection scenarios use `review-gauntlet config preset list` and `review-gauntlet config preset show <preset>` instead of top-level `config list` and `config show`. -->

#### Scenario: Preset names are listed

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config preset list`
**Then**: stdout lists exactly the preset names `claude`, `opencode`, and `codex`, one per line
**And**: the command exits `0`

#### Scenario: Preset names are listed as JSON

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config preset list --format json`
**Then**: stdout contains JSON with a `presets` array containing exactly `claude`, `opencode`, and `codex`
**And**: the command exits `0`

#### Scenario: Preset contents are shown

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config preset show opencode`
**Then**: stdout contains the bundled `opencode` JSONC config contents
**And**: the command exits `0`
**And**: no config file is written

#### Scenario: Unknown preset is rejected

**Given**: an installed or `uvx` invocation of `review-gauntlet`
**When**: the developer runs `review-gauntlet config preset show custom`
**Then**: the command fails with the existing CLI usage-error behavior
**And**: stdout does not contain a fallback or dummy preset
