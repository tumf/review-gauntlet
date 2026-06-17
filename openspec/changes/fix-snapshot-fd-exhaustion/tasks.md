## Implementation Tasks

- [ ] `SessionStore.connect()` を `@contextmanager` でラップし `finally: conn.close()` を追加する。commit/rollback は維持。`row_factory` 設定も維持。検証: `tests/test_session_store.py` に DB 接続が閉じていることを確認する unit テストを追加 (verification: unit)

- [ ] `RunController.snapshot()` の例外捕捉を `except OSError` から `except Exception` に広げ、`_status_snapshot` と `_ready_prompt` 両方で `sqlite3.OperationalError` をブロッカー化する。`_status_unavailable_snapshot` の blocker 文言を汎用化。検証: `tests/test_run_controller.py` に `sqlite3.OperationalError` を raise する注入テストを追加 (verification: unit)

- [ ] `_ready_prompt()` から重複する `_effective_current_target_coverage()` 呼び出しを除去し、`file_digests(root)` と `target_digest(root)` の計算を snapshot 1 回あたり最大 1 回に抑制する。検証: `tests/test_cli_ready.py` の既存テストがパスすること (verification: unit)

- [ ] `make test` で全テストがパスし、`make check` が format-check、lint、typecheck、test すべてパスする (verification: integration)

- [ ] 1,000 回相当の snapshot 操作後 FD カウントが許容範囲に収まることを smoke 検証するテストを追加。macOS では FD 制限内、Linux CI ではスキップまたは looser 基準 (verification: integration)

## Future Work

- TUI refresh レートの動的制御（idle 時は 1s 間隔に落とす等）— 別 proposal として検討
- 全ファイル digest の増分更新とキャッシュ — パフォーマンス課題として追跡

## Final Validation

Archive バリデーションが正式な OpenSpec 最終バリデーションゲートです。
期待される archive gate: `cflx openspec validate fix-snapshot-fd-exhaustion --archive-gate`
