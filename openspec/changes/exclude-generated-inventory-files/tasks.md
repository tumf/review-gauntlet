## Implementation Tasks

- [ ] Add shared inventory exclusion predicates for relative paths and filesystem paths so both Git-backed discovery and fallback recursive discovery apply the same built-in exclusions. (verification: unit - `tests/test_inventory.py` asserts excluded paths are absent from `build_inventory` output)
- [ ] Exclude review-gauntlet-generated state and common generated artifacts, including `.review-gauntlet/`, `.ruff_cache/`, `.pyright/`, `.mypy_cache/`, `build/`, `dist/`, `wheels/`, `*.egg-info/`, `.coverage`, `htmlcov/`, `.DS_Store`, `.idea/`, and `.vscode/`. (verification: unit - add `tests/test_inventory.py::test_build_inventory_excludes_generated_artifacts` and run `uv run pytest tests/test_inventory.py`)
- [ ] Preserve existing source classification behavior for normal project files while adding the exclusion layer. (verification: unit - keep `tests/test_inventory.py::test_build_inventory_classifies_project_files` passing via `uv run pytest tests/test_inventory.py`)
- [ ] Add `.review-gauntlet/` to `.gitignore` so generated session artifacts are ignored in standard Git-backed inventory and normal Git workflows. (verification: integration - add `tests/test_inventory.py::test_git_inventory_excludes_review_gauntlet_state` using a temporary Git repo and run `uv run pytest tests/test_inventory.py`)
- [ ] Verify self-review artifacts do not inflate the review universe after a run. (verification: integration - add `tests/test_inventory.py::test_inventory_omits_review_run_artifacts` and run `uv run review-gauntlet inventory . --json` to confirm `.review-gauntlet/` paths are absent)
- [ ] Run the project quality gate. (verification: integration - `make check`)

## Future Work

- Complete `.gitignore` pattern parsing for fallback mode if review-gauntlet needs exact Git ignore semantics outside Git repositories.

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate exclude-generated-inventory-files --archive-gate`
