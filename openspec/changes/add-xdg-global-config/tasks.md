## Implementation Tasks

- [ ] Preserve explicit and repo-local discovery precedence in `src/review_gauntlet/config.py`, then add global fallback lookup for `$XDG_CONFIG_HOME/review-gauntlet/config.jsonc` and `$XDG_CONFIG_HOME/review-gauntlet/config.json`. (verification: unit - `uv run pytest tests/test_config.py` includes precedence assertions proving repo-local config wins over global config)
- [ ] Implement unset-`XDG_CONFIG_HOME` fallback to `Path.home() / ".config"` without creating directories or files during discovery. (verification: unit - `uv run pytest tests/test_config.py` monkeypatches `Path.home` or environment state and proves `~/.config/review-gauntlet/config.jsonc` is discovered)
- [ ] Keep explicit `--config` repository-confinement behavior unchanged. (verification: unit - existing `tests/test_config.py::test_explicit_config_rejects_out_of_repo_path` and `tests/test_config.py::test_explicit_config_takes_precedence` continue to pass)
- [ ] Document the updated discovery order in `README.md`, including global XDG fallback and repo-local precedence. (verification: integration - run `python -c "from pathlib import Path; text=Path('README.md').read_text(); assert '$XDG_CONFIG_HOME/review-gauntlet/config.jsonc' in text"`)
- [ ] Run repository checks after implementation. (verification: integration - `make check` passes)

## Future Work

- Optional future CLI support for printing or initializing the effective config path is intentionally excluded from this change.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-xdg-global-config --archive-gate`
