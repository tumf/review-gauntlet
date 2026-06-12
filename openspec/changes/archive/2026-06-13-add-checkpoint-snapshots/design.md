# Design: Finalize-driven checkpoint snapshots

## Goals

- Preserve `ledger.sqlite` as the durable source of truth while a session is active.
- Make `finalize` the single operation that closes a complete session into a Git-reviewable latest checkpoint.
- Ensure latest checkpoints are always complete and safe to use as the next review base.
- Make default `init` deterministic: latest checkpoint to `HEAD`, otherwise all eligible files.
- Prevent old active sessions from being accidentally advanced after they have been finalized into a checkpoint.
- Prevent silent corruption from dirty worktrees, partial checkpoint writes, and non-ancestor checkpoint bases.

## Non-Goals

- No independent `checkpoint` command.
- No incomplete checkpoint snapshots.
- No automatic Git add/commit.
- No timestamped checkpoint history in the first implementation.
- No archive retention/pruning policy in the first implementation.
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

### Migration from old bare init behavior

Before this change, `review-gauntlet init` without explicit target flags defaulted to worktree mode. After this change, bare `init` uses latest usable checkpoint to `HEAD`, or all eligible files when no checkpoint exists. Developers and scripts that require the old worktree behavior must call `review-gauntlet init --worktree` explicitly.

## Finalize Behavior

`finalize` keeps the existing completion gate semantics: it only succeeds when coverage is closed, live findings are closed, terminal decisions are not expired, at least one real review run exists, and the last reviewed target digest matches the current target digest.

The completion gate is extended with a dirty-worktree safety check. Because `target_digest` is computed from working-tree bytes, recording `HEAD` as `review_base_commit` is only safe when eligible review-universe files have no staged, unstaged, or untracked differences from `HEAD`. If any eligible review-universe file is dirty, finalization fails with a blocker and does not update latest checkpoint files.

On success, `finalize`:

1. captures checkpoint data from the active session ledger
2. verifies eligible review-universe files are clean relative to `HEAD`
3. resolves current `HEAD` to a commit OID
4. writes checkpoint files to a temporary directory
5. verifies all generated files carry the same checkpoint metadata
6. atomically replaces `.review-gauntlet/checkpoints/latest/`
7. archives or cleans up active runtime state
8. emits a structured result

On failure, `finalize`:

- does not update checkpoint files
- does not archive or remove active session state
- emits blockers and exits non-zero as it does today

## Dirty Worktree Check

The dirty check is scoped to files that can affect review truth. The implementation should inspect eligible review-universe paths for:

- staged changes
- unstaged changes
- untracked eligible files
- deletions or renames affecting eligible files

The check may use Git status/diff plumbing plus the existing review path filter. Non-review artifacts ignored by review-universe rules should not block finalization. If the check cannot determine cleanliness reliably, it should fail closed with an actionable blocker rather than emit a usable review base.

## Atomic Checkpoint Writes

Checkpoint generation must not leave a mixed-generation `latest/` directory. The writer should:

1. compute a `checkpoint_id`, for example from `session_id`, `review_base_commit`, and generation time or a UUID
2. write all four files into `.review-gauntlet/checkpoints/latest.tmp/` or another same-filesystem temporary path
3. include `checkpoint_id`, `session_id`, and `review_base_commit` in `status.json`, `findings.json`, and `events.json`, and include the same identifiers in `summary.md`
4. verify generated files are internally consistent before publishing
5. atomically replace `latest/` with the completed temporary directory

If the process crashes before the replacement, the previous `latest/` remains intact. If replacement atomicity is platform-limited for directories, the implementation must still avoid a state where `init` can consume a partially generated checkpoint; writing `status.json` last plus consistency validation is an acceptable fallback only if `init` validates all file-level checkpoint metadata before use.

## Checkpoint Data Model

Checkpoint output is derived from existing session tables and computed status logic before cleanup.

`deterministic` means stable ordering and stable formatting for the same generated state. It does not mean byte-identical output across finalizations because `created_at` is a generation timestamp unless a future implementation chooses to derive it from commit metadata.

### `status.json`

`status.json` combines status output with durable metadata, freshness evidence, and review-base evidence:

- `schema_version`
- `checkpoint_id`
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
- `next_required_action`, set to `init_next_session` for complete checkpoints

`target_digest` is recomputed against the current repository root. `last_run_target_digest` is read from the latest real run record and must not be refreshed by finalization except through real review work that already happened before finalization.

### `findings.json`

