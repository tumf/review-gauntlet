---
change_type: implementation
priority: high
dependencies: []
references:
  - src/review_gauntlet/review_cells.py
  - src/review_gauntlet/findings.py
  - src/review_gauntlet/run_controller.py
  - src/review_gauntlet/cli.py
  - src/review_gauntlet/session_store.py
  - src/review_gauntlet/continuation.py
  - openspec/CONSTITUTION.md
---

**Change Type**: implementation

# 2フェーズ並列レビュープロセスへの簡素化

## Problem/Context

現在のレビュープロセスは、セルレビュー・判定・修正・検証が逐次的かつ入り組んでいる:
- PENDINGセルレビュー → Finding(UNTRIAGED) 作成
- UNTRIAGED判定 → CONFIRMED / FALSE_POSITIVE / WAIVED / ACCEPTED_RISK
- CONFIRMED修正 → FIXED_PENDING_VERIFICATION
- FIXED_PENDING_VERIFICATION検証 → FIXED_VERIFIED / REOPENED
- ファイル変更によるステイル(STALE)判定と再レビュー

この複雑さにより:
- 収束性が不透明（判定⇄修正⇄検証のループ）
- ステイル管理のオーバーヘッド
- 並列化が困難（読み取り/書き込みが混在）

## Proposed Solution

プロセスを2つの明確なフェーズに分割:

```
init → Phase 1: review (全セル並列) → Phase 2: resolve (ファイル単位並列) → finalize
```

**Phase 1: 全Finding導出** (`review` コマンド)
- 全 PENDING セルに対し、レビューアダプタを並列実行（読み取り専用）
- Finding を state=`open` で収集
- 成功セル → REVIEWED、失敗セル → PENDING のまま

**Phase 2: Finding対処** (`resolve` コマンド、新規)
- 全 open Finding をファイルパスでグループ化
- ファイル単位で対処エージェントを並列実行（ファイル競合なし）
- 対処エージェントは判定(confirmed/dismissed)と修正を1ステップで実施
- verdict.json で `finish`/`continue`/`abort` を宣言
- 全ファイルが `finish` になるまで継続実行

**データモデル簡素化:**
- CellState: `PENDING`, `REVIEWED` のみ (STALE, SUPERSEDED 削除)
- FindingState: `open`, `confirmed`, `dismissed` のみ (7状態→3状態)
- ContinuationVerdict: `error` → `abort` にリネーム、`resolutions` フィールド追加

## Acceptance Criteria

1. `review-gauntlet review` が全PENDINGセルを並列レビューし、全Findingを `open` で収集する
2. `review-gauntlet resolve` が全open Findingをファイル単位で並列対処し、全findingが終端状態になる
3. `review-gauntlet run` がPhase 1→Phase 2を通し実行する
4. `verify-fixes` コマンドが削除されている
5. CellState から STALE/SUPERSEDED が削除されている
6. FindingState が open/confirmed/dismissed の3状態のみである
7. 既存の全テストが新モデルでパスする（または移行されている）

## Explicit Completion Conditions

1. `src/review_gauntlet/review_cells.py`: CellState が PENDING/REVIEWED のみ、TERMINAL_CELL_STATES が {REVIEWED}
2. `src/review_gauntlet/findings.py`: FindingState が open/confirmed/dismissed、ALLOWED_TRANSITIONS が新モデル
3. `src/review_gauntlet/cli.py`: `review` が全PENDINGセル並列実行、`resolve` コマンド追加、`verify-fixes` 削除
4. `src/review_gauntlet/session_store.py`: ステイル関連コード削除、`list_fixed_pending_findings` 削除
5. `src/review_gauntlet/continuation.py`: `error`→`abort`、`FindingResolution` 追加、スキーマ v2
6. `src/review_gauntlet/run_controller.py`: 2フェーズモデル対応
7. `tests/`: 全既存テストが新モデルでパス
8. `make check` が成功

## Out of Scope

- Phase 1/Phase 2 の subprocess 並列実行の実装詳細（`concurrent.futures` vs `asyncio`）は実装時に決定
- TUI のフェーズ表示 UI/UX 詳細
- リモート分散実行
