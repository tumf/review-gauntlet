# Design: OCR-Inspired File Filtering

## Goals

- Keep review coverage deterministic and explainable.
- Reduce review-cell noise from generated, vendored, dependency, specification, documentation, and conventional test files.
- Preserve a clean boundary between general inventory classification and default review-cell eligibility.
- Keep future include/exclude configuration possible without rewriting filter logic.

## Source Reference

Alibaba `open-code-review` commit `c323c6b40c72aa95d7cb801bedcb957b52ff9807` uses multiple file-selection gates:

1. hardcoded diff directory exclusions for IDE metadata, VCS metadata, vendor/dependency/build package directories
2. binary exclusion
3. user exclude patterns
4. supported extension allowlist
5. user include bypass for built-in default excludes
6. built-in default exclude patterns for test/generated paths

This proposal adopts the relevant deterministic filtering concepts, not the full OCR configuration model.

## Proposed Filtering Layers

### Artifact Inclusion Filter

This layer answers: "Can this path belong to the project inventory/review universe at all?"

It should exclude:

- existing review-gauntlet state and Python/editor artifacts
- VCS metadata
- dependency/vendor/build directories from OCR (`vendor`, `node_modules`, `target`, `_packages`, `rpm`, `pkgs`)
- generated/cache directories from OCR (`.happypack`, `.cachefile`, `oh_modules`)

This layer should apply to inventory discovery and target-scoped inventory construction.

### Default Review Eligibility Filter

This layer answers: "Should this otherwise-included path become a default review cell?"

It should exclude repository-local default review directories and OCR-style default review patterns:

- `openspec/**`, `tests/**`, and `docs/**`
- Go/Rust/Python/Ruby test naming patterns
- Java `*Test.java` / `*Tests.java` and Maven/Gradle test source paths
- Kotlin test source paths
- frontend `.test.*`, `.spec.*`, and `__tests__` paths
- ETS test files
- `oh_modules` generated paths

The layer should be implemented as named pattern constants plus a helper such as `is_default_review_excluded_path(relative)` or an equivalent API.

## Caller Responsibilities

- `build_inventory()` and `build_inventory_for_paths()` use artifact inclusion filtering.
- Review cell generation uses artifact inclusion plus default review eligibility filtering.
- `target_digest()` and `file_digests()` use the review eligibility filter so excluded files do not stale active review coverage.
- Classification remains responsible only for categorizing included files, not deciding review eligibility.

## Trade-offs

- Excluding `openspec/`, `tests/`, `docs/`, and test files from default review cells reduces noise but may miss spec-only, docs-only, or test-only regressions until include/exclude configuration exists. This is acceptable because the proposal explicitly tracks the behavior and future override support is out of scope.
- Extension allowlisting is deferred. `review-gauntlet` already uses category/risk tagging and may need broader project visibility than OCR's per-file review model.
- User configurable include/exclude patterns are deferred to avoid mixing default behavior with configuration precedence rules in one change.

## Verification Strategy

- Unit tests cover helper behavior and fallback inventory walking.
- Integration-style tests cover Git-backed inventory and init target modes.
- Digest tests ensure coverage staleness follows the same review-universe filter as cell generation.
