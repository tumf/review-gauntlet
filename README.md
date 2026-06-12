Review Gauntlet
===============

Coverage-driven review orchestration for agentic code reviews.

The goal is not to pretend an LLM can guarantee bug-free code. The goal is to
guarantee that a defined review surface was inspected, with evidence, before a
project is called reviewed.

## Commands

```bash
uv sync
make check
```

Start normal use by initializing a review session, then run exactly one review step
with a configured external CLI adapter:

```bash
uv run review-gauntlet init
uv run review-gauntlet review --config review-gauntlet.jsonc
```

Target selection happens on `init`; `review` only advances the active session once.
OCR-compatible target mappings are:

```bash
# OCR workspace diff review: staged, unstaged, and untracked non-ignored files.
uv run review-gauntlet init
uv run review-gauntlet init --worktree  # explicit alias

# OCR branch/range review: files changed between two refs.
uv run review-gauntlet init --from main --to HEAD

# OCR single-commit review: files changed by one commit.
uv run review-gauntlet init --commit <commit-oid>

# review-gauntlet-only full repository review: every eligible inventory file.
uv run review-gauntlet init --all

# Execute exactly one review step for the initialized session.
uv run review-gauntlet review --config review-gauntlet.jsonc

# Select at most 20 cells for this run and execute up to 4 adapter calls at once.
uv run review-gauntlet review --budget 20 --concurrency 4
```

After a review step, inspect session state and findings, optionally record human
finding decisions, and finalize only when both coverage and findings are closed:

```bash
uv run review-gauntlet status
uv run review-gauntlet findings
uv run review-gauntlet mark <finding-id> fixed --reason "fixed in follow-up"
uv run review-gauntlet finalize
```

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
uv run review-gauntlet inventory
```

Inspect the legacy review plan with slices and required checks:

```bash
uv run review-gauntlet plan
```

Render the legacy markdown matrix report:

```bash
uv run review-gauntlet report
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
`review-gauntlet.jsonc`, then `review-gauntlet.json`. The command adapter uses
argv arrays and never shell strings; provider login, model choice, and secrets stay
inside the external CLI configuration.

Minimal JSONC configuration for opencode file-json verdicts:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "--dangerously-skip-permissions", "{prompt}"],
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

## Developer Workflow

```bash
make format
make lint
make typecheck
make test
make coverage
```

## Design

Review Gauntlet treats review as a coverage matrix:

- inventory the project files
- classify files into review slices
- attach risk-specific checks to each slice
- require evidence for each matrix row before final pass

The first version is intentionally small: it creates the inventory, review plan,
and matrix. Review runners for Codex, Claude, static analyzers, and custom tools
can plug into the same matrix later.
