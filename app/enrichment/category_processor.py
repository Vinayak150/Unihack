"""Category processors: Global Pipeline + Category Processor, as required by
the challenge. Every processor shares the same base extraction/normalization
contract; category subclasses only add category-specific knowledge (which
attributes matter most, extra deterministic parsing, generation hints).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.extraction.deterministic import extract_deterministic_claims
from app.lov.vocabulary import get_vocabulary
from app.normalization.normalize import normalize_all
from app.provenance.claims import Claim, ClaimRegistry


@dataclass
class ProductContext:
    mpn: str
    part_desc: str
    manufacturer: str | None
    brand: str | None
    classpath: str | None
    leaf_node: str | None
    flags: list[str] = field(default_factory=list)  # e.g. ["Display Only"]


class CategoryProcessor:
    """Default/generic processor: applies deterministic extraction against
    whatever attributes the classpath's LOV entry defines, normalizes them,
    and validates enum values against the controlled vocabulary. Any
    classpath without a dedicated subclass below still gets this — full
    coverage, not just the deep-dived category."""

    classpath_match: str | None = None  # None => fallback for anything

    def applicable_attribute_labels(self, ctx: ProductContext) -> set[str]:
        vocab = get_vocabulary()
        return {a.attribute_label for a in vocab.attributes_for(ctx.classpath or "")}

    def extract(self, ctx: ProductContext) -> ClaimRegistry:
        registry = ClaimRegistry()
        attr_labels = self.applicable_attribute_labels(ctx)

        det_claims = extract_deterministic_claims(ctx.part_desc, ctx.mpn, attr_labels)
        det_claims = normalize_all(det_claims)

        vocab = get_vocabulary()
        for claim in det_claims:
            if ctx.classpath:
                match = vocab.validate_value(ctx.classpath, claim.attribute, claim.value or "")
                if match.status == "IN_VOCABULARY" and match.canonical_value:
                    claim.value = match.canonical_value
            registry.add(claim)

        for label in attr_labels:
            if registry.get(label) is None:
                registry.add(Claim(label, None, None, "UNKNOWN", [], 0.0))

        for flag in ctx.flags:
            if registry.get("Additional Information") is None:
                registry.add(Claim("Additional Information", flag, None, "DIRECT", ["input_row"], 0.9))

        return registry


class DishwasherProcessor(CategoryProcessor):
    """Deep processor for Built-In Dishwashers — the one category this build
    has a verified ground-truth record for. Encodes the exact attribute set
    Unilog's delivery format expects (Series, Model, Wash Cycles, Voltage,
    Amperage, Mounting, Plug Type, Size, Depth-With-Door-Open, Min/Max
    Height, Sound Level, Material, Color, Additional Information)."""

    classpath_match = "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers"
    ORDERED_ATTRIBUTES = [
        "Series", "Model", "Number of Wash Cycles", "Voltage Rating", "Amperage Rating",
        "Mounting Type", "Plug Type", "Size", "Depth With Door Open", "Minimum Height",
        "Maximum Height", "Sound Level", "Material", "Color", "Additional Information",
    ]

    def extract(self, ctx: ProductContext) -> ClaimRegistry:
        registry = super().extract(ctx)
        # Mounting type heuristic from free text, still fully grounded (DIRECT):
        text_low = (ctx.part_desc or "").lower()
        if registry.get("Mounting Type") is None or registry.value_of("Mounting Type") is None:
            if "bltln" in text_low or "built-in" in text_low or "built in" in text_low:
                self._replace(registry, Claim("Mounting Type", "Built-in", None, "DIRECT", ["input_row"], 0.85))
            elif "leg" in text_low.split():
                self._replace(registry, Claim("Mounting Type", "Leg", None, "DIRECT", ["input_row"], 0.85))
        return registry

    @staticmethod
    def _replace(registry: ClaimRegistry, claim: Claim):
        registry.claims = [c for c in registry.claims if c.attribute != claim.attribute]
        registry.add(claim)


class AbrasiveDiscProcessor(CategoryProcessor):
    classpath_match = "Tools & Equipment>Power Tool Accessories>Abrasive Discs"


class CutOffDiscProcessor(CategoryProcessor):
    classpath_match = "Tools & Equipment>Power Tool Accessories>Cut-Off Discs"


_REGISTRY: dict[str, CategoryProcessor] = {
    cls.classpath_match: cls() for cls in (DishwasherProcessor, AbrasiveDiscProcessor, CutOffDiscProcessor)
}
_GENERIC = CategoryProcessor()


def get_processor(classpath: str | None) -> CategoryProcessor:
    if classpath and classpath in _REGISTRY:
        return _REGISTRY[classpath]
    return _GENERIC
