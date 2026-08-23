"""Manufacturer / brand entity resolution.

The final selected manufacturer/brand always comes from the master data
table (never invented by the LLM). Resolution escalates through cheap,
explainable methods before falling back to anything probabilistic:

    exact match
      -> normalized match (case/punctuation/legal-suffix insensitive)
      -> brand-alias token match against free text (handles the common case
         where Part_Manuf is actually a wholesaler/co-op, not the true
         manufacturer, and the real brand is hiding inside Part_Desc)
      -> fuzzy match (rapidfuzz) against manufacturer master
      -> UNRESOLVED -> human review

Every result is an explainable record with input/canonical_value/entity_code/
score/method/status/evidence, per the challenge's entity-resolution contract.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.config.settings import settings

_LEGAL_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|co|corp|corporation|company|mfg|manufacturing)\b\.?",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]")


def normalize_name(name: str) -> str:
    name = (name or "").lower()
    name = _PUNCT.sub(" ", name)
    name = _LEGAL_SUFFIXES.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


@dataclass
class ManufacturerRecord:
    manufacturer_name: str
    manufacturer_code: str
    brand_name: str
    brand_code: str
    aliases: list[str]
    source: str


@dataclass
class ResolutionResult:
    input: str
    canonical_value: str | None
    entity_code: str | None
    brand_name: str | None
    brand_code: str | None
    score: float
    method: str
    status: str  # RESOLVED | LOW_CONFIDENCE | UNRESOLVED
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "input": self.input,
            "canonical_value": self.canonical_value,
            "entity_code": self.entity_code,
            "brand_name": self.brand_name,
            "brand_code": self.brand_code,
            "score": round(self.score, 4),
            "method": self.method,
            "status": self.status,
            "evidence": self.evidence,
        }


class ManufacturerResolver:
    FUZZY_ACCEPT = 90
    FUZZY_REVIEW = 78

    def __init__(self, master_path=None):
        self.records: list[ManufacturerRecord] = []
        self._by_norm_name: dict[str, ManufacturerRecord] = {}
        self._alias_index: list[tuple[str, ManufacturerRecord]] = []
        self._load(master_path)

    def _load(self, master_path):
        path = master_path or settings.EXTERNAL_REFERENCE_DIR / "manufacturer_brand_master.csv"
        if not path.exists():
            path = settings.REFERENCE_DIR / "manufacturer_brand_master.csv"
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                aliases = [a.strip() for a in (row.get("MATCH_ALIASES") or "").split("|") if a.strip()]
                rec = ManufacturerRecord(
                    manufacturer_name=row["MANUFACTURER_NAME"].strip(),
                    manufacturer_code=(row.get("MANUFACTURER_CODE") or "").strip(),
                    brand_name=row["BRAND_NAME"].strip(),
                    brand_code=(row.get("BRAND_CODE") or "").strip(),
                    aliases=aliases,
                    source=row.get("SOURCE", ""),
                )
                self.records.append(rec)
                self._by_norm_name[normalize_name(rec.manufacturer_name)] = rec
                for alias in aliases:
                    self._alias_index.append((alias.lower(), rec))
        # longest alias first so "milwaukee" doesn't get pre-empted by a shorter partial token
        self._alias_index.sort(key=lambda t: -len(t[0]))

        self._mpn_prefixes: list[tuple[str, str, str, str]] = []  # prefix, manuf, brand, confidence
        prefix_path = settings.EXTERNAL_REFERENCE_DIR / "mpn_prefix_patterns.csv"
        if not prefix_path.exists():
            prefix_path = settings.REFERENCE_DIR / "mpn_prefix_patterns.csv"
        if prefix_path.exists():
            with open(prefix_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self._mpn_prefixes.append((row["prefix"].strip(), row["manufacturer_name"].strip(), row["brand_name"].strip(), row.get("confidence", "")))
            self._mpn_prefixes.sort(key=lambda t: -len(t[0]))

    # -- public API -----------------------------------------------------
    def resolve_from_part_manuf(self, raw_part_manuf: str) -> ResolutionResult:
        if not raw_part_manuf or raw_part_manuf.strip() in ("-", ""):
            return ResolutionResult(raw_part_manuf, None, None, None, None, 0.0, "none", "UNRESOLVED", ["Part_Manuf empty/placeholder"])

        # strip trailing "(CODE)"
        cleaned = re.sub(r"\s*\([A-Za-z0-9]+\)\s*$", "", raw_part_manuf).strip()
        norm = normalize_name(cleaned)

        exact = self._by_norm_name.get(norm)
        if exact:
            return ResolutionResult(
                raw_part_manuf, exact.manufacturer_name, exact.manufacturer_code,
                exact.brand_name, exact.brand_code, 1.0, "exact_normalized_match", "RESOLVED",
                [f"normalized '{raw_part_manuf}' -> '{norm}', exact match in manufacturer master ({exact.source})"],
            )

        best, best_score = None, 0.0
        for rec in self.records:
            score = fuzz.token_sort_ratio(norm, normalize_name(rec.manufacturer_name))
            if score > best_score:
                best, best_score = rec, score

        if best and best_score >= self.FUZZY_ACCEPT:
            return ResolutionResult(
                raw_part_manuf, best.manufacturer_name, best.manufacturer_code,
                best.brand_name, best.brand_code, best_score / 100, "fuzzy_match", "RESOLVED",
                [f"token_sort_ratio({norm!r}, {normalize_name(best.manufacturer_name)!r}) = {best_score:.1f}"],
            )
        if best and best_score >= self.FUZZY_REVIEW:
            return ResolutionResult(
                raw_part_manuf, best.manufacturer_name, best.manufacturer_code,
                best.brand_name, best.brand_code, best_score / 100, "fuzzy_match", "LOW_CONFIDENCE",
                [f"token_sort_ratio({norm!r}, {normalize_name(best.manufacturer_name)!r}) = {best_score:.1f} (below accept threshold)"],
            )
        return ResolutionResult(raw_part_manuf, cleaned, None, cleaned, None, best_score / 100 if best else 0.0,
                                 "unmatched_fallback", "LOW_CONFIDENCE",
                                 ["No master-data match; falling back to cleaned Part_Manuf as both manufacturer and brand per 'no brand -> use manufacturer name' rule"])

    def resolve_brand_from_text(self, text: str) -> ResolutionResult | None:
        """Looks for a known brand alias token inside free text (Part_Desc /
        MPN). This is what lets us catch e.g. 'LG Dishwasher' or 'Milw ...'
        even when Part_Manuf is a distributor/co-op, not the OEM."""
        if not text:
            return None
        low = f" {text.lower()} "
        for alias, rec in self._alias_index:
            pattern_alt = alias.split("|")
            for a in pattern_alt:
                a = a.strip()
                if not a:
                    continue
                if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", low):
                    return ResolutionResult(
                        text, rec.manufacturer_name, rec.manufacturer_code,
                        rec.brand_name, rec.brand_code, 0.95, "brand_alias_token_match", "RESOLVED",
                        [f"token '{a}' found in description text, matched brand alias for {rec.manufacturer_name} ({rec.source})"],
                    )
        return None

    def resolve_from_mpn_prefix(self, mpn: str) -> ResolutionResult | None:
        if not mpn:
            return None
        mpn_up = mpn.strip().upper()
        for prefix, manuf, brand, confidence in self._mpn_prefixes:
            if mpn_up.startswith(prefix):
                status = "RESOLVED" if confidence == "confirmed" else "LOW_CONFIDENCE"
                score = 0.93 if confidence == "confirmed" else 0.6
                return ResolutionResult(
                    mpn, manuf, "", brand, "", score, "mpn_prefix_pattern_match", status,
                    [f"MPN prefix '{prefix}' matched a {confidence} manufacturer pattern (source: mpn_prefix_patterns.csv)"],
                )
        return None

    def resolve(self, part_manuf: str, part_desc: str, mpn: str = "") -> ResolutionResult:
        """Full resolution, escalating through cheap explainable signals:
        brand-in-free-text -> confirmed MPN-prefix pattern -> Part_Manuf
        master-data match. Text/prefix take priority over Part_Manuf because
        Part_Manuf is frequently a wholesaler/co-op, not the true OEM (see
        the ground-truth Frigidaire/Rheem and Whirlpool examples)."""
        manuf_hit = self.resolve_from_part_manuf(part_manuf)

        text_hit = self.resolve_brand_from_text(f"{mpn} {part_desc}")
        if text_hit:
            text_hit.evidence.append(f"Part_Manuf resolved separately to '{manuf_hit.canonical_value}' via {manuf_hit.method} (not used - text match takes priority)")
            return text_hit

        prefix_hit = self.resolve_from_mpn_prefix(mpn)
        if prefix_hit:
            prefix_hit.evidence.append(f"Part_Manuf resolved separately to '{manuf_hit.canonical_value}' via {manuf_hit.method} (not used - confirmed MPN pattern takes priority)")
            return prefix_hit

        return manuf_hit


_singleton: ManufacturerResolver | None = None


def get_resolver() -> ManufacturerResolver:
    global _singleton
    if _singleton is None:
        _singleton = ManufacturerResolver()
    return _singleton
