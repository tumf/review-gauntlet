# Design: Align Docs, Bootstrap, and Report Output

## Scope

This proposal addresses user-facing correctness and safety after the core review lifecycle has evolved beyond the original README design text.

## Decisions

- Prefer fail-closed bootstrap behavior over silently executing mutable remote code. If automatic install remains necessary, it must be pinned and checksum-verified.
- Keep markdown as the report output format, but escape dynamic cell content so existing consumers are not forced onto a new format.
- Treat AGENTS and README as part of the operational contract because repo-local agent instructions and user docs guide day-to-day usage.

## Verification Strategy

Docs and bootstrap changes are primarily manual-inspection changes, while markdown report escaping should be covered by unit tests because it is deterministic string rendering.
