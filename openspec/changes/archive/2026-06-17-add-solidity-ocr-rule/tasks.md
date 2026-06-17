## Implementation Tasks

- [x] Add the bundled Solidity rule mapping. Completion condition: `src/review_gauntlet/rules/ocr/system_rules.json` maps `**/*.sol` to `solidity.md` and all existing mappings still resolve to their current documents. (verification: unit - `uv run pytest tests/test_ocr_rules.py` fails if `.sol` does not select `solidity.md` or existing representative mappings regress.)
- [x] Add Solidity-specific OCR rule guidance. Completion condition: `src/review_gauntlet/rules/ocr/rule_docs/solidity.md` is loaded by `load_ruleset()` and includes the full requested Solidity checklist: specification/assumptions; compiler settings; access control; reentrancy/external calls; ETH/token transfers; input validation; numeric calculation/casting; state/invariants; randomness/time/block data/on-chain secrecy; oracle/pricing/external data; gas/DoS; upgradeable/proxy; signatures/permits/replay; ERC/interface compliance; emergency design; events/auditability; testing/verification; deployment/operations; code quality; high-risk signals; and practical review order. (verification: unit - `uv run pytest tests/test_ocr_rules.py` asserts the document is present; manual - reviewer inspects the rule text for the required checklist coverage because prose quality and checklist completeness are intentionally human-reviewed.)
- [x] Extend OCR rule regression tests. Completion condition: `tests/test_ocr_rules.py` includes `solidity.md` in the loaded document assertion and includes a representative Solidity path such as `contracts/Vault.sol` in the mapping cases. (verification: unit - `uv run pytest tests/test_ocr_rules.py`.)
- [x] Run full repository verification. Completion condition: formatting, linting, type checking, and tests remain green after the rule addition. (verification: integration - `make check`.)

## Future Work

- Optional future proposals may add static-analysis integration for Solidity tools such as Slither or Mythril, but this change is limited to bundled prompt/rule selection.

## Final Validation

Archive validation itself is the authoritative final OpenSpec validation gate.
Expected archive gate: `cflx openspec validate add-solidity-ocr-rule --archive-gate`
