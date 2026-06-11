# AGENTS.md

## Project shape

- Python 3.11 CLI package managed by `uv`; CI setup is `uv python install` then `uv sync --all-groups`.
- Console entrypoint is `review-gauntlet = review_gauntlet.cli:main` in `pyproject.toml`.
- Runtime code is in `src/review_gauntlet/`; tests are in `tests/`.
- Main flow: `cli.py` parses commands and exits with `64` for usage errors; `inventory.py` discovers/classifies files; `planner.py` builds slices/checks/matrix; `report.py` renders markdown.

## Commands

- CI-equivalent check: `make check`.
- `make check` runs in Make dependency order: `format-check`, `lint`, `typecheck`, `test`.
- Individual checks: `make format`, `make lint`, `make typecheck`, `make test`, `make coverage`.
- Hook parity: `make hooks`; install hooks with `make install-hooks` (`prek` pre-commit runs format+lint, pre-push runs typecheck+test).
- Focused tests: `uv run pytest tests/test_cli.py` or `uv run pytest tests/test_cli.py::test_cli_inventory_outputs_json`.
- CLI smoke commands: `uv run review-gauntlet inventory /path/to/repo --json`, `uv run review-gauntlet plan /path/to/repo --json`, `uv run review-gauntlet report /path/to/repo`.

## Tooling constraints

- Ruff line length is 100; lint rules are `E`, `F`, `I`, `UP`, `B`, `SIM`.
- Pyright is strict over `src` and `tests`; keep tests typed.
- Version bumps use Hatch targets in the Makefile; version source is `src/review_gauntlet/__about__.py`.

## Behavior to preserve

- JSON CLI output uses Pydantic `model_dump_json(indent=2)`; tests parse stdout directly.
- `inventory.py` prefers `git ls-files --cached --others --exclude-standard`; fallback is recursive walking with ignored dirs.
- Keep `git ls-files` subprocess bounded with the existing 10-second timeout.
- File classification drives review slices and checks; update `tests/test_inventory.py` and `tests/test_planner.py` when changing categories, risk tags, or check mapping.
