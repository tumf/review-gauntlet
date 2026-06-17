---
change_type: implementation
priority: medium
dependencies: []
references:
  - src/review_gauntlet/ocr_rules.py
  - src/review_gauntlet/rules/ocr/system_rules.json
  - src/review_gauntlet/rules/ocr/rule_docs/
  - tests/test_ocr_rules.py
  - openspec/specs/review-sessions/spec.md
---

# Add Solidity OCR review rule

**Change Type**: implementation

## Premise / Context

- The user requested adding a Solidity rule after asking for the current built-in review-rule list.
- Existing OCR-derived rules are selected by `src/review_gauntlet/rules/ocr/system_rules.json` and loaded with local Markdown documents from `src/review_gauntlet/rules/ocr/rule_docs/`.
- Current `system_rules.json` has language mappings for Java, TypeScript/JavaScript, Kotlin, Rust, C/C++, ArkTS, config files, and build manifests, but no `**/*.sol` mapping.
- Unmatched files currently fall back to `default.md`, so Solidity contracts do not get smart-contract-specific guidance.
- The canonical `review-sessions` spec already requires bundled OCR-derived path rules and rule documents, so this change modifies that existing behavior with an additional local rule document.

## Problem/Context

Solidity smart contracts have security review concerns that are not represented by the generic default OCR rule. A `.sol` file currently receives only generic correctness, security, and maintainability guidance. That makes review prompts less likely to emphasize smart-contract-specific risks such as reentrancy, authorization boundaries, unsafe low-level calls, upgradeable storage layout, gas-related denial of service, and transaction-origin misuse.

## Proposed Solution

Add a bundled Solidity OCR rule document and map Solidity source files to it. The smallest coherent implementation is to:

- add `solidity.md` under the bundled OCR rule documents,
- add a `**/*.sol` entry in the OCR system rule map,
- update OCR rule tests so `.sol` files are selected deterministically,
- preserve existing fallback and existing language mappings.

The Solidity rule document should follow the current OCR attribution style while adding concise Solidity-specific review guidance.

## Acceptance Criteria

- The default ruleset includes `solidity.md` as local package data.
- `ruleset.select_rule_doc("contracts/Vault.sol").filename` returns `solidity.md`.
- Existing OCR rule mappings for package manifests, config files, and supported languages remain unchanged.
- Solidity guidance explicitly covers smart-contract-specific review concerns including reentrancy, access control, unchecked external calls, integer/precision handling, `tx.origin` misuse, delegatecall/low-level call risk, upgradeable storage layout, event/state observability, and gas/DoS-sensitive loops.
- Ruleset digest changes naturally because the bundled rule map and documents are part of the digest payload.
- `make check` passes.

## Explicit Completion Conditions

- `src/review_gauntlet/rules/ocr/system_rules.json` contains a deterministic `**/*.sol` mapping to `solidity.md` without removing existing mappings.
- `src/review_gauntlet/rules/ocr/rule_docs/solidity.md` exists and contains the required Solidity-specific review guidance.
- `tests/test_ocr_rules.py` asserts that `solidity.md` is present in loaded documents and that a representative `.sol` path selects it.
- Focused verification via `uv run pytest tests/test_ocr_rules.py` passes.
- Full verification via `make check` passes.

## Out of Scope

- Adding a Solidity parser, compiler invocation, Slither/Mythril integration, or bytecode-level analysis.
- Changing review-cell planning categories, file inventory classification, or generic `CHECK_LIBRARY` checks.
- Changing upstream OCR attribution commit metadata.
- Adding custom user-configurable rule overrides beyond the bundled rule map.
