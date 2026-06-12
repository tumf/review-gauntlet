# Design: Verify Fixes Command

## Goals

- Provide a clear command for the post-fix workflow: re-review fixed-pending findings and report whether they are verified.
- Preserve the existing review evidence model: a finding is verified only by executing an adapter-backed review of the relevant current cell.
- Keep orchestration external. The command should advance one verification run, not loop or wait for developers.
- Reuse existing review adapter contracts so provider login, model choice, command output handling, and artifacts remain consistent with `review`.

## Command Shape

`review-gauntlet verify-fixes [root]` should mirror the execution controls of `review` where applicable:

- `--config <path>` for command adapter configuration
- `--fixture <path>` for test/local fixture mode
- `--budget <n>` to cap selected verification cells
- `--concurrency <n>` to cap parallel adapter calls
- `--format text|json` for output
- `--audience human|agent` for progress output

Focused selection options:

- `--finding <finding-id>` can be repeated and matches exact IDs.
- `--path <repo-relative-path-or-prefix>` can be repeated and uses existing safe path normalization and prefix matching semantics from `findings`.

## Selection Model

The command should derive targeted findings from the active session's persisted ledger:

1. Load fixed-pending findings only.
2. Apply optional `--finding` and `--path` filters.
3. Build current review cells from the active target and current file digests.
4. Select cells whose `file_path` is one of the targeted fixed-pending finding paths.
5. Apply `--budget` to the selected cell list.

This keeps verification focused on finding paths rather than generic coverage backlog. It also avoids claiming verification for findings whose current path has not been successfully evaluated.

## Outcome Model

For every targeted fixed-pending finding:

- If its path is successfully evaluated and its fingerprint is not seen in the run, transition it to `fixed_verified`.
- If its fingerprint is seen in the run, transition it to `reopened`.
- If its path is not evaluated because of `--budget`, missing current cells, superseded paths, or adapter failure, leave it `fixed_pending_verification` and report it in `unverifiable_ids`.

The command should exit non-zero when any targeted finding is reopened or unverifiable. That makes the command useful for agentic and CI-style orchestration without hiding incomplete verification.

## Adapter Reuse

`verify-fixes` should call the same adapter abstractions as `review`:

- `FakeReviewAdapter` for fixtures
- `CommandReviewAdapter` for external command execution
- `review_cells_concurrently` for concurrency/cancellation/progress
- `normalize_ocr_comment` for fingerprint generation
- existing verdict validation in the adapter before findings or coverage are affected

This avoids a second prompt/output contract and keeps the command aligned with OCR-derived review behavior.

## State And Coverage

The command creates a run only when it has at least one selected verification cell and `--budget` is positive. A no-op verification should not refresh finalization evidence or create run records.

Successful verification may mark selected cells reviewed as ordinary review evidence, but the command's primary output is finding verification state. Unrelated pending or stale cells must remain visible and should not be selected merely because verification is running.

## Trade-offs

Using path-level cell selection means multiple fixed-pending findings in the same file can be verified with one adapter call. This is preferable to one adapter call per finding because the existing adapter reviews cells, not individual findings, and fingerprints determine whether each targeted issue reappeared.

Findings whose files are removed or excluded from the current review universe cannot be automatically verified by this command. Leaving them as unverifiable is intentionally conservative and consistent with the constitution's unknown-must-stay-visible principle.
