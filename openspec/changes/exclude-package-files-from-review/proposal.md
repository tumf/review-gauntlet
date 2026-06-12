---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/inventory.py
  - src/review_gauntlet/targets.py
  - src/review_gauntlet/cli.py
  - tests/test_inventory.py
  - tests/test_init_targets.py
  - README.md
  - openspec/specs/review-sessions/spec.md
  - openspec/CONSTITUTION.md
---

# Exclude Package Files From Review

**Change Type**: implementation

## Problem/Context

Review Gauntlet records deterministic review coverage, and the current review universe is built from inventory plus default review-path exclusions. The existing exclusions remove generated artifacts, docs, tests, and OCR-style test paths, but package manager manifests and lock files such as `uv.lock` can still become review cells.

Large package files are noisy review targets. They often encode dependency resolution output rather than application behavior, can produce oversized or low-value review work, and may stale review sessions whenever dependency metadata changes. The user's request is to exclude `uv.lock` and equivalent package files for other language ecosystems by default.

This must be a default review-target selection change, not an inventory deletion. Inventory and legacy planning diagnostics may still classify these files, but session review cells and target digests should omit them unless a future explicit override is introduced.

## Proposed Solution

Add a deterministic package-file review exclusion layer to `should_include_review_relative_path()`:

- Exclude common package manager lock files and dependency manifests from default review cells.
- Apply the same exclusion to worktree, branch, commit, and explicit `--all` session targets because all session target plans pass through the review-path filter.
- Keep artifact filtering separate from review filtering so package files can remain visible in general inventory diagnostics.
- Keep executable build scripts in scope unless they are clearly package metadata. Files such as `setup.py`, `build.gradle`, `build.gradle.kts`, `mix.exs`, `conanfile.py`, and `build.zig` should remain review-eligible because they can contain executable logic.
- Document the new default in README default file filtering guidance.

The initial exclusion set should cover widely used ecosystems without trying to detect every possible custom dependency file:

- Python: `uv.lock`, `poetry.lock`, `Pipfile`, `Pipfile.lock`, `requirements.txt`, `requirements-*.txt`, `constraints.txt`, `constraints-*.txt`, `environment.yml`, `environment.yaml`
- Node/Bun/Deno: `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lock`, `bun.lockb`, `deno.json`, `deno.jsonc`, `deno.lock`
- Rust: `Cargo.toml`, `Cargo.lock`
- Go: `go.mod`, `go.sum`, `go.work`, `go.work.sum`
- JVM: `pom.xml`, `gradle.lockfile`, `gradle/libs.versions.toml`
- Ruby: `Gemfile`, `Gemfile.lock`, `*.gemspec`
- PHP: `composer.json`, `composer.lock`
- Swift: `Package.swift`, `Package.resolved`
- Dart/Flutter: `pubspec.yaml`, `pubspec.lock`
- Elixir/Erlang: `mix.lock`, `rebar.lock`
- C/C++ package managers: `vcpkg.json`, `vcpkg-lock.json`, `conanfile.txt`
- Nix: `flake.lock`
- Haskell: `cabal.project.freeze`, `stack.yaml.lock`, `package.yaml`
- Julia/R: `Manifest.toml`, `renv.lock`

## Acceptance Criteria

- `uv.lock` and representative package manifests/lock files from major language ecosystems are excluded by default from session review cells.
- The exclusion applies consistently to default worktree init, explicit `--worktree`, branch range, commit, and `--all` session target planning.
- Package files remain eligible for general inventory classification unless already removed by artifact or Git ignore filtering.
- Review target digests and file digests omit package files so package-only changes do not create or stale review cells by default.
- Executable build scripts and project logic files are not broadly excluded merely because they are package-adjacent.
- README default file filtering documentation describes the package-file review exclusion and clarifies the inventory-vs-review distinction.
- Tests cover both direct review-path filtering and session cell creation behavior.

## Explicit Completion Conditions

The change is complete when repository evidence shows:

- `src/review_gauntlet/inventory.py` defines and applies a default package-file review exclusion inside `should_include_review_relative_path()`.
- `tests/test_inventory.py` proves representative package files return `False` from `should_include_review_relative_path()` while normal source files and executable package-adjacent scripts remain review-eligible.
- `tests/test_init_targets.py` proves session initialization omits package files from review cells for at least worktree/diff and full-repository targets.
- Target digest behavior is covered either directly or indirectly by tests that exercise `review_universe_files()` / `file_digests()` through session planning.
- `README.md` documents package files as default review-path exclusions without claiming they are removed from inventory.
- Focused tests for inventory and target initialization pass.
- `make check` passes.
- `cflx openspec validate exclude-package-files-from-review --strict` passes.

## Out of Scope

- Removing package files from general inventory output.
- Adding a user-facing include/override flag for package files.
- Auditing dependency vulnerability, license, or supply-chain risk from lockfiles.
- Changing OCR rule mapping for package files.
- Broadly excluding executable build scripts such as `setup.py`, `build.gradle`, `build.gradle.kts`, `mix.exs`, `conanfile.py`, or `build.zig`.
