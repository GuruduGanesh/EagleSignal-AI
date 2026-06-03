"""SKILL-056 Sector/ticker policy-impact mapper.

Links market-wide government events (FDA recalls, DOJ/FTC actions, Federal
Register / GDELT policy news) to the *specific* watchlist names they plausibly
affect — instead of leaving them as undifferentiated market context.

Two match tiers, deliberately conservative (SKILL-056 validation: "avoid
overbroad mapping"):

* ``direct``   — the event title names the company itself (normalized, suffix-
  stripped). High confidence. Regulatory actions (recall/antitrust) get a small
  negative polarity because they are typically adverse.
* ``thematic`` — only for broad ``policy`` headlines that mention a sector keyword
  mapped from the asset's strategy tags. Treated as neutral *context* (polarity 0)
  so it explains/colours a name without fabricating a directional bias.

FDA recalls of unrelated firms and FTC consent orders against unrelated small
companies therefore do NOT attach to mega-cap tech just because they share a
sector — only a direct name match (or a sector-themed policy headline) links.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..ingestion.government import GovEvent, GovSnapshot
from ..schemas import AssetEntity

# Corporate suffixes / filler tokens removed before name matching.
_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "lp",
    "ltd", "limited", "plc", "holdings", "group", "trust", "the", "class",
    "common", "stock", "etf", "fund",
}

# Generic business words that are too common to be a distinctive brand token —
# never used as the sole basis for a direct match (avoids "Medical"/"Digital"
# matching unrelated firms).
_GENERIC = {
    "medical", "systems", "system", "digital", "works", "media", "technologies",
    "technology", "solutions", "services", "global", "international", "national",
    "american", "health", "healthcare", "pharma", "pharmaceuticals", "labs",
    "laboratories", "industries", "partners", "capital", "financial", "energy",
    "motors", "products", "brands", "enterprises", "networks", "data",
}

# Thematic sector keywords keyed by watchlist strategy tags. Conservative: each
# keyword should be specific enough that its presence in a *policy* headline
# genuinely implicates the sector.
_TAG_KEYWORDS: dict[str, list[str]] = {
    "semiconductors": ["semiconductor", "chip", "export control", "chips act"],
    "ai": ["artificial intelligence", "ai regulation", "ai safety", "ai export"],
    "technology": ["big tech", "antitrust", "app store", "section 230", "data privacy"],
    "ev": ["electric vehicle", "ev tax credit", "ev subsidy", "auto tariff"],
    "cloud": ["cloud", "federal cloud", "data center"],
    "small_caps": ["small business", "regional bank"],
    "energy": ["crude", "opec", "energy policy", "drilling"],
    "healthcare": ["fda", "drug pricing", "medicare", "medicaid"],
    "pharma": ["fda", "drug pricing", "clinical"],
    "biotech": ["fda", "clinical trial", "drug approval"],
}


@dataclass
class PolicyImpact:
    event: GovEvent
    match_kind: str  # "direct" | "thematic:<keyword>"
    polarity: float  # -1..+1; negative for adverse regulatory actions


def _brand_tokens(company_name: str | None) -> list[str]:
    """Distinctive (non-suffix, non-generic) tokens, in order. The first is the
    brand we require for a direct match; generic words like 'Medical' are dropped
    so they can't match an unrelated firm on their own."""
    if not company_name:
        return []
    cleaned = re.sub(r"[^a-z0-9 ]", " ", company_name.lower())
    return [
        t for t in cleaned.split()
        if t and t not in _SUFFIXES and t not in _GENERIC and len(t) > 2
    ]


def _keywords_for(asset: AssetEntity) -> list[str]:
    kws: list[str] = []
    tags = [t.lower() for t in asset.strategy_tags]
    if asset.sector:
        tags.append(asset.sector.lower())
    if asset.industry:
        tags.append(asset.industry.lower())
    for tag in tags:
        kws.extend(_TAG_KEYWORDS.get(tag, []))
    return sorted(set(kws))


def map_impacts(asset: AssetEntity, gov: GovSnapshot | None) -> list[PolicyImpact]:
    if gov is None or not gov.available or not gov.events:
        return []
    tokens = _brand_tokens(asset.company_name)
    brand = tokens[0] if tokens else None  # primary brand token must be present
    keywords = _keywords_for(asset)
    impacts: list[PolicyImpact] = []
    seen: set[str] = set()

    for ev in gov.events:
        title = ev.title.lower()
        key = (ev.source, ev.title)
        if key in seen:
            continue

        # Tier 1: direct company-name match — require the distinctive brand token.
        if brand and re.search(rf"\b{re.escape(brand)}\b", title):
            polarity = -0.3 if ev.kind in ("fda", "antitrust") else -0.1
            impacts.append(PolicyImpact(event=ev, match_kind="direct", polarity=polarity))
            seen.add(key)
            continue

        # Tier 2: thematic sector match — only for broad policy/admin headlines.
        if ev.kind in ("policy", "trump_admin") and keywords:
            hit = next((k for k in keywords if k in title), None)
            if hit:
                impacts.append(PolicyImpact(event=ev, match_kind=f"thematic:{hit}", polarity=0.0))
                seen.add(key)

    return impacts
