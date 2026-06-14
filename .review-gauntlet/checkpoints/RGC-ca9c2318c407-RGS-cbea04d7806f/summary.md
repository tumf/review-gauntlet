# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: ca9c2318c407e1975801656dfeb8fd3b13d85113
- Session ID: RGS-cbea04d7806f
- Created at: 2026-06-14T07:57:49.581943Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 4 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0083 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | `review` reports success even when some selected cells never produce a result. `review_cells_concurrently` can return without entries for futures that are cancelled during executor shutdown or fail to be tracked in an unexpected path, and `_cmd_review` indexes `results[selected.id]` directly. That raises an uncaught `KeyError`, bypassing the CLI's structured failure response and exit handling. Treat missing results as adapter failures so the CLI contract remains stable. |
| RGF-0084 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | `verify-fixes` has the same direct lookup of concurrent review results. If a selected cell is missing from `results`, the command crashes with `KeyError` before emitting the verification summary, so callers lose `targeted_finding_ids`, reopened/unverifiable state, and the expected non-zero CLI response. Mirror the defensive handling used for review results. |
| RGF-0085 | fixed_verified | src/review_gauntlet/cli.py | data-validation | Expired accepted-risk decisions are never detected because the SQL filter uses the dashed state value 'accepted-risk', while persisted FindingState.ACCEPTED_RISK values are 'accepted_risk'. This lets expired accepted-risk findings pass finalize validation. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 158 | RGF-0083 | untriaged | confirmed | Direct results[selected.id] lookup can raise KeyError if concurrent review returns no entry, bypassing structured CLI failure handling. |
| 159 | RGF-0084 | untriaged | confirmed | verify-fixes uses the same direct results[selected.id] lookup and can crash before emitting the expected verification summary. |
| 160 | RGF-0083 | confirmed | fixed_pending_verification | Handled missing concurrent review results as structured adapter failures |
| 161 | RGF-0084 | confirmed | fixed_pending_verification | Handled missing concurrent verify-fixes results as structured adapter failures |
| 162 | RGF-0085 | untriaged | fixed_pending_verification | Code already uses persisted accepted_risk state value in expired terminal decision query. |
| 163 | RGF-0085 | fixed_pending_verification | fixed_verified | review_verification |
| 164 | RGF-0083 | fixed_pending_verification | fixed_verified | review_verification |
| 165 | RGF-0084 | fixed_pending_verification | fixed_verified | review_verification |

## Blockers

None
