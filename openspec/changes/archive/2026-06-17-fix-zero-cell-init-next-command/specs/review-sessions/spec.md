## MODIFIED Requirements

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL be the diff from that checkpoint's `review_base_commit` to `HEAD`. If no latest checkpoint exists, the default target SHALL include all eligible repository files. If a latest checkpoint exists but cannot safely be used, `init` SHALL fail explicitly instead of silently falling back. This is a breaking change from the previous bare-`init` worktree default; callers that require worktree review SHALL pass `--worktree` explicitly.

`review-gauntlet init` SHALL create an active review session and review cells, but SHALL NOT start review execution or create a review run. Its output SHALL distinguish the active session lifecycle from the absent review-run lifecycle. When initialized review cells exist, the output SHALL point developers to the command that starts review execution. When no review cells are initialized, the output SHALL NOT identify `review-gauntlet review` as the next command.

<!-- Expected canonical result after archive: the canonical review-sessions spec will make explicit that init next-command guidance is conditional on initialized review cells existing, and zero-cell init does not guide developers toward a no-op review command. -->

#### Scenario: Init creates an active session without starting a run

**Given**: a repository with eligible review files
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: the session ledger contains the initialized review cells
**And**: no review run row is created for the session
**And**: stdout includes `session_state: active`, `run_count: 0`, and a lifecycle field showing that no run has started
**And**: stdout identifies `review-gauntlet review` as the next command for starting review execution

#### Scenario: Init with no review cells does not suggest review

**Given**: a repository target whose changed files are all excluded from review cells
**When**: the developer runs `review-gauntlet init --worktree --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: stdout reports `cell_count: 0`, `run_count: 0`, and `run_state: none`
**And**: stdout does not identify `review-gauntlet review` as `next_command`
**And**: no review run row is created for the session
