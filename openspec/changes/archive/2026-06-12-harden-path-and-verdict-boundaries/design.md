# Design: Harden Path and Verdict Boundaries

## Scope

This change hardens trust boundaries without changing the public review workflow. The implementation should reject unsafe inputs early and preserve current successful behavior for normal repository-relative paths.

## Decisions

- Treat repository-relative path validation as a reusable concern rather than duplicating ad hoc string checks in each caller.
- Reject path traversal and absolute paths for CLI filters and target-scoped inventory inputs because these values conceptually address repository content.
- Resolve filesystem paths before containment checks, but avoid following symlinks into review universe content when a symlink can escape the root.
- Keep command adapter `cwd` constrained to the repository root. Out-of-repository cwd would expand the trust boundary and should require a separate proposal if needed.
- Validate adapter verdict scope after JSON schema validation and before writing canonical verdict artifacts or returning findings to the review flow.

## Verification Strategy

Use focused unit tests for pure path validation and integration-style adapter tests for verdict handling because those failures must prove no coverage or finding persistence occurs after invalid external output.
