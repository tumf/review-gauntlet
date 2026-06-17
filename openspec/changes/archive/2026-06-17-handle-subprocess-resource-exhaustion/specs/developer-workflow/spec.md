## MODIFIED Requirements

### Requirement: CLI help SHALL disclose meaningful default values

The `review-gauntlet` CLI SHALL include meaningful parser defaults in subcommand help text so developers can understand default behavior without inspecting source code. Defaults SHALL be shown for optional positional roots, output formats, numeric limits, concurrency, audience selection, boolean flags, repeatable filters, and empty metadata strings when those defaults already exist in the parser. Help output SHALL NOT invent default text for required positional arguments or optional arguments where the absence of a value has command-specific semantics that would be misleading to describe as a concrete default.

#### Scenario: Help shows common defaults

**Given**: an installed or development invocation of the `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet review --help`
**Then**: stdout includes help for `root` indicating `default: .`
**And**: stdout includes help for `--format` indicating `default: text`
**And**: stdout includes help for `--budget` indicating `default: 50`
**And**: stdout includes help for `--concurrency` indicating `default: 3`
**And**: stdout includes help for `--audience` indicating `default: human`

#### Scenario: Verify-fixes help shows concurrency default

**Given**: an installed or development invocation of the `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet verify-fixes --help`
**Then**: stdout includes help for `--concurrency` indicating `default: 3`
**And**: stdout includes help for `--format` indicating `default: text`

#### Scenario: Help shows repeatable and boolean defaults

**Given**: an installed or development invocation of the `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet findings --help`
**Then**: stdout includes help for `root` indicating `default: .`
**And**: stdout includes help for `--all` indicating `default: false`
**And**: stdout includes help for repeatable filters such as `--path` and `--mark` indicating `default: none`
**And**: stdout includes help for `--format` indicating `default: text`

#### Scenario: Help-only change preserves CLI behavior

**Given**: the existing `review-gauntlet` subcommands and flags
**When**: developers run supported subcommands with or without explicit flag values
**Then**: their accepted arguments, parser defaults, usage-error exits, output formats, shell completion option discovery, and session behavior remain unchanged by the help text additions, except that review and verify-fixes now default concurrency to `3`
