from review_gauntlet.ocr_rules import UPSTREAM_COMMIT, load_ruleset


def test_ocr_rules_record_pinned_commit_and_docs() -> None:
    ruleset = load_ruleset()
    assert ruleset.upstream_commit == UPSTREAM_COMMIT
    for name in ["default.md", "package_json.md", "rust.md", "ts_js_tsx_jsx.md"]:
        assert name in ruleset.documents


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
        "README.md": "default.md",
    }
    for path, doc in cases.items():
        assert ruleset.select_rule_doc(path).filename == doc
