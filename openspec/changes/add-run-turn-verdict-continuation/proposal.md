---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/run_controller.py
  - tests/test_cli.py
  - tests/test_run_tui.py
  - /Users/tumf/work/conflux/src/acceptance.rs
  - /Users/tumf/work/conflux/src/parallel/executor.rs
  - /Users/tumf/work/conflux/src/agent/prompt.rs
---

# Add run turn verdict continuation

**Change Type**: implementation

## Problem / Context

`review-gauntlet run` currently sends a file-scoped actionable prompt that assumes the external agent can complete the target file's triage/fix/verification work in one subprocess turn. In practice, Claude Code can emit tool calls and partial progress but then stay open for a long time before completing the process. This makes `triage_findings` feel stuck even when a useful partial handoff exists.

The desired behavior is not to split findings into one-finding prompts. The agent should still receive the same file-scoped actionable set, but each turn must explicitly write a durable JSON verdict and continuation handoff so the next turn can resume without relying on a long-lived agent process or stdout-only memory.

Conflux has analogous patterns: JSON-primary verdict parsing, verdict grace termination for lingering child processes, and previous-attempt context injection. Review Gauntlet should adopt the same shape for run turns while preserving its own session ledger and coverage/finding-state rules.

## Proposed Solution

Add a run-turn continuation contract for file-scoped `run` prompts:

- Render a repository-confined JSON continuation path into the ready prompt.
- Require the external agent to write a JSON file with `verdict: continue | finish | error`, summary, touched finding IDs, remaining finding IDs, and next-turn instructions before ending the turn.
- Read any existing JSON file for the same session/action/file and inject a compact previous-turn context into the next prompt.
- Monitor the JSON verdict file while the agent subprocess is running. After a valid verdict is detected, start a bounded grace period and terminate a still-running child when the grace period expires.
- Treat `error` verdicts and invalid/missing required verdict files as structured run failures, not generic timeouts.
- Detect no-progress `continue`/`finish` outcomes where the targeted actionable state did not change, and stop with a structured `no_progress` failure.

## Acceptance Criteria

- File-scoped `run` prompts for actionable findings continue to include all actionable findings for the selected file; findings are not split into separate prompts solely because of this change.
- Each such prompt includes a deterministic continuation JSON path and schema instructions.
- A valid continuation JSON file is persisted under `.review-gauntlet/` and is used as compact context in the next prompt for the same session/action/file.
- `review-gauntlet run` can finish a turn early after detecting a valid JSON verdict file, with a short grace period for the agent to exit before termination.
- `continue` and `finish` verdicts allow the run controller to re-evaluate readiness and proceed to the next turn.
- `error`, malformed JSON, missing required verdict files, or no-progress `continue`/`finish` outcomes are surfaced as structured run failures with distinct reasons.
- Existing review-cell verdict contracts and adapter file-json review behavior remain unchanged.

## Explicit Completion Conditions

The change is complete when:

- Ready-prompt generation writes deterministic continuation-file instructions for file-scoped actionable finding work without reducing the finding list to one item.
- The run command runner monitors the declared JSON verdict file, persists artifacts, and grace-terminates lingering agent children after verdict detection.
- Previous continuation JSON is validated, compacted, and included in later prompts for the same task key.
- Tests cover prompt rendering, JSON validation/parsing, verdict-file monitoring, error handling, no-progress detection, and non-regression of existing run timeout semantics.
- `make check` passes, or any remaining failures are documented as unrelated pre-existing failures with focused passing tests for this change.

## Out of Scope

- Splitting actionable findings into one-finding prompts.
- Changing `review-gauntlet review` OCR verdict JSON format.
- Replacing the session ledger with continuation files.
- Requiring agents to write tracked source files for continuation handoff.
- Adding external services, credentials, or non-local persistence.
