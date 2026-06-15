# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: ceb3e47cd92d22e6e68a76be152b998de61f0758
- Session ID: RGS-7b9e48e2abae
- Created at: 2026-06-15T02:45:56.988828Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 13 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0106 | fixed_verified | src/review_gauntlet/cli.py | data-validation | `_positive_int` calls `int(value)` directly, so a non-integer value such as `--max-steps abc` raises an uncaught `ValueError` and prints a traceback instead of argparse's normal usage error. Wrap the conversion and raise `argparse.ArgumentTypeError` so invalid user input is reported consistently. |
| RGF-0107 | false_positive | src/review_gauntlet/run_controller.py | test-evidence | The controller emits `agent_started` only after `_command_runner` returns, so observers never see the agent as started while the potentially long-running command is executing. This makes the run status/event stream misleading and leaves the TUI unable to show an in-progress command before completion. |
| RGF-0108 | fixed_verified | src/review_gauntlet/run_controller.py | cli-contract | `agent_started` is emitted only after `_command_runner` has returned, so event sinks and the TUI cannot observe that the external command is running while it is actually in progress. This makes the run contract misleading for long-running adapters: observers receive both start and finish only after the subprocess exits. Emit a pre-run event before calling `_command_runner` (or move argv rendering out of the runner so `agent_started` can be emitted before execution). |
| RGF-0109 | false_positive | src/review_gauntlet/run_controller.py | data-validation | `agent_started` is emitted only after `_command_runner` returns, so observers cannot see the command as started while it is actually running and the event ordering is misleading for long-running adapters. Build or expose the argv before invoking the runner, or rename/reorder this event so progress consumers do not receive a late start event. |
| RGF-0110 | false_positive | src/review_gauntlet/run_tui.py | cli-contract | The TUI schedules the full controller run on the Textual UI thread. Because controller.run() can execute long-running external review commands synchronously, the event loop is blocked while a step runs, so documented TUI controls such as q/refresh/Ctrl-C cannot be processed until after the command returns. This breaks the interactive CLI contract for stopping or interrupting a running review from the TUI. |
| RGF-0111 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | `validate-verdict` only runs `validate_verdict_json`, so it accepts comments for any `path`. The OCR contract shown in the prompt requires every comment path to equal the active review cell path, but this command has no way to enforce that. A malformed adapter can return a valid verdict for a different file, pass validation, and only fail later in the adapter/session path instead of at the requested validation step. |
| RGF-0112 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | The TUI displays the next ready prompt directly from session data without escaping Rich/Textual markup or control sequences. If a prompt contains Rich markup (for example bracketed tags) or terminal control characters, it can alter or corrupt the TUI rendering instead of being shown as literal task text. Escape or render it as plain text before passing it to Static. |
| RGF-0113 | fixed_verified | src/review_gauntlet/run_tui.py | test-evidence | The TUI tests skip entirely when the optional Textual dependency is missing, so CI can pass without exercising create_run_app(), refresh_view(), or the worker/exit path even though this module is part of the shipped runtime behavior. This leaves regressions in the text-mode-to-TUI integration undetected unless the local environment happens to have the optional extra installed. Add non-optional unit coverage by monkeypatching the textual modules used here, or ensure the TUI extra is installed in the test environment that owns these assertions. |
| RGF-0114 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | Event payload values are rendered without the same plain-text normalization used for prompts, even though step_started events include the review prompt and other payload fields can come from external adapter data. Control characters or Rich/Textual markup in those values can corrupt the TUI display or be interpreted as markup. Normalize keys and values with _plain_text before concatenating them into the Static renderable. |
| RGF-0115 | false_positive | src/review_gauntlet/run_tui.py | test-evidence | The TUI sanitizes the current task text, but other user- or adapter-controlled strings are rendered directly. command_argv and event payload values can contain Textual/Rich markup or control characters, which may alter the display or hide content in the TUI. Apply the same plain-text normalization used for task prompts before rendering argv and event payloads. |
| RGF-0116 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | The TUI renders `snapshot.command_argv` without applying the same plain-text sanitization used for prompts and event payloads. Because command adapter argv values can come from configuration, a value containing Textual/Rich markup such as `[red]...[/red]` or terminal control characters can alter the UI rendering instead of being displayed literally. |
| RGF-0117 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | Coverage/findings keys and values are rendered directly in the Textual/Rich view, unlike prompts/events/argv which pass through _plain_text. If a session status contains Rich markup or control characters in these fields, the TUI can render misleading formatting or unreadable control output. Sanitize both keys and values through the same plain-text helper before joining them. |
| RGF-0118 | accepted_risk | src/review_gauntlet/run_tui.py | cli-contract | Ctrl-C in the TUI exits with a hand-built interrupted result that omits the active session_id and the standard error field returned by the non-TUI KeyboardInterrupt path. This makes `review-gauntlet run` return different JSON shapes for the same interrupt depending on whether stdout is a TTY, violating the CLI contract and making callers unable to identify the interrupted session from TUI output. |
| RGF-0119 | accepted_risk | src/review_gauntlet/run_tui.py | test-evidence | Ctrl-C exits the TUI immediately while the controller worker thread may still be running the current command. This can make `review-gauntlet run` report an interrupted result even though the agent subprocess continues mutating the session in the background, which is especially risky for a review orchestration command. Wait for the controller worker to finish after requesting interruption, or make the controller/command runner actually terminate the in-flight command before returning the interrupted result. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 218 | RGF-0106 | untriaged | confirmed | Valid: _positive_int lets ValueError escape for non-integer argparse input |
| 219 | RGF-0109 | untriaged | false_positive | Duplicate of RGF-0108/RGF-0107 agent_started ordering issue; keep one representative finding |
| 220 | RGF-0108 | untriaged | confirmed | Valid: agent_started is emitted only after the blocking command runner returns |
| 221 | RGF-0107 | untriaged | false_positive | Duplicate of RGF-0108 agent_started ordering issue; no separate finding needed |
| 222 | RGF-0110 | untriaged | false_positive | Already fixed in current code: run_tui uses run_worker(thread=True) and call_from_thread |
| 223 | RGF-0106 | confirmed | fixed_pending_verification | Wrapped _positive_int conversion errors in argparse.ArgumentTypeError and added CLI regression test. |
| 224 | RGF-0108 | confirmed | fixed_pending_verification | Emitted agent_started before running command_runner and added regression coverage for event ordering. |
| 225 | RGF-0106 | fixed_pending_verification | fixed_verified | review_verification |
| 226 | RGF-0108 | fixed_pending_verification | fixed_verified | review_verification |
| 227 | RGF-0111 | untriaged | confirmed | validate-verdict validates schema but has no expected path argument, so it cannot enforce the prompt contract that every comment.path equals the active review cell path. |
| 228 | RGF-0113 | untriaged | confirmed | tests/test_run_tui.py skips TUI runtime coverage when optional Textual is absent, leaving shipped run_tui behavior untested in default environments without the extra. |
| 229 | RGF-0112 | untriaged | confirmed | run_tui renders next_ready_prompt directly into Static text without normalizing markup/control sequences, so arbitrary prompt text can affect TUI rendering. |
| 230 | RGF-0111 | confirmed | fixed_pending_verification | Added --expected-path validation for validate-verdict, updated file-json prompt command, and covered mismatched comment paths with tests. |
| 231 | RGF-0112 | confirmed | fixed_pending_verification | Escaped task prompt markup/control characters before TUI rendering and added regression coverage. |
| 232 | RGF-0113 | confirmed | fixed_pending_verification | Added rich/textual to the dev dependency group so default uv sync --all-groups CI installs TUI dependencies and executes TUI tests instead of skipping them. |
| 233 | RGF-0112 | fixed_pending_verification | fixed_verified | review_verification |
| 234 | RGF-0111 | fixed_pending_verification | fixed_verified | review_verification |
| 235 | RGF-0113 | fixed_pending_verification | fixed_verified | review_verification |
| 236 | RGF-0114 | untriaged | confirmed | TUI events render adapter/user-controlled payload values without _plain_text normalization; run_controller emits the full prompt in step_started payload. |
| 237 | RGF-0115 | untriaged | false_positive | Duplicate of RGF-0114; same run_tui.py normalization issue covers argv/event payload rendering. |
| 238 | RGF-0114 | confirmed | fixed_pending_verification | Normalized TUI event keys, values, timestamps, and event types with _plain_text before rendering; make check passes |
| 239 | RGF-0114 | fixed_pending_verification | fixed_verified | review_verification |
| 240 | RGF-0116 | untriaged | confirmed | Confirmed: run_tui._agent_text renders command_argv and agent_status without _plain_text while other dynamic TUI fields sanitize markup/control characters. |
| 241 | RGF-0116 | confirmed | fixed_pending_verification | Sanitized TUI agent status and command argv with _plain_text before rendering; added regression coverage. |
| 242 | RGF-0116 | fixed_pending_verification | fixed_verified | review_verification |
| 243 | RGF-0117 | untriaged | confirmed | run_tui.py sanitizes prompts/events/argv with _plain_text, but _counts_text renders status-derived coverage/finding keys and values directly; this is a real display-sanitization gap. |
| 244 | RGF-0117 | confirmed | fixed_pending_verification | Sanitized coverage and finding count keys/values through _plain_text in run_tui counts rendering; focused TUI tests and make check passed. |
| 245 | RGF-0117 | fixed_pending_verification | fixed_verified | review_verification |
| 246 | RGF-0118 | untriaged | accepted_risk | Known TUI Ctrl-C behavior accepted for now: the interrupted result is returned promptly, and changing worker termination semantics needs separate design work. |
| 247 | RGF-0119 | untriaged | accepted_risk | Known TUI Ctrl-C behavior accepted for now: background command cancellation semantics require broader controller design, not a stale-review blocker. |

## Blockers

None
