# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: fbad54fd7f86f3e7b6b4a5c7b15e7476e27ed912
- Session ID: RGS-7d2f570ffd4d
- Created at: 2026-06-15T12:25:50.251655Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 6 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0132 | fixed_verified | src/review_gauntlet/run_controller.py | data-validation | The checkpoint file list is accepted directly from the agent's stdout before it is passed to commit_latest_checkpoint. Although commit_latest_checkpoint filters paths, this parser does not validate that the values are relative checkpoint artifact paths or remove duplicates before forwarding them. That makes the trust boundary harder to reason about and can let malformed agent output influence the commit allowlist path calculation. Validate the schema at the boundary and only return normalized, allowed checkpoint artifact paths. |
| RGF-0133 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | The fallback text renderer ignores the events passed to compact_dashboard_text when rendering the header/progress line. dashboard_state(snapshot, events) is computed with events, but progress_text(snapshot) immediately recomputes dashboard_state with an empty event tuple, so the header can diverge from the rest of the compact dashboard if event-derived state is added or expected. Use the already computed view for the header instead of discarding the caller-provided events. |
| RGF-0134 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | The latest pointer validation rejects symlinks, but it still trusts any existing directory named latest as a checkpoint because latest_checkpoint_dir() falls back to returning the directory path. A stale or user-created .review-gauntlet/checkpoints/latest directory with forged status/findings/events can therefore be accepted as the review base, bypassing the intended single-segment checkpoint-id pointer validation. |
| RGF-0135 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | SessionCommandResult carries artifact paths and output_tail, but the persisted run step payload drops them. That means long/truncated command output or live activity evidence captured by the adapter is not present in run results, making failures harder to audit and contradicting the test-evidence goal for agent runs. |
| RGF-0136 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | When committing a checkpoint fails after `git add`, the staged checkpoint files are left in the index. The error result reports `git_failure`, but subsequent commands see a dirty/staged working tree, which can block retry or accidentally include checkpoint artifacts in a later user commit. Capture the pre-existing staged state or unstage the checkpoint paths in the exception path before returning. |
| RGF-0137 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | `snapshot.elapsed_seconds` originates from status/controller data and is typed as a float, but this formatter accepts arbitrary floats without rejecting non-finite values. If a malformed or mocked snapshot supplies `NaN` or `Infinity`, `int(seconds)` raises and can crash the TUI/text fallback instead of degrading safely. |
| RGF-0138 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | This helper also assumes finite numeric input. A non-finite timeout or output-age value from lifecycle/status data will raise during rendering, taking down the dashboard instead of showing a safe fallback. |
| RGF-0139 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | `checkpoint_generated_files_from_stdout` only accepts a top-level `generated_files` field, but stdout-json adapters commonly wrap agent verdict data under `verdict`. In that case checkpoint files reported as `verdict.generated_files` are silently ignored, so finalized runs can skip committing generated checkpoint artifacts despite the adapter returning valid JSON. Consider checking the nested verdict object as a fallback before rejecting the payload. |
| RGF-0140 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | The output redaction only matches KEY/TOKEN/SECRET environment assignments. It leaves common credential forms such as `Authorization: Bearer ...`, `x-api-key: ...`, JSON fields like `"api_key": "..."`, and `password=...` visible in the TUI activity feed, even though agent stdout/stderr may include provider credentials. This can expose secrets in terminal logs or recordings. Redact common header, JSON, and key/value credential patterns before displaying output. |
| RGF-0141 | fixed_verified | src/review_gauntlet/run_tui.py | data-validation | The fallback command label renders the raw argv into the TUI. If an adapter command includes inline credentials or secret flags, they will be displayed in the header and agent panel, even though agent output is redacted elsewhere in this file. |
| RGF-0142 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | If a stop/interrupt request arrives while the adapter command is running, the flag is never checked again after `_command_runner` returns. A command that ignores cancellation can therefore finalize the session or continue to the next step even though `interrupt()` was requested. Add a post-command interruption check before processing success/finalization, and cover it with a controller test that triggers `interrupt()` from inside the fake runner. |
| RGF-0143 | fixed_verified | src/review_gauntlet/run_controller.py | data-validation | `generated_files` の各要素がディレクトリや不正な拡張子でも `.review-gauntlet/checkpoints/` 配下というだけで受理され、最終 checkpoint commit の対象として渡されます。エージェント出力は外部入力なので、期待する verdict JSON ファイルなど通常ファイルだけに絞らないと、後続処理がディレクトリや任意種類のファイルを checkpoint 生成物として扱う可能性があります。 |
| RGF-0144 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | The git failure recovery only unstages checkpoint_dirty. If other paths were already staged before calling commit_latest_checkpoint, they remain staged after this function returns a git_failure result, leaving the caller's index mutated relative to its pre-call state. Capture and restore the full staged path set, or block/restore pre-existing staged changes before attempting the checkpoint commit. |
| RGF-0145 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | This blocks checkpoint commits whenever an unrelated generated checkpoint file is staged, but the rest of the function intentionally refuses to proceed with any unrelated dirty paths. If an operator has staged the latest pointer or another generated checkpoint artifact before finalization, this early return leaves the just-generated checkpoint uncommitted even though committing only checkpoint artifacts would be safe. Treat any preexisting staged allowed checkpoint paths as part of the checkpoint commit instead of blocking solely because they were already staged. |
| RGF-0146 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | A checkpoint path that already has staged changes can also have newer unstaged changes. Because paths already present in staged_before are excluded from paths_to_stage, those unstaged changes are never added; the subsequent commit can succeed with the stale staged version and leave the latest checkpoint files dirty while returning committed=True. |
| RGF-0147 | false_positive | src/review_gauntlet/checkpoint.py | test-evidence | When `git commit` fails, the rollback only unstages paths this function staged (`paths_to_stage`). If the caller already had checkpoint files staged, they remain staged after a failed commit, which leaves the working tree in a mutated state even though the checkpoint commit did not happen. The existing tests explicitly assert this behavior, so the failure path lacks test evidence for preserving the user's preexisting index state. Capture and restore the full pre-call staged set (or otherwise document/verify the intended mutation) so failed checkpoint commits do not leave staged artifacts behind. |
| RGF-0148 | fixed_verified | src/review_gauntlet/checkpoint.py | test-evidence | commit_latest_checkpoint stages any dirty allowed checkpoint path, not just files passed in generated_files. If a stale or manually edited checkpoint artifact already exists under .review-gauntlet/checkpoints, it can be committed together with the current checkpoint, because allowed_paths is expanded from latest_checkpoint_dir(root) and paths_to_stage includes every dirty allowed path. This weakens the test-evidence boundary: finalize may persist unrelated checkpoint evidence from a previous run. |
| RGF-0149 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | session_id is only checked for path separators and dot segments before being embedded into checkpoint_id and later committed in a git message. Characters such as newlines or control bytes can corrupt checkpoint artifact names/commit messages and make the checkpoint metadata ambiguous. Validate session_id against the actual run/session id format before using it in checkpoint_id. |
| RGF-0150 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | _validate_latest_checkpoint accepts findings.json and events.json payload entries as long as their checkpoint_id matches, but it does not verify that each entry belongs to this repository checkpoint or has the expected shape. A manually modified or partially corrupted checkpoint can therefore become the review base while carrying findings/events for unrelated paths or malformed records, which undermines the checkpoint integrity checks this function is meant to enforce. |
| RGF-0151 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | Checkpoint validation only checks that required finding/event fields are present, but it does not validate their types or allowed values. A malformed checkpoint can pass with non-string paths/rule IDs/content or an invalid finding state, then be accepted as a review base and later consumers may misclassify or fail on corrupted checkpoint data. |
| RGF-0152 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | When rolling back after a checkpoint write failure, this only restores the previous latest pointer if `pointer_path` does not exist. If `pointer_tmp.replace(pointer_path)` succeeds and a later operation in the try block raises, `pointer_path` already points at the new checkpoint, so the backup is deleted and `latest` remains advanced even though the operation failed. Restore the backup whenever it exists, replacing the current pointer if necessary. |
| RGF-0153 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | A checkpoint file with an empty schema_version is currently accepted because None is treated the same as an absent optional schema field. That means findings.json or events.json can omit the schema_version entirely and still become a trusted latest checkpoint, weakening the checkpoint format validation and allowing mixed/legacy data shapes to pass. Require schema_version to be present and equal to CHECKPOINT_SCHEMA_VERSION for every checkpoint sidecar file. |
| RGF-0154 | false_positive | src/review_gauntlet/checkpoint.py | data-validation | `commit_latest_checkpoint` stages every dirty path that is not already staged before checking whether it is an allowed checkpoint artifact. When untracked or unstaged non-checkpoint files exist, `blocked_paths` correctly blocks the commit, but the function may already have staged those unrelated files and then returns without restoring them. This mutates the caller's index even though the commit was rejected. |
| RGF-0155 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | Checkpoint artifact paths allow any single path segment as the checkpoint directory name. If a caller passes a generated file under `.review-gauntlet/checkpoints/latest/...`, or a hidden/temp directory such as `.review-gauntlet/checkpoints/.tmp/status.json`, it is treated as safe for checkpoint commits. Tighten the checkpoint id validation here to match the path-safe, non-latest RGC checkpoint ids that `write_latest_checkpoint` creates before staging files. |
| RGF-0156 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | `events.json` checkpoint validation only requires `event_id` to be an int and a few string fields, but it never validates that `from_state`/`to_state` are valid FindingState values. A corrupted or edited checkpoint can therefore be accepted as a review base with impossible transition states, which defeats the integrity checks this loader is trying to enforce. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 276 | RGF-0134 | untriaged | confirmed | Real data validation issue: latest checkpoint dir accepts a directory as valid pointer, bypassing symlink validation |
| 277 | RGF-0132 | untriaged | confirmed | Real trust-boundary issue: generated_files from adapter stdout should be normalized and filtered before commit allowlist use |
| 278 | RGF-0133 | untriaged | confirmed | Real data flow bug: compact_dashboard_text ignores caller-provided events by recomputing dashboard_state in progress_text() |
| 279 | RGF-0136 | untriaged | confirmed | commit_latest_checkpoint stages checkpoint paths before commit, and the CalledProcessError path returns without unstaging those paths, so failed commits can leave checkpoint artifacts staged. |
| 280 | RGF-0135 | untriaged | confirmed | _run_step_payload persists stdout and stderr but omits SessionCommandResult artifact paths and output_tail, so captured adapter evidence is dropped from run step payloads. |
| 281 | RGF-0134 | confirmed | fixed_pending_verification | latest checkpoint pointer now rejects symlink, directory, unreadable file, invalid file content, and missing pointer paths instead of accepting a latest directory fallback |
| 282 | RGF-0136 | confirmed | fixed_pending_verification | commit_latest_checkpoint now unstages checkpoint paths if git add/diff/commit path raises CalledProcessError |
| 283 | RGF-0132 | confirmed | fixed_pending_verification | checkpoint_generated_files_from_stdout now normalizes, deduplicates, and only accepts relative .review-gauntlet/checkpoints artifact paths |
| 284 | RGF-0135 | confirmed | fixed_pending_verification | run step payload now persists stdout/stderr/activity artifacts and structured output_tail evidence |
| 285 | RGF-0133 | confirmed | fixed_pending_verification | compact dashboard fallback now renders the header from the event-aware dashboard view instead of recomputing without events |
| 286 | RGF-0134 | fixed_pending_verification | fixed_verified | review_verification |
| 287 | RGF-0133 | fixed_pending_verification | fixed_verified | review_verification |
| 288 | RGF-0136 | fixed_pending_verification | fixed_verified | review_verification |
| 289 | RGF-0135 | fixed_pending_verification | fixed_verified | review_verification |
| 290 | RGF-0132 | fixed_pending_verification | fixed_verified | review_verification |
| 291 | RGF-0139 | untriaged | confirmed | Valid: stdout-json adapter payloads may nest verdict data, so generated checkpoint files under verdict.generated_files are currently ignored. |
| 292 | RGF-0137 | untriaged | confirmed | Valid: format_elapsed_time converts arbitrary float input with int() and non-finite values can raise during rendering. |
| 293 | RGF-0138 | untriaged | confirmed | Valid: format_duration converts arbitrary float input with int() and non-finite values can raise during lifecycle rendering. |
| 294 | RGF-0140 | untriaged | confirmed | Valid: agent output sanitization only redacts narrow environment assignment forms and misses common credential header, JSON, and key/value formats. |
| 295 | RGF-0139 | confirmed | fixed_pending_verification | Handled nested verdict.generated_files fallback and added regression test |
| 296 | RGF-0137 | confirmed | fixed_pending_verification | Guarded elapsed time formatting against non-finite values and added regression test |
| 297 | RGF-0138 | confirmed | fixed_pending_verification | Guarded duration formatting against non-finite values and added regression test |
| 298 | RGF-0140 | confirmed | fixed_pending_verification | Expanded agent output redaction patterns for common credential forms and added regression tests |
| 299 | RGF-0138 | fixed_pending_verification | fixed_verified | review_verification |
| 300 | RGF-0137 | fixed_pending_verification | fixed_verified | review_verification |
| 301 | RGF-0139 | fixed_pending_verification | fixed_verified | review_verification |
| 302 | RGF-0140 | fixed_pending_verification | fixed_verified | review_verification |
| 303 | RGF-0141 | untriaged | confirmed | Raw adapter argv can contain inline credentials and is rendered in the TUI without redaction; needs a code fix. |
| 304 | RGF-0141 | confirmed | fixed_pending_verification | Sanitize fallback command argv label before rendering in TUI. |
| 305 | RGF-0141 | fixed_pending_verification | fixed_verified | review_verification |
| 306 | RGF-0142 | untriaged | fixed_pending_verification | Added post-command interrupt check and regression test. |
| 307 | RGF-0143 | untriaged | fixed_pending_verification | Constrained generated checkpoint files to JSON checkpoint paths and added regression test. |
| 308 | RGF-0144 | untriaged | fixed_pending_verification | Blocked pre-existing staged checkpoint paths to avoid mutating caller index and added regression test. |
| 309 | RGF-0144 | fixed_pending_verification | fixed_verified | review_verification |
| 310 | RGF-0142 | fixed_pending_verification | fixed_verified | review_verification |
| 311 | RGF-0143 | fixed_pending_verification | fixed_verified | review_verification |
| 312 | RGF-0145 | untriaged | fixed_pending_verification | Preserved pre-existing staged checkpoint artifacts while only unstaging paths staged by checkpoint commit on failure. |
| 313 | RGF-0145 | fixed_pending_verification | fixed_verified | review_verification |
| 314 | RGF-0146 | untriaged | fixed_pending_verification | Added guard for checkpoint paths with both staged and unstaged changes to avoid committing stale staged checkpoint content. |
| 315 | RGF-0146 | fixed_pending_verification | fixed_verified | review_verification |
| 316 | RGF-0147 | untriaged | false_positive | Pre-existing staged checkpoint paths remaining staged after commit failure preserves the caller's pre-call index state; regression test covers this behavior. |
| 317 | RGF-0148 | untriaged | fixed_pending_verification | Restricted checkpoint commit allowlist to generated checkpoint artifacts plus latest pointer and added stale artifact regression test. |
| 318 | RGF-0148 | fixed_pending_verification | fixed_verified | review_verification |
| 319 | RGF-0149 | untriaged | fixed_pending_verification | Validated checkpoint session_id as ASCII alnum/hyphen/underscore single path segment and added newline rejection coverage. |
| 320 | RGF-0149 | fixed_pending_verification | fixed_verified | review_verification |
| 321 | RGF-0150 | untriaged | fixed_pending_verification | Added required-field validation for findings/events checkpoint payload entries and regression coverage for malformed payload rejection. |
| 322 | RGF-0150 | fixed_pending_verification | fixed_verified | review_verification |
| 323 | RGF-0151 | untriaged | fixed_pending_verification | Added type and FindingState validation for checkpoint findings/events payload entries with regression coverage. |
| 324 | RGF-0151 | fixed_pending_verification | fixed_verified | review_verification |
| 325 | RGF-0152 | untriaged | fixed_pending_verification | Rollback now restores backed-up latest pointer even after replacement succeeds; added regression for post-replace cleanup failure. |
| 326 | RGF-0152 | fixed_pending_verification | fixed_verified | review_verification |
| 327 | RGF-0153 | untriaged | fixed_pending_verification | Required sidecar schema_version to match checkpoint schema and updated legacy companion test to reject missing schema. |
| 328 | RGF-0153 | fixed_pending_verification | fixed_verified | review_verification |
| 329 | RGF-0154 | untriaged | false_positive | paths_to_stage is only computed before blocked_paths; git add runs after blocked_paths returns, so unrelated dirty files are not staged on rejection. |
| 330 | RGF-0155 | untriaged | confirmed | checkpoint artifact allowlist accepts arbitrary non-latest checkpoint directory names; code only rejects latest and does not enforce generated RGC-* checkpoint ids |
| 331 | RGF-0155 | confirmed | fixed_pending_verification | Tightened checkpoint artifact allowlist to require path-safe RGC checkpoint IDs and added regression coverage. |
| 332 | RGF-0155 | fixed_pending_verification | fixed_verified | review_verification |
| 333 | RGF-0156 | untriaged | fixed_pending_verification | Added validation that from_state and to_state values in events.json must be valid FindingState enum values, matching the existing findings.json state validation. |
| 334 | RGF-0156 | fixed_pending_verification | fixed_verified | review_verification |

## Blockers

None
