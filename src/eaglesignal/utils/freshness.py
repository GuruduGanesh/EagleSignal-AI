"""SKILL-004 Data Freshness Guard + SKILL-005 Source Reliability Ranker.

Stale data is downgraded, never silently treated as fresh.
"""
from __future__ import annotations

from datetime import datetime, timezone

# Reliability ranking from DATA_SOURCES.md section 7.
RELIABILITY = {
    "official": 100,
    "exchange": 90,
    "news": 80,
    "aggregator": 70,
    "search": 50,
    "social": 35,
    "rumor": 10,
    "unknown": 50,
}

# Freshness SLA in minutes by data type (DATA_SOURCES.md section 6).
FRESHNESS_SLA_MIN = {
    "intraday_price": 15,
    "daily_price": 60 * 24,
    "options_chain": 15,
    "sec_filing": 60 * 24,
    "macro": 60 * 24 * 45,
    "news": 60 * 12,
    "social": 60 * 24,
    "fundamentals": 60 * 24 * 120,
}


def reliability_score(source_type: str) -> int:
    return RELIABILITY.get(source_type, 50)


def freshness_score(published_at: datetime | None, data_type: str) -> tuple[int, int]:
    """Return (freshness_score 0..100, age_minutes). None timestamp -> low score."""
    if published_at is None:
        return 40, -1
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_min = max(0, int((datetime.now(timezone.utc) - published_at).total_seconds() // 60))
    sla = FRESHNESS_SLA_MIN.get(data_type, 60 * 24)
    if age_min <= sla:
        return 100, age_min
    # Linear decay to 0 over 4x the SLA window.
    over = age_min - sla
    score = max(0, int(100 * (1 - over / (3 * sla))))
    return score, age_min
