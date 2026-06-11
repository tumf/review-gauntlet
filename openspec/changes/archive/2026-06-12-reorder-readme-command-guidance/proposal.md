---
change_type: implementation
priority: medium
dependencies: []
references:
  - README.md
  - src/review_gauntlet/cli.py
  - openspec/specs/review-sessions/spec.md
---

# Reorder README command guidance around session workflow

**Change Type**: implementation

## Problem/Context

The README currently introduces `inventory`, `plan`, and `report` before the session workflow. Those commands are preserved compatibility and inspection surfaces, while the primary review workflow now runs through `init`, `review`, `status`, `findings`, `mark`, and `finalize`. This ordering can mislead readers into treating `inventory` as a day-to-day entry point rather than a diagnostic planning command.

## Proposed Solution

Update the README command guidance so the top-level usage path starts with setup and the session-based review workflow. Move `inventory`, `plan`, and `report` into a later diagnostic or compatibility subsection that explains their purpose as file discovery, slicing, and report-rendering inspection helpers rather than the normal review loop.

## Acceptance Criteria

- The README's initial command guidance shows the primary session workflow before legacy planning commands.
- The README presents `init`, `review`, `status`, `findings`, optional `mark`, and `finalize` as the normal review lifecycle.
- The README keeps the existing target-selection examples for `init` visible near the session workflow.
- The README still documents `inventory`, `plan`, and `report`, but labels them as diagnostic/inspection/legacy planning commands rather than top-level day-to-day commands.
- The documentation remains consistent with the CLI behavior in `src/review_gauntlet/cli.py` and the compatibility requirement for existing planning commands.

## Explicit Completion Conditions

- `README.md` no longer lists `uv run review-gauntlet inventory` as the first user-facing Review Gauntlet command after setup.
- A reader can follow the README from setup to `init` and one `review` run without first being directed through `inventory`, `plan`, or `report`.
- `inventory`, `plan`, and `report` remain documented with their diagnostic purpose and example invocations.
- `make check` passes after the README-only change, or any failure is unrelated and documented.
- `cflx openspec validate reorder-readme-command-guidance --strict` passes before implementation handoff.

## Out of Scope

- Changing CLI behavior, command names, flags, or output formats.
- Removing `inventory`, `plan`, or `report`.
- Changing file classification, target selection, review-cell generation, or adapter behavior.
