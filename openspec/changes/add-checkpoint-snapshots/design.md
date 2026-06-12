# Design: Finalize-driven checkpoint snapshots

## Goals

- Preserve `ledger.sqlite` as the durable source of truth while a session is active.
- Make `finalize` the single operation that closes a complete session into a Git-reviewable latest checkpoint.
- Ensure latest checkpoints are always complete and safe to use as the next review base.
- Make default `init` deterministic: latest checkpoint to `HEAD`, otherwise all eligible files.
- Prevent old active sessions from being accidentally advanced after they have been finalized into a checkpoint.

## Non-Goals

- No independent `checkpoint` command.
- No incomplete checkpoint snapshots.
- No automatic Git add/commit.
- No timestamped checkpoint history in the first implementation.
- No change to review/mark/verify-fixes state transitions before finalization.

## Workflow

### First review

```bash
review-gauntlet init
review-gauntlet review --config review-gauntlet.jsonc
review-gauntlet findings
review-gauntlet mark RGF-0001 false-positive --reason "..."
review-gauntlet verify-fixes --config review-gauntlet.jsonc
review-gauntlet finalize
git add .review-gauntlet/checkpoints/latest
git commit -m "Record review checkpoint"
```

When no latest checkpoint exists, `init` behaves like `--all`.

### Subsequent reviews

```bash
review-gauntlet init
review-gauntlet review --config review-gauntlet.jsonc
...
review-gauntlet finalize
git add .review-gauntlet/checkpoints/latest
git commit -m "Record review checkpoint"
```

When a usable latest checkpoint exists, `init` behaves like `--from <review_base_commit> --to HEAD`.

## Finalize Behavior

`finalize` keeps the existing completion gate semantics: it only succeeds when coverage is closed, live findings are closed, terminal decisions are not expired, at least one real review run exists, and the last reviewed target digest matches the current target digest.

On success, `finalize`:

1. captures checkpoint data from the active session ledger
2. resolves current `HEAD` to a commit OID
3. writes `.review-gauntlet/checkpoints/latest/status.json`
4. writes `.review-gauntlet/checkpoints/latest/findings.json`
5. writes `.review-gauntlet/checkpoints/latest/events.json`
6. writes `.review-gauntlet/checkpoints/latest/summary.md`
7. archives or cleans up active runtime state
8. emits a structured result

On failure, `finalize`:

- does not update checkpoint files
- does not archive or remove active session state
- emits blockers and exits non-zero as it does today

## Checkpoint Data Model

Checkpoint output is derived from existing session tables and computed status logic before cleanup.

### `status.json`

`status.json` combines status output with durable metadata, freshness evidence, and review-base evidence:

- `schema_version`
- `checkpoint_state`, always `complete`
- `usable_as_review_base`, always `true`
- `review_base_commit`, resolved current `HEAD`
- `created_from_head`, same commit as `review_base_commit` in the initial design
- `created_at`
- `session_id`
- `source_session_state`
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

`target_digest` is recomputed against the current repository root. `last_run_target_digest` is read from the latest real run record and must not be refreshed by finalization except through real review work that already happened before finalization.

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

`events.json` emits finding events joined to the session's findings so unrelated session data cannot leak into the checkpoint. Ordering is by `event_id`.

Metadata parsing follows a conservative rule:

- valid object JSON becomes `metadata`
- invalid or non-object JSON becomes `metadata_raw` plus a parse marker

This preserves human decision evidence even when malformed metadata would otherwise block completion.

### `summary.md`

`summary.md` is a human review surface, not a source of truth. It summarizes the same data as JSON files using deterministic Markdown tables and lists:

- checkpoint state and review base commit
- session and target summary
- coverage counts
- finding state counts
- findings table
- event summary
- blocker section, expected to be empty for successful finalization

Markdown cells should escape pipes and normalize newlines so table structure remains stable.

## Runtime Cleanup / Archive

Successful `finalize` means the active session should no longer be advanced. The implementation should remove or invalidate `.review-gauntlet/active-session.json` and archive enough runtime evidence for local troubleshooting without making it Git-tracked.

Acceptable initial strategies:

- move `ledger.sqlite`, `rules.lock`, and `runs/` into `.review-gauntlet/archive/<session_id>/`; or
- copy/export enough evidence to archive, then remove the active session marker while leaving ignored runtime files inaccessible to normal active-session commands.

The externally visible requirement is that after successful `finalize`, commands that require an active session such as `review` and `status` do not silently continue the old session. They must fail with an actionable message directing the developer to run `review-gauntlet init`.

## Default Init Target Selection

Explicit target modes retain priority:

- `--all`
- `--worktree`
- `--from/--to`
- `--commit`

When no explicit target mode is selected, `init` resolves the default target:

1. If `.review-gauntlet/checkpoints/latest/status.json` is absent, use all eligible files, equivalent to `--all`.
2. If latest checkpoint exists, parse it and require `usable_as_review_base: true` plus a non-empty `review_base_commit`.
3. Verify `review_base_commit` resolves to a Git commit in the current repository.
4. Use a branch target equivalent to `--from <review_base_commit> --to HEAD`.

If the checkpoint file exists but is malformed, unusable, missing `review_base_commit`, or references an unknown commit, `init` fails explicitly. It must not silently fall back to all-files mode because that hides checkpoint corruption or repository mismatch.

## Filesystem Behavior

Finalization writes to `.review-gauntlet/checkpoints/latest/`. The implementation should create the directory when needed and overwrite the four canonical files each time successful finalization occurs.

The initial scope intentionally avoids timestamped history. A future history feature can copy the same generated payload into a history directory, but that is not required for the first implementation.

## Git Tracking

`.gitignore` should no longer ignore `.review-gauntlet/` wholesale. It should ignore runtime artifacts by default while re-including latest checkpoint snapshots:

```gitignore
.review-gauntlet/*
!.review-gauntlet/checkpoints/
!.review-gauntlet/checkpoints/**
.review-gauntlet/ledger.sqlite
.review-gauntlet/active-session.json
.review-gauntlet/rules.lock
.review-gauntlet/runs/
.review-gauntlet/archive/
```

This keeps Git diffs centered on the latest checkpoint rather than binary ledger state or local runtime archives.

## Verification Strategy

Most behavior is locally verifiable with fixture-backed review sessions, temporary Git repositories, and direct SQLite assertions. No external credentials or real adapter calls are required.

- Integration CLI tests verify finalization writes checkpoint contents only on success.
- SQLite count/state assertions verify failed finalization does not mutate checkpoint or cleanup state.
- Temporary Git repos verify default `init` selects checkpoint-to-HEAD or all-files fallback.
- Active-session command tests verify cleanup prevents old sessions from being advanced.
- Manual Git ignore checks verify intended tracking behavior because Git ignore semantics are repository-level behavior.
