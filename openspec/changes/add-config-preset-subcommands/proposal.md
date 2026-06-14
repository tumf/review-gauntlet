---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/cli.py
  - openspec/specs/developer-workflow/spec.md
  - openspec/specs/review-sessions/spec.md
  - tests/test_cli_session_review.py
---

# Add config preset subcommands

**Change Type**: implementation

## Premise / Context

- `review-gauntlet config list` and `review-gauntlet config show <preset>` currently expose bundled command-adapter presets.
- `review-gauntlet config init --preset <name>` remains the command that materializes a selected preset into project or global config.
- The current canonical developer workflow spec describes preset inspection under the top-level `config` command group.
- Missing-config guidance currently points users to `review-gauntlet config list` for available presets.
- The requested CLI shape is to make preset inspection explicit as `review-gauntlet config preset list` and `review-gauntlet config preset show <preset>`.

## Problem / Context

The current `config list` and `config show` names are ambiguous because they appear to operate on effective config, while their actual behavior is limited to bundled preset inspection. This makes the command group less self-describing as additional config operations such as `init`, `validate`, and `effective` exist alongside them.

## Proposed Solution

Introduce a `preset` subgroup under `review-gauntlet config` and move preset inspection commands under it:

- `review-gauntlet config preset list`
- `review-gauntlet config preset show <preset>`

Keep existing config lifecycle commands unchanged:

- `review-gauntlet config init --preset <preset>`
- `review-gauntlet config validate`
- `review-gauntlet config effective`

Update user-facing guidance, specs, README examples, and tests to refer to the new command paths. The old `config list` and `config show` forms are not required to remain available for this change.

## Acceptance Criteria

- Running `review-gauntlet config preset list` prints the bundled preset names in the same order and format previously produced by `review-gauntlet config list`.
- Running `review-gauntlet config preset list --format json` prints the same JSON shape previously produced by `review-gauntlet config list --format json`.
- Running `review-gauntlet config preset show opencode` prints the bundled `opencode` preset contents without writing config files.
- Running `review-gauntlet config preset show custom` fails with the existing CLI usage-error behavior for unknown presets.
- Missing-config guidance points users to `review-gauntlet config preset list` for available presets.
- README and canonical specs document the new `config preset` command shape.
- Existing `config init`, `config validate`, and `config effective` behavior continues to work unchanged.

## Explicit Completion Conditions

This change is complete when repository evidence shows:

- `src/review_gauntlet/cli.py` parses and dispatches `config preset list` and `config preset show <preset>`.
- CLI tests cover text and JSON listing, preset content display, unknown preset rejection, and missing-config guidance using the new command path.
- Relevant README examples and canonical spec text no longer instruct users to run `review-gauntlet config list` or `review-gauntlet config show <preset>` for preset inspection.
- `make check` passes.
- `cflx openspec validate add-config-preset-subcommands --archive-gate` passes before archiving.

## Out of Scope

- Changing the preset file format or bundled preset contents.
- Changing where project or global config files are written.
- Introducing new preset names.
- Implementing compatibility aliases for the old `config list` and `config show` forms unless chosen during implementation for migration ergonomics.
