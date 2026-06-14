# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 9bb8c7f1074b4e27418a24954bd1e2f15c1f7556
- Session ID: RGS-cc9977d99640
- Created at: 2026-06-14T14:47:43.489753Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 6 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0098 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | When an existing checkpoint directory is replaced and a later step fails before the backup is restored, rollback deletes the partially-written checkpoint_dir and renames backup_dir back, but the successfully-written pointer_tmp is not removed if pointer_tmp.replace(pointer_path) already ran. A subsequent call can then fail at pointer_tmp.write_text because the stale pointer_tmp file remains. Remove pointer_tmp unconditionally before re-raising, not only under suppress after the backup/pointer restore logic. |
| RGF-0099 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | If the latest checkpoint pointer exists as a regular file and contains an unsafe checkpoint id (for example '../outside'), latest_checkpoint_dir falls through to returning the pointer file itself. load_latest_checkpoint then looks for latest/status.json under a file path and silently returns None, so an unsafe or corrupted pointer is ignored instead of being rejected. That can make init fall back to reviewing all files rather than failing closed on a tampered latest checkpoint. Return a guaranteed invalid directory path for any existing-but-unusable pointer content, matching the symlink case. |
| RGF-0100 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | The latest checkpoint validator only checks that referenced JSON files contain objects and matching checkpoint_id values, but it never verifies their schema_version fields. A stale or hand-edited findings.json/events.json with an incompatible schema can still be accepted as a review base, defeating the version gate applied to status.json. |
| RGF-0101 | false_positive | src/review_gauntlet/checkpoint.py | data-validation | `load_latest_checkpoint` follows the `latest` pointer and reads `status.json`, but it does not validate the checkpoint object before returning it. Callers that use this function directly can therefore consume a tampered checkpoint with an unsupported schema, incomplete state, unsafe base ref, or inconsistent companion files; only `target_from_latest_checkpoint` performs validation. Validate before returning so the data-validation guarantees are centralized at the load boundary. |
| RGF-0102 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | Existing latest checkpoint files are only checked with exists(), so a dangling symlink or directory named status.json/findings.json/events.json/summary.md can be accepted as present. For JSON files, read_text() then raises a raw OSError/IsADirectoryError instead of the intended checkpoint consistency error; for summary.md, a non-file path can pass validation entirely. Validate that each required checkpoint artifact is a regular non-symlink file before reading or accepting it. |
| RGF-0103 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | summary.md validation has the same issue: exists() treats directories and symlinks as acceptable, so a checkpoint can be considered internally consistent even when its summary artifact is not a regular file. Use is_file() and reject symlinks to match the hardened latest/checkpoint directory handling above. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 202 | RGF-0098 | untriaged | fixed_pending_verification | pointer_tmp.unlink() -> missing_ok=True added to handle case where pointer_tmp already replaced pointer_path before rollback |
| 203 | RGF-0099 | untriaged | fixed_pending_verification | latest_checkpoint_dir now returns invalid latest checkpoint path on pointer read failure instead of falling through to pointer path |
| 204 | RGF-0098 | fixed_pending_verification | fixed_verified | review_verification |
| 205 | RGF-0099 | fixed_pending_verification | fixed_verified | review_verification |
| 206 | RGF-0100 | untriaged | confirmed | Companion checkpoint files findings.json and events.json are loaded as checkpoint artifacts but only checkpoint_id and payload shape are validated; unlike status.json their schema_version is not checked, so mixed-version or hand-edited artifacts can be accepted as a review base. |
| 207 | RGF-0100 | confirmed | fixed_pending_verification | Validated companion checkpoint files now require matching schema_version and generated checkpoint findings/events include schema_version. |
| 208 | RGF-0100 | fixed_pending_verification | fixed_verified | review_verification |
| 209 | RGF-0101 | untriaged | false_positive | load_latest_checkpoint has no direct callers outside target_from_latest_checkpoint, and that caller validates the checkpoint before using fields; no unvalidated consumption path exists in current code. |
| 210 | RGF-0102 | untriaged | confirmed | Required checkpoint artifacts should be regular non-symlink files; exists() permits directories/symlinks and can leak raw filesystem errors. |
| 211 | RGF-0103 | untriaged | confirmed | summary.md has the same artifact type validation gap and should reject directories/symlinks. |
| 212 | RGF-0102 | confirmed | fixed_pending_verification | Validated checkpoint companion artifacts as regular non-symlink files and covered directory case in tests |
| 213 | RGF-0103 | confirmed | fixed_pending_verification | Validated checkpoint summary artifact as a regular non-symlink file and covered directory case in tests |
| 214 | RGF-0103 | fixed_pending_verification | fixed_verified | review_verification |
| 215 | RGF-0102 | fixed_pending_verification | fixed_verified | review_verification |

## Blockers

None
