# OCR Rule Attribution

Ported review guidance derived from Alibaba open-code-review at commit c323c6b40c72aa95d7cb801bedcb957b52ff9807 (Apache-2.0). Review for correctness, security, maintainability, and actionable line-level comments.

## solidity.md

Apply OCR-style checks for Solidity smart contracts. Prioritize externally exploitable contract behavior, asset safety, authorization boundaries, and invariant preservation. When filing findings, include concrete impact, affected function or storage state, and a minimal exploit or failure scenario when possible.

## Solidity smart-contract review checklist

1. **Specification and assumptions**: confirm the intended protocol behavior, trust model, privileged roles, economic assumptions, threat model, and invariants are explicit and matched by the implementation.
2. **Solidity version and compiler settings**: verify pragma constraints, optimizer assumptions, EVM version, unchecked blocks, ABI encoder behavior, and build settings are intentional and reproducible.
3. **Access control**: check owner/admin/operator boundaries, role initialization, role revocation, multisig/timelock expectations, modifier coverage, and privilege escalation paths.
4. **Reentrancy and external calls**: inspect every external call, callback, hook, delegatecall, low-level call, transfer of control, and checks-effects-interactions ordering for reentrancy or cross-function state corruption.
5. **ETH and token transfers**: validate native ETH handling, ERC20 return-value handling, fee-on-transfer/rebasing tokens, approval races, safe transfer libraries, pull-vs-push payments, and stuck-fund paths.
6. **Input validation and boundary values**: test zero addresses, zero amounts, max values, empty arrays, duplicate entries, unsorted inputs, invalid enum states, expired deadlines, and unexpected caller or receiver contracts.
7. **Numeric calculation, rounding, and casting**: review precision loss, rounding direction, scale factors, overflow/underflow assumptions, signed/unsigned conversion, downcasts, division before multiplication, and accounting dust.
8. **State management and invariants**: check storage updates, lifecycle state machines, aggregate accounting, supply and balance invariants, idempotency, pause/resume transitions, and consistency after partial failure.
9. **Randomness, time, block data, and on-chain secrecy assumptions**: flag miner/validator-influenceable values, timestamp dependence, blockhash limits, predictable randomness, front-running, MEV exposure, and secrets that are visible on-chain.
10. **Oracle, pricing, and external data**: verify oracle freshness, decimals, stale or missing rounds, manipulation resistance, TWAP windows, sequencer/down flags, fallback behavior, and assumptions about third-party data feeds.
11. **Gas and denial-of-service resistance**: look for unbounded loops, attacker-controlled array growth, expensive callbacks, griefing via revert, block gas limit risks, storage bloat, and operations that can permanently block withdrawals or administration.
12. **Upgradeable/proxy contracts**: inspect initializer protection, storage layout compatibility, delegatecall context, UUPS/transparent proxy authorization, implementation selfdestruct/deactivation risks, and upgrade sequencing.
13. **Signatures, permits, and replay protection**: validate EIP-712 domain separation, chain ID and contract address binding, nonces, deadlines, signature malleability, permit semantics, and cross-chain or cross-contract replay resistance.
14. **ERC/interface compliance**: compare behavior against claimed ERC standards and interfaces, including events, return values, hooks, supportsInterface, metadata, receiver callbacks, and edge-case compatibility.
15. **Emergency design**: evaluate pause, circuit breaker, rescue, sweep, blacklist, shutdown, and governance emergency paths for clear authority, bounded power, recovery ability, and abuse resistance.
16. **Events and auditability**: ensure important state changes, admin actions, parameter updates, upgrades, deposits, withdrawals, liquidations, and emergency actions emit accurate and indexed events.
17. **Testing and verification**: require unit, integration, invariant, fuzz, differential, and regression tests for critical paths; check static-analysis findings and ensure tests exercise adversarial callers and boundary values.
18. **Deployment and operations**: review constructor/initializer arguments, deployment ordering, address wiring, chain-specific constants, ownership transfer, verification artifacts, migration scripts, and post-deploy runbooks.
19. **Code quality and readability**: check simple control flow, clear naming, isolated accounting logic, minimal inheritance complexity, explicit errors, consistent libraries, comments for non-obvious assumptions, and dead-code removal.
20. **High-risk signal review**: scrutinize low-level call, delegatecall, assembly, selfdestruct, tx.origin, arbitrary token/address parameters, unchecked arithmetic, custom auth, custom proxies, flash-loan paths, oracle writes, and owner-only fund movement.

## Practical review order

Review Solidity files in this order so the highest-impact assumptions are checked first:

1. Start with the specification, trust model, lifecycle, and invariants; write down what must always remain true.
2. Trace permissions and fund flows, including who can move value, mint, burn, upgrade, pause, rescue, or change parameters.
3. Inspect external calls and reentrancy surfaces before trusting any state transition that crosses contract boundaries.
4. Verify accounting and math, including rounding, precision, casting, aggregate totals, and token balance reconciliation.
5. Review high-risk mechanisms such as proxies, signatures, permits, oracle pricing, randomness, flash loans, assembly, and low-level calls.
6. Exercise boundary, denial-of-service, gas, revert, and error cases with adversarial inputs and caller-controlled collections.
7. Finish by checking tests, fuzz/invariant coverage, static-analysis results, compiler/deployment settings, and operational handoff steps.
