## MODIFIED Requirements

### Requirement: Status and findings commands SHALL expose actionable session state

`findings --mark` SHALL map public CLI mark names to the persisted finding state values before filtering. Hyphenated public names such as `false-positive`, `accepted-risk`, and `fixed-pending-verification` SHALL match their underscore persisted states subject to the existing default terminal suppression and `--all` visibility rules.

`findings --path` filters SHALL accept only repository-relative paths and directory prefixes. Absolute paths and parent-directory traversal SHALL fail with a usage error so filtering semantics remain repository-scoped and deterministic.

`findings` SHALL cap emitted findings to 10 records by default after applying terminal visibility, path filters, and mark filters. `findings --limit N` SHALL cap emitted findings to the requested positive integer limit. `findings --all-findings` SHALL disable the result-size cap without changing terminal visibility. `findings --limit N --all-findings` SHALL fail with a usage error.

`findings` SHALL expose count metadata in both structured and text result payloads. `total` SHALL be the number of findings after terminal visibility, path, and mark filters but before result-size limiting. `returned` SHALL be the number of findings actually emitted. Findings SHALL be ordered deterministically by path, start line, end line, and finding ID before any result-size cap is applied.

Status and freshness computations SHALL use the same resolved repository root for review-universe traversal and relative digest paths. Invoking session status with the default root `.` SHALL be equivalent to invoking it with the absolute repository root. When current review cells are pending or stale, `status` SHALL expose review work as the next required action before exposing live finding work, including confirmed finding work and fixed-finding verification work. When the last reviewed target digest differs from the current target digest, `status` SHALL expose review work as the next required action without requiring `status` to mutate persisted review cell states, including when fixed findings require verification.

`review-gauntlet ready` SHALL expose whether a continuation task is available through both stdout and process exit status. When a ready prompt exists, the command SHALL emit the existing prompt output and exit `0`. When no continuation task exists, the command SHALL preserve the existing no-task output while exiting `1` so external orchestrators can distinguish no-op completion without parsing stdout. When current review cells are pending or stale, `ready` SHALL prompt for review coverage before prompting for reopened, untriaged, confirmed, or fixed-pending finding work. After review-cell and finding continuation work is exhausted, `ready` SHALL treat dirty working-tree finalize blockers as actionable by returning a prompt that instructs the agent to commit intended git changes before finalizing. Commit-resolvable dirty blockers include dirty review-universe files relative to `HEAD` and uncommitted non-review files. `ready` SHALL NOT treat non-dirty finalize blockers as commit-resolvable. `ready` SHALL also treat target digest drift since the last review run as actionable review work, returning a review-oriented prompt without mutating session ledger state.

<!-- Expected canonical result after archive: findings documents bounded default output, explicit limit override, all-findings escape hatch, total/returned metadata, and deterministic path-first ordering while preserving existing status and ready behavior. -->

#### Scenario: Findings default output is bounded and counted

**Given**: an active session with more than 10 non-terminal findings across multiple paths
**When**: the developer runs `review-gauntlet findings --format json`
**Then**: stdout contains parseable JSON with `total` greater than `10`
**And**: stdout contains `returned` equal to `10`
**And**: stdout contains exactly 10 findings
**And**: the emitted findings are ordered by path, start line, end line, and finding ID
**And**: no finding state, run, or finding event is modified

#### Scenario: Findings limit overrides the default cap

**Given**: an active session with at least 5 non-terminal findings
**When**: the developer runs `review-gauntlet findings --limit 3 --format json`
**Then**: stdout contains parseable JSON with `returned` equal to `3`
**And**: stdout contains exactly 3 findings
**And**: `total` remains the filtered finding count before limiting

#### Scenario: Findings all-findings disables only the size cap

**Given**: an active session with non-terminal and terminal findings
**When**: the developer runs `review-gauntlet findings --all-findings --format json`
**Then**: stdout contains parseable JSON with every non-terminal finding
**And**: stdout omits terminal findings unless `--all` is also provided
**And**: `returned` equals `total`

#### Scenario: Findings all and all-findings are independent

**Given**: an active session with non-terminal and terminal findings
**When**: the developer runs `review-gauntlet findings --all --all-findings --format json`
**Then**: stdout contains parseable JSON with terminal and non-terminal findings
**And**: `returned` equals `total`

#### Scenario: Findings rejects conflicting limit controls

**Given**: an active session
**When**: the developer runs `review-gauntlet findings --limit 3 --all-findings`
**Then**: the command fails with a usage error
**And**: no finding state, run, or finding event is modified
