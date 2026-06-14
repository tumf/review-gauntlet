# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 8e8f8af85e9ffd8a57b746cf19eb64ec441b63f8
- Session ID: RGS-cb7b00287f4a
- Created at: 2026-06-14T07:07:54.530976Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 9 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0079 | fixed_verified | src/review_gauntlet/config.py | data-validation | Escaped template braces are removed before scanning, so malformed inputs such as `{{repo_root}` have balanced brace counts after removal and are accepted even though they are not a valid escaped literal or template. This can let invalid adapter configuration pass validation and fail later during formatting/execution. Validate unmatched braces on the original string or use a parser that consumes escaped brace pairs instead of deleting them first. |
| RGF-0080 | fixed_verified | src/review_gauntlet/cli.py | data-validation | The mark command accepts waiver metadata for every target state and stores it even when it is not semantically applicable. That lets `review-gauntlet mark RGF-0001 confirmed --until 2000-01-01` persist expiry metadata on a confirmed finding, and if the finding is later transitioned to waived without a fresh `--until`, expiry checks only inspect the latest waived/accepted-risk event and will treat the waiver as non-expiring. Validate `--until` (and owner expiry metadata) only for terminal waiver/risk states, or clear/reject it for other state transitions so stale metadata cannot influence later policy decisions. |
| RGF-0081 | fixed_verified | src/review_gauntlet/config.py | data-validation | This validator accepts NaN and Infinity because Pydantic will parse them as floats and the only check is `<= 0`. Those values are not meaningful subprocess timeouts: `subprocess.communicate(timeout=float("nan"))` can behave as an immediate timeout and `Infinity` can effectively disable the configured bound, so a malformed config can either fail every review or hang indefinitely. Require a finite positive timeout. |
| RGF-0082 | fixed_verified | src/review_gauntlet/config.py | cli-contract | `XDG_CONFIG_HOME` is used without resolving or constraining it. If this CLI is run in a repository with no local config, an attacker-controlled environment can make review-gauntlet load an adapter config from an arbitrary directory outside the repo, causing an unexpected external review command to execute. Consider ignoring global config in non-interactive/CI contexts or requiring an explicit opt-in/ownership check before using env-provided global adapter config. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 146 | RGF-0080 | untriaged | confirmed | 実装確認済み: --until/owner metadata が waived/accepted-risk 以外の状態にも保存されるため、状態遷移後の expiry policy を曖昧にし得る |
| 147 | RGF-0079 | untriaged | confirmed | 実装確認済み: escaped braces を削除してから brace balance を見るため、半端な escape を不正として検出できない |
| 148 | RGF-0080 | confirmed | fixed_pending_verification | Rejected --until for non-waiver mark states and omitted metadata for non-terminal transitions; added regression test. |
| 149 | RGF-0079 | confirmed | fixed_pending_verification | Validated template brace parsing on the original string so half-escaped braces like {{repo_root} are rejected; added regression coverage. |
| 150 | RGF-0081 | untriaged | confirmed | Non-finite adapter.timeout_seconds is accepted by current validator; subprocess timeouts require finite positive values. |
| 151 | RGF-0081 | confirmed | fixed_pending_verification | Rejected non-finite adapter.timeout_seconds values with math.isfinite and added regression coverage for inf, -inf, and nan. |
| 152 | RGF-0080 | fixed_pending_verification | fixed_verified | review_verification |
| 153 | RGF-0081 | fixed_pending_verification | fixed_verified | review_verification |
| 154 | RGF-0079 | fixed_pending_verification | fixed_verified | review_verification |
| 155 | RGF-0082 | untriaged | confirmed | config.py reads XDG_CONFIG_HOME global config without canonicalizing the env-provided directory; this is a real trust-boundary concern for implicit adapter config discovery |
| 156 | RGF-0082 | confirmed | fixed_pending_verification | Resolved by canonicalizing XDG_CONFIG_HOME and home config paths with Path.resolve before global config discovery. |
| 157 | RGF-0082 | fixed_pending_verification | fixed_verified | review_verification |

## Blockers

None
