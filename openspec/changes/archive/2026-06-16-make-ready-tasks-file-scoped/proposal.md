---
change_type: implementation
priority: medium
dependencies: []
references:
  - "src/review_gauntlet/cli.py:_ready_prompt"
  - "src/review_gauntlet/cli.py:_READY_PROMPTS"
  - "src/review_gauntlet/run_controller.py:ReadyPrompt"
---

**Change Type**: implementation

# Make ready/run task prompts file-scoped with explicit triage-fix-mark workflow

## Problem / Context

`review-gauntlet ready` と `review-gauntlet run` は、共通の `_ready_prompt()` を使い、`_READY_PROMPTS` の固定文言を返しています。例:

- `"pending_review_cell": "Review pending review cells; stop when no pending review cells remain."`
- `"untriaged": "Triage untriaged findings; stop when no untriaged findings remain."`
- `"confirmed": "Fix the next confirmed finding; stop when confirmed findings are resolved or require re-triage."`

これらは「全 pending / 全 untriaged / 全 confirmed」を対象にする広めの指示です。外部エージェント（opencode など）が受け取った場合、1回の起動で複数ファイルにまたがる可能性が高く、タスクの粒度が不明瞭です。

ユーザー要望は、**1回の agent 起動に対して対象 file を1つだけ指定し、その file について `triage → fix if needed → mark` の流れを指示する**ことです。

## Proposed Solution

- `_ready_prompt()` を固定文言から、session state を読んで **file-scoped task** を生成する形に変更する。
- prompt は「次に処理すべき1つの file」を選び、その file について以下の流れを明示する。
  1. triage（finding があれば）
  2. fix if needed（必要なら修正）
  3. mark（triage/fix の結果を mark する）
- prompt は対象 file、現在の状態（pending/stale cells、untriaged/confirmed/fixed-pending findings）、および完了条件を具体的に記述する。
- `run` は `ready` と同じ prompt を外部エージェントに渡すため、両コマンドで整合する。

## Acceptance Criteria

- `review-gauntlet ready` が返す prompt は、1つの target `file_path` を明示する。
- prompt はその file について `triage → fix if needed → mark` のワークフローを指示する。
- prompt は「この file に絞る」「他 file は対象外」と明示する。
- `review-gauntlet run` は `ready` と同じ file-scoped prompt を外部エージェントに渡す。
- pending/stale/untriaged/confirmed/fixed-pending のいずれの場合でも、prompt は file-scoped になる。
- 複数 file に actionable items があっても、prompt は1つの target file を選ぶ。

## Explicit Completion Conditions

- `src/review_gauntlet/cli.py` の `_ready_prompt()` が file-scoped prompt を返す。
- `_READY_PROMPTS` が固定文言 dict から、session state を読んで file-scoped prompt を生成する関数群に置き換わっている。
- `tests/` に「ready が file-scoped prompt を返す」「prompt に triage/fix/mark が含まれる」「run が同じ prompt を使う」テストが追加されている。
- `review-gauntlet ready --format json` および `review-gauntlet run` の実行結果で、prompt に具体的な `file_path` とワークフロー指示が含まれることを確認できる。

## Out of Scope

- ready prompt の TUI 表示フォーマットの大幅変更（内容が変わっても表示層は既存のまま）。
- 外部エージェント側の実装変更（prompt を渡す側のみ）。
- 複数 file を1回の agent 起動でまとめて処理するモードの追加。
