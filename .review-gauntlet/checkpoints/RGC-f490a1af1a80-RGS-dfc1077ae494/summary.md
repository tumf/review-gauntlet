# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: f490a1af1a8043e59421934363af664f3ec74c3d
- Session ID: RGS-dfc1077ae494
- Created at: 2026-06-17T02:33:13.673089Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 2 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0704 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | Variable `seconds` (the function parameter) is shadowed by the `seconds` variable from `divmod(remainder, 60)`. While currently not a bug because `total_seconds` is already derived, any future maintenance that references `seconds` after line 425 will silently use the divmod remainder (an int) instead of the original float parameter. Rename the divmod output to avoid confusion. |
| RGF-0705 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | `_count_value` silently returns 0 for string-encoded integers (e.g. `"3"`), which is a common representation in JSON-derived data. If `coverage` or `findings` dictionaries ever contain string values from a JSON source that doesn't coerce types, all counts will silently read as zero, producing a dashboard that looks idle when work is actually tracked. Consider adding a `str` → `int` conversion path. |
| RGF-0706 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | `sanitize_agent_output_line` applies three regex substitutions on the full (potentially unbounded) input string before truncating via `_summarize_text` at the end. For very long agent output lines, this does unnecessary work. Truncate early — before applying the secret-redaction regexes — to bound the cost and avoid processing data that will be discarded anyway. Use a generous early limit (e.g., 2× `limit`) to avoid cutting a secret token in half before redaction can match it. |
| RGF-0707 | fixed_verified | src/review_gauntlet/run_tui.py | test-evidence | Rich markup escaping leaks into plain-text output. `_plain_text` unconditionally replaces `[` with `\[` (a Rich-specific escape), but this function is also called from plain-text rendering paths (e.g., `_summarize_text`, `sanitize_agent_output_line`, `short_session_id`, `terminal_state`). In non-Rich contexts, users will see literal `\[` instead of `[` in any text that contains square brackets. |
| RGF-0708 | fixed_verified | src/review_gauntlet/run_tui.py | test-evidence | Variable shadowing: the `seconds` parameter of `format_elapsed_time` is overwritten by `minutes, seconds = divmod(remainder, 60)` on line 425. While this doesn't cause a runtime bug because `total_seconds` already captured the sanitized value, it silently rebinds the parameter to an `int`, which would mask bugs if future edits reference `seconds` expecting the original `float` argument. |
| RGF-0709 | false_positive | src/review_gauntlet/run_tui.py | test-evidence | In `refresh_view`, the `session_header` widget never gets the base `"panel"` CSS class toggled, unlike the other panel widgets. Line 216 sets `session_header.set_class(state_class == view.state_class, state_class)` for all state classes, but skips `enabled` (which includes the `"panel"` base class). If a CSS rule targets `.panel` on the session header, it will never be applied. |
| RGF-0710 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | `payload.get("reason", "command failed")` only returns the default when the key is missing, not when it is explicitly `None`. If the payload contains `{"reason": None}`, `_summarize_text(None, ...)` renders as the string `"None"` via `str(None)` instead of the intended fallback. Use `event.payload.get("reason") or "command failed"` to cover both cases. |
| RGF-0711 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | Same `None`-value issue: if `payload["prompt"]` is explicitly `None`, `str(None)` produces `"None"`, which `format_task_title` would fail to match any mapping and display as `"READY TASK None"`. Use `event.payload.get("prompt") or ""` for safe fallback. |
| RGF-0712 | false_positive | src/review_gauntlet/run_tui.py | test-evidence | The positional-arg construction of `RunSnapshot` is fragile. If the dataclass fields are reordered or a field is inserted, this call silently passes the wrong values to the wrong parameters with no type error. Use keyword arguments. |
| RGF-0713 | false_positive | src/review_gauntlet/run_tui.py | test-evidence | Secret redaction runs after a `limit * 4` truncation, so secrets positioned beyond that offset survive into the returned string (which is then truncated to `limit`). If `limit` is large (e.g. passed explicitly), the gap between redaction scope and output scope grows. Move the truncation after redaction, or apply redaction to the full text. |
| RGF-0714 | false_positive | src/review_gauntlet/run_tui.py | test-evidence | The `id` parameter shadows the built-in `id` function. While harmless inside this closure, it can confuse linters and readers. Rename to `panel_id` or `widget_id`. |
| RGF-0715 | false_positive | src/review_gauntlet/run_tui.py | data-validation | `select_active_gate` indexes into `gates` with `gates[mapped_index - 1]` without a bounds check. While `_NEXT_ACTION_GATE_INDEX` values (1–6) currently match the 6-element tuple from `derive_finalize_gates`, adding a new action mapping or changing gate count would silently produce an `IndexError` at runtime. A guard `if 1 <= mapped_index <= len(gates)` before the index access makes this robust against future drift. |
| RGF-0716 | false_positive | src/review_gauntlet/run_tui.py | data-validation | `format_event_time` uses `timestamp.replace("Z", "+00:00")` which replaces every occurrence of the character "Z" in the string, not just a trailing UTC designator. Although ISO 8601 timestamps won't normally have "Z" elsewhere, validating untrusted or malformed input could produce unexpected parse results before the `except ValueError` fires. Consider anchoring the replacement to the end of the string. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1247 | RGF-0704 | untriaged | fixed_pending_verification | Renamed shadowed seconds variable to secs in format_elapsed_time divmod result |
| 1248 | RGF-0708 | untriaged | fixed_pending_verification | Duplicate of RGF-0704 — same seconds shadowing fix applied (renamed to secs) |
| 1249 | RGF-0706 | untriaged | fixed_pending_verification | Added early truncation (limit*4) before secret-redaction regex to bound processing cost |
| 1250 | RGF-0707 | untriaged | fixed_pending_verification | Split _plain_text into bracket-escaping-free base and _rich_safe_text for Rich contexts |
| 1251 | RGF-0705 | untriaged | fixed_pending_verification | Added str-to-int conversion path in _count_value for JSON string-encoded integers |
| 1252 | RGF-0709 | untriaged | false_positive | session_header is intentionally styled via #session_header CSS selector, not .panel class — the different set_class behavior is by design |
| 1253 | RGF-0707 | fixed_pending_verification | fixed_verified | review_verification |
| 1254 | RGF-0708 | fixed_pending_verification | fixed_verified | review_verification |
| 1255 | RGF-0705 | fixed_pending_verification | fixed_verified | review_verification |
| 1256 | RGF-0706 | fixed_pending_verification | fixed_verified | review_verification |
| 1257 | RGF-0704 | fixed_pending_verification | fixed_verified | review_verification |
| 1258 | RGF-0714 | untriaged | false_positive | Textual framework convention uses id= as widget parameter name — shadowing builtin id is standard practice |
| 1259 | RGF-0713 | untriaged | false_positive | Secrets beyond limit*4 are truncated by _summarize_text(limit) and never appear in output — no leak possible |
| 1260 | RGF-0712 | untriaged | false_positive | Dead code marked with pyright reportUnusedFunction suppression — positional args in unused function are not actionable |
| 1261 | RGF-0711 | untriaged | fixed_pending_verification | Changed .get('prompt', '') to .get('prompt') or '' to handle explicit None values |
| 1262 | RGF-0710 | untriaged | fixed_pending_verification | Changed .get('reason', 'command failed') to .get('reason') or 'command failed' to handle explicit None values |
| 1263 | RGF-0711 | fixed_pending_verification | fixed_verified | review_verification |
| 1264 | RGF-0710 | fixed_pending_verification | fixed_verified | review_verification |
| 1265 | RGF-0715 | untriaged | false_positive | _NEXT_ACTION_GATE_INDEX values are 1-6 and derive_finalize_gates always returns exactly 6 gates, so gates[mapped_index-1] is always in bounds. Both are co-maintained in the same file. |
| 1266 | RGF-0716 | untriaged | false_positive | In valid ISO 8601 timestamps, Z only appears as the timezone suffix. The date/time portion uses digits, hyphens, colons, and dots only. Even if input were malformed, the subsequent fromisoformat() call would raise ValueError caught by the except clause. |

## Blockers

None
