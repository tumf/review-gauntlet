## Implementation Tasks

- [x] Add deterministic package-file review exclusion constants and matching logic in `src/review_gauntlet/inventory.py` without changing artifact inventory filtering. (verification: unit - `tests/test_inventory.py` asserts `should_include_review_relative_path()` rejects representative package files while `build_inventory()` can still include package files that are not artifacts or Git-ignored)
- [x] Cover representative ecosystem package files and patterns including Python, Node/Bun/Deno, Rust, Go, JVM, Ruby, PHP, Swift, Dart, Elixir/Erlang, C/C++ package managers, Nix, Haskell, Julia, and R. (verification: unit - `tests/test_inventory.py` parametrizes or lists the package file names and glob-style patterns from the proposal acceptance criteria)
- [x] Preserve review eligibility for package-adjacent executable logic files that can contain application or build behavior, including `setup.py`, `build.gradle`, `build.gradle.kts`, `mix.exs`, `conanfile.py`, and `build.zig`. (verification: unit - `tests/test_inventory.py` asserts these paths still pass `should_include_review_relative_path()` unless excluded by another existing rule)
- [x] Ensure session initialization omits package files from review cells for worktree/diff target planning. (verification: integration - `tests/test_init_targets.py` creates changed package files such as `uv.lock`, `package-lock.json`, and `Cargo.lock` alongside changed source and asserts only source paths appear in `SessionStore.list_cells()`)
- [x] Ensure explicit full-repository review omits package files from review cells while preserving normal source files. (verification: integration - `tests/test_init_targets.py` extends the `--all` exclusion test or adds an equivalent case covering representative package files)
- [x] Ensure review universe digest inputs omit package files by default. (verification: unit or integration - a test in `tests/test_init_targets.py` or a focused target test proves package-only changes do not add review cells or package paths to the current review universe)
- [x] Update README default file filtering documentation to describe package manifest and lock file review exclusions while clarifying that inventory may still classify them. (verification: manual - repository evidence: `README.md:103-117` documents review-path package manifest and lock-file exclusions, inventory-vs-review distinction, and package-adjacent executable eligibility)
- [x] Run focused verification for filtering and target selection behavior. (verification: integration - `uv run pytest tests/test_inventory.py tests/test_init_targets.py` passes)
- [x] Run the project quality gate after implementation. (verification: integration - `make check` passes)

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected proposal validation: `cflx openspec validate exclude-package-files-from-review --strict`
Expected archive gate: `cflx openspec validate exclude-package-files-from-review --archive-gate`

## Acceptance Notes

Archive commitability was previously blocked by the real archive-gate validation step because `tasks.md:9` used a manual verification note. The task now cites repository-verifiable README path and line evidence instead of manual inspection.
