from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from importlib import resources
from typing import cast

from pydantic import BaseModel, ConfigDict

UPSTREAM_REPOSITORY = "https://github.com/alibaba/open-code-review"
UPSTREAM_COMMIT = "c323c6b40c72aa95d7cb801bedcb957b52ff9807"
ADAPTER_VERSION = "fake-ocr-v1"


class OCRComment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    content: str
    suggestion_code: str = ""
    existing_code: str = ""
    start_line: int = 0
    end_line: int = 0
    thinking: str | None = None

    @property
    def imprecise(self) -> bool:
        return self.start_line == 0 and self.end_line == 0


class RuleDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    filename: str
    content: str


class Ruleset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    upstream_repository: str
    upstream_commit: str
    system_rules: dict[str, str]
    documents: dict[str, RuleDocument]
    digest: str

    def select_rule_doc(self, path: str) -> RuleDocument:
        for pattern, filename in self.system_rules.items():
            if _matches(pattern, path):
                return self.documents[filename]
        return self.documents["default.md"]


def load_ruleset() -> Ruleset:
    base = resources.files("review_gauntlet.rules.ocr")
    rules_raw = (base / "system_rules.json").read_text(encoding="utf-8")
    system_rules = cast(dict[str, str], json.loads(rules_raw))
    docs: dict[str, RuleDocument] = {}
    docs_root = base / "rule_docs"
    doc_names = sorted(item.name for item in docs_root.iterdir() if item.name.endswith(".md"))
    for doc_name in doc_names:
        doc = docs_root / doc_name
        docs[doc_name] = RuleDocument(
            id=doc_name.removesuffix(".md"),
            filename=doc_name,
            content=doc.read_text(encoding="utf-8"),
        )
    payload = {
        "upstream_repository": UPSTREAM_REPOSITORY,
        "upstream_commit": UPSTREAM_COMMIT,
        "adapter_version": ADAPTER_VERSION,
        "system_rules": system_rules,
        "documents": {name: docs[name].content for name in sorted(docs)},
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return Ruleset(
        upstream_repository=UPSTREAM_REPOSITORY,
        upstream_commit=UPSTREAM_COMMIT,
        system_rules=system_rules,
        documents=docs,
        digest=digest,
    )


def _matches(pattern: str, path: str) -> bool:
    patterns = _expand_braces(pattern)
    normalized = path.replace(os.sep, "/")
    basename = normalized.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(normalized, expanded)
        or fnmatch.fnmatch(basename, expanded)
        or (expanded.startswith("**/") and fnmatch.fnmatch(normalized, expanded[3:]))
        or (expanded.startswith("**/") and fnmatch.fnmatch(basename, expanded[3:]))
        for expanded in patterns
    )


def _expand_braces(pattern: str) -> list[str]:
    start = pattern.find("{")
    end = pattern.find("}", start + 1)
    if start == -1 or end == -1:
        return [pattern]
    prefix = pattern[:start]
    suffix = pattern[end + 1 :]
    return [prefix + part + suffix for part in pattern[start + 1 : end].split(",")]
