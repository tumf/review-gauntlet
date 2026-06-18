# 2フェーズ並列レビュープロセス: 設計

## Architecture Overview

```
                    ┌──────────────────────────┐
                    │     review-gauntlet      │
                    │       orchestrator       │
                    └──────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌──────────────────┐            ┌──────────────────┐
    │   Phase 1        │            │   Phase 2        │
    │   review cells   │            │   resolve        │
    │   (parallel)     │            │   findings       │
    │   read-only      │            │   (parallel)     │
    └──────────────────┘            └──────────────────┘
              │                               │
              ▼                               ▼
    ┌──────────────────┐            ┌──────────────────┐
    │   Findings       │            │   Resolved       │
    │   (state=open)   │ ────────▶  │   Findings       │
    └──────────────────┘            │   (confirmed/    │
                                    │    dismissed)    │
                                    └──────────────────┘
```

## Data Model Changes

### CellState (review_cells.py)

```python
class CellState(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"

TERMINAL_CELL_STATES = {CellState.REVIEWED}
```

削除: `STALE`, `SUPERSEDED`

### FindingState (findings.py)

```python
class FindingState(StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"

TERMINAL_FINDING_STATES = {FindingState.CONFIRMED, FindingState.DISMISSED}

ALLOWED_TRANSITIONS = {
    FindingState.OPEN: {FindingState.CONFIRMED, FindingState.DISMISSED},
    FindingState.CONFIRMED: set(),
    FindingState.DISMISSED: set(),
}
```

### NormalizedFinding (findings.py)

追加フィールド: `dismiss_reason: str | None = None`

### FindingResolution (新規, findings.py)

```python
class FindingResolution(BaseModel):
    finding_id: str
    state: Literal["confirmed", "dismissed"]
    dismiss_reason: str | None = None
```

### ContinuationVerdict (continuation.py)

- `schema_version`: 1 → 2
- `verdict`: `error` → `abort`
- 追加: `resolutions: tuple[FindingResolution, ...]`

## Phase Execution Flow

### Phase 1: review

```
controller.review_phase1() {
    cells = store.get_pending_cells()
    executor = ThreadPoolExecutor(max_workers=N)
    futures = [executor.submit(review_cell, cell) for cell in cells]
    for future in as_completed(futures):
        result = future.result()  # ReviewAdapterResult
        if result.success:
            store.mark_cell_reviewed(cell)
            for comment in result.comments:
                finding = normalize(comment)
                store.upsert_finding(finding, state=OPEN)
}
```

### Phase 2: resolve

```
controller.resolve_phase2() {
    findings = store.get_open_findings()
    by_file = group_by_file(findings)
    while has_unfinished(by_file):
        executor = ThreadPoolExecutor(max_workers=N)
        futures = {}
        for file_path, file_findings in by_file.items():
            if not is_finished(file_path):
                futures[executor.submit(resolve_file, file_path, file_findings)] = file_path
        for future in as_completed(futures):
            verdict = future.result()  # ContinuationVerdict
            file_path = futures[future]
            match verdict.verdict:
                case "finish":
                    for resolution in verdict.resolutions:
                        store.transition_finding(resolution.finding_id, resolution.state)
                    mark_finished(file_path)
                case "continue":
                    update_context(file_path, verdict)
                case "abort":
                    mark_aborted(file_path, verdict.error)
}
```

## Ready Prompt Priorities (新)

```
1. PENDING review cells → review prompt
2. OPEN findings → resolve prompt
3. All cells REVIEWED ∧ all findings terminal → finalize prompt
```

## Constitution Modifications

以下の原則を修正:

- **Principle 4** (Unknown must stay visible): "stale" を削除
- **Principle 5** (One review command advances once): Phase単位の進行に変更
- **Principle 9** (Fixed is not final until verified): 判定と修正の統合を反映
- **Principle 11** (Changes invalidate truth): ステイル概念の削除を反映

## CLI Changes

| コマンド | 変更 |
|---------|------|
| `review` | Phase 1: 全PENDINGセル並列実行。`--parallel N` 追加 |
| `resolve` | **新規**: Phase 2: 全open finding並列対処。`--parallel N` |
| `run` | Phase 1→2 通し実行。TUI対応 |
| `verify-fixes` | **削除** |

## Rollback Consideration

小規模変更（データモデル + ワークフローの簡素化のみ）であり、セッションストアのスキーマに後方互換性のない変更はない（FindingState値の変更のみ）。必要に応じて旧状態からのマイグレーションは実装時に検討。
