"""Hierarchical Dept > Class > Fine taxonomy classification.

Rule/keyword based first (cheap, deterministic, explainable) with an LLM
adjudication fallback only for genuinely ambiguous cases - see
app.classification.llm_classifier. Classification must land on a classpath
that actually exists in the LOV table so attribute extraction always has a
consistent, validated set of applicable attributes to work against.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.config.settings import settings


@dataclass
class ClasspathNode:
    classpath: str
    leaf_node: str
    keywords: list[str]


@dataclass
class ClassificationResult:
    classpath: str | None
    leaf_node: str | None
    method: str
    score: float
    status: str  # RESOLVED | LOW_CONFIDENCE | UNRESOLVED
    evidence: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "classpath": self.classpath, "leaf_node": self.leaf_node, "method": self.method,
            "score": round(self.score, 4), "status": self.status, "evidence": self.evidence,
        }


class TaxonomyClassifier:
    def __init__(self, lov_path=None):
        self.nodes: list[ClasspathNode] = []
        self._load(lov_path)

    def _load(self, lov_path):
        path = lov_path or settings.EXTERNAL_REFERENCE_DIR / "category_keywords.csv"
        if not path.exists():
            path = settings.REFERENCE_DIR / "category_keywords.csv"
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cp = row["Classpath"].strip()
                leaf = row.get("Leaf Node", cp.split(">")[-1]).strip()
                kws = [k.strip() for k in (row.get("Keywords") or "").split("|") if k.strip()]
                self.nodes.append(ClasspathNode(cp, leaf, kws))

    def classpaths(self) -> list[str]:
        return [n.classpath for n in self.nodes]

    def classify(self, text: str, manufacturer: str = "", brand: str = "") -> ClassificationResult:
        text_low = f" {text.lower()} "
        best_node, best_hits = None, []
        for node in self.nodes:
            hits = []
            for pattern in node.keywords:
                try:
                    if re.search(pattern, text_low):
                        hits.append(pattern)
                except re.error:
                    if pattern in text_low:
                        hits.append(pattern)
            if len(hits) > len(best_hits):
                best_node, best_hits = node, hits

        if best_node and best_hits:
            score = min(0.6 + 0.15 * len(best_hits), 0.97)
            status = "RESOLVED" if score >= 0.72 else "LOW_CONFIDENCE"
            return ClassificationResult(
                best_node.classpath, best_node.leaf_node, "keyword_rule_match", score, status,
                [f"matched keyword(s) {best_hits} for classpath '{best_node.classpath}'"],
            )
        return ClassificationResult(None, None, "none", 0.0, "UNRESOLVED", ["no keyword/leaf match against taxonomy_lov.csv"])


_singleton: TaxonomyClassifier | None = None


def get_classifier() -> TaxonomyClassifier:
    global _singleton
    if _singleton is None:
        _singleton = TaxonomyClassifier()
    return _singleton
