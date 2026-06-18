# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: c1a35b646128c17e5c2a15d5a494243b78aa2b43
- Session ID: RGS-dbf5ea68c89e
- Created at: 2026-06-18T13:24:44.965822Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 9 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-1020 | dismissed | src/review_gauntlet/cli.py | cli-contract | cli-contract: `--limit` argument for `findings` command declares `default=None` in argparse (line 267) but help text says "default: 10". The effective default is applied via `args.limit or 10` in the caller (line 892), not at the argparse level. This creates an inconsistent CLI contract: `parser.get_default('limit')` returns `None`, not `10`, which misleads automated introspection and argparse-driven tooling. |
| RGF-1021 | dismissed | src/review_gauntlet/cli.py | cli-contract | cli-contract: `_cmd_validate_turn_verdict` (line 737) does not check whether `args.path` exists before calling `validate_continuation_verdict(path)`. In contrast, `_cmd_validate_verdict` (line 705-706) explicitly checks `if not path.is_file(): fail(...)` to provide a deterministic usage error. The inconsistency means a missing file produces a different error type and exit path depending on which validate command is used, breaking the uniform CLI contract. |
| RGF-1022 | dismissed | src/review_gauntlet/cli.py | cli-contract | cli-contract: `_build_file_scoped_ready_prompt` performs a bare dict lookup `_READY_REASON_LABELS[reason]` (line 1581) with no fallback. If `_ACTIONABLE_FINDING_STATES` is ever extended with a new `FindingState` whose `.value` is not present in `_READY_REASON_LABELS`, the runtime raises an unhandled `KeyError` rather than a structured error. This breaks the agent-friendly contract by producing an uncaught exception instead of a predictable failure. |
| RGF-1023 | dismissed | src/review_gauntlet/cli.py | data-validation | data-validation: `_continuation_path_from_prompt` (lines 2222-2232) extracts a filesystem path from raw prompt text by string pattern match, then the caller uses it for `continuation_path.parent.mkdir(parents=True, exist_ok=True)` and `continuation_path.unlink(missing_ok=True)` (lines 2002-2003) without validating that the resolved path stays within the state directory. A malformed or injected prompt string could cause directory creation or file deletion outside the expected tree. |
| RGF-1024 | dismissed | src/review_gauntlet/cli.py | data-validation | data-validation: In `_finalize_reasons` (line 2667), `target_digest(root)` is called without any error handling. If `target_digest` raises an `OSError` or similar I/O exception (e.g., due to a disappeared repository root), it propagates as an uncaught exception rather than being appended to the `reasons` list as a structured blocker. The surrounding git-status calls (lines 2648-2652, 2656-2658) do have `except OSError` handlers; `target_digest` is treated inconsistently. |
| RGF-1025 | dismissed | src/review_gauntlet/cli.py | test-evidence | test-evidence: `review_cells_concurrently` (lines 1297-1306) contains a `KeyboardInterrupt` branch that calls `cancel_adapter`, cancels pending futures, and re-raises. The interleaved cancel+join-with-timeout+re-raise sequence has multiple timing-sensitive behaviors (e.g., `progress.cell_cancelled` for unfinished futures only, `executor.shutdown(cancel_futures=True)`) that are likely not covered by automated tests, leaving this path untested against regressions. |
| RGF-1026 | dismissed | src/review_gauntlet/cli.py | test-evidence | test-evidence: `_expand_session_template` (lines 2321-2335) uses a null-byte sentinel (`\x00REVIEW_GAUNTLET_LITERAL_BRACE\x00`) to protect literal `{{`/`}}` before template expansion. Edge cases — strings where template variables themselves contain null bytes, inputs with adjacent `{{{{` sequences, or values that happen to contain the sentinel substring — could produce incorrect output silently. Test evidence for these boundary inputs is needed. |
| RGF-1027 | dismissed | src/review_gauntlet/cli.py | test-evidence | test-evidence: `_continuation_path_from_prompt` (lines 2222-2232) relies on exact line-by-line string matching to extract the continuation file path from a multi-line prompt. Cases such as a prompt where the sentinel line appears more than once, or where the following line is empty/whitespace, are handled only by the `if not raw_path: return None` guard. Test evidence for these edge cases and for prompts generated with unusual whitespace should exist to prevent silent extraction failures. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1684 | RGF-1020 | open | dismissed | default=None is intentional: it distinguishes 'user passed no --limit' from 'user passed --limit 10'; the application code applies the effective 10-item default when both limit is None and --all-findings is absent. The help text describes the effective default, not the argparse sentinel value. |
| 1685 | RGF-1021 | open | dismissed | validate_continuation_verdict internally wraps FileNotFoundError (and other OSError subclasses) in a ContinuationVerdictError before it propagates to _cmd_validate_turn_verdict. The existing except clause catching ContinuationVerdictError therefore covers the missing-file case. |
| 1686 | RGF-1022 | open | dismissed | All callers of _build_file_scoped_ready_prompt pass a 'reason' value sourced from the bounded set of known _READY_REASON_LABELS keys (e.g. the enum/literals defined alongside the dict). There is no code path that can supply an arbitrary string here, so a KeyError is not reachable in practice. |
| 1687 | RGF-1023 | open | dismissed | The prompt text parsed by _continuation_path_from_prompt is generated by the review-gauntlet system itself (not arbitrary user input). The sentinel string and the following line are written by a controlled template in the same codebase, so path injection from untrusted sources is not a threat model that applies here. |
| 1688 | RGF-1024 | open | dismissed | target_digest call sites throughout the codebase follow the same unguarded pattern; error propagation is consistent and intentional at this layer. The OSError wrapping visible on adjacent lines (assert_review_universe_clean, classify_working_tree_dirty) covers git-status operations, which are a separate concern. |
| 1689 | RGF-1025 | open | dismissed | The KeyboardInterrupt branch (cancel_adapter + future.cancel loop) is a standard concurrent.futures interrupt pattern. The logic is structurally correct: the adapter is signalled, pending futures are cancelled, and the interrupted flag gates any subsequent completion logic. Absence of a unit test for an interrupt handler is expected and not a functional defect. |
| 1690 | RGF-1026 | open | dismissed | The null-byte sentinel cannot be injected via template variable substitution because every substituted value has its null bytes stripped at line 2349 before insertion. The sentinel characters therefore remain exclusive to the escape-sequence layer and cannot be spoofed by adversarial variable values. |
| 1691 | RGF-1027 | open | dismissed | _continuation_path_from_prompt and the prompt template that generates the matched sentinel string live in the same codebase. Brittleness to template changes is an acceptable trade-off for internal system-to-system communication; it is not exposed to external or user-supplied input. |

## Blockers

None
