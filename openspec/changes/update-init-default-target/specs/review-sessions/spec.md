## MODIFIED Requirements

### Requirement: Init SHALL default to latest checkpoint or all-files review

`review-gauntlet init` without explicit target flags SHALL choose a deterministic default target. If a usable latest checkpoint exists, the default target SHALL include eligible files changed from that checkpoint's `review_base_commit` to `HEAD` and SHALL also include current eligible uncommitted worktree changes: staged, unstaged, and untracked non-ignored files. If no latest checkpoint exists, the default target SHALL be an all-files review over the current eligible review inventory. If a latest checkpoint exists but is invalid or unusable, initialization SHALL fail with the checkpoint validation error instead of falling back to all-files review. The `--worktree` flag remains an explicit request for worktree-only review; callers that need committed changes without uncommitted worktree changes SHALL use `--commit` or `--from/--to`.

#### Scenario: Init creates an active session without starting a run

**Given**: a repository with eligible review files
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: the session ledger contains the initialized review cells
**And**: no review run row is created for the session
**And**: stdout includes `session_state: active`, `run_count: 0`, and a lifecycle field showing that no run has started
**And**: stdout identifies `review-gauntlet review` as the next command for starting review execution

#### Scenario: Init with no review cells does not suggest review

**Given**: a repository target whose selected files are all excluded from review cells
**When**: the developer runs `review-gauntlet init --format json`
**Then**: `.review-gauntlet/active-session.json` records the new active session ID
**And**: stdout reports `cell_count: 0`, `run_count: 0`, and `run_state: none`
**And**: stdout does not identify `review-gauntlet review` as `next_command`
**And**: no review run row is created for the session

#### Scenario: Worktree flag is accepted

**Given**: an installed `review-gauntlet` CLI
**When**: the developer runs `review-gauntlet init --worktree`
**Then**: the session target is a WORKTREE kind reviewing uncommitted changes
**And**: the command exits successfully

#### Scenario: Init with no flags and no checkpoint defaults to all-files review

**Given**: a repository with no latest checkpoint
**And**: the repository has eligible unchanged tracked files and eligible uncommitted files
**When**: the developer runs `review-gauntlet init` without target flags
**Then**: the session target is ALL kind
**And**: review cells cover the eligible current review inventory, including unchanged tracked files and eligible uncommitted files

#### Scenario: Init with latest checkpoint includes uncommitted worktree changes

**Given**: a repository with a usable latest checkpoint whose `review_base_commit` is an ancestor of `HEAD`
**And**: there are eligible files changed between the checkpoint base and `HEAD`
**And**: there are eligible staged, unstaged, and untracked non-ignored worktree files
**When**: the developer runs `review-gauntlet init` without target flags
**Then**: the session target records the checkpoint base and `HEAD` as the committed review range
**And**: the session target records that worktree changes are included
**And**: review cells cover the union of eligible checkpoint-base-to-HEAD files and eligible staged, unstaged, and untracked worktree files

#### Scenario: Explicit branch init excludes uncommitted worktree changes

**Given**: a repository with a valid base reference and head reference
**And**: there are eligible uncommitted worktree files outside that committed range
**When**: the developer runs `review-gauntlet init --from <base> --to <head>`
**Then**: the session target is BRANCH kind without worktree inclusion
**And**: review cells cover eligible files changed between the base and head references
**And**: review cells do not include the unrelated uncommitted worktree files
