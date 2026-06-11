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

Generate an inventory for a repository:

```bash
uv run review-gauntlet inventory /path/to/repo --json
```

Generate a review plan with slices and required checks:

```bash
uv run review-gauntlet plan /path/to/repo --json
```

Generate a markdown report:

```bash
uv run review-gauntlet report /path/to/repo
```

Run one review step with a configured external CLI adapter:

```bash
uv run review-gauntlet init /path/to/repo
uv run review-gauntlet review /path/to/repo --config /path/to/review-gauntlet.jsonc --format json
```

Target selection happens on `init`; `review` only advances the active session once.
OCR-compatible target mappings are:

```bash
# OCR workspace diff review: staged, unstaged, and untracked non-ignored files.
uv run review-gauntlet init /path/to/repo
uv run review-gauntlet init /path/to/repo --worktree  # explicit alias

# OCR branch/range review: files changed between two refs.
uv run review-gauntlet init /path/to/repo --from main --to HEAD

# OCR single-commit review: files changed by one commit.
uv run review-gauntlet init /path/to/repo --commit <commit-oid>

# review-gauntlet-only full repository review: every eligible inventory file.
uv run review-gauntlet init /path/to/repo --all

# Execute exactly one review step for the initialized session.
uv run review-gauntlet review /path/to/repo --config /path/to/review-gauntlet.jsonc --format json

# Select at most 20 cells for this run and execute up to 4 adapter calls at once.
uv run review-gauntlet review /path/to/repo --budget 20 --concurrency 4 --format json
```

`review --concurrency` defaults to `8` and must be a positive integer. `--budget`
still caps the total cells selected for one review run; `--concurrency` only limits
how many of those selected adapter invocations run at the same time. It does not
automatically pass a concurrency flag through to the nested external adapter
command.

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
