## ADDED Requirements

### Requirement: Local CLI install SHALL be available through Make

The repository SHALL provide a `make install` workflow that installs the local package as a uv tool and exposes the canonical `review-gauntlet` command. The install workflow SHALL NOT introduce or document the typo command name `review-guantlet`.

#### Scenario: Make install installs the canonical CLI

**Given**: a developer is in the repository root with `uv` available
**When**: they run `make install`
**Then**: the Make target invokes `uv tool install .`
**And**: the installed executable is the canonical `review-gauntlet` command declared by package metadata
**And**: no `review-guantlet` alias is added

#### Scenario: Installed CLI help is documented

**Given**: a developer reads the repository README
**When**: they follow the local CLI install guidance
**Then**: the guidance tells them to run `make install`
**And**: the guidance verifies the installed command with `review-gauntlet --help`
**And**: the guidance does not instruct them to use `review-guantlet`
