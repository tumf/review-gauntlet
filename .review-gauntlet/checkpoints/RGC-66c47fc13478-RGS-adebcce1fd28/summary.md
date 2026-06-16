# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 66c47fc1347820de32d2387f1707b8333cf2819c
- Session ID: RGS-adebcce1fd28
- Created at: 2026-06-16T14:17:26.478572Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 3 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0562 | false_positive | src/review_gauntlet/cli.py | data-validation | The `args.limit or 10` fallback uses truthiness instead of an explicit `None` check. If `_positive_int` were ever relaxed to allow `0` (e.g., changed to `_non_negative_int`), `0 or 10` would silently produce `10`. Using `args.limit if args.limit is not None else 10` is more precise and future-proof. |
| RGF-0563 | false_positive | src/review_gauntlet/cli.py | data-validation | `_finding_states` constructs a raw SQL query with a dynamic IN clause and calls `store.connect()` directly, bypassing the `SessionStore` abstraction. While the query is properly parameterized (no injection risk), this couples CLI logic to the database schema. If the `findings` table or column names change, this breaks without any type-system or interface guardrail. Consider adding a `get_finding_states(session_id, finding_ids)` method to `SessionStore`. |
| RGF-0564 | false_positive | src/review_gauntlet/cli.py | test-evidence | All `cell_start` events are emitted in the submission loop before any cell actually begins executing. This makes progress reporting misleading — every cell is reported as 'started' immediately, rather than when it is picked up by the thread pool. Move `cell_start` into the submitted callable or emit it from the future callback. |
| RGF-0565 | false_positive | src/review_gauntlet/cli.py | test-evidence | N+1 query: for each finding matching the session, an additional query fetches its latest event metadata. With many waived/accepted-risk findings this becomes expensive. Consider joining findings and finding_events in a single query. |
| RGF-0566 | false_positive | src/review_gauntlet/cli.py | test-evidence | The `_finding_states` function constructs SQL and calls `store.connect()` directly, bypassing the SessionStore API. Other similar lookups (e.g. in `_ready_findings`, `_findings`) do the same. This makes the CLI layer coupled to the database schema. Consider moving this query into a SessionStore method. |
| RGF-0567 | false_positive | src/review_gauntlet/cli.py | test-evidence | Mutating the argparse Namespace with an undeclared private attribute (`_tui_rendered`) to communicate state between `_cmd_run` and its caller is fragile. If the attribute name changes or a new code path forgets to check it, the text output is silently emitted or suppressed. Consider returning a richer result type or a named tuple that carries both the result dict and a `tui_rendered` flag. |
| RGF-0568 | false_positive | src/review_gauntlet/cli.py | cli-contract | N+1 query pattern: `_expired_terminal_decision_count` executes one additional SQL query per finding row returned by the initial query. For sessions with many waived/accepted-risk findings, this linearly scales database round-trips. This can be collapsed into a single query with a JOIN between `findings` and `finding_events`. |
| RGF-0569 | false_positive | src/review_gauntlet/cli.py | cli-contract | The round-robin interleaving of stdout and stderr lines in `_agent_output_tail` does not reflect the actual temporal order of output. When an agent writes 5 lines to stdout then 3 to stderr, the tail shows them alternating (stdout[0], stderr[0], stdout[1], stderr[1], ...) rather than in emission order. Since this tail is displayed to users and persisted in activity.jsonl, it can make debugging agent failures misleading. |
| RGF-0570 | false_positive | src/review_gauntlet/cli.py | cli-contract | Mutating the argparse Namespace with a private attribute (`args._tui_rendered = True`) couples TUI rendering state to the argument parser in a fragile way. If `_validated_run_result` or any intermediate code accesses `args` from a different scope, or if argparse internals change, this breaks silently. Consider returning a result wrapper or flag from `_cmd_run` instead. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1077 | RGF-0562 | untriaged | false_positive | args.limit uses _positive_int type (>=1), so 0 is impossible. Speculative about hypothetical future type changes. |
| 1078 | RGF-0563 | untriaged | false_positive | Design suggestion to move SQL into SessionStore. SQL is properly parameterized, no data-validation bug. |
| 1079 | RGF-0566 | untriaged | false_positive | Duplicate of RGF-0563. Refactoring suggestion, not a test-evidence concern. |
| 1080 | RGF-0564 | untriaged | false_positive | cell_start at submission time is consistent and predictable. Enhancement suggestion, not a bug. |
| 1081 | RGF-0567 | untriaged | false_positive | Working pattern for TUI state communication. Design preference, not a correctness issue. |
| 1082 | RGF-0570 | untriaged | false_positive | Duplicate of RGF-0567. Same _tui_rendered design concern. |
| 1083 | RGF-0569 | untriaged | false_positive | Without timestamps, no approach preserves true temporal order. Round-robin interleaving is a valid design choice. |
| 1084 | RGF-0565 | untriaged | false_positive | SQLite is in-process with negligible overhead for N+1. Optimization suggestion, not a bug. |
| 1085 | RGF-0568 | untriaged | false_positive | Duplicate of RGF-0565. Same N+1 SQLite concern. |

## Blockers

None
