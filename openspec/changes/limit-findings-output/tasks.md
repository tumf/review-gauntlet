## Implementation Tasks

- [x] Add bounded findings CLI arguments in `src/review_gauntlet/cli.py`: `--limit N` with default `10`, `--all-findings`, and usage-error handling for `--limit` combined with `--all-findings`. (verification: integration - `uv run pytest tests/test_cli_findings.py` includes parser-level assertions for default behavior, explicit limit, unlimited behavior, and the invalid combination exiting with code `64`)
- [x] Update findings result construction in `src/review_gauntlet/cli.py` so visibility and filter rules run before counting, results are sorted by `path`, `start_line`, `end_line`, and `finding_id`, `total` is computed before limiting, and `returned` matches the emitted findings length. (verification: integration - `uv run pytest tests/test_cli_findings.py` asserts count metadata, deterministic ordering, default limit of 10, and explicit `--limit` slicing)
- [x] Preserve the independence of `--all` and `--all-findings` so terminal visibility and result-size limiting remain separate controls. (verification: integration - `uv run pytest tests/test_cli_findings.py` covers `--all-findings` without terminal findings and `--all --all-findings` with terminal findings)
- [x] Preserve existing `--path`, `--mark`, terminal suppression, and non-mutating behavior while applying the new count and limit rules. (verification: integration - existing and updated `uv run pytest tests/test_cli_findings.py` cases continue to pass, including filtered non-mutating assertions against `runs` and `finding_events`)
- [x] Update `skills/review-gauntlet/SKILL.md` to instruct agents to rely on bounded findings output by default and to use `--all-findings` only when the workflow explicitly needs the entire filtered set. (verification: manual - inspect `skills/review-gauntlet/SKILL.md` and confirm it distinguishes `--all` terminal visibility from `--all-findings` result-size control)
- [x] Run focused and full verification after implementation. (verification: integration - `uv run pytest tests/test_cli_findings.py`; verification: integration - `make check`)

## Future Work

- Consider pagination or cursor support only if future workflows need incremental traversal rather than bounded inspection.
- Consider adding a user-selectable `--sort` option only after concrete alternate ordering needs emerge.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate limit-findings-output --archive-gate`
