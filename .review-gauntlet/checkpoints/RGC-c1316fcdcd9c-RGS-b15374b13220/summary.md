# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: c1316fcdcd9c5ba228f906241323a3e1923e1b67
- Session ID: RGS-b15374b13220
- Created at: 2026-06-19T00:09:58.740583Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 4 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-1037 | confirmed | src/review_gauntlet/coverage_projection.py | data-validation | `store.session_metadata(session_id)` の戻り値に対して `metadata["target"]` を直接アクセスしているため、キーが存在しない場合や `None` が返った場合に文脈のない `KeyError`/`TypeError` が発生します。データ取得後に必須キーの存在を確認するガード節を追加してください。 |
| RGF-1038 | confirmed | src/review_gauntlet/coverage_projection.py | data-validation | DBから取得した `row["state"]` をそのまま `str()` でキャストするだけで、期待される状態値（`"open"`, `"pending"`, `"reviewed"` など）であるかの検証が行われていません。予期しない状態値は優先度計算を経てサイレントに誤った結果を生み出します。許容される状態の集合を定義し、不正値は早期にエラーにするか警告を記録してください。 |
| RGF-1039 | dismissed | src/review_gauntlet/coverage_projection.py | data-validation | `min()` の `key` に `("P0","P1","P2","P3").index(label)` を使用していますが、`priority_label` が型チェック上は `Literal` であってもランタイムでは単なる `str` です。`_priority_label` のロジックバグや将来の変更で予期しないラベルが生成された場合、`list.index()` が `ValueError` を送出しアプリ全体がクラッシュします。安全な比較のために辞書ルックアップかデフォルト付きの方法を使用してください。 |
| RGF-1040 | confirmed | src/review_gauntlet/run_tui.py | data-validation | `format_event_time` only catches `ValueError`, but if `timestamp` is not a string (e.g., `None` from a missing JSON field), `timestamp.replace(...)` raises `AttributeError` which propagates uncaught and would crash the TUI. Since `event.timestamp` comes from external data, non-string values are plausible. |
| RGF-1041 | dismissed | src/review_gauntlet/run_tui.py | data-validation | `select_active_gate` accesses `gates[-1]` as a default without checking that `gates` is non-empty. It also accesses `gates[mapped_index - 1]` where `mapped_index` comes from `_NEXT_ACTION_GATE_INDEX` (values 1–4) without validating that the tuple has enough elements. If `gates` were ever empty or shorter than expected (e.g., from a future refactor), this raises `IndexError`. |
| RGF-1042 | confirmed | src/review_gauntlet/coverage_projection.py | test-evidence | The `stale` field is hardcoded to 0 in `_rule_summaries`, but the sorting key on line 450 includes `summary.stale`. This makes that sort term permanently dead code and the `RuleCoverageSummary.stale` field always misleadingly reports 0 regardless of how many stale cells exist. The same bug appears in `_file_summaries` at line 470. Callers that display or test stale counts will see incorrect data. |
| RGF-1043 | confirmed | src/review_gauntlet/coverage_projection.py | test-evidence | Same hardcoded `stale=0` bug in `_file_summaries`. The sorting key at line 484 references `summary.stale`, making that term permanently dead code. Fix by counting entries whose state equals "stale". |
| RGF-1044 | confirmed | src/review_gauntlet/coverage_projection.py | test-evidence | When a finding's `latest_cell_id` does not match any current cell, `_findings_by_cell` fans the finding out to **every** cell that shares the same `(file_path, rule_id)`. If a file is covered by multiple slices, the finding is appended to all of their buckets, inflating `finding_count` and `actionable_finding_count` in each resulting `QueueEntry`. Priority scores and labels computed in `_queue_entry_for_cell` are therefore overcounted for multi-slice files. A test pairing two slices on the same file with a single orphaned finding would expose this. |
| RGF-1045 | confirmed | src/review_gauntlet/coverage_projection.py | test-evidence | `changed_since_review` is set to `True` whenever `cell.state == "stale"`, even if the file content has not actually changed. This propagates an incorrect `changed_since_review=True` value into every `QueueEntry` for stale cells, misleading consumers that inspect the field directly. Line 360 only suppresses the "changed file" human-readable reason for stale cells; the boolean field itself still says the file changed. Consider separating the two signals. |
| RGF-1046 | confirmed | src/review_gauntlet/run_tui.py | test-evidence | sanitize_agent_output_line is a security-critical function that redacts credentials (tokens, secrets, API keys, passwords) from agent stdout/stderr before they are rendered in the TUI. It has zero test coverage: no test in tests/test_run_tui.py or any other test file imports or exercises it. Without tests, silent regressions to the redaction logic (e.g. a pattern silently failing to match, ANSI-stripping interacting badly with a secret pattern, or a new credential format being missed) would reach the TUI undetected. The function should have at minimum: a test that a Bearer token is redacted, a test that KEY=value env-var form is redacted, and a test that ANSI escape sequences are stripped before redaction so a credential split across CSI codes cannot bypass the patterns. |
| RGF-1047 | confirmed | src/review_gauntlet/run_tui.py | test-evidence | The `cov.stale` branch in header_status_text (and the parallel branch at line 1147-1148 in header_status_tui_lines) is dead code: ProgressMetrics.stale is always 0 because calculate_progress_metrics initialises `stale = 0` and never increments it (comment reads 'stale is intentionally ignored'). No test documents that this omission is intentional, so a future maintainer who changes calculate_progress_metrics to start populating stale counts will unknowingly activate these display paths without any test signalling the behavioural change. Add a test that verifies stale entries are NOT shown in the header even when the coverage dict contains stale cells, or remove the dead branches. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1701 | RGF-1037 | open | confirmed | session_metadata は dict を保証するが 'target' キーの存在は保証しない。checkpoint.py:294 では metadata.get('target') を使うため None がセットされる可能性があり、その場合 TargetSpec.model_validate(None) がPydantic ValidationError で失敗する。KeyError も 'target' キー欠如時に発生しうる。 |
| 1702 | RGF-1038 | open | confirmed | DBから取得した row['state'] を str() のみでキャスト。期待される状態値（open/pending/reviewed等）の検証がなく、DB破損や外部からの不正データが混入した場合、不正なstateが下流処理に伝播する。 |
| 1703 | RGF-1039 | open | dismissed | priority_label は常に _priority_label() が返す値であり、その戻り値は CoveragePriorityLabel = Literal['P0','P1','P2','P3'] の4値のいずれか。コード上の全ての呼び出しパスで不正値の混入経路がなく、ValueErrorは実際には発生しない。 |
| 1704 | RGF-1042 | open | confirmed | stale=0 がハードコードされコメント '# stale is intentionally ignored' がある一方、ソートキー（line 450）で -(summary.pending + summary.stale + summary.actionable_findings) として summary.stale を参照。常に0のためデッドコードとなり、staleセルがrule優先度ソートに影響することを示すテストが不可能な設計になっている。 |
| 1705 | RGF-1043 | open | confirmed | RGF-1042と同様、_file_summaries でも stale=0 ハードコード（# stale is intentionally ignored）だがソートキー（line 484）で -(summary.pending + summary.stale) として参照。summary.stale は常に0でソートへの影響なし、デッドコード状態。 |
| 1706 | RGF-1044 | open | confirmed | latest_cell_id が現在のセルに一致しない場合（line 318-320）、同じ (file_path, rule_id) を持つ全候補セルに finding を配布する。これにより finding_count / actionable_finding_count / resolved_finding_count が二重計上（またはN重計上）される。 |
| 1707 | RGF-1045 | open | confirmed | cell.state == 'stale' のとき changed_since_review=True がセットされるが（line 177）、コンテンツがrevertされた場合、changed_files セットに含まれなくても stale 状態のまま残る可能性がある。その場合、実際には変更がないのに changed_since_review=True となり、優先度スコアが誤って上昇する。 |
| 1708 | RGF-1040 | open | confirmed | format_event_time catches only ValueError but None.replace() raises AttributeError that escapes the handler. Type hints are unenforced at runtime; the function's defensive intent (try/except with fallback) is incomplete. |
| 1709 | RGF-1041 | open | dismissed | gates[-1] and gates[mapped_index-1] are safe in practice: the sole caller passes the result of derive_finalize_gates, which always returns a tuple of 4-5 gates; _NEXT_ACTION_GATE_INDEX values 1-4 stay within that range. No exploitable code path produces an empty or shorter tuple. |
| 1710 | RGF-1046 | open | confirmed | sanitize_agent_output_line redacts credentials (tokens, API keys, passwords) from agent output but has zero test coverage. Security-sensitive redaction logic must have tests to catch regressions in the regex patterns. |
| 1711 | RGF-1047 | open | confirmed | All existing tests pass stale=0, so the 'if cov.stale:' branch in header_status_text (line 1034) and header_status_tui_lines (line 1148) has no test coverage. A stale-count regression would go undetected. |

## Blockers

None
