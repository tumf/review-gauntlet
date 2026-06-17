# Design: Run TUI value flash highlights

## Classification

This is an implementation proposal. It changes runtime TUI rendering behavior while preserving existing controller state and non-TUI output contracts.

## Current shape

`create_run_app()` constructs a Textual `RunApp` with `Static` widgets for the header, finalize checklist, agent summary, session summary, and activity timeline. `refresh_view()` periodically rebuilds plain text for each section and updates the entire widget. This makes implementation simple but provides no field-level update identity.

## Proposed rendering model

Introduce a small TUI-only field model with three concepts:

1. A stable field key, such as `session.coverage.completed` or `agent.status.kind`.
2. A comparison value, normalized to ignore volatile time-only text when appropriate.
3. A display value, which is the human-facing text rendered in the TUI.

The flash detector compares current comparison values to the previous refresh. When a field changes, the TUI marks that field as flash-active for a bounded window. TUI rendering then applies a flash style only around that field's display value.

Plain-text helper functions can remain unchanged. TUI-specific rich rendering helpers may be added alongside them so existing tests and non-TUI output do not receive markup.

## Volatile value policy

The following changes should not count as semantic changes:

- spinner frame changes
- elapsed-time changes
- quiet-duration numeric changes after the liveness kind is already quiet
- last-output-age numeric changes after an output age is already present
- timeout countdown numeric changes after the timeout display kind is already countdown

The following should count as semantic changes:

- status kind changes, such as running to quiet
- timeout display kind changes, such as not configured to countdown
- command changes
- artifact path changes
- coverage count or percent changes
- finding count changes
- active gate, gate state, gate marker, or gate detail changes
- new activity event/output rows

## Granularity

The implementation should prefer field/value granularity over text-diff granularity. This avoids brittle character diffs while satisfying the requirement that updates such as `0 / 2` to `1 / 2` highlight the changed count rather than the full panel. If a value cannot be safely split further, the narrowest named semantic field is acceptable, but the highlight must not expand to the entire panel.

## Verification strategy

Automated tests should exercise the field-change detector and TUI render helpers directly where possible. Headless Textual tests may be used for lifecycle integration, but the core behavior should be unit-testable without relying on terminal rendering.
