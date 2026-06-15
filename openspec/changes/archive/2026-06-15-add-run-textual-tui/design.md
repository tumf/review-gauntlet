# Design: Textual TUI for `review-gauntlet run`

## Goals

- Improve long-running `review-gauntlet run` observability for humans.
- Preserve existing run semantics and JSON/script behavior.
- Keep TUI dependencies optional.
- Keep controller state authoritative and UI state read-only.

## Architecture

```text
CLI run command
  ├─ selects presentation mode
  │   ├─ JSON / --no-tui / non-TTY / fallback text
  │   └─ Textual TUI
  └─ RunController
      ├─ active session lookup
      ├─ ready prompt evaluation
      ├─ session command execution
      ├─ status refresh
      ├─ event emission
      ├─ stop-after-current-step request
      └─ final result construction

RunApp
  ├─ subscribes to controller events/snapshots
  ├─ renders panels
  ├─ maps keys to controller requests
  └─ never writes session ledger state directly
```

## Controller Responsibilities

`RunController` owns the existing run state machine currently embedded in `_cmd_run`:

- Load effective adapter config.
- Resolve the active session.
- Ask the same ready prompt computation used by `review-gauntlet ready` for work.
- Execute the configured session-level command with the ready prompt.
- Re-evaluate durable session state after each step.
- Stop successfully when the active-session marker disappears.
- Stop unsuccessfully on no ready task, command failure, max-step exhaustion, or stop-after-current-step with an active session still present.
- Emit structured events that presentation layers can consume.

The controller should expose test seams for command execution and status snapshots so tests can verify behavior without spawning real long-running agents.

## Event Model

Initial events:

```json
{"type": "run_started", "session_id": "RGS-xxxx"}
{"type": "status_refreshed", "coverage": {}, "findings": {}}
{"type": "step_started", "step": 1, "prompt": "..."}
{"type": "agent_started", "argv": ["opencode", "run", "..."]}
{"type": "agent_finished", "returncode": 0}
{"type": "blocked", "reason": "..."}
{"type": "finalized"}
{"type": "failed", "reason": "..."}
```

Events should be structured data first. Text rendering should happen at the presentation layer.

## TUI Responsibilities

`RunApp` should render:

- `HeaderBar`: title, session id, target summary, adapter/agent identity.
- `CoveragePanel`: reviewed, pending, stale, superseded counts.
- `FindingsPanel`: untriaged, confirmed, reopened, fixed-pending verification, and optionally terminal states.
- `CurrentTaskPanel`: current ready prompt summary or blocker.
- `AgentPanel`: status, step, elapsed time, command argv.
- `EventLogPanel`: timestamped controller events.
- `FooterBar`: key hints and status legend.

## Key Bindings

- `q`: request stop after current step.
- `Ctrl-C`: interrupt immediately using controller interrupt/cancellation handling.
- `r`: request status refresh.
- `h`: show help.
- `o`: out of scope for initial implementation unless implemented as a no-op with explicit event feedback.

## Presentation Selection

TUI is enabled only when all conditions are true:

- command is `run`
- output format is `text`
- stdout is a TTY
- `--no-tui` is absent
- Textual support imports successfully

If Textual is unavailable, the CLI falls back to text mode and emits:

```text
TUI support is not installed; falling back to text mode.
Install with: uv tool install "review-gauntlet[tui]"
```

JSON mode must never receive fallback warnings on stdout.

## Testing Strategy

- Controller unit tests cover run semantics independent of presentation.
- CLI integration tests cover presentation selection and fallback behavior with monkeypatched TTY/import availability.
- TUI construction tests avoid real terminal sessions and validate widget/app creation from snapshots where practical.
- Existing JSON run tests remain the compatibility contract.

## Trade-offs

Initial TUI does not stream subprocess output live. The existing implementation captures command output after process completion, and preserving that behavior keeps the first TUI implementation smaller and less risky. Live output can be added later by replacing command execution internals with incremental event emission.
