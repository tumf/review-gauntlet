---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - openspec/specs/review-sessions/spec.md
  - .gitignore
---

# Add Git-reviewable checkpoint snapshots

**Change Type**: implementation

## Problem / Context

`review-gauntlet` currently stores review coverage, findings, occurrences, and triage events in `.review-gauntlet/ledger.sqlite`. That ledger is appropriate as the durable source of truth, but it is not useful for Git-based review because SQLite diffs are opaque.

Developers need a small, normalized snapshot of the current review session that can be committed and reviewed in PRs after review runs, human triage, fix verification, and finalization checks. The snapshot must preserve the constitution principles that coverage is explicit, unknown states remain visible, human decisions remain ledger-backed, and review orchestration stays external.

## Proposed Solution

Add an explicit `review-gauntlet checkpoint [root] [--format text|json]` command that writes deterministic, Git-reviewable files under:

```text
.review-gauntlet/checkpoints/latest/
  status.json
  findings.json
  events.json
  summary.md
```

The command reads the active session from the existing ledger and writes a latest-only snapshot. It does not replace the ledger, mutate finding states, run review work, finalize sessions, or invoke Git.

The checkpoint snapshot includes:

- session metadata, target, target digest, ruleset digest, run count, last reviewed target digest, coverage counts, finding state counts, finalization blockers, and next required action
- all findings, including terminal findings normally hidden by `findings` default output
- latest occurrence line evidence for each finding when available
- parsed triage and verification events with stable ordering
- a Markdown summary optimized for PR review

Update repository ignore rules so `.review-gauntlet/checkpoints/latest/**` is trackable while runtime files such as `ledger.sqlite`, `active-session.json`, `rules.lock`, and `runs/` remain ignored.

## Acceptance Criteria

- `review-gauntlet checkpoint --format json` creates or overwrites `.review-gauntlet/checkpoints/latest/` with `status.json`, `findings.json`, `events.json`, and `summary.md`.
- The command output lists generated files and includes `session_id`, `checkpoint_dir`, `can_finalize`, and `next_required_action`.
- `status.json` contains status-equivalent data plus active session metadata, target data, current `target_digest`, `last_run_target_digest`, and `ruleset_digest` when available.
- `findings.json` contains all findings for the active session, including terminal findings, with stable ordering and latest occurrence details when any occurrence exists.
- `events.json` contains all finding events for the active session with stable ordering, parsed `metadata` when valid, and conservative raw metadata representation when malformed.
- `summary.md` presents coverage, findings, triage state, and finalize blockers in a deterministic Markdown format suitable for PR diff review.
- Running `checkpoint` repeatedly updates the same `latest/` files instead of creating timestamped history directories.
- Checkpoint generation does not create runs, change cell states, change finding states, finalize sessions, or execute adapter commands.
- `.gitignore` allows committing `.review-gauntlet/checkpoints/latest/**` while keeping ledger/runtime artifacts ignored.

## Explicit Completion Conditions

This proposal is complete when:

- `src/review_gauntlet/cli.py` exposes a parser-visible `checkpoint` command with text and JSON output formats.
- Checkpoint serialization logic reads from `SessionStore`/SQLite and writes the four deterministic files under `.review-gauntlet/checkpoints/latest/`.
- Tests verify file creation, repeated overwrite behavior, terminal finding inclusion, event metadata parsing/malformed fallback, no runtime state mutation, CLI JSON output, and `.gitignore` tracking rules.
- `make check` passes.
- `cflx openspec validate add-checkpoint-snapshots --strict --evidence warn` passes without unresolved behavior-coverage warnings.

## Out of Scope

- Automatically running `git add` or `git commit` from `review-gauntlet`.
- Committing or diffing `ledger.sqlite`.
- Timestamped checkpoint history or `--keep-history` support.
- Automatically generating checkpoints as an implicit side effect of `review`, `mark`, `verify-fixes`, or `finalize`.
- Changing existing review, triage, verification, or finalization state-transition semantics.
