---
change_type: implementation
priority: medium
dependencies: []
references:
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/cli.py
  - pyproject.toml
  - tests/test_cli.py
---

# Add Textual TUI for `review-gauntlet run`

**Change Type**: implementation

## Problem / Context

`review-gauntlet run` already orchestrates active review sessions by repeatedly executing the same ready prompt used by `review-gauntlet ready`. Its current user-facing presentation is text or JSON only, which is adequate for scripts but hard to monitor during long-running agent sessions. Developers need an interactive dashboard that makes coverage, finding state, current task, agent status, and recent events visible without changing the underlying run semantics.

The project constitution requires explicit visibility into reviewed, unreviewed, stale, failed, and undecided states. A TUI for `run` should strengthen that visibility while preserving deterministic session progression and existing JSON/script behavior.

## Proposed Solution

Add an optional Textual-based TUI as the default presentation for interactive `review-gauntlet run` executions. The implementation will keep `run` semantics unchanged by separating orchestration from rendering:

- Introduce a `RunController` responsible for the existing run state machine, ready-task evaluation, session-level adapter execution, status refresh, event emission, stop-after-current-step, and interrupt handling.
- Introduce a Textual `RunApp` that subscribes to controller events and renders status only; it must not mutate review cells, findings, or session state directly.
- Add `--no-tui` to force the existing non-TUI text presentation.
- Disable TUI for `--format json`, non-TTY output, and explicit `--no-tui`.
- Add optional dependency extra `review-gauntlet[tui]` containing Textual and Rich.
- Fall back to text mode with a clear warning when TUI support is unavailable in an interactive text run.

The TUI will initially provide dashboard panels for header/session metadata, coverage counts, finding counts, current task, agent status, event log, and footer/key help. It will support `q`, `Ctrl-C`, `r`, and `h`; `o` may remain future work.

## Acceptance Criteria

- Interactive `review-gauntlet run` launches the Textual TUI by default when stdout is a TTY, output format is text, `--no-tui` is absent, and TUI dependencies are installed.
- `review-gauntlet run --no-tui`, `review-gauntlet run --format json`, and non-TTY executions do not launch the TUI.
- JSON output remains parseable and compatible with the existing run result contract.
- Textual/Rich dependencies are available through the optional `tui` extra, not required for base installation.
- Missing TUI dependencies in an interactive text run produce a warning and fall back to text mode rather than failing the run.
- TUI rendering shows coverage, finding counts, current ready task, agent status, elapsed/step information, command information, and recent controller events.
- TUI key actions only request controller operations: stop after current step, refresh, help, or immediate interrupt.
- `run` task selection continues to use the same ready prompt computation as `review-gauntlet ready` and does not introduce TUI-specific task priority logic.

## Explicit Completion Conditions

This change is complete when repository evidence shows all of the following:

- `pyproject.toml` defines a `tui` optional dependency extra with Textual and Rich version constraints.
- `review-gauntlet run --help` documents `--no-tui`.
- Run orchestration logic is available through a controller abstraction used by both TUI and non-TUI paths.
- Textual imports are optional and do not break base installations without `review-gauntlet[tui]`.
- Unit or integration tests cover TUI selection rules, fallback behavior, JSON no-TUI behavior, and `--no-tui` behavior without requiring a real terminal UI session.
- Controller-level tests cover event emission and stop-after-current-step behavior with fixture or fake command adapters.
- `make check` passes.

## Out of Scope

- Editing, marking, waiving, or accepting findings from inside the TUI.
- Prompt editing inside the TUI.
- Agent switching from inside the TUI.
- Managing multiple sessions from a single TUI.
- Web UI, daemon mode, or remote monitoring.
- Live command-output streaming beyond event/log summaries.
- Implementing artifact-directory opening for `o` unless it is trivial and fully tested.
