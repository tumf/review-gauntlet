# Design: Simplified command adapter prompt transport

## Current issue

The existing command adapter has an `input.mode` abstraction with `stdin` and `prompt-file`. This creates extra configuration surface and conflates prompt persistence with prompt transport. It also encouraged using `opencode run --file {prompt_file}`, but opencode's `--file` option attaches files to the message; it is not a prompt-file argument.

## Target model

The adapter generates one OCR-derived prompt string per selected review cell and exposes it as the `{prompt}` template variable. Configured command arguments are argv elements, not shell strings. If an argument is exactly `{prompt}`, the generated prompt is passed as one argv element.

Minimal opencode config:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": [
      "run",
      "--dangerously-skip-permissions",
      "{prompt}"
    ],
    "output": {
      "mode": "file-json",
      "path": "{output_file}"
    }
  }
}
```

The adapter may still write the generated prompt to an artifact file such as `prompt.md` or `prompt.txt` so the review evidence remains inspectable. That artifact is not a configured input transport and is not exposed as `{prompt_file}`.

## Configuration model

Remove:

- `input`
- `input.mode`
- `InputMode`
- `CommandInputConfig`
- `{prompt_file}`

Keep:

- `command`
- `args`
- `output.mode`
- `output.path`
- `timeout_seconds`
- `cwd`
- `env`

Add:

- `{prompt}` template variable

`timeout_seconds` should remain optional at the JSON/JSONC level and default to 600 seconds.

## Process context defaults

`cwd` and `env` are useful escape hatches but should not be required for standard usage.

- If `cwd` is omitted, subprocess execution inherits the current process cwd by passing `cwd=None`.
- If `cwd` is configured, the value is template-expanded and used as the subprocess cwd.
- If `env` is omitted, subprocess execution inherits the current process environment without fixed automatic additions.
- If `env` is configured, configured values are template-expanded and merged over the inherited environment.

No automatic `REVIEW_GAUNTLET=1` or similar marker should be injected by default.

## Output and artifacts

The existing output modes remain:

- `stdout-json`
- `file-json`

The artifact set should continue to include enough evidence for review replay/debugging, including generated prompt text, command metadata, stdout, stderr, normalized verdict, and failure details.

`command.json` should record whether cwd was inherited or explicitly set, and should avoid implying a default cwd when none was configured.

## Compatibility and migration

Legacy configs with `input` or `{prompt_file}` should fail validation with actionable errors rather than silently behaving differently.

README should explain that CLIs receiving prompt text should use `{prompt}` in `args`, and that prompt-file transport is no longer part of the command adapter contract.
