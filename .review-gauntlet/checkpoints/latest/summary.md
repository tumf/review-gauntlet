# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: a597b7ffc2c0cc1778bf418096a91b9ad6cbce7b
- Session ID: RGS-7372f688802f
- Created at: 2026-06-12T22:14:03.174438Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 18 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0050 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | A cleanup failure after the new latest checkpoint has already been installed can make finalize report failure after mutating the checkpoint state. If shutil.rmtree(old_dir) raises on line 168, checkpoint_dir has already been replaced at line 167, but the exception propagates; the CLI will not finalize/clean the session even though .review-gauntlet/checkpoints/latest now points at the new generation. This violates the CLI contract that failed finalize is no-write/no-cleanup and can leave users with a new review base from an apparently failed command. |
| RGF-0051 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | The latest checkpoint accepts any schema_version value, including future or incompatible versions, as long as the required keys are present. A checkpoint format change could then be silently treated as a valid review base and produce incorrect target reconstruction. Validate the schema version before trusting the rest of the file. |
| RGF-0052 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | review_base_commit is coerced with str() and then passed to git commands. Non-string JSON values such as null or arrays become strings like 'None' or "['x']", which results in misleading git failures instead of rejecting malformed checkpoint data at the validation boundary. Check the field is a string before using it as a commit id. |
| RGF-0053 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | The findings --mark filter exposes hyphenated CLI values such as false-positive and accepted-risk, but _FINDING_MARK_TO_STATE stores underscore enum values for those states. As a result, filtering with --mark false-positive or --mark accepted-risk produces no rows even when matching findings exist, breaking the CLI contract for advertised filter choices. |
| RGF-0054 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | Checkpoint validation never verifies schema_version, even though status.json records CHECKPOINT_SCHEMA_VERSION. A future incompatible checkpoint can still be accepted as a review base as long as the other required fields/files are present, so init may silently reuse data written with an unsupported schema. Please reject unsupported schema versions and add a regression test that writes a latest checkpoint with a mismatched schema_version. |
| RGF-0055 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | `checkpoint_id` is coerced with `str(...)`, so a checkpoint whose status.json contains a non-string ID can pass validation if findings.json/events.json use the same stringified value. This weakens the checkpoint schema and can make malformed or corrupted checkpoint metadata usable as a review base. |
| RGF-0056 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | Checkpoint validation only checks that findings.json/events.json are JSON objects with a matching checkpoint_id, so a corrupt checkpoint such as {"checkpoint_id": "..."} is accepted as a valid review base even though the required findings/events arrays are missing or malformed. This can make target_from_latest_checkpoint resume from an unusable checkpoint and silently lose audit data. |
| RGF-0057 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | argparse のデフォルト error() は不正な引数や unknown option で SystemExit(2) を送出するため、このプロジェクトの CLI 契約（usage error は 64）と食い違います。root 検証や config エラーは fail() 経由で 64 になりますが、parse_args() 前の argparse エラーだけ 2 になり、機械利用側が usage error を一貫して判定できません。 |
| RGF-0058 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | When replacing an existing latest checkpoint, a failure after checkpoint_dir.rename(old_dir) but before tmp_dir.rename(checkpoint_dir) leaves no latest checkpoint behind. The except block only removes tmp_dir and never restores old_dir, so a transient filesystem error can violate the CLI checkpoint contract by losing the previous usable review base. |
| RGF-0059 | fixed_verified | src/review_gauntlet/review_adapter.py | cli-contract | When adapter.output.path is configured, the prompt tells the external CLI to write to the resolved custom output path, but the command template variable {output_file} still expands to the default cell_dir/verdict.json. A CLI configured with args like '--output {output_file}' will therefore write a different file than the adapter later reads, producing a false 'missing verdict output file' failure. Keep the output_file variable aligned with the resolved file-json output path before expanding command args/env/cwd. |
| RGF-0060 | fixed_verified | src/review_gauntlet/review_adapter.py | data-validation | The adapter reads the external verdict file without any size limit. A misconfigured or malicious review command can write an arbitrarily large file under the allowed cell directory, causing this process to allocate excessive memory before JSON validation runs. Validate the file size before reading it, similar to the existing raw snippet limiting behavior. |
| RGF-0061 | false_positive | src/review_gauntlet/review_adapter.py | data-validation | When an adapter process is cancelled after producing a non-zero status, `_run_command` rewrites any negative return code to 0 via `process.returncode or 0`. As a result, external SIGTERM/SIGKILL cancellation can be reported as a successful command and the adapter will proceed to parse stale or missing verdict output instead of surfacing cancellation deterministically. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 78 | RGF-0050 | untriaged | fixed_pending_verification | 修正済み: cleanup failureをfinalize失敗にしないようにした |
| 79 | RGF-0051 | untriaged | fixed_pending_verification | 修正済み: checkpoint schema_version検証を追加 |
| 80 | RGF-0052 | untriaged | fixed_pending_verification | 修正済み: review_base_commitの型検証を追加 |
| 81 | RGF-0053 | untriaged | fixed_pending_verification | 修正済み: findings --markのhyphen/underscore対応を追加 |
| 82 | RGF-0054 | untriaged | fixed_pending_verification | 修正済み: schema_version検証と回帰テストを追加 |
| 83 | RGF-0050 | fixed_pending_verification | fixed_verified | review_verification |
| 84 | RGF-0052 | fixed_pending_verification | fixed_verified | review_verification |
| 85 | RGF-0054 | fixed_pending_verification | fixed_verified | review_verification |
| 86 | RGF-0053 | fixed_pending_verification | fixed_verified | review_verification |
| 87 | RGF-0051 | fixed_pending_verification | fixed_verified | review_verification |
| 88 | RGF-0055 | untriaged | fixed_pending_verification | 修正済み: checkpoint_idの型検証を追加 |
| 89 | RGF-0055 | fixed_pending_verification | fixed_verified | review_verification |
| 90 | RGF-0056 | untriaged | fixed_pending_verification | 修正済み: findings/eventsのpayload list検証を追加 |
| 91 | RGF-0056 | fixed_pending_verification | fixed_verified | review_verification |
| 92 | RGF-0057 | untriaged | fixed_pending_verification | 修正済み: argparse usage errorのexit codeを64に統一 |
| 93 | RGF-0057 | fixed_pending_verification | fixed_verified | review_verification |
| 94 | RGF-0058 | untriaged | fixed_pending_verification | 修正済み: latest置換失敗時に旧checkpointを復元 |
| 95 | RGF-0059 | untriaged | fixed_pending_verification | 修正済み: {output_file}を解決済みfile-json output pathに合わせた |
| 96 | RGF-0059 | fixed_pending_verification | fixed_verified | review_verification |
| 97 | RGF-0058 | fixed_pending_verification | fixed_verified | review_verification |
| 98 | RGF-0060 | untriaged | fixed_pending_verification | 修正済み: file-json verdict outputのサイズ上限を追加 |
| 99 | RGF-0060 | fixed_pending_verification | fixed_verified | review_verification |
| 100 | RGF-0061 | untriaged | false_positive | 誤検知: 負のreturncodeはtruthyなので0にはならず、直前のcancelled分岐でfailする |

## Blockers

None
