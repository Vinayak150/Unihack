"""Source/evidence model, honoring the manufacturer-first source hierarchy.

This build has no live web-retrieval budget wired to an external crawler
(no credentials, and the challenge explicitly restricts sourcing to
manufacturer-owned properties, not marketplaces). What IS implemented and
real: the source-authority ranking, the evidence-span schema, and the
retrieval-adapter interface, so a manufacturer-page/PDF connector can be
dropped in later without touching any downstream code. Until then, the only
"source" most records have is `input_row` (the record itself) and, for the
two verified dishwasher records, the manufacturer URLs present in the
ground-truth file. Every claim honestly reports which of these it used.
"""
from __future__ import annotations

from dataclasses import dataclass

AUTHORITY_RANK = {
    "manufacturer_product_page": 1,
    "manufacturer_documentation": 2,
    "manufacturer_specification_pdf": 3,
    "manufacturer_installation_manual": 4,
    "manufacturer_catalog": 5,
    "manufacturer_technical_bulletin": 6,
    "input_row": 90,   # the raw catalog record itself — always available, lowest external authority
    "ground_truth_reference": 0,  # only used in eval/regression tooling, never in production inference
}


@dataclass
class Source:
    source_id: str
    source_type: str
    url: str | None
    manufacturer: str | None
    mpn: str | None
    text_span: str
    retrieved_at: str | None = None

    @property
    def authority(self) -> int:
        return AUTHORITY_RANK.get(self.source_type, 99)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id, "source_type": self.source_type, "url": self.url,
            "manufacturer": self.manufacturer, "mpn": self.mpn, "text_span": self.text_span,
            "authority_rank": self.authority, "retrieved_at": self.retrieved_at,
        }
