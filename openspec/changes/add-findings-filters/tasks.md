## Implementation Tasks

- [x] Add `findings --path` parser support in `src/review_gauntlet/cli.py` with repeatable values and repository-relative exact/prefix matching semantics. (verification: unit - `tests/test_cli_findings.py` asserts a single file filter, a directory-style prefix filter, and repeated path filters include only matching findings)
- [x] Add `findings --mark` parser support in `src/review_gauntlet/cli.py` with repeatable user-facing mark values mapped to persisted finding states. (verification: unit - `tests/test_cli_findings.py` asserts `--mark confirmed`, repeated `--mark confirmed --mark reopened`, and invalid mark values fail with an argparse usage error)
- [x] Preserve existing visibility rules by applying terminal suppression unless `--all` is present before optional filters are returned. (verification: unit - `tests/test_cli_findings.py` asserts `--mark false-positive` returns no terminal finding without `--all`, and returns it with `--all`)
- [x] Preserve the existing findings output contract for both text and JSON after filtering. (verification: integration - `tests/test_cli_findings.py` executes `main(["findings", ..., "--format", "json"])` and parses the existing `{"session_id", "findings"}` payload while text output continues to include matching finding IDs only)
- [x] Keep `findings` as a non-progress, non-mutating summary command. (verification: unit - `tests/test_cli_findings.py` confirms `findings --help` lists `--path` and `--mark`, `--audience` is absent, and running filtered findings does not insert finding events or review runs)
- [x] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate add-findings-filters --strict`
Expected archive gate: `cflx openspec validate add-findings-filters --archive-gate`
