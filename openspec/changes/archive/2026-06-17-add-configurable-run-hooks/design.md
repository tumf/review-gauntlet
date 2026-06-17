# Design: Configurable run event hooks

## Overview

`review-gauntlet run` already emits structured lifecycle events through `RunEvent`. This change exposes selected lifecycle events to user-configured local commands while preserving review-gauntlet's core responsibility: deterministic review state, coverage, findings, and finalization evidence.

Hooks are an integration surface, not a source of review truth. Hook failures must not hide unreviewed work, alter finding state, or make the CLI claim completion incorrectly.

## Configuration shape

The config surface is an optional top-level `hooks` object:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "{prompt}"]
  },
  "hooks": {
    "run_started": [
      {
        "command": "python",
        "args": ["scripts/on-run-started.py", "{session_id}"]
      }
    ],
    "finalized": [
      {
        "command": "sh",
        "args": ["-c", "printf '%s\\n' \"$REVIEW_GAUNTLET_EVENT_JSON\""]
      }
    ]
  }
}
```

Each hook command should mirror adapter command safety rules:

- `command` is one argv element, not a shell string.
- `args` is a tuple/list of argv elements.
- `cwd` is optional and resolves under the repository root.
- `env` overlays the inherited environment with validated portable env names.
- `timeout_seconds` is finite and greater than zero, with a conservative default.

## Supported events

The initial hookable event set should include lifecycle events emitted by `RunController._emit()` that represent meaningful transitions:

- `run_started`
- `step_started`
- `agent_started`
- `agent_finished`
- `failed`
- `blocked`
- `checkpoint_commit_started`
- `checkpoint_commit_finished`
- `finalized`
- `stop_requested`
- `interrupt_requested`
- `interrupted`

`status_refreshed` should not be hookable initially because the TUI may refresh often, which could create surprising repeated subprocess execution. If future users need it, it should be added with throttling or explicit opt-in semantics.

## Dispatch model

The implementation should build a hook event sink for `review-gauntlet run` after loading effective config. If another sink is needed by the TUI or tests, event sinks should be composed so every sink receives the same event.

Hook execution can be synchronous and sequential for the MVP. Synchronous dispatch is simpler to reason about and makes artifact ordering deterministic. Each command has a timeout so a hook cannot hang the run indefinitely.

For each emitted event:

1. Check whether the event type is configured and hookable.
2. Build the template context from the event, root, and state dir.
3. Execute each configured hook in declaration order.
4. Persist artifacts and diagnostics for every attempt.
5. Continue run processing regardless of hook command failure.

## Template and environment context

Scalar template variables should cover common use cases without requiring JSON parsing:

- `{event_type}`
- `{timestamp}`
- `{repo_root}`
- `{state_dir}`
- `{session_id}`
- `{step}`
- `{reason}`
- `{returncode}`

Missing payload values should expand to an empty string rather than inventing values.

The full event should also be available as JSON environment data:

- `REVIEW_GAUNTLET_EVENT_JSON`
- `REVIEW_GAUNTLET_EVENT_TYPE`
- `REVIEW_GAUNTLET_REPO_ROOT`
- `REVIEW_GAUNTLET_STATE_DIR`

Configured hook `env` should be applied after these default env values so users can add integration-specific variables. The implementation should avoid logging secrets from inherited environment values.

## Artifact strategy

Hook artifacts should live under `.review-gauntlet` and be distinct from adapter cell artifacts. A deterministic enough layout is:

```text
.review-gauntlet/runs/hooks/<event-type>/<uuid>/
  stdout.log
  stderr.log
  result.json
```

`result.json` should include argv, cwd, event type, timestamp, return code, timeout, failure reason, and artifact paths. It should not include a full inherited environment dump.

## Failure handling

Hook failures are integration diagnostics. They should not become review findings or coverage facts.

Failure cases to handle:

- executable not found
- template expansion failure
- cwd resolution failure
- non-zero exit
- timeout
- unexpected subprocess errors

Each case should create artifacts when possible and surface a concise warning. The primary run result and exit status should remain determined by the normal review-gauntlet workflow.

## Alternatives considered

### Shell-string hooks

Rejected for the initial feature because it conflicts with existing adapter safety conventions. Users who need shell features can explicitly configure `sh -c`.

### Background asynchronous hooks

Rejected for MVP because it complicates ordering, shutdown, artifact completeness, and error visibility. Bounded synchronous hooks are sufficient for notifications and local automation.

### Hooking every RunEvent

Rejected because `status_refreshed` can fire repeatedly during TUI refreshes. The initial set should include meaningful lifecycle transitions only.
