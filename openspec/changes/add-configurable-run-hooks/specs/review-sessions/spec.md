## ADDED Requirements

### Requirement: Run command SHALL execute configured lifecycle hooks

`review-gauntlet run` SHALL allow Review Gauntlet configuration to define local command hooks for supported run lifecycle events. Hook commands SHALL execute when their configured event is emitted, SHALL use argv-style execution with `shell=False`, SHALL run in declaration order for a given event, and SHALL use bounded timeouts. Hook execution SHALL be an integration side effect and SHALL NOT alter review coverage, finding state, finalization state, or checkpoint commit semantics.

#### Scenario: Hook runs for configured run lifecycle event

**Given**: an active review session
**And**: the effective Review Gauntlet config defines a `run_started` hook command that writes a marker file
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the hook command is executed when the `run_started` event is emitted
**And**: the marker file contains evidence from the actual hook subprocess
**And**: the run result remains determined by the normal run workflow

#### Scenario: Multiple hooks for one event run in declaration order

**Given**: the effective Review Gauntlet config defines two hook commands for `agent_finished`
**When**: `review-gauntlet run` emits `agent_finished`
**Then**: both hook commands are executed
**And**: the first configured hook is attempted before the second configured hook
**And**: each hook attempt has separate persisted execution evidence

#### Scenario: High-frequency refresh event is not hookable by default

**Given**: a config file defines a hook for `status_refreshed`
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: validation fails with an actionable unsupported hook event error
**And**: no hook command is executed

### Requirement: Hook configuration SHALL be validated before hook execution

Hook configuration SHALL be validated as part of the same JSON/JSONC config loading and effective-config inspection path used for command adapters. Hook commands SHALL reject shell-string-style commands containing whitespace, invalid environment variable names, unsupported template variables, unsafe cwd resolution, and non-finite or non-positive timeout values before executing any hook subprocess.

#### Scenario: Valid hook config appears in effective config

**Given**: a repository or user environment with a valid Review Gauntlet config containing hooks
**When**: the developer runs `review-gauntlet config effective --format json`
**Then**: stdout displays the merged hook configuration
**And**: the hook commands, args, cwd, env, and timeout values are represented in parseable JSON

#### Scenario: Invalid hook command is rejected before execution

**Given**: a config file whose hook command is `echo hello` as a single shell-string command value
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: validation fails with an actionable hook command validation error
**And**: no adapter or hook command is executed

#### Scenario: Invalid hook template is rejected before execution

**Given**: a config file whose hook args contain an unsupported template variable `{unknown_value}`
**When**: the developer runs `review-gauntlet config validate --config <that-file>`
**Then**: validation fails with an actionable template validation error
**And**: no adapter or hook command is executed

### Requirement: Hook commands SHALL receive structured event context and preserve diagnostics

When executing a hook command, `review-gauntlet run` SHALL provide scalar template variables for common event context and SHALL provide the full event as JSON in the hook subprocess environment. Each hook attempt SHALL persist stdout, stderr, argv, cwd, return code, timeout or failure details, event type, and artifact metadata under `.review-gauntlet` without recording a full inherited environment dump.

#### Scenario: Hook receives event JSON environment

**Given**: the effective config defines a `step_started` hook command that writes `$REVIEW_GAUNTLET_EVENT_JSON` to a file
**When**: `review-gauntlet run` emits `step_started`
**Then**: the hook subprocess receives `REVIEW_GAUNTLET_EVENT_JSON`
**And**: the JSON contains the emitted event `type`, `timestamp`, and step payload
**And**: the hook subprocess also receives scalar environment values for event type, repo root, and state dir

#### Scenario: Hook templates expand event values

**Given**: the effective config defines an `agent_finished` hook with args containing `{event_type}` and `{returncode}`
**When**: `review-gauntlet run` emits `agent_finished` after an agent subprocess exits with code `0`
**Then**: the hook command receives argv values containing `agent_finished` and `0`
**And**: missing optional event fields expand to empty strings rather than invented values

#### Scenario: Hook artifacts preserve failure diagnostics without masking run result

**Given**: the effective config defines a hook command that exits non-zero for `finalized`
**And**: the active session otherwise finalizes successfully
**When**: the developer runs `review-gauntlet run --format json`
**Then**: the run result reports normal successful completion
**And**: the hook attempt persists stdout, stderr, argv, return code, and failure reason under `.review-gauntlet`
**And**: the hook failure does not create or modify review findings or coverage rows

#### Scenario: Hook timeout is bounded and diagnostic

**Given**: the effective config defines a hook command with a short positive timeout
**And**: the hook subprocess runs longer than that timeout
**When**: the configured event is emitted during `review-gauntlet run`
**Then**: the hook subprocess is terminated after the configured timeout
**And**: timeout diagnostics are persisted as hook artifacts
**And**: the primary run result is not replaced by the hook timeout
