---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/run-controller/spec.md
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/session_store.py
  - tests/test_cli.py
---

# Guard run without active session

**Change Type**: implementation

## Problem / Context

`review-gauntlet status` already fails actionably when no review session has been initialized, surfacing `no active review session; run review-gauntlet init` before doing any session work. `review-gauntlet run` does not currently enforce the same precondition at the CLI boundary. Instead, it can proceed into config loading, RunController construction, and TUI selection before the missing active session is discovered indirectly.

That indirect path produces less useful behavior: the user can see adapter-config errors or a `session_disappeared` style run result rather than the same clear guidance used by `status`. For terminal users, the expected behavior is that `run` refuses to start when no active session exists and does not render the TUI for a session that was never initialized.

## Proposed Solution

Add an early active-session preflight to the `review-gauntlet run` command path before configuration loading, RunController execution, or TUI startup. The preflight should reuse the existing `SessionStore.active_session_id()` behavior so missing sessions fail through the existing top-level `LookupError` handler and display the same message as `status`.

The command should:

- require an existing active session before loading run adapter configuration;
- fail with `no active review session; run review-gauntlet init` and exit code `1` when the active marker is absent;
- avoid starting or rendering the run TUI in the no-session case;
- preserve existing initialized-session run behavior, including normal TUI behavior and controller execution;
- add regression coverage proving the missing-session guard runs before config/TUI/controller side effects.

## Acceptance Criteria

- Running `review-gauntlet run` in a repository with no active review session exits non-zero with the same no-active-session guidance used by `status`.
- The no-session `run` path does not start the TUI, does not instantiate a controller run, and does not emit a structured `session_disappeared` result.
- Missing adapter configuration does not mask the no-active-session error; the session preflight happens first.
- Existing initialized-session `run` behavior remains unchanged.
- Focused CLI tests and the project quality gate pass.

## Explicit Completion Conditions

This change is complete when:

- `src/review_gauntlet/cli.py` checks for an active session at the beginning of `_cmd_run()` before `load_config()`, `RunController(...)`, or `should_use_tui(...)` can influence output.
- Tests in `tests/test_cli.py` or an equivalent CLI test module assert that `run` without `init` exits with code `1` and writes `no active review session; run review-gauntlet init` to stderr.
- Tests assert that the missing-session `run` error is reported even when no run adapter config is present, proving config validation does not happen first.
- Tests or a focused mock/monkeypatch assertion prove the TUI creation path is not reached for the no-session case.
- `make check` passes.

## Out of Scope

- Changing `status`, `ready`, `review`, `finalize`, or session initialization behavior.
- Changing RunController's handling of sessions that disappear after a run has already started.
- Changing adapter config discovery or validation semantics for initialized sessions.
- Adding a cancel/reset command for active sessions.
