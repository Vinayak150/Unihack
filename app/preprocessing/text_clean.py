"""Deterministic text cleanup — no LLM calls. Casing, punctuation, whitespace,
token splitting used by every downstream stage."""
from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_MPN_PREFIX_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9\-\./]{2,})\s+")


def normalize_whitespace(text: str) -> str:
    return _WS_RE.sub(" ", (text or "")).strip()


def strip_leading_mpn(desc: str, mpn: str | None) -> str:
    """Part_Desc frequently repeats the MPN as its first token
    ('PDSH4816AF Dishwasher SS - Display Only'). Strip it before
    running keyword/category heuristics on the remaining free text."""
    desc = normalize_whitespace(desc)
    if mpn:
        mpn_norm = mpn.strip().upper()
        if desc.upper().startswith(mpn_norm):
            return normalize_whitespace(desc[len(mpn_norm):])
    m = _MPN_PREFIX_RE.match(desc)
    if m and any(c.isdigit() for c in m.group(1)):
        return normalize_whitespace(desc[m.end():])
    return desc


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\.\/#'\"]*", text or "")


def title_case_brandsafe(text: str) -> str:
    """Title-cases free text while leaving all-caps brand-style acronyms
    (SS, LED, GFCI, PVC...) and existing internal caps untouched."""
    out = []
    for tok in (text or "").split(" "):
        if not tok:
            out.append(tok)
            continue
        if tok.isupper() and len(tok) <= 5:
            out.append(tok)
        elif tok[0].isalpha():
            out.append(tok[0].upper() + tok[1:])
        else:
            out.append(tok)
    return " ".join(out)


def strip_trailing_notes(desc: str) -> tuple[str, list[str]]:
    """Splits off trailing ' - Note' style qualifiers such as
    '- Display Only' so they can be captured as claims/flags rather than
    silently swallowed into a generic description."""
    parts = [p.strip() for p in re.split(r"\s+-\s+", desc) if p.strip()]
    if len(parts) <= 1:
        return desc.strip(), []
    return parts[0], parts[1:]
