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
uv run review-gauntlet init /path/to/repo --worktree
uv run review-gauntlet review /path/to/repo --config /path/to/review-gauntlet.jsonc --format json
```

`review` discovers configuration in this order: explicit `--config`,
`.review-gauntlet/config.jsonc`, `.review-gauntlet/config.json`,
`review-gauntlet.jsonc`, then `review-gauntlet.json`. The command adapter uses
argv arrays and never shell strings; provider login, model choice, and secrets stay
inside the external CLI configuration.

Example JSONC configuration for stdin JSON verdicts:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "--json"],
    "input": {"mode": "stdin"},
    "output": {"mode": "stdout-json"},
    "timeout_seconds": 300,
    "cwd": "{repo_root}",
    "env": {"REVIEW_GAUNTLET": "1"}
  }
}
```

Example prompt-file/file-json style for claude/codex-like CLIs:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "claude",
    "args": ["-p", "{prompt_file}", "--output", "{output_file}"],
    "input": {"mode": "prompt-file"},
    "output": {"mode": "file-json", "path": "{output_file}"},
    "timeout_seconds": 300,
    "cwd": "{repo_root}"
  }
}
```

The verdict must be JSON with OCR-style comments:

```json
{"comments":[{"path":"src/app.py","content":"Issue","start_line":1,"end_line":1}]}
```

Supported template variables include `{repo_root}`, `{state_dir}`, `{run_id}`,
`{run_dir}`, `{cell_id}`, `{cell_dir}`, `{prompt_file}`, `{output_file}`,
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
