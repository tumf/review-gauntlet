## Implementation Tasks

- [x] Route legacy plan construction through review eligibility filtering in `src/review_gauntlet/cli.py`. Completion condition: `review-gauntlet plan` and `review-gauntlet report` both construct their `ReviewPlan` from `_review_inventory(inventory)` or an equivalent shared path, while `inventory` output remains unfiltered by review eligibility. (verification: unit - `uv run pytest tests/test_cli.py::test_cli_plan_applies_review_exclusions`)

- [x] Add CLI regression coverage for filtered legacy planning output in `tests/test_cli.py`. Completion condition: the test creates eligible source files plus excluded `docs/`, `openspec/`, test-pattern, and package files, then verifies plan JSON includes only eligible review paths. (verification: unit - `uv run pytest tests/test_cli.py::test_cli_plan_applies_review_exclusions`)

- [x] Preserve general inventory behavior for package and non-review files. Completion condition: existing inventory tests still demonstrate `build_inventory` includes package files that are excluded from review planning. (verification: unit - `uv run pytest tests/test_inventory.py::test_package_files_remain_in_general_inventory`)

- [x] Run focused verification for affected planning and exclusion behavior. Completion condition: focused CLI, inventory, and init target tests pass locally. (verification: unit - `uv run pytest tests/test_cli.py tests/test_inventory.py tests/test_init_targets.py`)

## Final Validation

Expected full project gate: `make check`.
Expected OpenSpec gate: `cflx openspec validate fix-plan-review-exclusions --strict --evidence warn`.
