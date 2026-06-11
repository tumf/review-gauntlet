# AGENTS.md

## Project shape

- Python 3.11 CLI package managed by `uv`; install with `uv sync --all-groups` to match CI.
- Console entrypoint is `review-gauntlet = review_gauntlet.cli:main` in `pyproject.toml`.
- Runtime code lives in `src/review_gauntlet/`; tests live in `tests/`.
- Main flow: `cli.py` parses commands, `inventory.py` collects/classifies files, `planner.py` builds review slices/checks, `report.py` renders reports.

## Commands

- Full CI-equivalent check: `make check`.
- `make check` runs, in order: `format-check`, `lint`, `typecheck`, `test`.
- Format: `make format`; lint only: `make lint`; typecheck only: `make typecheck`; tests only: `make test`.
- Coverage: `make coverage` writes terminal output and `htmlcov/`.
- Focused tests: `uv run pytest tests/test_cli.py` or `uv run pytest tests/test_cli.py::test_cli_inventory_outputs_json`.
- CLI smoke examples: `uv run review-gauntlet inventory /path/to/repo --json`, `uv run review-gauntlet plan /path/to/repo --json`, `uv run review-gauntlet report /path/to/repo`.

## Tooling constraints

- Ruff line length is 100; lint rules are `E`, `F`, `I`, `UP`, `B`, `SIM`.
- Pyright runs in strict mode over `src` and `tests`.
- CI installs Python via `uv python install`, syncs with `uv sync --all-groups`, then runs `make check`.
- Version bumps use Hatch targets in the Makefile; the version source is `src/review_gauntlet/__about__.py`.

## Behavior to preserve

- The CLI exits with code `64` for usage errors such as a missing root.
- `inventory.py` prefers `git ls-files --cached --others --exclude-standard`; non-git fallback is recursive file walking with ignored dirs.
- `inventory.py` has a 10-second timeout around `git ls-files`; keep subprocess behavior bounded.
- JSON output is Pydantic `model_dump_json(indent=2)`; tests parse the CLI stdout directly.
