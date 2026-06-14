Review Gauntlet
===============

Plan-first AI code review with files × rules coverage.

Review Gauntlet is a plan-first coverage gate for AI code review. Before running
reviewers, it builds a files × rules review matrix. Each cell represents a
concrete review obligation: this file must be checked against this rule. Review
Gauntlet then runs AI reviewers, static analyzers, or custom adapters against
those cells, records evidence and findings, and only finalizes when the required
coverage is complete.

Reviewers find issues. Review Gauntlet proves which files were checked against
which rules.

## Quick Start

The fastest way to review a repository:

```bash
# 1. Install the CLI (skip if already installed)
uv tool install review-gauntlet

# 2. Create an adapter config (uses bundled presets — no clone required)
uvx review-gauntlet config init --preset opencode

# 3. Run the review pipeline
review-gauntlet init
review-gauntlet review
review-gauntlet status
review-gauntlet finalize
```

Review Gauntlet builds a files × rules coverage matrix, runs the configured
reviewer against each cell, records evidence, and only finalizes when all
required coverage is complete.

## How is this different from AI review tools?

AI review tools usually generate comments from a diff. Review Gauntlet starts one
layer earlier: it creates a review plan. It crosses files with review rules to
build a coverage matrix, then runs reviewers against the required cells and
records evidence for each completed review obligation.

| Tool type | Primary job |
|---|---|
| Codex Review / Open Code Review / opencode | Generate review comments |
| Static analyzers | Detect known rule violations |
| Review Gauntlet | Plan the review, build the files × rules matrix, track coverage, preserve evidence, and gate finalization |

Review Gauntlet is designed to work with reviewers, not compete with them.

## How it works

Review Gauntlet makes code review plan-first and auditable.

1. Define the review surface
   - files, directories, diffs, commits, or other review targets
2. Define the review rules
   - security, correctness, maintainability, architecture, project-specific checks, or custom rules
3. Build a review matrix
   - each file × rule pair becomes a review cell
4. Run reviewers
   - AI reviewers, static analyzers, opencode, Codex-style agents, or custom adapters inspect assigned cells
5. Track evidence and findings
   - prompts, outputs, findings, coverage state, and unresolved issues are recorded
6. Finalize only when complete
   - Review Gauntlet only finalizes when required coverage is complete and live findings are closed

## Before you run a review

A review session does not work from the CLI alone. Install all required pieces first:

1. install the `review-gauntlet` CLI
2. install and configure an external review agent CLI
3. install the matching Review Gauntlet skill or prompt guidance for that agent
4. add a discoverable adapter config such as `review-gauntlet.jsonc`

### Install the CLI

```bash
uv tool install review-gauntlet
```

### Install the skill

Install the Review Gauntlet agent skill:

```bash
npx skills add tumf/review-gauntlet
```

### Create an adapter config

Review Gauntlet discovers config automatically from
`.review-gauntlet/config.jsonc`, `review-gauntlet.jsonc`, or the XDG user config
directory. Starter presets are bundled in the installed package, so first-time users
do not need to clone this repository to create a config.

Create a project config:

```bash
review-gauntlet config init --preset opencode
```

Create a global default config instead:

```bash
review-gauntlet config init --global --preset opencode
```

Inspect available presets and validate the effective config:

```bash
review-gauntlet config preset list
review-gauntlet config preset show opencode
review-gauntlet config validate
review-gauntlet config effective --format json
```

Use `--force` to overwrite an existing generated config, `--dry-run` to preview the
write target and preset contents without creating files, and `--output <path>` to write
to a custom path. Edit the generated JSONC if your agent command or arguments differ, then
verify that `review-gauntlet review` runs end-to-end.

---

```bash
uvx review-gauntlet config init --preset opencode
# (install and authenticate the matching external review agent separately)
review-gauntlet init
review-gauntlet review
review-gauntlet status
```

`uvx review-gauntlet config init --preset opencode` is the clone-free starter flow.
For regular use, install the CLI with `uv tool install review-gauntlet` so the same
command is available as `review-gauntlet`.

## Installation

For regular use, install the CLI as `review-gauntlet`:

```bash
uv tool install review-gauntlet
review-gauntlet --help
```

## Install from source

Use this when you want the latest GitHub version or want to contribute:

```bash
git clone https://github.com/tumf/review-gauntlet.git
cd review-gauntlet
uv sync
make install
review-gauntlet --help
```

`make install` installs the local package as the canonical `review-gauntlet`
command with `uv tool install --reinstall .`.

## Basic usage

Start normal use by initializing a review session, then run exactly one review step
with a configured external CLI adapter:

```bash
review-gauntlet init
review-gauntlet review
review-gauntlet status
review-gauntlet findings
review-gauntlet verify-fixes --config review-gauntlet.jsonc
review-gauntlet finalize
```

