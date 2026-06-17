## MODIFIED Requirements

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`status`, `run` readiness, and `finalize` SHALL tolerate subprocess startup `OSError` from git-based cleanliness checks without printing a raw traceback as the final user-facing result. If review-universe cleanliness, non-review dirty state, or target digest freshness cannot be verified because a git subprocess cannot start, the command SHALL surface a conservative blocker and SHALL NOT claim finalization readiness.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

Dirty review-universe blockers SHALL identify that review-universe files are dirty relative to `HEAD` without including individual dirty file paths in `finalize_blockers`.

#### Scenario: Malformed decision metadata blocks finalize without crashing

**Given**: a terminal finding event with malformed JSON metadata or an invalid `until` date
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command returns a structured failure result
**And**: the result includes a blocker for invalid or expired terminal-decision metadata
**And**: no traceback is printed
**And**: no latest checkpoint file is created or overwritten
**And**: no runtime session cleanup or archive is performed

#### Scenario: Successful finalize writes latest checkpoint files

**Given**: an active review session with complete reviewed coverage and all live findings closed
**And**: review-universe files are clean relative to `HEAD`
**And**: the current repository `HEAD` can be resolved to a commit
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: `.review-gauntlet/checkpoints/latest/status.json` is written
**And**: `.review-gauntlet/checkpoints/latest/findings.json` is written
**And**: `.review-gauntlet/checkpoints/latest/events.json` is written
**And**: `.review-gauntlet/checkpoints/latest/summary.md` is written
**And**: stdout contains parseable JSON listing the generated files and checkpoint directory
**And**: the result includes `checkpoint_state: complete`
**And**: the result includes `usable_as_review_base: true`
**And**: the result includes a `review_base_commit` equal to the resolved current `HEAD`
**And**: the result includes `next_required_action: init_next_session`

#### Scenario: Dirty review-universe files block finalize

**Given**: an active review session that otherwise satisfies completion requirements
**And**: an eligible review-universe file has staged, unstaged, deleted, renamed, or untracked changes relative to `HEAD`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with a structured dirty-worktree blocker
**And**: the dirty-worktree blocker does not include the dirty file path
**And**: no latest checkpoint file is created or overwritten
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed

#### Scenario: Dirty review-universe status omits dirty file paths

**Given**: an active review session that otherwise satisfies completion requirements
**And**: an eligible review-universe file has staged, unstaged, deleted, renamed, or untracked changes relative to `HEAD`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: the result includes a structured dirty-worktree blocker in `finalize_blockers`
**And**: the dirty-worktree blocker does not include the dirty file path

#### Scenario: Git resource exhaustion blocks status finalization readiness

**Given**: an active review session that otherwise may be close to finalizable
**And**: a git subprocess used to compute review-universe cleanliness raises `OSError` with `errno.EMFILE`
**When**: the developer runs `review-gauntlet status --format json`
**Then**: stdout contains parseable JSON
**And**: `finalize_blockers` includes a blocker indicating git cleanliness or status checks are unavailable due to resource exhaustion
**And**: `can_finalize` is `false`
**And**: no raw traceback is printed as the final user-facing result

#### Scenario: Git resource exhaustion blocks finalize without checkpoint writes

**Given**: an active review session that otherwise may be close to finalizable
**And**: a git subprocess used to compute review-universe cleanliness raises `OSError` with `errno.EMFILE`
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with structured blockers
**And**: no latest checkpoint file is created or overwritten
**And**: `can_finalize` is not reported as true
**And**: no raw traceback is printed as the final user-facing result

#### Scenario: Failed finalize does not update checkpoint or clean up session

**Given**: an active review session with pending review cells, stale review cells, open findings, fixed findings requiring verification, expired terminal decisions, no completed review run, stale target digest evidence, dirty review-universe files, an unresolved current `HEAD`, or unavailable git cleanliness checks
**And**: an existing latest checkpoint may already exist
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with structured blockers
**And**: no latest checkpoint file is created or overwritten
**And**: existing latest checkpoint file contents remain unchanged
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed
