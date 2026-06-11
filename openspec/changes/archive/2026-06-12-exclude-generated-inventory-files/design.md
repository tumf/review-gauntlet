# Design: Exclude generated files from inventory

## Current behavior

`list_project_files()` prefers `git ls-files --cached --others --exclude-standard`. This respects Git ignore rules for untracked files, but it still returns untracked generated files when the generated directory is not ignored. The fallback path uses `root.rglob("*")` and a narrow `IGNORED_DIRS` set.

Because `.review-gauntlet/` is the durable session state directory, review execution can create files that later become part of the next review universe. That violates the expectation that coverage represents the reviewed project target, not review-gauntlet's own generated evidence.

## Design choices

### Built-in exclusions remain deterministic

A fixed built-in exclusion list should always apply before classification. This keeps review-universe generation deterministic and avoids relying on external tools for review-gauntlet's own generated state.

### Git remains the source for Git ignore semantics

When Git is available, `git ls-files --cached --others --exclude-standard` remains the primary discovery mechanism because it already implements repository ignore rules. The implementation should filter Git output through the same built-in exclusion predicate used by fallback discovery.

### Fallback covers common generated artifacts, not full Git pattern semantics

Fallback mode should exclude common generated artifacts directly. A complete `.gitignore` parser is intentionally out of scope for this change to keep implementation small and dependency-free.

## Expected implementation shape

- Add directory and file/name exclusion constants in `inventory.py`.
- Add a relative-path predicate that rejects paths with excluded directory components or excluded names/patterns.
- Apply that predicate to Git output before converting strings to `Path` objects.
- Apply the same predicate from `should_include_path()` after confirming the filesystem path is a file.

## Verification strategy

Unit tests should construct temporary project trees with normal source files and generated artifacts, then assert that only normal project files appear. Integration-style tests should exercise Git-backed inventory in a temporary repository so ignored and built-in excluded paths are verified through the primary discovery path.
