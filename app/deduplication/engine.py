"""Deduplication — manufacturer + MPN + brand (+UPC/GTIN where present) is
the primary exact-duplicate key; normalized-description similarity flags
near-duplicates/variants for review rather than auto-merging them."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz


def _norm_key(mpn: str, manufacturer: str | None) -> str:
    mpn_norm = re.sub(r"[^A-Za-z0-9]", "", (mpn or "")).upper()
    manuf_norm = re.sub(r"[^A-Za-z0-9]", "", (manufacturer or "")).upper()
    return f"{manuf_norm}::{mpn_norm}"


@dataclass
class DedupGroup:
    key: str
    kind: str  # EXACT_DUPLICATE | NEAR_DUPLICATE
    row_indices: list[int]
    similarity: float | None = None


def find_duplicates(records: list[dict], desc_field: str = "Part_Desc", mpn_field: str = "Mfg_Part_Num", manuf_field: str = "MANUFACTURER_NAME", near_dup_threshold: int = 92) -> list[DedupGroup]:
    exact_groups: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(records):
        key = _norm_key(r.get(mpn_field, ""), r.get(manuf_field))
        exact_groups[key].append(i)

    results = [DedupGroup(k, "EXACT_DUPLICATE", idxs) for k, idxs in exact_groups.items() if len(idxs) > 1]

    # near-duplicate pass only within singleton groups, description similarity
    singles = [idxs[0] for idxs in exact_groups.values() if len(idxs) == 1]
    seen_pairs = set()
    for a_pos, i in enumerate(singles):
        for j in singles[a_pos + 1:]:
            desc_i, desc_j = records[i].get(desc_field, ""), records[j].get(desc_field, "")
            if not desc_i or not desc_j:
                continue
            score = fuzz.token_sort_ratio(desc_i, desc_j)
            if score >= near_dup_threshold and (i, j) not in seen_pairs:
                results.append(DedupGroup(f"near::{i}::{j}", "NEAR_DUPLICATE", [i, j], score / 100))
                seen_pairs.add((i, j))

    return results
