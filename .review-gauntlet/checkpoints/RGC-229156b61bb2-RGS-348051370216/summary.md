# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 229156b61bb2387a974ef1c5c7383f08bb145c61
- Session ID: RGS-348051370216
- Created at: 2026-06-17T02:03:30.780776Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 2 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0692 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | `RunEvent.model_dump()` copies `self.payload` into `result` first, then unconditionally overwrites `result["type"]` and `result["timestamp"]`. If `payload` ever contains a key named `"type"` or `"timestamp"` (e.g. from an `_emit` call like `self._emit("foo", type="bar")`), the payload value is silently lost. Either detect the collision and raise, or namespace the envelope fields (e.g. `event_type`) to avoid shadowing. |
| RGF-0693 | waived | src/review_gauntlet/run_controller.py | test-evidence | `_current_agent_lifecycle` accesses `self._agent_output_progress` (set to `None` on another thread at lines 341/351/465) without holding a lock. Under CPython the GIL makes this safe in practice, but the pattern is fragile: a non-CPython runtime (PyPy free-threading, Python 3.13+ free-threaded mode) could read a partially-written reference. Consider reading the reference once into a local before using it, which is already done but the field could still change between the `is not None` check and `.snapshot()` call in a free-threaded build. |
| RGF-0694 | fixed_verified | src/review_gauntlet/run_controller.py | data-validation | `model_dump` flattens `self.payload` into the top-level dict, then unconditionally overwrites `result["type"]` and `result["timestamp"]`. If a caller passes `type` or `timestamp` as keyword arguments to `RunEvent.create()`, those values are silently lost. This is a data-corruption bug: the payload key is accepted without error but never appears in the serialized output. |
| RGF-0695 | waived | src/review_gauntlet/run_controller.py | data-validation | `RunExecutionContext.from_active_session` calls `store.session_metadata(session_id)` solely for its side effect (raising `LookupError` if the session is missing), but discards the return value. This makes the intent unclear and wastes any work the method does to build the metadata object. Assign to `_` or add a brief comment to signal that the call is intentional validation. |
| RGF-0696 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | Race condition: `now` is captured before the lock, so a concurrent `push()` can set `_last_output_at` to a timestamp *after* `now`, producing a negative age. Move the `datetime.now(UTC)` call inside the lock (or after it) so the age is always non-negative. |
| RGF-0697 | waived | src/review_gauntlet/run_controller.py | data-validation | The return value of `store.session_metadata(session_id)` is discarded. This call appears to serve as an existence/validation check (raising `LookupError` if the session is missing), but the intent is non-obvious. If the goal is validation, consider naming it explicitly or adding a brief comment so future readers don't remove the call as dead code. |
| RGF-0698 | waived | src/review_gauntlet/run_controller.py | data-validation | `_run_step_payload` embeds the full `stdout` and `stderr` strings in every step dict. These dicts accumulate in the `steps` list across the run loop (line 371). For long-running sessions with verbose agent output, this can lead to unbounded memory growth proportional to `max_steps * output_size`. Consider truncating or streaming large outputs to artifact files (as is already done via `stdout_artifact`/`stderr_artifact`) and only keeping a bounded tail in the in-memory payload. |
| RGF-0699 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | Thread safety issue: `_current_agent_lifecycle` reads multiple mutable fields (`_agent_status`, `_agent_step_started_at`, `_agent_timeout_seconds`, `_agent_output_progress`, `_agent_lifecycle`) without synchronization, while `run()` mutates them from another thread. Since `snapshot()` is designed to be called from a TUI/refresh thread, this is a data race. For example, `_agent_step_started_at` could be set to `None` between the check on line 242 and the read on line 247, causing an `AttributeError` or computing with stale `now`. Consider adding a `threading.Lock` to protect controller state accessed across threads. |
| RGF-0700 | fixed_verified | src/review_gauntlet/run_controller.py | test-evidence | `RunExecutionContext.from_active_session` calls `store.session_metadata(session_id)` on line 138 and discards the return value. If this is a validation-only call (to raise `LookupError` on missing sessions), the intent is non-obvious and fragile — a future refactor could remove the 'side-effect' call assuming it's dead code. Add a brief comment or use `assert` / explicit existence check to clarify the intent. |
| RGF-0701 | waived | src/review_gauntlet/run_controller.py | test-evidence | Thread-safety issue: `_current_agent_lifecycle` reads multiple instance attributes (`_agent_lifecycle`, `_agent_step_started_at`, `_agent_timeout_seconds`, `_agent_output_progress`) that are written by `run()` on a different thread without holding a lock. While individual attribute reads are atomic in CPython due to the GIL, the combination of reads is not atomic — between reading `_agent_step_started_at` and `_agent_timeout_seconds`, the `run()` thread could set one to `None` and the other to a new value, producing an inconsistent snapshot. Consider protecting these fields with a `threading.Lock`. |
| RGF-0702 | waived | src/review_gauntlet/run_controller.py | test-evidence | Path traversal check is incomplete: the validation rejects `..` in path parts and non-`.review-gauntlet/checkpoints/` prefixes, but does not guard against symlink-based escapes. If an attacker can place a symlink inside the checkpoints directory before `commit_latest_checkpoint` acts on these paths, the resolved path could point outside the repository. Consider resolving symlinks (e.g., `Path.resolve()`) and re-checking that the resolved path is still under the repository root before acting on these paths downstream. |
| RGF-0703 | false_positive | src/review_gauntlet/run_controller.py | test-evidence | `_RESERVED_KEYS` is defined as a class attribute inside a frozen dataclass, which means it also becomes a dataclass field visible to `dataclasses.asdict()` and similar introspection. This is likely unintended. Use a module-level constant or prefix with a ClassVar annotation to exclude it from the dataclass field list. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1227 | RGF-0692 | untriaged | confirmed | model_dumpでpayloadキーがtype/timestampと衝突すると無言でデータが失われる。衝突検出を追加する。 |
| 1228 | RGF-0694 | untriaged | confirmed | RGF-0692と同一問題。衝突検出で修正する。 |
| 1229 | RGF-0695 | untriaged | waived | 意図的なバリデーション呼び出し。コメント追加はスタイル的な提案のみで低リスク。 |
| 1230 | RGF-0693 | untriaged | waived | 既にローカル変数パターンで正しく実装済み。free-threaded Pythonは現時点でターゲット外。 |
| 1231 | RGF-0692 | confirmed | fixed_pending_verification | model_dumpに予約キー衝突検出を追加。既存テストも更新済み。 |
| 1232 | RGF-0694 | confirmed | fixed_pending_verification | RGF-0692と同一修正。予約キー衝突検出で対応済み。 |
| 1233 | RGF-0692 | fixed_pending_verification | fixed_verified | review_verification |
| 1234 | RGF-0694 | fixed_pending_verification | fixed_verified | review_verification |
| 1235 | RGF-0696 | untriaged | confirmed | datetime.now(UTC)がロック取得前に呼ばれており、concurrent pushで負のageが出る可能性がある。ロック後に移動する。 |
| 1236 | RGF-0697 | untriaged | waived | RGF-0695と同一指摘。意図的なバリデーション呼び出しでスタイル的提案のみ。 |
| 1237 | RGF-0698 | untriaged | waived | stdout/stderrのメモリ使用は設計判断。artifactシステムが既に存在し、max_stepsで制限されている。今回のスコープ外。 |
| 1238 | RGF-0696 | confirmed | fixed_pending_verification | datetime.now(UTC)をロック解放後に移動。concurrent pushで負のageが出る問題を解消。 |
| 1239 | RGF-0696 | fixed_pending_verification | fixed_verified | review_verification |
| 1240 | RGF-0700 | untriaged | fixed_pending_verification | Fix already applied: line 152 has the clarifying comment '# raises LookupError if session missing'. The finding's existing_code metadata shows the old version without the comment. |
| 1241 | RGF-0699 | untriaged | fixed_pending_verification | Fix already applied: lines 248-251 snapshot mutable fields into locals (lifecycle, step_started_at, timeout_seconds, output_progress) to avoid TOCTOU races. The finding's existing_code metadata shows the old version without these snapshots. A full threading.Lock is overkill for this display-only TUI path under CPython GIL. |
| 1242 | RGF-0699 | fixed_pending_verification | fixed_verified | review_verification |
| 1243 | RGF-0700 | fixed_pending_verification | fixed_verified | review_verification |
| 1244 | RGF-0701 | untriaged | waived | Display-only TUI refresh path. CPython GIL makes individual attribute reads atomic; local-variable snapshotting (already applied) prevents TOCTOU within the method body. Worst case is one slightly stale refresh cycle with no correctness impact. A full threading.Lock is disproportionate for this use case. |
| 1245 | RGF-0702 | untriaged | waived | Theoretical symlink escape requires write access to .review-gauntlet/checkpoints/ inside the repo, meaning the attacker already has full repo access. String-level validation (no absolute paths, no .., prefix check, .json suffix) is sufficient for the threat model. No practical attack surface. |
| 1246 | RGF-0703 | untriaged | false_positive | Unannotated class-level assignments are not dataclass fields in Python. _RESERVED_KEYS = frozenset(...) without a type annotation is correctly excluded from the field list by the dataclass machinery. The finding's own analysis confirms this. |

## Blockers

None
