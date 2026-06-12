## Implementation Tasks

- [x] Add a top-level `completion` subcommand to `src/review_gauntlet/cli.py` that accepts `bash`, `zsh`, or `fish` and dispatches before root validation. (verification: unit - add `tests/test_cli.py::test_cli_completion_bash_outputs_script_without_root_validation` or equivalent that calls `main(["completion", "bash"])` from outside any prepared repository and asserts exit `0` with non-empty stdout; completion condition: no `.review-gauntlet` state or root directory validation is touched for completion generation)

- [x] Generate deterministic shell scripts for `bash`, `zsh`, and `fish` that cover current top-level commands and subcommand option names. (verification: unit - add `tests/test_cli.py` assertions that inspect each generated script for representative command and option names such as `review`, `verify-fixes`, `--format`, `--budget`, `--concurrency`, `--fixture`, `--config`, `--audience`, `--finding`, `--path`, `--mark`, and `--until`; completion condition: the generated script content changes when the parser-visible command or option set changes)

- [x] Preserve argparse usage-error behavior for unsupported shell names. (verification: unit - add `tests/test_cli.py::test_cli_completion_rejects_unsupported_shell` or equivalent that `main(["completion", "powershell"])` raises `SystemExit` with argparse error code `2`; completion condition: unsupported shells do not emit partial or dummy completion scripts)

- [x] Preserve existing CLI parser and dispatch behavior for all current commands. (verification: unit - run `uv run pytest tests/test_cli.py` and focused session CLI tests such as `uv run pytest tests/test_cli_session_review.py tests/test_cli_verify_fixes.py`, which cover invalid flags, help output, and root validation; completion condition: existing command tests pass without relaxing assertions)

- [x] Document shell completion setup in `README.md` using the installed canonical `review-gauntlet` command. (verification: unit - add or extend a README documentation assertion in `tests/test_cli.py` or a documentation test that reads `README.md` and checks for `review-gauntlet completion bash`, `review-gauntlet completion zsh`, `review-gauntlet completion fish`, and absence of `review-guantlet`; completion condition: repository documentation covers supported shells without documenting the typo alias)

- [x] Run full project quality gates after implementation. (verification: integration - run `make check`; completion condition: format check, lint, typecheck, and tests all pass)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-shell-completion-command --archive-gate`.

## Future Work

- Dynamic completions for repository paths, finding IDs, or active-session state can be proposed separately if there is demand.
- Packaging pre-generated completion files for Homebrew, distro packages, or release artifacts can be proposed separately.
