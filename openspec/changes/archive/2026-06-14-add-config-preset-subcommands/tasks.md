## Implementation Tasks

- [x] Update CLI parser structure so `review-gauntlet config preset list` and `review-gauntlet config preset show <preset>` are accepted while `config init`, `config validate`, and `config effective` remain unchanged. (verification: integration - `uv run review-gauntlet config preset list` and `uv run review-gauntlet config preset show opencode` execute successfully)
- [x] Update config command dispatch in `src/review_gauntlet/cli.py` so preset listing and display are handled through the nested `preset` command path. (verification: unit - `uv run pytest tests/test_cli.py` asserts text output, JSON output, and preset content output for the nested command path)
- [x] Update missing-config guidance to reference `review-gauntlet config preset list` for available presets. (verification: integration - `tests/test_cli_session_review.py` assertions for no-config review failures expect the new guidance text)
- [x] Add or update CLI tests for `config preset list --format json`, `config preset show opencode`, and unknown preset rejection via `config preset show custom`. (verification: integration - `uv run pytest tests/test_cli.py` fails if commands are no-op, routed to old paths only, or accept dummy presets)
- [x] Update `README.md`, `openspec/specs/developer-workflow/spec.md`, and `openspec/specs/review-sessions/spec.md` to document `config preset list` and `config preset show <preset>` instead of the old `config list` and `config show <preset>` forms. (verification: integration - repository paths `README.md`, `openspec/specs/developer-workflow/spec.md`, and `openspec/specs/review-sessions/spec.md` contain the new command shape; `uv run pytest tests/test_cli.py` verifies canonical CLI examples and preset behavior)
- [x] Run the project verification suite after implementation. (verification: integration - `make check` passes)

## Future Work

- Decide whether a later release should add temporary compatibility aliases or migration notes for users of the old `config list` and `config show` commands.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-config-preset-subcommands --archive-gate`
