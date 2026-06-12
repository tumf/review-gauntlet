## Implementation Tasks

- [x] Add a phony `install` target to `Makefile` that runs `uv tool install .`. (verification: manual - inspected `Makefile` and ran `make install`; manual coverage is intentional because `uv tool install` mutates the user's uv tool environment)
- [x] Preserve the canonical `review-gauntlet` console script and avoid adding the typo alias. (verification: manual - ran `rg -n "review-gauntlet|review-guantlet" pyproject.toml` and confirmed `review-gauntlet` exists and `review-guantlet` does not)
- [x] Document the local install workflow in `README.md`, including `make install` and `review-gauntlet --help`. (verification: manual - ran `rg -n "make install|review-gauntlet --help|review-guantlet" README.md` and confirmed only the correct install commands are documented)
- [x] Verify the installed CLI runs after installation. (verification: manual - ran `review-gauntlet --help` after `make install` and confirmed argparse help exits successfully)

## Final Validation

Archive validation is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-make-install-cli --archive-gate`.

## Future Work

- Publishing release artifacts or adding registry installation instructions can be proposed separately if needed.
