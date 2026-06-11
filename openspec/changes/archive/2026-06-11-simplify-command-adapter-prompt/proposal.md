---
change_type: implementation
priority: high
dependencies: []
references:
  - openspec/CONSTITUTION.md
  - openspec/specs/review-sessions/spec.md
  - src/review_gauntlet/config.py
  - src/review_gauntlet/review_adapter.py
  - src/review_gauntlet/cli.py
  - README.md
---

# Simplify command adapter prompt passing and process defaults

**Change Type**: implementation

## Problem / Context

The current command adapter supports `input.mode`, `stdin`, `prompt-file`, and `{prompt_file}`. This overfits the adapter around prompt-file transport and led to an incorrect opencode configuration: `opencode run --file` attaches files to the message rather than selecting a prompt file. Some external CLIs accept prompt text as argv message content and may not accept prompt files at all.

The command adapter should keep the runtime contract simple: generate the OCR-derived prompt, expose it as `{prompt}` for argv template expansion, collect verdict JSON from the configured output mode, and preserve artifacts for auditability. Optional process controls such as `cwd`, `env`, and `timeout_seconds` should remain configurable but should not appear in the minimal recommended config unless needed.

## Proposed Solution

Replace command adapter prompt transport modes with argv prompt templating:

- remove `input` / `input.mode` from command adapter configuration,
- remove `prompt-file` transport as a runtime input mode,
- remove `{prompt_file}` as a supported template variable,
- add `{prompt}` as a supported template variable for `args` and `env` template expansion,
- keep `cwd` and `env` optional configuration fields,
- make omitted `cwd` inherit the current process cwd by passing `cwd=None` to subprocess,
- make omitted `env` inherit the current process env with no automatic fixed env injection,
- keep explicit env overrides as parent env plus configured key/value overrides,
- make `timeout_seconds` optional with a default of 600 seconds,
- continue writing prompt artifacts for evidence, but do not pass prompt artifacts as command input unless a future command explicitly references them through a supported mechanism,
- update README and the checked-in self-review config to use minimal opencode `{prompt}` argv configuration.

## Acceptance Criteria

- Command adapter configs no longer accept or require `input` or `input.mode`.
- `{prompt}` is accepted in command `args` and expands to the generated OCR-derived prompt as one argv element.
- `{prompt_file}` is rejected as an unsupported template variable.
- The command adapter does not send the prompt via stdin and does not pass a prompt file as an input-mode side effect.
- Prompt artifacts may still be persisted for review evidence.
- `cwd` remains optional and configurable; when omitted, subprocess execution inherits the parent process cwd.
- `env` remains optional and configurable; when omitted, subprocess execution inherits the parent process environment without adding fixed values such as `REVIEW_GAUNTLET=1`.
- Explicit `env` values override or add to the inherited environment only when configured.
- `timeout_seconds` is optional and defaults to 600 seconds; non-positive values remain invalid.
- README examples and `review-gauntlet.jsonc` use minimal opencode configuration with `{prompt}` and no `input`, `cwd`, `env`, or explicit timeout unless explaining optional overrides.

## Explicit Completion Conditions

- `src/review_gauntlet/config.py` removes `InputMode` and `CommandInputConfig`, removes the `input` field from `CommandAdapterConfig`, adds `{prompt}`, removes `{prompt_file}`, and defaults `timeout_seconds` to 600.
- `src/review_gauntlet/review_adapter.py` expands `{prompt}` into argv/env templates, records prompt artifacts for evidence, invokes subprocess without stdin prompt transport, and uses `cwd=None` when no cwd is configured.
- `README.md` and `review-gauntlet.jsonc` show the minimal opencode `{prompt}` configuration.
- Unit tests reject legacy `input` config and `{prompt_file}`, validate `{prompt}` expansion, validate timeout defaults, and verify cwd/env defaults.
- Integration tests prove an opencode-like fake command receives the prompt as an argv element and writes file-json verdict output.
- `make check` passes.

## Out of Scope

- Reintroducing prompt-file transport under a different name.
- Shell-string command execution.
- Provider-specific opencode, claude, or codex presets beyond the generic JSON/JSONC command adapter config.
- Automatic environment variable injection.
