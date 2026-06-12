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

Two safety constraints are central to the design:

- `review_base_commit` is only sound when reviewed worktree bytes match `HEAD`; dirty review-universe files must block finalization.
- latest checkpoint writes must be atomic and internally consistent so `init` cannot consume a mixed-generation checkpoint after a crash.

## Proposed Solution

Change `review-gauntlet finalize` so successful finalization means:

1. verify the active session is complete using the existing completion blockers
2. verify review-universe files have no tracked, staged, unstaged, or untracked differences from `HEAD`
3. write deterministic checkpoint files atomically under `.review-gauntlet/checkpoints/latest/`
4. record the current `HEAD` commit as `review_base_commit`
5. mark the checkpoint as `checkpoint_state: complete` and `usable_as_review_base: true`
6. archive or clean up active runtime session state so old sessions are not accidentally advanced
7. return structured output listing the generated checkpoint files and next action

Change `review-gauntlet init` with no explicit target flags so it chooses its default target as follows:

1. if `.review-gauntlet/checkpoints/latest/status.json` exists and the checkpoint is usable and internally consistent, initialize a branch-diff target from `review_base_commit` to `HEAD`
2. if no latest checkpoint exists, initialize an all-files target equivalent to `--all`
3. if a latest checkpoint exists but is invalid, inconsistent, unusable, or based on a commit that is not an ancestor of `HEAD`, fail explicitly instead of falling back silently

Keep explicit target modes (`--all`, `--worktree`, `--from/--to`, `--commit`) as overrides. This is a breaking default change for bare `init`: scripts that relied on previous worktree mode must pass `--worktree` explicitly. Do not add an independent `checkpoint` command in this change.

The checkpoint snapshot includes:

- schema version, checkpoint ID, checkpoint state, usability as review base, `review_base_commit`, current `HEAD`, and creation timestamp
- session metadata, target, target digest, ruleset digest, run count, last reviewed target digest, coverage counts, finding state counts, blockers, and checkpoint-specific next required action (`init_next_session`)
- all findings, including terminal findings normally hidden by `findings` default output
- latest occurrence line evidence for each finding when available
- parsed triage and verification events with stable ordering
- a Markdown summary optimized for PR review

Update repository ignore rules so only `.review-gauntlet/checkpoints/latest/**` is trackable while runtime files such as `ledger.sqlite`, `active-session.json`, `rules.lock`, `runs/`, runtime archives, and any future checkpoint history remain ignored.

## Acceptance Criteria

- `review-gauntlet finalize --format json` succeeds only when the active session has no completion blockers and review-universe files are clean relative to `HEAD`.
- Successful `finalize` creates or overwrites `.review-gauntlet/checkpoints/latest/status.json`, `findings.json`, `events.json`, and `summary.md` via an atomic temp-directory replacement so a partial write is not consumable as latest.
- Successful `finalize` output lists generated checkpoint files and includes `session_id`, `checkpoint_id`, `checkpoint_dir`, `checkpoint_state`, `usable_as_review_base`, `review_base_commit`, and `next_required_action`.
- Successful `finalize` records the current Git `HEAD` commit as `review_base_commit` and writes `checkpoint_state: complete` plus `usable_as_review_base: true`.
- Failed `finalize` does not update any latest checkpoint file and does not clean up or archive the active session.
- `status.json` contains status-equivalent data plus active session metadata, target data, current `target_digest`, `last_run_target_digest`, `ruleset_digest`, checkpoint fields, generated timestamp, and `next_required_action: init_next_session`.
- `findings.json` contains all findings for the finalized active session, including terminal findings, with stable ordering and latest occurrence details when any occurrence exists.
- `events.json` contains all non-blocking finding events for the session findings with stable ordering, parsed `metadata` when valid, and conservative raw metadata representation when malformed; malformed terminal-decision metadata remains a finalization blocker.
- `summary.md` presents checkpoint state, review base commit, coverage, findings, triage events, and blockers in a stable-order Markdown format suitable for PR diff review.
- Successful `finalize` clears the active session marker and archives or cleans up runtime session artifacts so later `review` or `status` cannot silently continue the old session.
- After cleanup, `review` and `status` without a new session fail with an actionable message directing the developer to run `review-gauntlet init`.
- `review-gauntlet init` without explicit target flags uses latest usable checkpoint `review_base_commit -> HEAD` when a usable and internally consistent checkpoint exists.
- `review-gauntlet init` without explicit target flags behaves like `--all` when no latest checkpoint exists.
- `review-gauntlet init` without explicit target flags fails explicitly when a latest checkpoint exists but is invalid, internally inconsistent, unusable, references a commit that cannot be resolved, or references a commit that is not an ancestor of `HEAD`.
- Explicit `init` target flags keep their existing behavior and override the checkpoint/default-all target selection.
- `.gitignore` allows committing `.review-gauntlet/checkpoints/latest/**` while keeping ledger/runtime/archive/history artifacts ignored.

## Migration Note

Before this change, `review-gauntlet init` without target flags defaulted to worktree mode. After this change, bare `init` uses latest usable checkpoint to `HEAD`, or all eligible files when no checkpoint exists. Developers or scripts that need the old worktree-only behavior must call `review-gauntlet init --worktree` explicitly.

## Explicit Completion Conditions

This proposal is complete when:

- `src/review_gauntlet/cli.py` keeps `finalize` parser-visible and wires successful finalization to checkpoint export plus active session cleanup.
- `src/review_gauntlet/targets.py` or adjacent target-resolution code supports default target selection from latest checkpoint to `HEAD`, with all-files fallback only when no checkpoint exists.
- Finalization rejects dirty review-universe files before checkpoint export.
- Default checkpoint-based `init` rejects non-ancestor `review_base_commit` values before building cells.
- Checkpoint serialization logic reads from `SessionStore`/SQLite before cleanup and writes the four deterministic files under `.review-gauntlet/checkpoints/latest/` atomically.
- Runtime cleanup/archive leaves no active session that `review` or `status` can accidentally advance after successful `finalize`.
- Tests verify successful finalize checkpoint creation, dirty-worktree finalize blocking, failed finalize no-write behavior using content hashes rather than mtimes, atomic write consistency, terminal finding inclusion, non-terminal malformed event metadata fallback, terminal malformed metadata blocking, active session cleanup, default `init` from checkpoint, default `init` all-files fallback, invalid checkpoint failure, non-ancestor checkpoint failure, explicit target override behavior, and `.gitignore` tracking rules.
- `make check` passes.
- `cflx openspec validate add-checkpoint-snapshots --strict --evidence warn` passes without unresolved behavior-coverage warnings.

## Out of Scope

- Adding an independent `review-gauntlet checkpoint` command.
- Creating incomplete checkpoints or `--allow-incomplete` behavior.
- Automatically running `git add` or `git commit` from `review-gauntlet`.
- Committing or diffing `ledger.sqlite`.
- Timestamped checkpoint history or `--keep-history` support.
- Archive retention, pruning, or compaction policies for `.review-gauntlet/archive/`.
- Changing existing review, triage, or verification state-transition semantics before finalization.
