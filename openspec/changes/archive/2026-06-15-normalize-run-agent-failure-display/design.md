# Design: normalize run agent failure display

## Classification

Requested artifact: implementation.

The change affects runtime state propagation and TUI rendering, with tests proving that distinct agent failure modes remain distinguishable.

## Relationship to clarify-run-finalize-timeout

`clarify-run-finalize-timeout` handles a specific recovery case: the external adapter timed out after the session was otherwise ready to finalize. This proposal depends on that change and generalizes failure display outside that special case.

Implementation should avoid undoing the finalize-ready timeout cue. Instead, it should make that cue one specialized rendering branch within a broader status taxonomy.

## Status taxonomy

The controller should preserve a machine-readable reason and the TUI should map it to user-facing display text:

| Reason | Display intent |
| --- | --- |
| `timeout` | Timed out, with effective timeout duration when available |
| `command_failed` | Command exited non-zero |
| `startup_error` | Command could not start |
| `template_error` | Adapter config/template/cwd validation failed |
| `interrupted` | User/controller interruption |
| `max_steps_exhausted` | Orchestration stopped after max steps |

The exact internal enum/string names may differ, but the displayed states must remain distinguishable and machine-readable run output must keep reason/error fields.

## Rendering rules

- Do not display timeout language unless the underlying reason is an actual timeout.
- Do not duplicate labels in adjacent text, such as `timeout timeout not set`.
- Treat stdout/stderr tails as evidence; do not replace the controller's reason with guessed parsing from stderr.
- When stderr evidence contains a tool-level issue such as `File not found`, show it in the tail/activity area while the primary status remains the command execution reason.
- Preserve finalize-ready timeout recovery wording from `clarify-run-finalize-timeout`.

## Verification strategy

Use small synthetic `RunSnapshot`, `RunEvent`, and `SessionCommandResult` fixtures rather than invoking real external agents. Add integration coverage around CLI run JSON only where it proves machine-readable reason/error stability.
