# Design: Git-reviewable checkpoint snapshots

## Goals

- Preserve `ledger.sqlite` as the durable source of truth.
- Export a deterministic latest-only snapshot that is readable in Git diffs.
- Keep checkpoint generation explicit and side-effect limited.
- Make incomplete coverage, undecided findings, and finalization blockers visible.

## Data Model

Checkpoint output is derived from existing session tables and computed status logic.

### `status.json`

`status.json` combines `_status()` output with durable metadata and freshness evidence:

- `session_id`
- `session_state`
- `metadata`
- `target`
- `target_digest`
- `last_run_target_digest`
- `ruleset_digest`
- `coverage`
- `finding_state_counts`
- `run_count`
- `can_finalize`
- `finalize_blockers`
- `next_required_action`

`target_digest` is recomputed against the current repository root so PR reviewers can see whether the latest checkpoint is stale relative to the current target. `last_run_target_digest` is read from the latest real run record and must not be refreshed by checkpoint generation.

### `findings.json`

`findings.json` includes all active-session findings, including terminal findings. Each finding includes the persisted finding row plus latest occurrence evidence:

- `finding_id`
- `state`
- `path`
- `rule_id`
- `content`
- parsed `metadata` when valid, raw fallback when malformed
- `latest_occurrence` with `run_id`, `cell_id`, `start_line`, `end_line`, and `imprecise`

Ordering is by `finding_id`, with latest occurrence selected by highest `occurrence_id` for each finding.

### `events.json`

`events.json` emits finding events joined to active-session findings so unrelated session data cannot leak into the checkpoint. Ordering is by `event_id`.

Metadata parsing follows a conservative rule:

- valid object JSON becomes `metadata`
- invalid or non-object JSON becomes `metadata_raw` plus a parse marker

This mirrors finalize's conservative handling of malformed terminal decision metadata without treating checkpoint generation as a blocker or state transition.

### `summary.md`

`summary.md` is a human review surface, not a source of truth. It summarizes the same data as JSON files using deterministic Markdown tables and lists:

- session and target summary
- coverage counts
- finding state counts
- findings table
- recent/event table or event summary
- finalize blockers

Markdown cells should escape pipes and normalize newlines so table structure remains stable.

## Filesystem Behavior

Checkpoint generation writes to `.review-gauntlet/checkpoints/latest/`. The implementation should create the directory when needed and overwrite the four canonical files each time.

The initial scope intentionally avoids timestamped history. A future `--keep-history` can copy the same generated payload into a history directory, but that is not required for the first implementation.

## Side Effects

Allowed side effects:

- create `.review-gauntlet/checkpoints/latest/`
- overwrite `status.json`, `findings.json`, `events.json`, and `summary.md`
- print command result to stdout

Disallowed side effects:

- create run records
- mutate review cell states
- mutate finding states
- write finding events
- finalize sessions
- invoke external review adapters
- invoke Git commands

## Git Tracking

`.gitignore` should no longer ignore `.review-gauntlet/` wholesale. It should ignore runtime artifacts by default while re-including checkpoint snapshots:

```gitignore
.review-gauntlet/*
!.review-gauntlet/checkpoints/
!.review-gauntlet/checkpoints/**
.review-gauntlet/ledger.sqlite
.review-gauntlet/active-session.json
.review-gauntlet/rules.lock
.review-gauntlet/runs/
```

This keeps Git diffs centered on the latest checkpoint rather than binary ledger state.

## Verification Strategy

Most behavior is locally verifiable with fixture-backed review sessions and direct SQLite assertions. No external credentials or real adapter calls are required.

- Unit/parser coverage verifies command registration.
- Integration CLI tests verify snapshot contents and repeated overwrite behavior.
- SQLite count/state assertions verify checkpoint generation does not mutate runtime state.
- Manual Git ignore checks verify intended tracking behavior because Git ignore semantics are repository-level behavior.
