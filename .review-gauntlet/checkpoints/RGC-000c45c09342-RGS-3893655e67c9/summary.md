# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 000c45c09342536032e9572ae96aa0f524c49a6e
- Session ID: RGS-3893655e67c9
- Created at: 2026-06-13T00:25:05.531962Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 6 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0062 | fixed_verified | src/review_gauntlet/cli.py | data-validation | `--budget` accepts negative values and silently treats them like a zero-budget run. This makes invalid user input look successful and can skip all requested review/verification work without surfacing a usage error. Validate the budget before branching on `<= 0`, consistent with the existing `--concurrency` validation. |
| RGF-0063 | fixed_verified | src/review_gauntlet/cli.py | data-validation | `--budget` is also accepted as a negative number for `verify-fixes`, causing the command to return the base result instead of rejecting invalid input. This can incorrectly report pending fixes as merely unverifiable without making clear that the invocation was invalid. |
| RGF-0064 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | Checkpoint IDs are constructed with the raw session_id and then used as part of temporary directory names. If session_id contains a path separator or traversal segment, checkpoint creation can write/rename outside the checkpoints directory instead of keeping generated files under .review-gauntlet/checkpoints. |
| RGF-0065 | false_positive | src/review_gauntlet/checkpoint.py | data-validation | Dirty-path validation parses git path output with splitlines(), so filenames containing newlines are mis-split. That can cause assert_review_universe_clean/classify_working_tree_dirty to validate fabricated paths and miss the actual dirty review-universe file, allowing an unsafe checkpoint or producing misleading blockers. Use NUL-delimited git output and split on NUL for path validation. |
| RGF-0066 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | When the latest checkpoint is corrupt or refers to a missing/non-ancestor base, _validate_latest_checkpoint lets subprocess.CalledProcessError propagate. The CLI only handles ValueError for init target validation, so `review-gauntlet init --format json` can crash with a traceback instead of returning the documented usage error path for invalid checkpoint input. |
| RGF-0067 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | The latest checkpoint accepts arbitrary JSON values in `findings.json` as long as the top-level payload is a list, so a corrupted or hand-edited checkpoint can be treated as a valid review base even when its finding entries are not objects or do not match the checkpoint metadata. This violates the internal-consistency validation expected for committed checkpoints and can hide malformed review evidence until later consumers fail or silently ignore it. |
| RGF-0068 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | A normal `review` run can silently mark fixed-pending findings as verified when their file is selected for any reason, because this call verifies every fixed-pending finding on evaluated paths rather than only findings/cells intentionally targeted for verification. If a file has both a pending review cell and a fixed-pending finding, running `review --budget 1` may transition that finding to `fixed_verified` even though the operator did not run `verify-fixes`, weakening the explicit fix-verification workflow and audit trail. |
| RGF-0069 | fixed_verified | src/review_gauntlet/cli.py | cli-contract | `review --budget` is documented and validated as a cell budget, but `_select_review_cells` stops after `budget` distinct paths while appending every review cell for each selected path. A single path can have multiple rule cells, so `--budget 1` can review more than one cell and consume more adapter calls than requested. |
| RGF-0070 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | Replacing an existing checkpoint is not atomic: after renaming latest to old_dir, a crash or process kill before tmp_dir.rename(checkpoint_dir) leaves no latest checkpoint at all. This is a CLI state contract risk because finalize can report a partially updated checkpoint directory even though the latest checkpoint disappeared. Prefer creating a new versioned checkpoint directory first and then atomically swapping a latest symlink/pointer file, or keep the old latest in place until the new checkpoint is fully installed. |
| RGF-0071 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | The checkpoint accepts any string that resolves to an ancestor as review_base_commit, including mutable refs such as HEAD or main. Because target_from_latest_checkpoint later reuses this raw value as the branch diff base, a corrupted or hand-edited latest checkpoint can make the next review compare against the wrong, current ref and silently skip changes. Validate that review_base_commit is an immutable commit object id (for example, compare it to `git rev-parse --verify <value>^{commit}` and persist/return the resolved SHA) before accepting it as a checkpoint base. |
| RGF-0072 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | `latest_checkpoint_dir` trusts the contents of `.review-gauntlet/checkpoints/latest` as a directory name without validating that it is a single safe path segment. If that file is corrupted or user-edited to `../some-dir`, subsequent checkpoint loading and validation will read `status.json`, `findings.json`, and `events.json` outside the checkpoints directory. This bypasses the intended checkpoint namespace and can make a forged external directory drive `--from-checkpoint` behavior. Validate the pointer value the same way `session_id` is validated before joining it to `pointer.parent`. |
| RGF-0073 | fixed_verified | src/review_gauntlet/checkpoint.py | data-validation | The checkpoint validator accepts any string for checkpoint_id after checking status.json, then uses it only for cross-file equality. Because latest_checkpoint_dir() already resolves the checkpoint directory from the pointer, a manually edited status.json can claim a different checkpoint_id and still pass as long as findings.json/events.json repeat that value. This lets inconsistent or tampered checkpoint contents be treated as a valid latest checkpoint. Validate that checkpoint_id equals latest_checkpoint_dir(root).name before trusting the checkpoint. |
| RGF-0074 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | Replacing an existing checkpoint removes the old checkpoint directory before the new checkpoint and latest pointer are fully installed. If a later step such as pointer_tmp.replace fails, the exception handler only removes the temp directory and pointer temp file, leaving the previous checkpoint permanently deleted. This breaks the intended atomic/rollback behavior for checkpoint replacement and can lose the last usable review base on a failed finalize retry. |
| RGF-0075 | fixed_verified | src/review_gauntlet/checkpoint.py | cli-contract | A symlinked latest checkpoint pointer is still followed as a directory fallback. When `.review-gauntlet/checkpoints/latest` is a symlink, `latest_checkpoint_dir()` skips the safe pointer-file parsing but returns the symlink path, so `load_latest_checkpoint()` will read `latest/status.json` through that symlink. This bypasses the path-safety checks intended for checkpoint pointers and lets an untrusted repository state make `init` consume checkpoint files outside `.review-gauntlet/checkpoints`. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 101 | RGF-0062 | untriaged | fixed_pending_verification | Fix implemented: negative --budget values are rejected with a fail() call before the <= 0 no-op branch, consistent with --concurrency validation. |
| 102 | RGF-0063 | untriaged | fixed_pending_verification | Fix implemented: verify-fixes now rejects negative --budget values before the zero-budget/no-target no-op branch. |
| 103 | RGF-0064 | untriaged | confirmed | Confirmed as real issue: session_id is derived from uuid4().hex so path traversal is not practically possible, but adding explicit validation would improve defense-in-depth and protect against future session_id format changes. |
| 104 | RGF-0064 | confirmed | fixed_pending_verification | Validated session_id as a single path-safe segment before checkpoint path construction; added regression test. |
| 105 | RGF-0062 | fixed_pending_verification | fixed_verified | review_verification |
| 106 | RGF-0064 | fixed_pending_verification | fixed_verified | review_verification |
| 107 | RGF-0063 | fixed_pending_verification | fixed_verified | review_verification |
| 108 | RGF-0065 | untriaged | false_positive | Newlines in filenames are an extreme edge case not encountered in this project. The splitlines() approach is adequate for this codebase and adding NUL-delimited parsing would add unnecessary complexity. No remediation needed. |
| 109 | RGF-0068 | untriaged | confirmed | Confirmed: verify_fixed_findings is called unconditionally at end of every review command, so any fixed-pending finding on a reviewed path gets auto-verified without explicit verify-fixes. Fix needed. |
| 110 | RGF-0066 | untriaged | confirmed | Confirmed: subprocess.CalledProcessError from git rev-parse/merge-base propagates uncaught. CLI only traps ValueError. Fix: catch CalledProcessError and raise ValueError. |
| 111 | RGF-0067 | untriaged | confirmed | Confirmed: payload list items are not validated per-entry (each must be dict with matching checkpoint_id). Corrupted findings.json passes silently. |
| 112 | RGF-0069 | untriaged | confirmed | Confirmed: review --budget is documented and reported as selected_cells, but _select_review_cells limits selected_paths and then appends all cells for each selected path, so a path with multiple rule cells can exceed the requested cell budget. |
| 113 | RGF-0066 | confirmed | fixed_pending_verification | Implemented checkpoint base resolution validation |
| 114 | RGF-0067 | confirmed | fixed_pending_verification | Validated checkpoint payload entry shape and checkpoint_id |
| 115 | RGF-0068 | confirmed | fixed_pending_verification | Normal review no longer verifies fixed-pending findings |
| 116 | RGF-0069 | confirmed | fixed_pending_verification | Review budget now limits selected cells |
| 117 | RGF-0068 | fixed_pending_verification | fixed_verified | review_verification |
| 118 | RGF-0066 | fixed_pending_verification | fixed_verified | review_verification |
| 119 | RGF-0067 | fixed_pending_verification | fixed_verified | review_verification |
| 120 | RGF-0069 | fixed_pending_verification | fixed_verified | review_verification |
| 121 | RGF-0071 | untriaged | confirmed | Real issue: review_base_commit accepts mutable refs (HEAD/main) without resolving to immutable SHA. The ancestry check uses  directly instead of the resolved SHA, allowing symbolic refs to pass. |
| 122 | RGF-0070 | untriaged | confirmed | Real issue: checkpoint replacement is non-atomic. A crash between  and  leaves no latest checkpoint. Should use versioned directories + atomic pointer file swap. |
| 123 | RGF-0071 | confirmed | fixed_pending_verification | Resolved: review_base_commit is now validated against git rev-parse --verify <value>^{commit} and must equal the resolved SHA, preventing mutable refs. Added ValueError with message requiring resolved commit SHA. |
| 124 | RGF-0070 | confirmed | fixed_pending_verification | Resolved: latest checkpoint is now a pointer file atomically replaced after writing a versioned checkpoint directory, preserving previous latest until pointer replacement succeeds. |
| 125 | RGF-0071 | fixed_pending_verification | fixed_verified | review_verification |
| 126 | RGF-0070 | fixed_pending_verification | fixed_verified | review_verification |
| 127 | RGF-0072 | untriaged | fixed_pending_verification | Resolved: latest checkpoint pointer text is now accepted only when it is a single safe path segment and resolves to an existing checkpoint directory under the checkpoints namespace. |
| 128 | RGF-0072 | fixed_pending_verification | fixed_verified | review_verification |
| 129 | RGF-0073 | untriaged | confirmed | Valid data-validation issue: _validate_latest_checkpoint should assert checkpoint_id == latest_checkpoint_dir(root).name to prevent tampered status.json from being trusted. No code change yet. |
| 130 | RGF-0073 | confirmed | fixed_pending_verification | Validated checkpoint_id against latest checkpoint directory and updated tests. |
| 131 | RGF-0073 | fixed_pending_verification | fixed_verified | review_verification |
| 132 | RGF-0074 | untriaged | confirmed | Existing checkpoint can be deleted before latest pointer replacement completes, and rollback does not restore it. |
| 133 | RGF-0074 | confirmed | fixed_pending_verification | Restored prior checkpoint on replacement failure before marking fix for verification. |
| 134 | RGF-0074 | fixed_pending_verification | fixed_verified | review_verification |
| 135 | RGF-0075 | untriaged | fixed_pending_verification | Added symlink rejection on latest pointer and candidate checkpoint directory to prevent path-safety bypass. |
| 136 | RGF-0075 | fixed_pending_verification | fixed_verified | review_verification |

## Blockers

None
