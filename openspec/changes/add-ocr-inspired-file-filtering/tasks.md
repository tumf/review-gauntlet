## Implementation Tasks

- [x] Add shared filtering helpers for artifact exclusions and default review-path exclusions, preserving existing generated artifact rules and adding OCR-inspired directories (`vendor`, `node_modules`, `target`, `.happypack`, `.cachefile`, `_packages`, `rpm`, `pkgs`, `oh_modules`). Completion condition: filtering constants/helpers are defined in `src/review_gauntlet/inventory.py` or a dedicated module and existing callers no longer duplicate directory-name checks. (verification: unit - extend `tests/test_inventory.py` to assert fallback inventory excludes the new generated/dependency directories while keeping normal source files.)

- [x] Apply artifact exclusions consistently to Git-backed and fallback full inventory discovery. Completion condition: `list_project_files()` and `build_inventory_for_paths()` both use the shared artifact inclusion helper for relative paths returned by Git or filesystem walking. (verification: integration - extend `tests/test_inventory.py` with a Git-backed repository containing tracked or untracked files under `vendor/`, `node_modules/`, and `target/`, and assert they are absent from inventory output.)

- [x] Add default review-path pattern filtering for repository specification/test/documentation directories and OCR-style test/generated paths without changing file classification for source files outside those patterns. Completion condition: review-universe construction can distinguish general inventory inclusion from default review-cell eligibility and contains default exclusions for `openspec/**`, `tests/**`, `docs/**`, plus patterns equivalent to OCR defaults for Go, Java, Kotlin, Rust, JS/TS, Python, Ruby, ETS, `__tests__`, and `oh_modules` paths. (verification: unit - add or extend tests around review cell generation to assert `src/app.py` remains eligible while `openspec/specs/review-sessions/spec.md`, `tests/test_core.py`, `docs/usage.md`, `foo_test.go`, `FooTest.java`, `app.spec.ts`, `spec/foo_spec.rb`, and `oh_modules/generated.ets` do not produce default review cells.)

- [x] Route all session target modes through the shared review eligibility filter. Completion condition: default/worktree init, branch init, commit init, and `init --all` all omit default-excluded review paths from initial cells while still recording eligible changed files. (verification: integration - extend `tests/test_init_targets.py` or related session tests with changed files in source and excluded test/generated paths for at least worktree and `--all` target modes.)

- [x] Align review target digesting with review eligibility to avoid stale coverage from excluded files. Completion condition: `target_digest()` and `file_digests()` in `src/review_gauntlet/targets.py` use the same review-universe file filter rather than only excluding `.review-gauntlet`. (verification: unit - add tests in `tests/test_targets.py` or session reconciliation tests showing changes under excluded generated/test paths do not alter the digest for the active review universe, while eligible source file changes do.)

- [x] Preserve Git ignored-file behavior and bounded subprocess execution. Completion condition: existing `git ls-files --cached --others --exclude-standard` calls and 10-second timeouts remain intact; new filtering is applied after Git output rather than replacing Git ignore semantics. (verification: unit - keep or extend existing `.gitignore` tests in `tests/test_inventory.py` and `tests/test_init_targets.py` to prove ignored files remain absent.)

- [x] Update user-facing documentation for default file filtering. Completion condition: README or CLI documentation describes built-in artifact exclusions, OCR-style default review exclusions, and the fact that Git ignore behavior still applies. (verification: manual - intentionally documentation-facing coverage; compare documented behavior against `uv run review-gauntlet inventory <repo> --json` and `uv run review-gauntlet init <repo> --all --format json` output on a fixture repository.)

## Future Work

- Add project/user configurable include/exclude patterns that can override default review-path exclusions.
- Add a supported-extension allowlist or rule-aware eligibility layer if review scope needs to converge further with OCR behavior.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-ocr-inspired-file-filtering --archive-gate`

## Acceptance Notes

- Acceptance #1 identified missing Rust `_test.rs` default review-path exclusion coverage. This apply added `_test.rs` to the shared review exclusion suffixes and added focused unit/integration/digest regression coverage.
- Focused verification passed with `agent-exec run -- uv run pytest tests/test_inventory.py tests/test_init_targets.py tests/test_targets.py` (job `ca4c3a79994d23af66460859c46a4500`, exit code 0).
