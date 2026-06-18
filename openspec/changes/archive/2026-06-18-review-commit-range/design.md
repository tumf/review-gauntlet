# Design: Commit-Range Review Target

## Architecture

### New function: `file_digests_at_commit`

```python
# targets.py
def file_digests_at_commit(root: Path, commit: str) -> dict[str, str]:
    """Return SHA256 of git show <commit>:<relpath> for each review-universe file."""
```

Replaces `file_digests(root)` in `_current_target_cells` when `review_head_commit` is present. Falls back to `file_digests(root)` for sessions without the commit metadata (backward compat).

### Session metadata addition

```python
# cli.py _cmd_init
head_commit = git("rev-parse", "HEAD^{commit}")
metadata["review_head_commit"] = head_commit
```

### Digest flow comparison

```
BEFORE (working tree):
  init → cells_from_plan(plan, file_digests(root))
       → digest = SHA256(path.read_bytes())
       → fix changes file → digest ≠ persisted → STALE

AFTER (committed):
  init → cells_from_plan(plan, file_digests_at_commit(root, review_head_commit))
       → digest = SHA256(git_show(commit, path))
       → fix changes file → working tree digest changes but committed digest unchanged → NOT stale
```

### Staleness simplification

Three locations currently have the `fixed_pending_paths` guard:

1. `_effective_current_target_coverage_for_cells` (cli.py ~1840)
2. `_reconcile_cells` (cli.py ~1314)
3. `_ready_review_cells` (cli.py ~1729)

All three simplify to: `persisted["content_digest"] != current_cell.content_digest` without the `fixed_pending_paths` exception.

### verify-fixes divergence

`verify-fixes` intentionally uses `file_digests(root)` (working tree) because it needs to verify that the fix resolved the finding. This creates a deliberate asymmetry:

- **review**: committed content (what the finding was reported against)
- **verify-fixes**: working tree content (did the fix actually work?)

### Target spec changes

```
TargetKind: BRANCH, COMMIT  (remove: WORKTREE, ALL)
```

`ALL` is subsumed by `COMMIT` at HEAD. `WORKTREE` has no replacement — users who want to review uncommitted changes should commit first.

### Default init resolution

```python
# BEFORE
target = target_from_latest_checkpoint(root)  # branch target
if target is None:
    # falls through to resolve_target(args) → WORKTREE default

# AFTER
target = target_from_latest_checkpoint(root)  # branch target
if target is None:
    head = git("rev-parse", "HEAD^{commit}")
    target = TargetSpec(kind=COMMIT, commit=head, head_mode=FIXED)
```

### Prompt changes

Review prompt (`review_adapter.py:build_review_prompt`) adds commit reference:

```
Before: "Read the file at {file_path}"
After:  "Read the file at {file_path} as it exists at commit {commit_sha}.
        Use `git show {commit_sha}:{file_path}` to inspect the committed version."
```

Run prompt (`cli.py:_build_file_scoped_ready_prompt`) adds commit sha to target file section:

```
## Target file
file_path: src/app.py
review_commit: a1b2c3d4e5f6  # NEW
reason: untriaged findings need triage
```

## Migration

- Existing sessions without `review_head_commit` continue using `file_digests(root)` → backward compatible
- Sessions with `review_head_commit` use the new commit-based digest
- No database migration needed (metadata JSON field)
