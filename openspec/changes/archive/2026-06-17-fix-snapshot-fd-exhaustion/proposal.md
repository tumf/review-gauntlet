---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - openspec/specs/run-controller/spec.md
  - openspec/specs/review-sessions/spec.md
---

# Fix: snapshot FD exhaustion during TUI run

**Change Type**: implementation

## Problem

TUI の `review-gauntlet run` 実行中、0.25 秒間隔の `refresh_view` が毎回 `snapshot()` を呼ぶ。各 snapshot で `_status()` → `_ready_prompt()` が実行され、~16 回の `sqlite3.connect`、~12 回の git subprocess、全レビュー対象ファイルの digest 計算が走る。16 分間で約 3,935 回の snapshot 呼び出しが発生する。

根本的な問題は `SessionStore.connect()` にある:

```python
def connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.ledger_path)
    conn.row_factory = sqlite3.Row
    return conn
```

コード全体で `with store.connect() as conn:` と使われているが、`sqlite3.Connection.__exit__` は commit/rollback のみで close しない。接続は `__del__` で解放されるが、Row オブジェクト等との参照循環により世代別 GC が走るまで解放されず、FD が蓄積する。

実測: 3,000 回の snapshot 模擬操作で FD は 757 まで蓄積し、`gc.collect()` 後に 5 に戻る。

さらに `RunController.snapshot()` の例外捕捉は `except OSError` のみ。FD 枯渇時に発生する `sqlite3.OperationalError`（`sqlite3.Error` サブクラス）は捕捉されず worker スレッドをクラッシュさせる。

また `_status()` と `_ready_prompt()` は `file_digests(root)`、`target_digest(root)`、`_effective_current_target_coverage()` を**二重計算**している。

## Proposed Solution

1. `SessionStore.connect()` を `@contextmanager` でラップし `finally: conn.close()` によってコンテキスト終了時に接続を確実に閉じる
2. `RunController.snapshot()` の例外捕捉を `except OSError` から `except Exception` に広げ、`sqlite3.Error` や他のデータベースエラーもブロッカー化する
3. snapshot 内の重複計算（`file_digests`、`target_digest`、`_effective_current_target_coverage`）を排除

## Acceptance Criteria

- TUI が 30 分以上稼働しても FD 枯渇でクラッシュしない
- `sqlite3.OperationalError` 発生時も worker スレッドはクラッシュせず、TUI にブロッカーとして表示される
- 既存の全テスト (`make test`) がパスする
- `make check` が format-check、lint、typecheck、test すべてパスする

## Explicit Completion Conditions

- `SessionStore.connect()` が context manager を返し、コンテキスト終了時に FD が解放される
- `RunController.snapshot()` が `sqlite3.OperationalError` を含む任意の例外を捕捉しブロッカー化する
- `_ready_prompt()` 内で `_effective_current_target_coverage()` が 1 回のみ呼ばれる
- `file_digests(root)` / `target_digest(root)` の呼び出しが snapshot あたり合計 1 回に削減される
- `tests/test_run_controller.py` に `sqlite3.OperationalError` 捕捉のテストが追加される
- `tests/test_session_store.py` に connect が close を保証するテストが追加される
- 実コードパターンでの FD 蓄積テスト (`tests/test_run_tui.py` 相当) で snapshot 1,000 回後の FD 数が制御可能な範囲に収まる

## Out of Scope

- TUI 以外のコードパス（CLI JSON モード）のパフォーマンス最適化
- `git` subprocess の並列化やキャッシュ
- 全ファイル digest の増分更新（ファイル変更検知によるキャッシュ無効化）
