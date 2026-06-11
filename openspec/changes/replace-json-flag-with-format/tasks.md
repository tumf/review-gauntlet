## Implementation Tasks

- [ ] Replace `inventory` and `plan` parser wiring in `src/review_gauntlet/cli.py` so both commands accept `--format json|text` with default `text`, and no longer accept `--json` (verification: integration - `uv run pytest tests/test_cli.py` includes argument parsing checks that fail for legacy `--json`).
- [ ] Preserve JSON output for `inventory --format json` and `plan --format json` using the existing Pydantic `model_dump_json(indent=2)` contracts (verification: integration - `uv run pytest tests/test_cli.py` parses stdout with `json.loads` and asserts expected inventory/plan fields).
- [ ] Add deterministic text output for default `inventory` and `plan` execution without changing underlying inventory or planner models (verification: integration - `uv run pytest tests/test_cli.py` asserts stable text markers for default command output and does not parse it as JSON).
- [ ] Keep `report --format markdown|json` and session command `--format human|json` behavior unchanged (verification: integration - existing `tests/test_cli.py` report/status tests continue to pass, and a targeted regression test confirms `report` default markdown output remains available).
- [ ] Update OpenSpec canonical delta coverage for the planning command contract to describe `--format json` and default text behavior instead of legacy `--json` (verification: manual - compare this change delta against `openspec/specs/review-sessions/spec.md` and confirm archive would update the planning command requirement only).
- [ ] Run the repository CI-equivalent check after implementation (verification: manual - `make check` completes successfully in the repo root).

## Future Work

- If downstream scripts still call `inventory --json` or `plan --json`, update those scripts outside this repository after this breaking CLI change is accepted.

## Final Validation

Expected proposal validation: `cflx openspec validate replace-json-flag-with-format --strict`.
Expected implementation validation after apply: `make check`.
