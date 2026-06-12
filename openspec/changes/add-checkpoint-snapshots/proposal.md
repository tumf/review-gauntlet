---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/targets.py
  - openspec/specs/review-sessions/spec.md
  - .gitignore
---

# Finalize sessions into Git-reviewable checkpoints

**Change Type**: implementation

## Problem / Context

`review-gauntlet` currently stores review coverage, findings, occurrences, and triage events in `.review-gauntlet/ledger.sqlite`. That ledger is the durable source of truth while a session is active, but it is not useful for Git-based review because SQLite diffs are opaque.

A separate checkpoint command creates ambiguity: developers would need to decide whether checkpointing happens before or after finalization, incomplete checkpoints could accidentally become the next review base, and session `finalized` state would duplicate the more important fact of whether a Git-reviewable checkpoint is safe to use as the next base.

The better workflow is to make `finalize` collapse a complete active session into a latest checkpoint, clean up the active runtime session, and make the next `init` default to reviewing from that checkpoint to `HEAD`. If no checkpoint exists, `init` should treat the repository as a first review and use all eligible files.

## Proposed Solution

Change `review-gauntlet finalize` so successful finalization means:

1. verify the active session is complete using the existing completion blockers
2. write deterministic checkpoint files under `.review-gauntlet/checkpoints/latest/`
3. record the current `HEAD` commit as `review_base_commit`
4. mark the checkpoint as `checkpoint_state: complete` and `usable_as_review_base: true`
5. archive or clean up active runtime session state so old sessions are not accidentally advanced
6. return structured output listing the generated checkpoint files and next action

Change `review-gauntlet init` with no explicit target flags so it chooses its default target as follows:

1. if `.review-gauntlet/checkpoints/latest/status.json` exists and is usable, initialize a branch-diff target from `review_base_commit` to `HEAD`
2. if no latest checkpoint exists, initialize an all-files target equivalent to `--all`
3. if a latest checkpoint exists but is invalid or unusable, fail explicitly instead of falling back silently

Keep explicit target modes (`--all`, `--worktree`, `--from/--to`, `--commit`) as overrides. Do not add an independent `checkpoint` command in this change.

The checkpoint snapshot includes:

- schema version, checkpoint state, usability as review base, `review_base_commit`, current `HEAD`, and creation timestamp
- session metadata, target, target digest, ruleset digest, run count, last reviewed target digest, coverage counts, finding state counts, blockers, and next required action
- all findings, including terminal findings normally hidden by `findings` default output
- latest occurrence line evidence for each finding when available
- parsed triage and verification events with stable ordering
- a Markdown summary optimized for PR review

Update repository ignore rules so `.review-gauntlet/checkpoints/latest/**` is trackable while runtime files such as `ledger.sqlite`, `active-session.json`, `rules.lock`, `runs/`, and runtime archives remain ignored.

## Acceptance Criteria

- `review-gauntlet finalize --format json` succeeds only when the active session has no completion blockers.
- Successful `finalize` creates or overwrites `.review-gauntlet/checkpoints/latest/status.json`, `findings.json`, `events.json`, and `summary.md`.
- Successful `finalize` output lists generated checkpoint files and includes `session_id`, `checkpoint_dir`, `checkpoint_state`, `usable_as_review_base`, `review_base_commit`, and `next_required_action`.
- Successful `finalize` records the current Git `HEAD` commit as `review_base_commit` and writes `checkpoint_state: complete` plus `usable_as_review_base: true`.
- Failed `finalize` does not update any latest checkpoint file and does not clean up or archive the active session.
- `status.json` contains status-equivalent data plus active session metadata, target data, current `target_digest`, `last_run_target_digest`, `ruleset_digest`, checkpoint fields, and generated timestamp.
- `findings.json` contains all findings for the finalized active session, including terminal findings, with stable ordering and latest occurrence details when any occurrence exists.
- `events.json` contains all finding events for the session findings with stable ordering, parsed `metadata` when valid, and conservative raw metadata representation when malformed.
- `summary.md` presents checkpoint state, review base commit, coverage, findings, triage events, and blockers in a deterministic Markdown format suitable for PR diff review.
- Successful `finalize` clears the active session marker and archives or cleans up runtime session artifacts so later `review` or `status` cannot silently continue the old session.
- After cleanup, `review` and `status` without a new session fail with an actionable message directing the developer to run `review-gauntlet init`.
- `review-gauntlet init` without explicit target flags uses latest usable checkpoint `review_base_commit -> HEAD` when a usable checkpoint exists.
- `review-gauntlet init` without explicit target flags behaves like `--all` when no latest checkpoint exists.
- `review-gauntlet init` without explicit target flags fails explicitly when a latest checkpoint exists but is invalid, unusable, or references a commit that cannot be resolved.
- Explicit `init` target flags keep their existing behavior and override the checkpoint/default-all target selection.
- `.gitignore` allows committing `.review-gauntlet/checkpoints/latest/**` while keeping ledger/runtime/archive artifacts ignored.

## Explicit Completion Conditions

This proposal is complete when:

- `src/review_gauntlet/cli.py` keeps `finalize` parser-visible and wires successful finalization to checkpoint export plus active session cleanup.
- `src/review_gauntlet/targets.py` or adjacent target-resolution code supports default target selection from latest checkpoint to `HEAD`, with all-files fallback only when no checkpoint exists.
- Checkpoint serialization logic reads from `SessionStore`/SQLite before cleanup and writes the four deterministic files under `.review-gauntlet/checkpoints/latest/`.
- Runtime cleanup/archive leaves no active session that `review` or `status` can accidentally advance after successful `finalize`.
- Tests verify successful finalize checkpoint creation, failed finalize no-write behavior, terminal finding inclusion, event metadata parsing/malformed fallback, active session cleanup, default `init` from checkpoint, default `init` all-files fallback, invalid checkpoint failure, explicit target override behavior, and `.gitignore` tracking rules.
- `make check` passes.
- `cflx openspec validate add-checkpoint-snapshots --strict --evidence warn` passes without unresolved behavior-coverage warnings.

## Out of Scope

- Adding an independent `review-gauntlet checkpoint` command.
- Creating incomplete checkpoints or `--allow-incomplete` behavior.
- Automatically running `git add` or `git commit` from `review-gauntlet`.
- Committing or diffing `ledger.sqlite`.
- Timestamped checkpoint history or `--keep-history` support.
- Changing existing review, triage, or verification state-transition semantics before finalization.
