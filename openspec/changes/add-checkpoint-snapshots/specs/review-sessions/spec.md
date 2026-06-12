## ADDED Requirements

### Requirement: Checkpoint command SHALL export Git-reviewable session snapshots

`review-gauntlet checkpoint` SHALL export the active review session into deterministic latest-only checkpoint files that are suitable for Git diff review. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and finalization readiness, and SHALL NOT replace or mutate the ledger source of truth.

#### Scenario: Checkpoint writes latest snapshot files

**Given**: an active review session with persisted review state
**When**: the developer runs `review-gauntlet checkpoint --format json`
**Then**: `.review-gauntlet/checkpoints/latest/status.json` is written
**And**: `.review-gauntlet/checkpoints/latest/findings.json` is written
**And**: `.review-gauntlet/checkpoints/latest/events.json` is written
**And**: `.review-gauntlet/checkpoints/latest/summary.md` is written
**And**: stdout contains parseable JSON listing the generated files and checkpoint directory

#### Scenario: Checkpoint exposes full review state for diff review

**Given**: an active review session with reviewed cells, open findings, terminal findings, finding occurrences, and finding events
**When**: the developer runs `review-gauntlet checkpoint`
**Then**: `status.json` includes session metadata, target information, current target digest, last reviewed target digest, ruleset digest, coverage counts, finding state counts, run count, finalization blockers, and next required action
**And**: `findings.json` includes all session findings including terminal findings
**And**: each finding includes latest occurrence line evidence when occurrence evidence exists
**And**: `events.json` includes triage and verification events for the session findings in deterministic order
**And**: `summary.md` presents the same state in a Markdown format suitable for PR review

#### Scenario: Checkpoint preserves malformed event metadata as evidence

**Given**: an active review session with a finding event whose metadata is malformed JSON or not a JSON object
**When**: the developer runs `review-gauntlet checkpoint --format json`
**Then**: checkpoint generation succeeds without a traceback
**And**: `events.json` includes the event with raw metadata evidence
**And**: checkpoint generation does not reinterpret the event as a different triage decision

#### Scenario: Checkpoint is latest-only by default

**Given**: an active review session with an existing `.review-gauntlet/checkpoints/latest/` snapshot
**When**: the developer runs `review-gauntlet checkpoint` again
**Then**: the command overwrites the same latest snapshot files
**And**: no timestamped or session-history checkpoint directory is created by default

#### Scenario: Checkpoint does not mutate review session state

**Given**: an active review session with persisted run, review cell, finding, occurrence, and finding event records
**When**: the developer runs `review-gauntlet checkpoint`
**Then**: no new run record is created
**And**: no review cell state changes
**And**: no finding state changes
**And**: no finding event is written
**And**: no session is finalized

#### Scenario: Checkpoint files are the only tracked review-gauntlet state

**Given**: repository ignore rules for `.review-gauntlet` state
**When**: checkpoint files exist under `.review-gauntlet/checkpoints/latest/`
**Then**: those checkpoint files are eligible for Git tracking
**And**: `.review-gauntlet/ledger.sqlite` remains ignored
**And**: `.review-gauntlet/active-session.json` remains ignored
**And**: `.review-gauntlet/runs/` remains ignored
**And**: `.review-gauntlet/rules.lock` remains ignored
