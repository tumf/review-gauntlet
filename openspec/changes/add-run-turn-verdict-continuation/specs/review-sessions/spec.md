## ADDED Requirements

### Requirement: Run turns SHALL persist JSON continuation verdicts

`review-gauntlet run` SHALL support file-scoped actionable finding turns that are allowed to span multiple external-agent subprocess turns without splitting the selected file's actionable findings into one-finding prompts. For each continuation-aware turn, the generated prompt SHALL identify a repository-confined JSON continuation file under `.review-gauntlet/turns/<session-id>/`, require the external agent to write a valid verdict file before ending the turn, and use any valid previous continuation file for the same session/action/file task as compact next-turn context.

Continuation verdict files SHALL be handoff artifacts only. The session ledger SHALL remain authoritative for finding state, review-cell coverage, and finalization readiness.

#### Scenario: Finding prompt keeps grouped findings and declares continuation file

**Given**: an active review session with multiple actionable findings for `src/example.py`
**When**: `review-gauntlet run` renders a file-scoped actionable finding prompt for that file
**Then**: the prompt includes all actionable findings for `src/example.py` selected by the current ready action
**And**: the prompt does not split those findings into separate one-finding turns solely because continuation is enabled
**And**: the prompt includes a deterministic continuation JSON file path under `.review-gauntlet/turns/<session-id>/`
**And**: the prompt includes the required JSON schema and valid `verdict` values `continue`, `finish`, and `error`

#### Scenario: Previous continuation context is injected into the next matching prompt

**Given**: an active review session has a valid continuation JSON file for the `triage_findings` task on `src/example.py`
**And**: the file contains `verdict: continue`, a summary, completed finding IDs, remaining finding IDs, and next-turn instructions
**When**: `review-gauntlet run` renders the next prompt for the same session/action/file task
**Then**: the prompt includes a compact previous-turn context derived from that JSON file
**And**: the prompt does not include continuation context from a different file, action, or session
**And**: the session ledger remains the source of truth for which findings are still actionable

#### Scenario: Verdict file allows early completion of a lingering agent process

**Given**: `review-gauntlet run` starts an external agent subprocess for a continuation-aware finding turn
**And**: the subprocess writes a valid continuation JSON file with `verdict: continue`
**And**: the subprocess keeps running after writing the verdict file
**When**: the configured verdict grace period expires
**Then**: `review-gauntlet run` terminates the lingering subprocess
**And**: the run step is classified from the continuation verdict rather than waiting for the quiet-timeout deadline
**And**: stdout, stderr, activity, and verdict artifact paths remain available for diagnosis

#### Scenario: Error verdict fails the run step distinctly

**Given**: a continuation-aware finding turn writes a valid continuation JSON file with `verdict: error`
**When**: `review-gauntlet run` processes the completed turn
**Then**: the run result reports a structured failure reason distinct from command failure, quiet timeout, and overall timeout
**And**: the failure includes the continuation file path and error message
**And**: the active session remains available for later retry

#### Scenario: Missing or malformed required verdict is a structured failure

**Given**: a continuation-aware finding turn exits without writing a valid continuation JSON file
**When**: `review-gauntlet run` processes the completed turn
**Then**: the run result reports a structured missing-or-invalid-verdict failure
**And**: the failure is not reported as a quiet timeout unless the quiet-output deadline was actually reached
**And**: stdout and stderr artifacts remain available for diagnosis

#### Scenario: Continue without ledger progress is stopped

**Given**: a continuation-aware finding turn targets findings `RGF-0001` and `RGF-0002`
**And**: the external agent writes a valid continuation JSON file with `verdict: continue`
**And**: none of the targeted finding or review-cell states changed during the turn
**When**: `review-gauntlet run` compares pre-turn and post-turn target state
**Then**: the run result reports a structured `no_progress` failure
**And**: the failure includes the task key and targeted IDs
**And**: the run does not continue indefinitely with the same unchanged actionable work

#### Scenario: Partial verdict file write is not treated as invalid verdict

**Given**: `review-gauntlet run` starts an external agent subprocess for a continuation-aware finding turn
**And**: the subprocess creates the continuation JSON file but has not finished writing valid JSON yet
**When**: `review-gauntlet run` polls the continuation file during agent execution
**Then**: the incomplete file is treated as not-yet-written
**And**: polling continues normally without reporting `invalid_step_verdict`
**And**: the verdict is detected only after the file contains valid JSON with a recognized `verdict` value

#### Scenario: Verdict file overwrite updates detected verdict

**Given**: `review-gauntlet run` starts an external agent subprocess for a continuation-aware finding turn
**And**: the subprocess writes a valid continuation JSON file with `verdict: continue`
**And**: the subprocess later overwrites the same file with `verdict: finish`
**And**: the grace period from the first detection has not yet expired
**When**: `review-gauntlet run` detects the updated verdict
**Then**: the run uses the most recently validated verdict (`finish`) for step classification

#### Scenario: Verdict grace period defaults to adapter configuration

**Given**: a command adapter configuration with `verdict_grace_seconds: 10`
**And**: `review-gauntlet run` starts a continuation-aware finding turn
**And**: the agent writes a valid verdict file and continues running
**When**: 10 seconds elapse after verdict detection
**Then**: the subprocess is terminated
**And**: the run step uses the detected verdict for classification
**And**: the default 30-second grace period is not applied

#### Scenario: Continuation path traversal is rejected

**Given**: a continuation-aware finding turn
**And**: the task key computation would produce a path component containing `../`
**When**: `review-gauntlet run` computes the continuation file path
**Then**: the path is rejected before being included in the prompt
**And**: no file is read or written outside `.review-gauntlet/turns/<session-id>/`

## MODIFIED Requirements

### Requirement: Run agent liveness SHALL reflect actual output activity

`review-gauntlet run` SHALL track agent subprocess stdout and stderr output as it is produced, not only after the subprocess exits. The agent liveness status SHALL reflect the time since the most recent output line, not the time since the subprocess was started. An agent that is actively producing output SHALL be displayed as "running", not "quiet". The Activity panel SHALL show live output tail entries during agent execution.

Output activity SHALL also reset quiet-timeout enforcement. stdout and stderr output lines SHALL both count as liveness. When no output has ever been produced for a running subprocess, quiet-timeout elapsed time SHALL be measured from the agent step start time.

Continuation verdict file detection SHALL be a separate liveness/completion signal for continuation-aware run turns. A valid verdict file MAY start a verdict grace period and terminate a lingering child before quiet timeout, but it SHALL NOT be treated as stdout/stderr output for the purpose of hiding actual output silence. The verdict grace period SHALL be configurable via `adapter.verdict_grace_seconds` and SHALL default to 30 seconds when not explicitly configured.

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

#### Scenario: Verdict file finalization is distinct from output liveness

**Given**: a continuation-aware finding turn writes a valid continuation JSON file before producing any further stdout or stderr
**When**: `review-gauntlet run` detects the verdict file
**Then**: the run may start the verdict grace period
**And**: the agent lifecycle still reports output age based on stdout/stderr activity
**And**: the final run reason distinguishes verdict-finalized completion from quiet timeout
