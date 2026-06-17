from review_gauntlet.ocr_rules import UPSTREAM_COMMIT, load_ruleset

SOLIDITY_REQUIRED_PHRASES = (
    "Specification and assumptions",
    "Solidity version and compiler settings",
    "Access control",
    "Reentrancy and external calls",
    "ETH and token transfers",
    "Input validation and boundary values",
    "Numeric calculation, rounding, and casting",
    "State management and invariants",
    "Randomness, time, block data, and on-chain secrecy assumptions",
    "Oracle, pricing, and external data",
    "Gas and denial-of-service resistance",
    "Upgradeable/proxy contracts",
    "Signatures, permits, and replay protection",
    "ERC/interface compliance",
    "Emergency design",
    "Events and auditability",
    "Testing and verification",
    "Deployment and operations",
    "Code quality and readability",
    "High-risk signal review",
    "Practical review order",
)


def test_ocr_rules_record_pinned_commit_and_docs() -> None:
    ruleset = load_ruleset()
    assert ruleset.upstream_commit == UPSTREAM_COMMIT
    expected_docs = [
        "default.md",
        "package_json.md",
        "rust.md",
        "solidity.md",
        "ts_js_tsx_jsx.md",
    ]
    for name in expected_docs:
        assert name in ruleset.documents


def test_solidity_rule_document_covers_required_review_topics() -> None:
    ruleset = load_ruleset()
    content = ruleset.documents["solidity.md"].content
    for phrase in SOLIDITY_REQUIRED_PHRASES:
        assert phrase in content


def test_representative_rule_mapping() -> None:
    ruleset = load_ruleset()
    cases = {
        "app.properties": "properties.md",
        "src/user_mapper.xml": "mapper_dao_xml.md",
        "pom.xml": "pom_xml.md",
        "build.gradle": "build_gradle.md",
        "package.json": "package_json.md",
        "Cargo.toml": "cargo_toml.md",
        "data.json5": "json.md",
        "config.yml": "yaml.md",
        "Main.java": "java.md",
        "page.ets": "arkts.md",
        "src/app.tsx": "ts_js_tsx_jsx.md",
        "Main.kt": "kotlin.md",
        "src/lib.rs": "rust.md",
        "src/main.cpp": "cpp.md",
        "src/main.c": "c.md",
        "contracts/Vault.sol": "solidity.md",
        "README.md": "default.md",
    }
    for path, doc in cases.items():
        assert ruleset.select_rule_doc(path).filename == doc
