## Design

### Current implementation boundary

The existing TUI is concentrated in `src/review_gauntlet/run_tui.py`, with session state supplied by `RunSnapshot` and event history supplied by `RunController.events`. The project is already using Textual for interactive TTY mode, so this change should not migrate to another TUI framework. Textual remains the application layer for layout, CSS, actions, events, reactivity, and workers; Rich renderables may still be used inside Textual widgets where helpful.

This change should preserve the controller/UI boundary: presentation-specific logic belongs in TUI view-model and formatter helpers, while execution semantics remain in `RunController`.

A small controller-facing adjustment may be needed so the TUI can show a command or agent display label while the session-level command is running. Today `RunController` only records `command_argv` after `_command_runner` returns and emits `agent_started` with `argv=[]`. The TUI can hide empty argv, but accurate running-state display is better if the controller exposes a display label derived from effective adapter config before command execution starts.

### Dashboard regions

The TUI should render these regions in order:

1. Header / session summary
2. Metrics dashboard
3. Current operation
4. Activity timeline
5. Footer controls

Normal-width layout should keep Coverage and Findings side by side. Compact layout may stack them and shorten labels, but must keep all required counts visible.

### View-model and formatter-first design

Most behavior should be implemented by first converting raw controller data into a human-facing display model, then rendering that model with Textual widgets. This avoids repeating the current pattern of placing raw payloads directly inside panels.

A `RunViewState`-style model should contain fields equivalent to:

- `status`
- `session_short_id`
- `agent_name`
- `step_label`
- `coverage_percent`
- `reviewed_cells`
- `total_cells`
- `pending_cells`
- `stale_cells`
- `superseded_cells`
- `open_findings`
- `task_title`
- `task_description`
- `command_label`
- `timeline_events`

Most formatting behavior should be deterministic functions that accept `RunSnapshot`, `RunEvent`, and terminal/layout hints. This keeps the display testable without requiring a live terminal.

Recommended helpers:

- `short_session_id(session_id: str | None) -> str`
- `format_event_time(timestamp: str) -> str`
- `format_task_title(prompt: str | None) -> TaskDisplay`
- `format_command_label(snapshot: RunSnapshot) -> str | None`
- `format_activity_event(event: RunEvent, snapshot: RunSnapshot | None) -> str`
- `dashboard_state(snapshot: RunSnapshot, events: tuple[RunEvent, ...]) -> RunViewState`

The implementation may use different names, but tests should exercise equivalent behavior.

### Prompt intent mapping

The TUI must not display ready prompts as the primary task text. It should classify known prompt intents by substring or more structured metadata if available.

Minimum mappings:

- pending review work -> `REVIEW PENDING CELLS`
- stale review work -> `REVIEW STALE CELLS`
- untriaged finding work -> `TRIAGE FINDINGS`
- confirmed finding fix work -> `FIX CONFIRMED FINDING`
- fixed-pending verification work -> `VERIFY FIXES`
- finalization work -> `FINALIZE SESSION`

Unknown prompts should be sanitized and summarized without dumping the full prompt body.

### Event transformation

Raw event payloads remain useful as evidence, but the dashboard timeline should transform them into user-facing rows. Event formatting should:

- Convert ISO timestamps to `HH:MM:SS`.
- Use stable event labels such as `run started`, `status refreshed`, `step 1 started`, `agent started`, `blocked`, `failed`, and `finalized`.
- Shorten session IDs.
- Omit empty argv values.
- Summarize prompt details through the same prompt intent mapping used for Current task.
- Escape Rich/Textual markup and control characters.

Malformed timestamps or unexpected payloads should not crash rendering.

### Color and state semantics

The Textual CSS should define normal panels independently from warning state. Yellow should be reserved for pending/warning/blocker text or blocked panel styling. Failed and finalized states should have explicit classes or style hooks so tests can assert the classes exist and manual review can verify colors.

### Verification strategy

Most acceptance criteria are presentation formatting and should be unit-tested without requiring Textual to be installed. Textual construction/headless tests should remain optional or skipped when the optional dependency is unavailable, consistent with existing behavior.

Manual verification is still appropriate for final color and 80x24 wrapping behavior because terminal rendering and theme support vary by environment.
