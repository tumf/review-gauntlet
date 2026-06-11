## Design Notes

The current CLI uses a shared `_session_output_args` helper for multiple session commands. That helper is too broad for `findings` because it couples the command to progress/audience concepts that only matter for commands with decorative or intermediate output.

The minimal design is to keep the shared helper for commands whose current contract still requires it and define findings output arguments inline in `build_parser`. This avoids changing unrelated commands and keeps the compatibility impact limited to the requested command.

`_emit` already treats any non-JSON format as text-style output, so the implementation should not need a new renderer. The behavioral change is the accepted CLI vocabulary and help output, not the findings payload or default text rendering shape.

## Compatibility

This is a breaking CLI option cleanup for `findings` only:

- `--format human` is no longer accepted.
- `--audience` is no longer accepted.

The default command remains human-readable/text output, so users running `review-gauntlet findings` without these options see the same class of output as before.