`findings.json` includes all active-session findings, including terminal findings. Each finding includes the persisted finding row plus latest occurrence evidence:

- `checkpoint_id`
- `session_id`
- `review_base_commit`
- `finding_id`
- `state`
- `path`
- `rule_id`
- `content`
- parsed `metadata` when valid, raw fallback when malformed
- `latest_occurrence` with `run_id`, `cell_id`, `start_line`, `end_line`, and `imprecise`

Ordering should be stable and numeric for standard zero-padded `RGF-<number>` IDs, with lexical fallback for non-standard IDs.

### `events.json`

`events.json` emits finding events joined to the session's findings so unrelated session data cannot leak into the checkpoint. Ordering is by `event_id`.

Metadata parsing follows a conservative rule:

- valid object JSON becomes `metadata`
- invalid or non-object JSON on non-terminal-decision events becomes `metadata_raw` plus a parse marker
- malformed terminal-decision metadata remains governed by the canonical finalize blocker and prevents checkpoint creation

This preserves non-blocking human decision evidence without contradicting the existing rule that malformed terminal-decision metadata blocks finalization.

### `summary.md`

`summary.md` is a human review surface, not a source of truth. It summarizes the same data as JSON files using deterministic Markdown tables and lists:

- checkpoint ID, state, and review base commit
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

Archive growth is accepted in the initial scope. Retention, pruning, and compaction are future work.

## Default Init Target Selection

Explicit target modes retain priority:

- `--all`
- `--worktree`
- `--from/--to`
- `--commit`

When no explicit target mode is selected, `init` resolves the default target:

1. If `.review-gauntlet/checkpoints/latest/status.json` is absent, use all eligible files, equivalent to `--all`.
2. If latest checkpoint exists, parse it and require `usable_as_review_base: true` plus a non-empty `review_base_commit`.
3. Validate `status.json`, `findings.json`, `events.json`, and `summary.md` belong to the same checkpoint generation using `checkpoint_id`, `session_id`, and `review_base_commit` metadata.
4. Verify `review_base_commit` resolves to a Git commit in the current repository.
5. Verify `review_base_commit` is an ancestor of `HEAD` with merge-base semantics.
6. Use a branch target equivalent to `--from <review_base_commit> --to HEAD`.

If the checkpoint file exists but is malformed, internally inconsistent, unusable, missing `review_base_commit`, references an unknown commit, or references a non-ancestor commit, `init` fails explicitly. It must not silently fall back to all-files mode because that hides checkpoint corruption, repository mismatch, or history rewrite risk.

## Filesystem Behavior

Finalization writes to `.review-gauntlet/checkpoints/latest/` by way of an atomic publish step. The implementation should create required parent directories when needed and overwrite the canonical latest checkpoint each time successful finalization occurs.

The initial scope intentionally avoids timestamped history. A future history feature can copy the same generated payload into a history directory, but that is not required for the first implementation.

## Git Tracking

`.gitignore` should no longer ignore `.review-gauntlet/` wholesale. It should ignore runtime artifacts by default while re-including only latest checkpoint snapshots:

```gitignore
.review-gauntlet/*
!.review-gauntlet/checkpoints/
.review-gauntlet/checkpoints/*
!.review-gauntlet/checkpoints/latest/
!.review-gauntlet/checkpoints/latest/**
.review-gauntlet/ledger.sqlite
.review-gauntlet/active-session.json
.review-gauntlet/rules.lock
.review-gauntlet/runs/
.review-gauntlet/archive/
```

Some ignore lines are redundant after `.review-gauntlet/*`; they are intentionally kept as defense-in-depth documentation for runtime artifacts that must not become tracked if the surrounding pattern changes later. Future checkpoint history directories remain ignored unless a later proposal explicitly changes that.

## Verification Strategy

Most behavior is locally verifiable with fixture-backed review sessions, temporary Git repositories, and direct SQLite assertions. No external credentials or real adapter calls are required.

- Integration CLI tests verify finalization writes checkpoint contents only on success.
- Git-based integration tests verify dirty eligible files block finalization.
- Writer tests verify atomic publish and generation-consistency metadata.
- Content-hash assertions verify failed finalization does not mutate checkpoint files.
- Temporary Git repos verify default `init` selects checkpoint-to-HEAD, all-files fallback, and rejects non-ancestor checkpoint bases.
- Active-session command tests verify cleanup prevents old sessions from being advanced.
- Manual Git ignore checks verify intended tracking behavior because Git ignore semantics are repository-level behavior.
