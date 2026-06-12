## Implementation Tasks

- [ ] Add repository-relative path validation helpers for CLI filters and inventory target paths, rejecting absolute paths and parent traversal before classification or filtering. (verification: unit - `uv run pytest tests/test_inventory.py tests/test_cli_findings.py` covers absolute and `..` inputs)
- [ ] Harden review universe digest construction to resolve the repository root and skip or reject symlinked files that escape the root. (verification: unit - `uv run pytest tests/test_targets.py` covers symlink escape and normal in-repo files)
- [ ] Constrain explicit adapter config paths to files under the reviewed repository root. (verification: unit - `uv run pytest tests/test_config.py` covers explicit in-repo and out-of-repo config paths)
- [ ] Constrain command adapter artifact directories by validating resolved `cell.id` paths stay under the run cells directory before creating files. (verification: unit - `uv run pytest tests/test_command_review_adapter.py` covers malformed cell IDs with path separators or `..`)
- [ ] Constrain command adapter `cwd` values so relative and absolute values must resolve under the repository root and point to a directory. (verification: unit - `uv run pytest tests/test_command_review_adapter.py` covers in-repo cwd, out-of-repo absolute cwd, and traversal cwd)
- [ ] Validate parsed OCR verdict comments against the current review cell path and line count, preserving valid `start_line=0,end_line=0` imprecise findings. (verification: integration - `uv run pytest tests/test_command_review_adapter.py tests/test_cli_session_review.py` covers accepted and rejected verdicts)
- [ ] Normalize or reject adapter-derived finding paths before persisting findings so absolute paths and parent traversal cannot become session finding paths. (verification: unit - `uv run pytest tests/test_findings.py` covers path normalization and rejection)
- [ ] Run full repository checks after implementation. (verification: integration - `make check`)

## Future Work

- Consider documenting any future intentionally out-of-repository adapter execution mode as an explicit opt-in capability, if such a use case is later required.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate harden-path-and-verdict-boundaries --archive-gate`
