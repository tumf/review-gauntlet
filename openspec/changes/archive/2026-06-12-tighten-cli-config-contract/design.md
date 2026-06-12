# Design: Tighten CLI and Config Contract

## Scope

This proposal addresses contract correctness and validation clarity without changing the review session lifecycle.

## Decisions

- Use persisted enum values for filtering because the ledger stores underscore values while the CLI exposes hyphenated aliases.
- Prefer strict environment variable validation over attempting to pass through platform-specific invalid names.
- Keep template validation simple. Literal brace support must be explicit and tested; otherwise braces should remain reserved for template variables with clear errors.
- Pin CI to Python 3.11 because project instructions and `pyproject.toml` target that runtime.

## Verification Strategy

Focused unit/integration tests are sufficient because these are parser, config, and workflow-file contract changes.
