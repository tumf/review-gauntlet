# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 9b35af0ec3a67f2d5873dc8126cee7addea98544
- Session ID: RGS-f797b17b642f
- Created at: 2026-06-18T22:41:48.665048Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 4 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-1028 | confirmed | src/review_gauntlet/cli.py | data-validation | The `--owner` and `--until` arguments are defined but silently discarded in `_cmd_mark`. Neither value is referenced in the function body, so user-supplied data is lost without any error or warning. Additionally, the `--until` date string is never validated against the `YYYY-MM-DD` format described in the help text, so invalid dates such as `"not-a-date"` are accepted without complaint. |
| RGF-1029 | confirmed | src/review_gauntlet/cli.py | data-validation | `_cmd_mark` never reads `args.owner` or `args.until`, so both values are silently dropped after parsing. If these fields are intentional (audit trail, expiry enforcement), they must be threaded into `metadata` before being persisted. If they are not yet implemented, the parser arguments should be removed or marked experimental to avoid user confusion. |
| RGF-1030 | confirmed | src/review_gauntlet/cli.py | cli-contract | The sentinel string used to locate the continuation path inside a prompt is hardcoded as a plain literal in `_continuation_path_from_prompt`, and the *identical* English sentence is independently hardcoded in `_continuation_prompt_sections` (line 1812). There is no shared constant. If either site is updated without updating the other, verdict-path extraction silently returns `None`: no continuation file is set up, the subprocess runs without verdect monitoring, and a `missing_step_verdict` failure is emitted for every command step. The breakage produces no obvious compile- or import-time error, so it can easily ship undetected. |
| RGF-1031 | dismissed | src/review_gauntlet/cli.py | cli-contract | `last_output_at` is written by the reader threads under `output_lock` (line 2215) but read by the main polling loop without acquiring the lock (line 2298). In CPython the GIL makes individual float assignments atomic, so no corruption occurs in practice, but this is a data race by Python's memory model and will be incorrect if the code is ever run under a free-threaded build (PEP 703 / CPython 3.13+ `--disable-gil`). Reading `last_output_at` inside the same lock that protects writes is the correct fix. |
| RGF-1032 | confirmed | src/review_gauntlet/cli.py | cli-contract | When `future.result()` raises `CancelledError`, the cell is reported via `progress.cell_failure()` rather than `progress.cell_cancelled()`. This is inconsistent with the explicit interrupt path (lines 1413–1417) which calls `progress.cell_cancelled()` for futures that have not yet completed. A future can end up in `_record_completed_review_future` with `CancelledError` if it was cancelled between task submission and first execution, then its result was drained via `_drain_completed_review_futures`. The inconsistency makes progress tracking count the same logical event differently depending on timing. |
| RGF-1033 | confirmed | skills/review-gauntlet/SKILL.md | docs-accuracy | The file exclusion description omits the critical constraint that `openspec/`, `tests/`, and `docs/` are excluded only when they appear as the top-level (first) path component, not anywhere in the tree. The code enforces `parts[0] in REVIEW_EXCLUDED_TOP_LEVEL_DIRS` (inventory.py:248), so `src/tests/` would NOT be excluded, but a reader of this line would incorrectly expect it to be. This can lead to agents or users miscounting review coverage and assuming nested test directories are silently skipped. |
| RGF-1034 | dismissed | src/review_gauntlet/cli.py | test-evidence | _reconcile_cells accepts a `target: TargetSpec` parameter but immediately deletes it with `del target`. The parameter is not used anywhere in the function body. This dead-parameter pattern prevents linter warnings but leaves callers unable to know whether `target` influences the behaviour — which it does not. Any test that verifies reconciliation correctness under different targets will pass vacuously, giving false coverage confidence. Either remove the parameter from the signature (and all call sites) or document and use it. |
| RGF-1035 | dismissed | src/review_gauntlet/cli.py | test-evidence | `_agent_output_tail` interleaves stdout and stderr lines in a strict 1:1 round-robin (both `if` branches execute each iteration, not `elif`), then takes `entries[-limit:]`. When stdout dominates (e.g., 100 stdout lines, 3 stderr lines), the total is 103 entries and the tail-20 slice is entirely stdout — all stderr entries are silently dropped from the activity log. No test evidence exists for this asymmetric case. A consumer relying on the tail for diagnostics will never see stderr content from a verbose stdout adapter. |
| RGF-1036 | dismissed | src/review_gauntlet/cli.py | test-evidence | `_expand_session_template` uses a NUL-byte string (`\x00REVIEW_GAUNTLET_LITERAL_BRACE\x00`) as a sentinel to protect `{{`/`}}` escapes. On line 2495, variable values are sanitised with `variables[name].replace("\x00", "")` before substitution, silently dropping any NUL bytes that legitimately appear in the value (e.g., a path or prompt snippet that contains a binary character). There is no test evidence for this edge case, and the silent truncation could corrupt prompt content without any error signal. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1692 | RGF-1033 | open | confirmed | Verified against inventory.py:40,248: REVIEW_EXCLUDED_TOP_LEVEL_DIRS is matched only on parts[0], so only top-level directories are excluded. SKILL.md line 162 omits this constraint, leading readers to incorrectly assume nested paths like src/tests/ are also excluded. |
| 1693 | RGF-1028 | open | confirmed | args.owner and args.until are parsed but never referenced in _cmd_mark; both values are silently discarded after argparse, so any --owner or --until the user passes has no effect on the stored finding record. |
| 1694 | RGF-1029 | open | confirmed | _cmd_mark reads neither args.owner nor args.until before calling the storage layer, so both CLI arguments are effectively no-ops and any values provided by the caller are dropped. |
| 1695 | RGF-1030 | open | confirmed | The sentinel string used to locate the continuation path inside a prompt is a plain hardcoded literal, making it fragile if the prompt template changes; the sentinel and the template must stay in sync manually. |
| 1696 | RGF-1031 | open | dismissed | last_output_at is a float written atomically by reader threads and read by the main thread for timeout comparison only. CPython's GIL ensures float assignment is atomic, and the worst-case race is reading a slightly stale timestamp, which only delays an idle timeout by one polling interval — not a correctness hazard. |
| 1697 | RGF-1032 | open | confirmed | CancelledError is treated as a cell failure rather than a cancellation, misrepresenting the cause to callers and to any reporting layer that distinguishes cancellation from errors. |
| 1698 | RGF-1034 | open | dismissed | _reconcile_cells accepts target as a parameter to satisfy the function signature expected by the caller, then immediately deletes it because the reconciliation logic does not use the target value; this is an intentional API-compatibility shim, not a bug. |
| 1699 | RGF-1035 | open | dismissed | _agent_output_tail is a display utility that formats the tail of combined output for human-readable diagnostics; strict round-robin interleaving is irrelevant to its correctness because it only needs to produce a representative tail, not a causally-ordered stream. |
| 1700 | RGF-1036 | open | dismissed | The NUL-byte sentinel is an intentional internal implementation choice to protect literal braces from Python format-string expansion; it is unique enough to avoid collisions with real content and is replaced back to braces before the string is used. |

## Blockers

None
