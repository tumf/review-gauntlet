## MODIFIED Requirements

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

Command adapter configuration validation SHALL reject invalid environment variable names and SHALL define how literal braces are represented in template-bearing strings. Configuration errors SHALL be reported before adapter execution. Adapter `cwd` settings SHALL resolve under the reviewed repository root and cwd values that resolve outside the repository SHALL be rejected before executing any adapter command.

Review execution SHALL resolve configuration using deterministic precedence: built-in defaults, then global config, then project config, then explicit CLI config/options. Global config SHALL be discovered from `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` or fallback `~/.config/review-gauntlet/config.jsonc`. Project config SHALL prefer `.review-gauntlet/config.jsonc` and support `review-gauntlet.jsonc` for compatibility. Existing JSON config discovery MAY remain supported for backward compatibility. When multiple configuration layers are combined, objects SHALL deep merge, scalars SHALL use the last writer, and arrays SHALL replace earlier arrays. When no usable config is available, the failure guidance SHALL point to `review-gauntlet config preset list` for available bundled presets.

Explicit `--config` SHALL accept both absolute paths and repository-relative paths. Relative explicit config paths SHALL resolve under the reviewed repository root. Absolute explicit config paths MAY point outside the repository, but the resolved path SHALL exist and be a regular file. Explicit config SHALL take precedence over global and project discovery.

Command adapter output path templates SHALL be deterministic before prompt construction. `adapter.output.path` SHALL reject `{prompt}` because the prompt itself can contain the output path and would make prompt-time and read-time path resolution diverge. The `{prompt}` template variable SHALL remain supported for adapter `args` and `env`.

Command adapter configuration SHALL provide bounded execution defaults for autonomous agents. `adapter.timeout_seconds` SHALL default to 3600 seconds when not explicitly configured. `adapter.quiet_timeout_seconds` SHALL default to 600 seconds when not explicitly configured. Both timeout fields SHALL reject non-finite or non-positive values before adapter execution.

<!-- Expected canonical result after archive: command adapter configuration documents default overall timeout as 3600 seconds and default quiet timeout as 600 seconds, with validation requirements for both fields. -->

#### Scenario: Default adapter timeouts are applied

**Given**: a valid command adapter configuration omits `timeout_seconds` and `quiet_timeout_seconds`
**When**: Review Gauntlet loads the effective configuration
**Then**: `adapter.timeout_seconds` is `3600.0`
**And**: `adapter.quiet_timeout_seconds` is `600.0`

#### Scenario: Explicit adapter timeouts override defaults

**Given**: a valid command adapter configuration explicitly sets `timeout_seconds` and `quiet_timeout_seconds`
**When**: Review Gauntlet loads the effective configuration
**Then**: the configured timeout values are preserved
**And**: default timeout values do not override the explicit values

#### Scenario: Invalid quiet timeout fails validation before execution

**Given**: a command adapter configuration whose `quiet_timeout_seconds` value is zero, negative, NaN, or infinite
**When**: `review-gauntlet config validate` or an adapter-backed command loads that configuration
**Then**: configuration validation fails with an actionable error
**And**: no external adapter command is executed

### Requirement: Run agent failures SHALL display distinct failure reasons

`review-gauntlet run` SHALL preserve and display distinct external-agent and orchestration failure reasons instead of collapsing them into misleading timeout or generic failure labels. Timeout wording SHALL be reserved for actual timeout failures, and configured timeout details SHALL be rendered concisely without duplicated or unset wording.

Quiet timeout caused by lack of stdout/stderr output SHALL remain distinguishable from overall wall-clock command timeout in structured run results and artifacts, while human-facing terminal TUI wording MAY present both as timeout-family failures.

<!-- Expected canonical result after archive: run failure semantics distinguish `quiet_timeout` from overall `timeout` while preserving timeout-family terminal display. -->

#### Scenario: Quiet timeout remains distinct from overall command timeout

**Given**: a configured command adapter subprocess is still running
**And**: the subprocess has produced no stdout or stderr output for `adapter.quiet_timeout_seconds`
**And**: the overall `adapter.timeout_seconds` deadline has not been reached
**When**: `review-gauntlet run` enforces adapter timeouts
**Then**: the subprocess is terminated
**And**: the run result or persisted command artifact reports `reason` as `quiet_timeout`
**And**: the diagnostic includes the configured `quiet_timeout_seconds`
**And**: the diagnostic remains distinguishable from an overall `timeout` failure

#### Scenario: Overall timeout remains distinct

**Given**: a configured command adapter subprocess remains running until `adapter.timeout_seconds` elapses
**When**: `review-gauntlet run` enforces adapter timeouts
**Then**: the subprocess is terminated
**And**: the run result or persisted command artifact reports `reason` as `timeout`
**And**: the diagnostic includes the configured `timeout_seconds`
**And**: the failure is not reported as `quiet_timeout` unless the quiet-output deadline was the cause

#### Scenario: Quiet timeout renders as terminal timeout family in TUI

**Given**: a run step fails because of quiet timeout
**When**: the run TUI renders the result
**Then**: the agent is displayed as a terminal timeout-family failure
**And**: the display does not label the failure as command failed, startup error, interrupted, or max steps exhausted
**And**: timeout wording is concise and does not duplicate labels such as `timeout timeout`

### Requirement: Run agent liveness SHALL reflect actual output activity

`review-gauntlet run` SHALL track agent subprocess stdout and stderr output as it is produced, not only after the subprocess exits. The agent liveness status SHALL reflect the time since the most recent output line, not the time since the subprocess was started. An agent that is actively producing output SHALL be displayed as "running", not "quiet". The Activity panel SHALL show live output tail entries during agent execution.

Output activity SHALL also reset quiet-timeout enforcement. stdout and stderr output lines SHALL both count as liveness. When no output has ever been produced for a running subprocess, quiet-timeout elapsed time SHALL be measured from the agent step start time.

<!-- Expected canonical result after archive: run liveness defines stdout/stderr output as both display liveness and quiet-timeout reset evidence. -->

#### Scenario: Periodic output prevents quiet timeout

**Given**: a configured command adapter subprocess runs longer than `adapter.quiet_timeout_seconds`
**And**: the subprocess produces stdout or stderr output before each quiet-timeout window elapses
**When**: `review-gauntlet run` enforces adapter timeouts
**Then**: the subprocess is not terminated for quiet timeout
**And**: run completion remains governed by process exit or the overall `adapter.timeout_seconds`

#### Scenario: No initial output can quiet-timeout

**Given**: a configured command adapter subprocess starts successfully
**And**: the subprocess produces no stdout or stderr output after start
**When**: `adapter.quiet_timeout_seconds` elapses before the overall timeout
**Then**: `review-gauntlet run` terminates the subprocess for quiet timeout
**And**: `last_output_age_seconds` or equivalent diagnostics reflect silence since step start when available
