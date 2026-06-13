# Contributing

Thank you for improving Review Gauntlet. This project is a Python 3.11 CLI package managed with `uv`.

## Project layout

- Runtime code lives in `src/review_gauntlet/`.
- Tests live in `tests/`.
- The console entrypoint is `review-gauntlet = review_gauntlet.cli:main` in `pyproject.toml`.
- `cli.py` handles command parsing and usage exits.
- `inventory.py` discovers and classifies files.
- `planner.py` builds review slices, checks, and matrices.
- `report.py` renders markdown output.

## Setup

Install Python and dependencies with `uv`:

```bash
uv python install
uv sync --all-groups
```

Install local git hooks if you want pre-commit and pre-push parity with project checks:

```bash
make install-hooks
```

Install the CLI as a local tool when you want to run `review-gauntlet` outside `uv run`:

```bash
make install
```

## Development commands

Run the CI-equivalent check before submitting changes:

```bash
make check
```

`make check` runs these targets in order:

```bash
make format-check
make lint
make typecheck
make test
```

Useful focused commands:

```bash
make format
make lint
make typecheck
make test
make coverage
make hooks
uv run pytest tests/test_cli.py
uv run pytest tests/test_cli.py::test_cli_inventory_outputs_json
```

## CLI smoke testing

Use these commands to verify core CLI behavior while developing:

```bash
uv run review-gauntlet inventory /path/to/repo --format json
uv run review-gauntlet plan /path/to/repo --format json
uv run review-gauntlet report /path/to/repo
```

For the stateful review workflow, initialize a session and run one review step:

```bash
uv run review-gauntlet init
uv run review-gauntlet review --config review-gauntlet.jsonc
uv run review-gauntlet status
```

## Code style

- Ruff line length is 100.
- Ruff lint rules are `E`, `F`, `I`, `UP`, `B`, and `SIM`.
- Pyright runs in strict mode over `src` and `tests`.
- Keep tests typed.
- Prefer small, focused changes with tests that cover behavior.

## Testing expectations

Update tests whenever you change user-visible CLI behavior, inventory classification, review planning, risk tags, checks, or report rendering.

Classification and planning changes usually require updates in:

- `tests/test_inventory.py`
- `tests/test_planner.py`

JSON CLI output is parsed directly by tests, so preserve valid JSON on stdout for JSON output modes.

## Behavior to preserve

- JSON CLI output should use Pydantic `model_dump_json(indent=2)`.
- `inventory.py` should prefer `git ls-files --cached --others --exclude-standard`.
- Non-Git fallback discovery should continue to walk recursively while skipping ignored artifact directories.
- Keep the existing 10-second timeout around the `git ls-files` subprocess.
- External command adapters should use argv arrays, not shell strings.
- Provider login, model selection, and secrets should remain outside Review Gauntlet.

## Versioning

Version bumps use Hatch through Make targets:

```bash
make bump-patch
make bump-minor
make bump-major
```

The version source is `src/review_gauntlet/__about__.py`.

## Before submitting

Run:

```bash
make check
```

If you changed review workflow behavior, also run a relevant CLI smoke test and include the command in your PR notes.
