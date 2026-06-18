## MODIFIED Requirements

### Requirement: Run turns SHALL persist JSON continuation verdicts

`review-gauntlet run` SHALL support file-scoped actionable finding turns that are allowed to span multiple external-agent subprocess turns without splitting the selected file's actionable findings into one-finding prompts. For each continuation-aware turn, the generated prompt SHALL identify a repository-confined JSON continuation file under `.review-gauntlet/turns/<session-id>/`, require the external agent to write a valid verdict file before ending the turn, and use any valid previous continuation file for the same session/action/file task as compact next-turn context.

Continuation verdict files SHALL be handoff artifacts only. The session ledger SHALL remain authoritative for finding state, review-cell coverage, and finalization readiness.

The CLI SHALL provide an agent-operable command to validate continuation turn verdict files independently from OCR review-cell verdict validation. The command SHALL reuse the continuation verdict schema, return machine-readable success or failure output when requested, and exit non-zero for invalid continuation verdicts. Generated continuation-aware prompts SHALL instruct agents to run this validation command after writing the turn verdict file, repair invalid output, and re-run validation before ending the turn.

When runtime processing observes an invalid continuation verdict after the agent exits, `review-gauntlet run` SHALL use the invalid-verdict diagnostic as feedback for the same file-scoped continuation task while retry budget remains. Invalid-verdict retries SHALL be bounded. After the bound is exhausted, `run` SHALL report a terminal invalid-verdict failure with the last diagnostic and available artifact paths.

#### Scenario: Finding prompt includes turn verdict validation command

**Given**: an active review session with actionable findings for `src/example.py`
**When**: `review-gauntlet run` renders a file-scoped actionable finding prompt for that file
**Then**: the prompt includes a deterministic continuation JSON file path under `.review-gauntlet/turns/<session-id>/`
**And**: the prompt includes a command to validate that exact continuation file path
**And**: the prompt instructs the agent to rewrite the verdict and re-run validation if validation fails
**And**: the prompt instructs the agent not to end the turn until validation succeeds

#### Scenario: Turn verdict validation accepts a valid continuation verdict

**Given**: a continuation JSON file under `.review-gauntlet/turns/<session-id>/` with a valid `schema_version`, `verdict`, `summary`, finding ID lists, `resolutions`, `next_turn_instructions`, and `error`
**When**: the developer or agent runs `review-gauntlet validate-turn-verdict <path> --format json`
**Then**: the command exits successfully
**And**: stdout is parseable JSON containing `valid: true`
**And**: the command does not mutate source files, review cells, findings, or the session ledger

#### Scenario: Turn verdict validation rejects invalid resolution state names

**Given**: a continuation JSON file under `.review-gauntlet/turns/<session-id>/`
**And**: the file contains `resolutions: [{"finding_id": "RGF-0001", "state": "fixed"}]`
**When**: the developer or agent runs `review-gauntlet validate-turn-verdict <path> --format json`
**Then**: the command exits non-zero
**And**: stdout is parseable JSON containing `valid: false`
**And**: the error identifies the invalid continuation verdict schema or invalid resolution state

#### Scenario: Invalid runtime verdict is retried with diagnostic feedback

**Given**: `review-gauntlet run` starts a continuation-aware finding turn for `src/example.py`
**And**: the external agent exits after writing a continuation verdict containing `resolutions: [{"finding_id": "RGF-0001", "state": "fixed"}]`
**And**: invalid-verdict retry budget remains
**When**: `run` processes the completed turn
**Then**: `run` does not immediately terminate the whole run as terminal `VERDICT INVALID`
**And**: `run` schedules another agent invocation for the same file-scoped task
**And**: the next prompt includes the invalid verdict path and validation diagnostic
**And**: no finding state is mutated before a valid verdict is received

#### Scenario: Invalid runtime verdict retry is bounded

**Given**: `review-gauntlet run` starts a continuation-aware finding turn
**And**: each retry writes an invalid continuation verdict
**When**: the invalid-verdict retry bound is exhausted
**Then**: `run` reports a terminal invalid-verdict failure
**And**: the failure includes the last validation diagnostic
**And**: the failure includes stdout, stderr, activity, and verdict artifact paths when available
**And**: the run does not continue indefinitely with the same invalid task

#### Scenario: Turn verdict validation can reject impossible finding transitions

**Given**: an active review session with an `open` finding `RGF-0001`
**And**: a continuation JSON file under `.review-gauntlet/turns/<session-id>/` requests a resolution state that cannot be applied from `open`
**When**: the developer or agent runs `review-gauntlet validate-turn-verdict <path> --format json`
**Then**: the command exits non-zero before any ledger mutation
**And**: stdout is parseable JSON containing `valid: false`
**And**: the error identifies the finding ID and invalid transition

#### Scenario: OCR verdict validation remains separate

**Given**: an OCR review-cell verdict file shaped as `{"comments": []}`
**When**: the developer runs `review-gauntlet validate-verdict <path> --format json`
**Then**: the existing OCR verdict validation behavior remains unchanged
**And**: continuation verdict validation is performed only by the turn-verdict validation command
