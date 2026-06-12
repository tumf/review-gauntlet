## Implementation Tasks

- [x] Fix `findings --mark` state matching to compare against persisted `FindingState.value` values while preserving terminal suppression semantics. (verification: integration - `uv run pytest tests/test_cli_findings.py` covers hyphenated public marks and `--all` visibility)
- [x] Validate adapter env keys against a portable environment variable name pattern and reject empty, `=`, NUL, hyphenated, or otherwise invalid names. (verification: unit - `uv run pytest tests/test_config.py` covers valid and invalid env keys)
- [x] Define and implement template literal brace handling for command adapter config strings, with tests for supported variables and literal braces. (verification: unit - `uv run pytest tests/test_config.py` covers `{prompt}`, unsupported variables, and literal brace cases)
- [x] Pin CI Python installation to Python 3.11 in `.github/workflows/ci.yml`. (verification: manual - inspect workflow diff because CI execution occurs outside local runtime)
- [x] Run full repository checks after implementation. (verification: integration - `make check`)

## Future Work

- If users need richer templating, propose a dedicated template-language change rather than expanding validation implicitly.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate tighten-cli-config-contract --archive-gate`
