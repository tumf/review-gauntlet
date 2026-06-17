---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/config.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/run_tui.py
  - tests/test_config.py
  - tests/test_cli_run.py
  - tests/test_run_controller.py
  - tests/test_run_tui.py
  - README.md
  - README.ja.md
  - openspec/specs/review-sessions/spec.md
---

# Set run command timeout defaults and add quiet timeout

**Change Type**: implementation

## Problem / Context

`review-gauntlet run` currently defaults command adapter execution to 600 seconds. That is too short for long-running autonomous review agents. The run TUI already distinguishes active output from quiet liveness, but quiet is only a display state: an agent can remain alive without producing stdout or stderr until the overall command timeout is reached.

The requested behavior is to make the normal run budget much longer while still failing agents that appear stuck because they produce no output for too long.

## Proposed Solution

- Change the command adapter default `timeout_seconds` from 600 seconds to 3600 seconds.
- Add a command adapter `quiet_timeout_seconds` setting with a default of 600 seconds.
- Enforce `quiet_timeout_seconds` during `review-gauntlet run` by measuring time since the most recent stdout/stderr line, or since agent step start when no output has been produced yet.
- Kill the external agent subprocess when quiet timeout is exceeded before the overall command timeout.
- Preserve distinct failure diagnostics by reporting quiet timeout separately from overall command timeout in structured run results and artifacts.
- Keep `quiet` as a non-terminal liveness display before the quiet timeout threshold is reached.
- Update TUI, documentation, and tests so default timeout and quiet-timeout behavior are visible and verifiable.

## Acceptance Criteria

- A command adapter with no explicit `timeout_seconds` uses 3600 seconds.
- A command adapter with no explicit `quiet_timeout_seconds` uses 600 seconds.
- Config validation rejects non-finite or non-positive `quiet_timeout_seconds` values.
- Existing explicit `timeout_seconds` values continue to override the default.
- An agent that produces stdout or stderr at least once per quiet-timeout window is not killed by quiet timeout.
- An agent that produces no stdout or stderr for `quiet_timeout_seconds` is killed before the overall command timeout and returns a structured quiet-timeout failure.
- Overall command timeout remains available and distinguishable from quiet timeout.
- TUI displays quiet as a running/alive liveness state before quiet timeout and displays terminal timeout wording after quiet timeout.
- README and Japanese README describe the new defaults and quiet timeout behavior.

## Explicit Completion Conditions

This change is complete when the repository contains runtime support for `adapter.quiet_timeout_seconds`, default `adapter.timeout_seconds` is 3600 seconds, quiet-timeout subprocess termination is covered by integration tests, distinct timeout reasons are covered by controller/TUI tests, config validation covers default and invalid quiet-timeout values, documentation is updated, and `make check` passes.

## Out of Scope

- Changing the existing 5-second threshold for displaying an active agent as quiet in the TUI.
- Adding retry, resume, or automatic restart behavior after quiet timeout.
- Changing provider-specific CLI arguments for opencode, Claude, or Codex presets beyond inherited config defaults.
- Introducing external watchdog services or background daemons.
