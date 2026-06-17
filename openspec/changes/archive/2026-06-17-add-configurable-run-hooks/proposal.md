---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/config.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/presets/
  - tests/test_config.py
  - tests/test_cli_run.py
  - tests/test_run_controller.py
---

# Add configurable run event hooks

**Change Type**: implementation

## Premise / Context

- The requested behavior is to let users define multiple hook events and configure commands to run when those events occur.
- `review-gauntlet run` already emits structured `RunEvent` objects through `RunController._emit()` for run lifecycle events such as `run_started`, `step_started`, `agent_finished`, `blocked`, `failed`, and `finalized`.
- Review configuration is currently JSON/JSONC based and validated in `src/review_gauntlet/config.py`; it supports safe argv-style external command execution for the adapter rather than shell strings.
- Project constitution says orchestration and developer notification are external concerns, so hooks should expose lifecycle notifications without hiding coverage, findings, failures, or completion state.
- The requested artifact is implementation: source code, config schema, tests, and presets must change so the behavior works at runtime.

## Problem/Context

Developers can run `review-gauntlet run` through an external agent adapter, but there is no supported way to notify other tools or trigger local automation when important run lifecycle events occur. Users currently must wrap the CLI externally or watch artifacts/logs if they want post-run notifications, audit logging, or follow-up commands.

Because run lifecycle events already exist internally, the smallest coherent feature is to expose a safe config-driven hook surface that executes configured commands when selected run events are emitted.

## Proposed Solution

Extend `ReviewGauntletConfig` with an optional `hooks` mapping from event name to ordered hook command definitions. Hook commands SHALL reuse the existing safe command-adapter principles: argv arrays, `shell=False`, validated environment variable names, bounded timeouts, and template validation.

`review-gauntlet run` SHALL load the effective config once for run execution and construct an event sink that dispatches configured hooks for supported lifecycle events. Hook execution SHALL be best-effort by default: a failing, missing, or timed-out hook command SHALL produce hook artifacts and diagnostics, but SHALL NOT change the review session state or mask the primary run result.

Initial supported hook events SHALL be lifecycle events that are not emitted on routine refresh paths. `status_refreshed` SHALL NOT be hookable in the initial implementation to avoid high-frequency hook storms during TUI refreshes.

## Acceptance Criteria

- A valid config may define `hooks` with one or more commands for supported run event names.
- Config validation rejects unknown hook event names, whitespace-containing hook commands, invalid hook environment variable names, invalid templates, and non-positive hook timeouts before hook execution.
- `review-gauntlet config effective --format json` includes the merged hook configuration.
- During `review-gauntlet run`, each configured hook for an emitted supported event runs in declaration order with `shell=False` and a bounded timeout.
- Hook command templates can access event context such as event type, timestamp, repository root, state dir, session ID, step, reason, and return code when those values are present.
- Hook commands receive the full event payload in an environment variable so integrations can inspect fields not exposed as scalar templates.
- Hook stdout, stderr, argv, return code, timeout/failure reason, event type, and artifact paths are persisted under `.review-gauntlet` for diagnosis.
- Hook failures, missing executables, template errors, and timeouts are surfaced as hook diagnostics without changing successful run completion or hiding primary run failures.
- Existing adapter execution, review/verify-fixes configuration behavior, and TUI event rendering continue to work when no hooks are configured.

## Explicit Completion Conditions

- `src/review_gauntlet/config.py` defines validated hook configuration models and includes `hooks` in effective config serialization and validation.
- `src/review_gauntlet/cli.py` or a dedicated hook module executes configured hook commands for `review-gauntlet run` events and persists per-hook artifacts.
- `src/review_gauntlet/run_controller.py` continues to emit the existing run events and supports composition of the hook event sink with any TUI or internal sink so event display is not replaced by hooks.
- Preset JSONC files remain valid and either omit hooks or document a commented optional hook example.
- Unit tests cover schema validation and effective-config serialization for hooks.
- Integration-style CLI tests cover at least one real hook command running on `run_started` or `finalized`, environment payload delivery, artifact persistence, and non-blocking hook failure behavior.
- Existing run controller/TUI tests continue to pass without requiring hooks.
- `make check` passes.

## Out of Scope

- Running hooks for `status_refreshed` or other high-frequency refresh events.
- A long-running background hook worker, retry queue, or daemon.
- Remote webhook delivery or network-specific integrations.
- Per-command shell-string parsing beyond explicit `sh -c` usage chosen by the user.
- Changing the semantics of review coverage, findings, finalization, or checkpoint commits.