### Convenient `ready` usage

`ready` prints the next review prompt, making it easy to hand off one pending review
unit to an external agent:

```bash
review-gauntlet ready | opencode run
```

To keep feeding ready prompts to opencode until no review unit remains:

```bash
while p=$(review-gauntlet ready); do opencode run "$p"; done
```

## Shell completion

The installed `review-gauntlet` command can generate completion scripts for common
interactive shells. Evaluate the script for the current session, or write it to the
location your shell startup files load.

Bash:

```bash
source <(review-gauntlet completion bash)
```

Zsh:

```zsh
review-gauntlet completion zsh > "${fpath[1]}/_review-gauntlet"
autoload -Uz compinit && compinit
```

Fish:

```fish
review-gauntlet completion fish > ~/.config/fish/completions/review-gauntlet.fish
```

## Commands

Target selection happens on `init`; `review` only advances the active session once.
A bare `init` now uses `.review-gauntlet/checkpoints/latest/status.json` when a
complete usable checkpoint exists, reviewing from its `review_base_commit` to
`HEAD`. If no checkpoint exists, bare `init` reviews all eligible files. Scripts
that need the previous workspace-diff default must pass `--worktree` explicitly.
OCR-compatible target mappings are:

```bash
# Default review: latest finalized checkpoint -> HEAD, or all files for first review.
review-gauntlet init

# OCR workspace diff review: staged, unstaged, and untracked non-ignored files.
review-gauntlet init --worktree

# OCR branch/range review: files changed between two refs.
review-gauntlet init --from main --to HEAD

# OCR single-commit review: files changed by one commit.
review-gauntlet init --commit <commit-oid>

# review-gauntlet-only full repository review: every eligible inventory file.
review-gauntlet init --all

# Execute exactly one review step for the initialized session.
review-gauntlet review

# Select at most 20 cells for this run and execute up to 4 adapter calls at once.
review-gauntlet review --budget 20 --concurrency 4
```

After a review step, inspect session state and findings, optionally record human
finding decisions, and finalize only when both coverage and findings are closed:

```bash
review-gauntlet status
review-gauntlet findings
review-gauntlet mark <finding-id> fixed --reason "fixed in follow-up"
review-gauntlet verify-fixes --config review-gauntlet.jsonc
review-gauntlet finalize
# Finalize writes Git-reviewable JSON/Markdown snapshots atomically.
git add .review-gauntlet/checkpoints/latest
```

`status` reports `coverage` as counts of review cells by state:

| Coverage state | Meaning |
|---|---|
| `pending` | The file × rule cell still needs review. |
| `reviewed` | The cell has been reviewed against the current file digest. |
| `stale` | The file changed after review, so the cell must be reviewed again. |
| `superseded` | The old persisted cell is no longer part of the current target plan. |

`findings` reports open findings by default; pass `--all` to include terminal
findings. Each finding row includes:

| Field | Meaning |
|---|---|
| `finding_id` | Stable Review Gauntlet finding id, such as `RGF-...`. |
| `fingerprint` | Deduplication key derived from repository, target, path, rule, claim, code anchor, and ruleset. |
| `state` | Finding lifecycle state. Open states are `untriaged`, `confirmed`, `fixed_pending_verification`, and `reopened`; terminal states are `fixed_verified`, `false_positive`, `waived`, and `accepted_risk`. |
| `path` | Repository-relative file path for the latest occurrence. |
| `rule_id` | Review rule that produced the finding. |
| `content` | Reviewer-provided finding text. |
| `metadata` | JSON metadata recorded by human decisions, such as owner or expiration. |
| `start_line` / `end_line` | Latest line range, or `0` when no precise range is available. |
| `imprecise` | Whether the latest location is approximate. |

Successful `finalize` requires both coverage and live findings to be closed and
review-universe files to match `HEAD`; dirty tracked, staged, unstaged, or
untracked eligible files block checkpoint creation. It writes
`status.json`, `findings.json`, `events.json`, and `summary.md` under a generated
checkpoint directory such as `.review-gauntlet/checkpoints/<checkpoint_id>/`, then updates
`.review-gauntlet/checkpoints/latest` as a pointer to that checkpoint and clears the
active session so the next command is `review-gauntlet init`. There is intentionally
no separate checkpoint command.

`review --concurrency` defaults to `8` and must be a positive integer. `--budget`
still caps the total cells selected for one review run; `--concurrency` only limits
how many of those selected adapter invocations run at the same time. It does not
automatically pass a concurrency flag through to the nested external adapter
command.

### Diagnostic and legacy planning commands

The `inventory`, `plan`, and `report` commands remain available for compatibility
and inspection. Use them to inspect file discovery, review slicing, and report
rendering; they are not the normal day-to-day review lifecycle.

