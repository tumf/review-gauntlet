## ADDED Requirements

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL be the diff from that checkpoint's `review_base_commit` to `HEAD`. If no latest checkpoint exists, the default target SHALL include all eligible repository files. If a latest checkpoint exists but cannot safely be used, `init` SHALL fail explicitly instead of silently falling back. This is a breaking change from the previous bare-`init` worktree default; callers that require worktree review SHALL pass `--worktree` explicitly.

#### Scenario: Init defaults to latest checkpoint diff when available

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists
**And**: the latest checkpoint files share consistent checkpoint metadata
**And**: the checkpoint contains `usable_as_review_base: true`
**And**: the checkpoint contains a `review_base_commit` that resolves to a commit in the current repository
**And**: `review_base_commit` is an ancestor of `HEAD`
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the initialized session target is equivalent to `--from <review_base_commit> --to HEAD`
**And**: review cells are scoped to files changed between that commit and `HEAD`

#### Scenario: Init defaults to all files when no checkpoint exists

**Given**: `.review-gauntlet/checkpoints/latest/status.json` does not exist
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the initialized session target is equivalent to `--all`
**And**: review cells are built from all eligible repository files

#### Scenario: Init rejects invalid latest checkpoint instead of falling back

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists
**And**: the checkpoint is malformed, internally inconsistent, has `usable_as_review_base` other than `true`, lacks `review_base_commit`, references a commit that cannot be resolved, or references a commit that is not an ancestor of `HEAD`
**When**: the developer runs `review-gauntlet init --format json` without target flags
**Then**: the command fails with an actionable checkpoint error
**And**: no all-files fallback session is created

#### Scenario: Explicit init target flags override checkpoint default

**Given**: `.review-gauntlet/checkpoints/latest/status.json` exists and is usable
**When**: the developer runs `review-gauntlet init --all`, `review-gauntlet init --worktree`, `review-gauntlet init --from main --to HEAD`, or `review-gauntlet init --commit <commit>`
**Then**: the explicit target mode is used
**And**: the latest checkpoint does not override that explicit target selection

#### Scenario: Checkpoint files are the only tracked review-gauntlet state

**Given**: repository ignore rules for `.review-gauntlet` state
**When**: finalize writes checkpoint files under `.review-gauntlet/checkpoints/latest/`
**Then**: those checkpoint files are eligible for Git tracking
**And**: `.review-gauntlet/ledger.sqlite` remains ignored
**And**: `.review-gauntlet/active-session.json` remains ignored
**And**: `.review-gauntlet/runs/` remains ignored
**And**: `.review-gauntlet/rules.lock` remains ignored
**And**: `.review-gauntlet/archive/` remains ignored
**And**: checkpoint history directories other than `latest/` remain ignored

## MODIFIED Requirements

### Requirement: Finalize SHALL validate completion without running review work

`status` and `finalize` SHALL tolerate malformed persisted finding-event metadata without crashing. Malformed terminal-decision metadata SHALL be surfaced conservatively as a blocker so completion cannot hide invalid waiver or accepted-risk state.

`review-gauntlet finalize` SHALL close a complete active review session into deterministic latest-only checkpoint files that are suitable for Git diff review and safe as the next review base. Finalization SHALL only write checkpoint files when completion blockers are absent, when review-universe files are clean relative to `HEAD`, and when current `HEAD` can be resolved to a commit. The checkpoint SHALL be derived from the existing durable session ledger, SHALL include review coverage, findings, triage events, and review-base metadata, and SHALL NOT replace the ledger as the source of truth before successful finalization.

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
**And**: no latest checkpoint file is created or overwritten
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed

#### Scenario: Failed finalize does not update checkpoint or clean up session

**Given**: an active review session with pending review cells, stale review cells, open findings, fixed findings requiring verification, expired terminal decisions, no completed review run, stale target digest evidence, dirty review-universe files, or an unresolved current `HEAD`
**And**: an existing latest checkpoint may already exist
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: the command fails with structured blockers
**And**: no latest checkpoint file is created or overwritten
**And**: existing latest checkpoint file contents remain unchanged
**And**: the active session marker remains usable for continuing review work
**And**: no runtime session cleanup or archive is performed

#### Scenario: Finalize exposes full review state for diff review

**Given**: an active review session with reviewed cells, terminal findings, finding occurrences, and finding events
**When**: the developer runs `review-gauntlet finalize`
**Then**: `status.json` includes checkpoint ID, session metadata, target information, current target digest, last reviewed target digest, ruleset digest, coverage counts, finding state counts, run count, checkpoint state, review base commit, finalization blockers, and next required action
**And**: `findings.json` includes all session findings including terminal findings
**And**: each finding includes latest occurrence line evidence when occurrence evidence exists
**And**: `events.json` includes triage and verification events for the session findings in deterministic order
**And**: `summary.md` presents the same state in a Markdown format suitable for PR review

#### Scenario: Finalize preserves malformed non-terminal event metadata as evidence

**Given**: an active review session with a non-terminal-decision finding event whose metadata is malformed JSON or not a JSON object
**When**: the developer runs `review-gauntlet finalize --format json`
**Then**: finalization handles the metadata without a traceback
**And**: `events.json` includes the event with raw metadata evidence when the checkpoint is written
**And**: finalization does not reinterpret the event as a different triage decision

#### Scenario: Finalize publishes checkpoint atomically

**Given**: an active review session eligible for finalization
**And**: an existing `.review-gauntlet/checkpoints/latest/` snapshot may already exist
**When**: the developer runs `review-gauntlet finalize`
**Then**: checkpoint files are generated with matching checkpoint metadata before they become the new `latest/` snapshot
**And**: `status.json`, `findings.json`, `events.json`, and `summary.md` all identify the same checkpoint generation
**And**: a partial generation failure cannot leave a mixed-generation latest checkpoint consumable by the next `init`

#### Scenario: Finalize is latest-only by default

**Given**: an active review session eligible for finalization
**And**: an existing `.review-gauntlet/checkpoints/latest/` snapshot
**When**: the developer runs `review-gauntlet finalize`
**Then**: the command overwrites the same latest snapshot files atomically
**And**: no timestamped or session-history checkpoint directory is created by default

#### Scenario: Successful finalize prevents continuing the old active session

**Given**: an active review session eligible for finalization
**When**: the developer runs `review-gauntlet finalize`
**Then**: the active session marker is removed or invalidated after checkpoint files are written
**And**: subsequent `review-gauntlet review` without a new `init` fails with an actionable message
**And**: subsequent `review-gauntlet status` without a new `init` fails with an actionable message
**And**: neither command silently advances or reports the finalized old session as active
