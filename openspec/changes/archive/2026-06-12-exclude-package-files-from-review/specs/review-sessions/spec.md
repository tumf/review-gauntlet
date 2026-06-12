## MODIFIED Requirements

### Requirement: Review sessions SHALL persist durable state

`review-gauntlet` SHALL support durable review sessions stored under `.review-gauntlet/` at the reviewed repository root. A session SHALL preserve the target policy, active session metadata, ruleset identity, review universe state, immutable run history, review cells, findings, finding occurrences, and finding events. Target policy selection SHALL occur during `init`, not during `review`. The default `init` target SHALL be OCR-compatible workspace diff review; full-repository review SHALL require explicit `--all`. Review universe construction SHALL apply deterministic built-in artifact exclusions and default review-path exclusions before creating review cells. Default review-path exclusions SHALL include `openspec/`, `tests/`, `docs/`, common test-file patterns, and package manager manifest or lock files such as `uv.lock`, `package.json`, `package-lock.json`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `pom.xml`, `Gemfile.lock`, and equivalent dependency metadata files. Review-path exclusions SHALL apply consistently to session review cell creation, review universe file digests, and target digests. Package manager manifest or lock files MAY remain visible in general inventory diagnostics. Review cell ledger identity SHALL be scoped to the owning session, so multiple sessions MAY contain the same deterministic review cell ID without corrupting or blocking each other. `init` SHALL support `--format text|json`, defaulting to `text`, and SHALL NOT expose `--audience` because it only emits a final initialization result.

<!-- Expected canonical result after archive: the review universe requirement documents package manager manifest and lock file exclusions as default review-path exclusions that affect session cells and digests, while inventory diagnostics may still list them. -->

#### Scenario: Initialize a second session with overlapping review cells

**Given**: a repository with an existing `.review-gauntlet/` ledger from a prior `review-gauntlet init`
**And**: the next requested target includes one or more files that produce the same deterministic review cell IDs as the prior session
**When**: the developer runs `review-gauntlet init --all --format json`
**Then**: the CLI creates a new durable session
**And**: records review cells for the new session without failing on duplicate deterministic `cell_id` values from the prior session
**And**: keeps coverage and cell state scoped to each session
**And**: stdout contains parseable JSON for the final initialization result

#### Scenario: Init rejects obsolete output controls

**Given**: a repository root
**When**: the developer runs `review-gauntlet init --format human`
**Then**: the command fails with a usage error
**When**: the developer runs `review-gauntlet init --audience agent`
**Then**: the command fails with a usage error

#### Scenario: Package files are excluded from default review cells

**Given**: a repository with changed package files such as `uv.lock`, `package.json`, `package-lock.json`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `pom.xml`, and `Gemfile.lock`
**And**: the same repository has a changed source file such as `src/app.py`
**When**: the developer runs `review-gauntlet init --worktree --format json`
**Then**: review cells are created for the changed source file
**And**: no review cell is created for the changed package files

#### Scenario: Full-repository review still excludes package files

**Given**: a repository containing source files and package files such as `uv.lock`, `package-lock.json`, and `Cargo.lock`
**When**: the developer runs `review-gauntlet init --all --format json`
**Then**: review cells are created for eligible source files
**And**: no review cell is created for package manager manifest or lock files

#### Scenario: Package-only changes do not stale review target digest

**Given**: an active moving-target session whose current review universe has no package files
**When**: only package manager manifest or lock files change before a later status or review command
**Then**: those package-only changes are omitted from review universe file digests and the target digest
**And**: no new package-file review cells are added by default