Inspect the current repository inventory and classification:

```bash
review-gauntlet inventory
```

Inspect the legacy review plan with slices and required checks:

```bash
review-gauntlet plan
```

Render the legacy markdown matrix report:

```bash
review-gauntlet report
```

## Default file filtering

Inventory discovery keeps Git behavior intact: Git-backed repositories still use
`git ls-files --cached --others --exclude-standard` with the existing bounded
subprocess timeout, so `.gitignore` and other exclude-standard rules apply before
review-gauntlet's built-in filters.

The built-in artifact filter removes generated or dependency paths from both full
inventory and target-scoped inventory. This includes Python/editor/cache outputs
such as `.review-gauntlet/`, `__pycache__/`, `.ruff_cache/`, `build/`, `dist/`,
`wheels/`, `htmlcov/`, and OCR-inspired dependency/build staging paths such as
`vendor/`, `node_modules/`, `target/`, `.happypack/`, `.cachefile/`, `_packages/`,
`rpm/`, `pkgs/`, and `oh_modules/`.

Review sessions apply an additional default review-path filter when creating cells
and digests. Files can remain classifiable in general inventory, but `init` omits
`openspec/`, `tests/`, and `docs/` by default, as well as common OCR-style test or
generated paths such as `__tests__/`, `*_test.go`, `*Test.java`, `*Test.kt`,
`*.spec.ts`, `*.test.tsx`, `test_*.py`, `*_spec.rb`, `*.spec.ets`, and
`*.test.ets`. Review cells and target digests also omit common package manifests
and lock files such as `uv.lock`, `poetry.lock`, `requirements*.txt`,
`package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.toml`,
`Cargo.lock`, `go.mod`, `go.sum`, `pom.xml`, `Gemfile.lock`, `composer.lock`,
`Package.resolved`, `pubspec.lock`, `mix.lock`, `vcpkg.json`, `flake.lock`,
`stack.yaml.lock`, `Manifest.toml`, and `renv.lock`. These package files are not
removed from general inventory unless another artifact or Git ignore rule excludes
them. Normal source files and package-adjacent executable logic files such as
`setup.py`, `build.gradle`, `mix.exs`, and `build.zig` remain eligible for review
cells.

`review` discovers configuration in this order: explicit `--config`,
`.review-gauntlet/config.jsonc`, `.review-gauntlet/config.json`,
`review-gauntlet.jsonc`, `review-gauntlet.json`,
`$XDG_CONFIG_HOME/review-gauntlet/config.jsonc`, then
`$XDG_CONFIG_HOME/review-gauntlet/config.json`. When `XDG_CONFIG_HOME` is unset
or empty, the global fallback base is `~/.config`, so the JSONC fallback path is
`~/.config/review-gauntlet/config.jsonc`. Repository-local configuration always
wins over global XDG configuration, and discovery only reads existing files; it
never creates global config directories or files. The command adapter uses argv
arrays and never shell strings; provider login, model choice, and secrets stay
inside the external CLI configuration.

Minimal JSONC configuration for opencode file-json verdicts:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "{prompt}"],
    "output": {"mode": "file-json", "path": "{output_file}"}
  }
}
```

The generated OCR prompt is expanded into `{prompt}` as one argv element. Prompt
artifacts are still written for audit evidence, but prompt-file transport is not
part of the command adapter contract. `cwd`, `env`, and `timeout_seconds` are
optional escape hatches: omitted `cwd` inherits the caller's current working
directory, omitted `env` inherits the parent environment without fixed automatic
variables, explicit `env` values override that inherited environment, and omitted
`timeout_seconds` defaults to 600 seconds.

The verdict must be JSON with OCR-style comments:

```json
{"comments":[{"path":"src/app.py","content":"Issue","start_line":1,"end_line":1}]}
```

Supported template variables include `{repo_root}`, `{state_dir}`, `{run_id}`,
`{run_dir}`, `{cell_id}`, `{cell_dir}`, `{prompt}`, `{output_file}`,
`{file_path}`, and `{rule_id}`.

## Developer workflow

```bash
uv sync
make check
make format
make lint
make typecheck
make test
make coverage
```

## Design

Review Gauntlet treats review as a stateful coverage workflow:

- initialize a session from an explicit target set
- classify eligible files into review slices and coverage cells
- run exactly one review step at a time through an external command adapter
- record prompts, outputs, findings, and coverage state as audit evidence
- finalize only after required coverage and live findings are closed

External review tools are integrated through the command adapter rather than
hard-coded runners. The adapter accepts argv arrays, expands review artifacts into
safe template variables, and supports JSON verdicts written to stdout or files so
CLIs such as opencode, Codex-style tools, static analyzers, or custom wrappers can
participate without review-gauntlet owning provider login or secret management.
