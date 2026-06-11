# Design: Configurable external CLI review adapter

## Architecture

The change adds an adapter boundary around review execution:

- `FakeReviewAdapter` remains available for deterministic tests and `--fixture` runs.
- `CommandReviewAdapter` executes an external CLI configured by JSON/JSONC.
- A config loader discovers and validates adapter config before review execution.
- A prompt builder produces OCR-derived prompts from the selected review cell, ruleset, file path, file content, and required verdict contract.
- A verdict loader validates stdout or file JSON into the existing `OCRComment` model.

`review-gauntlet` remains the coverage and ledger owner. External CLIs only produce verdict JSON.

## Configuration discovery

The review command should resolve configuration in this order:

1. `review --config <path>`
2. `<repo>/.review-gauntlet/config.jsonc`
3. `<repo>/.review-gauntlet/config.json`
4. `<repo>/review-gauntlet.jsonc`
5. `<repo>/review-gauntlet.json`

If `--fixture` is provided, the fake adapter is used for deterministic tests. If no fixture and no valid command adapter config exists, `review` should fail with an actionable usage error rather than implicitly executing a default external tool.

## Config shape

Example:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "claude",
    "args": ["-p", "{prompt_file}"],
    "input": {
      "mode": "prompt-file"
    },
    "output": {
      "mode": "file-json",
      "path": "{output_file}"
    },
    "timeout_seconds": 300,
    "cwd": "{repo_root}",
    "env": {
      "REVIEW_GAUNTLET": "1"
    }
  }
}
```

Supported input modes:

- `stdin`: send generated prompt to command stdin.
- `prompt-file`: write prompt to `prompt.md` and pass `{prompt_file}` through configured args.

Supported output modes:

- `stdout-json`: parse verdict JSON from stdout.
- `file-json`: parse verdict JSON from the configured output path.

## Template variables

The command adapter may expand these variables in `args`, `cwd`, `output.path`, and configured environment values:

- `{repo_root}`
- `{state_dir}`
- `{run_id}`
- `{run_dir}`
- `{cell_id}`
- `{cell_dir}`
- `{prompt_file}`
- `{output_file}`
- `{file_path}`
- `{rule_id}`

Expansion must not go through a shell. The command must execute with `subprocess.run([command, *args], shell=False, ...)` or equivalent.

## Verdict contract

The command result must validate as:

```json
{
  "comments": [
    {
      "path": "src/example.py",
      "content": "Issue description",
      "suggestion_code": "Suggested code",
      "existing_code": "Existing code",
      "start_line": 1,
      "end_line": 1,
      "thinking": "Optional reasoning"
    }
  ]
}
```

`comments` may be empty. Each comment is validated into the existing OCR comment model before being normalized into a finding occurrence.

## Artifacts

For each reviewed cell, persist artifacts in a deterministic cell artifact directory, for example:

```text
.review-gauntlet/runs/<run-id>/cells/<cell-id>/
  prompt.md
  command.json
  stdout.txt
  stderr.txt
  verdict.json
  failure.json
```

Artifacts are evidence for the constitution's coverage principle: reviewed means a defined target was reviewed with a defined rule in a verifiable form.

## Failure semantics

A command adapter failure must not mark the selected cell reviewed. Failures include:

- command not found,
- non-zero exit,
- timeout,
- missing file-json output,
- unparseable JSON,
- schema-invalid verdict,
- output path outside the cell artifact directory or configured safe state area,
- invalid template variable, and
- unsupported input/output mode.

The review command should return non-zero for adapter failures and preserve failure artifacts for debugging. Unknown or failed coverage remains visible rather than being hidden as reviewed.

## Compatibility

Existing fake fixture behavior remains available for tests. The existing OCR ruleset digest and finding normalization logic remain authoritative; the command adapter only supplies OCR-style comments.
