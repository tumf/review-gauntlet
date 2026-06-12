## Implementation Tasks

- [ ] Add a phony `install` target to `Makefile` that runs `uv tool install .`. (verification: manual - inspect `Makefile` and run `make install`; manual coverage is intentional because `uv tool install` mutates the user's uv tool environment)
- [ ] Preserve the canonical `review-gauntlet` console script and avoid adding the typo alias. (verification: manual - inspect `pyproject.toml` or run `rg -n "review-gauntlet|review-guantlet" pyproject.toml` to confirm `review-gauntlet` exists and `review-guantlet` does not)
- [ ] Document the local install workflow in `README.md`, including `make install` and `review-gauntlet --help`. (verification: manual - run `rg -n "make install|review-gauntlet --help|review-guantlet" README.md` and confirm only the correct install commands are documented)
- [ ] Verify the installed CLI runs after installation. (verification: manual - run `review-gauntlet --help` after `make install` and confirm argparse help exits successfully)

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-make-install-cli --archive-gate`.

## Future Work

- Publishing release artifacts or adding registry installation instructions can be proposed separately if needed.
