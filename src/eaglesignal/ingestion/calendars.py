"""Market-moving event calendars (research only) — §3 data sources.

Three honest, mostly-keyless calendars feed the prediction engine's event-risk
awareness (§2 "measured, not guessed"):

* **Economic / financial calendar** — high-impact U.S. macro releases. FOMC
  decision days are read from the curated ``config/event_calendar.yml`` (only
  officially-published dates; never guessed). Recurring releases that are
  *rule-derivable* are generated deterministically: monthly **non-farm payrolls**
  (first Friday) and weekly **initial jobless claims** (Thursdays). CPI/PCE/GDP
  exact dates drift month to month, so they are intentionally NOT fabricated —
  add them to the YAML when you have the official date.
* **Political / policy calendar** — FOMC is the principal scheduled market-mover
  here; ad-hoc policy events arrive live through ``government.py``.
* **Company calendar** — next earnings date per ticker, pulled live (keyless)
  from the earnings connector.

Everything degrades gracefully: a missing YAML, a provider hiccup, or a year
with no curated dates simply yields fewer events — never an error, never a fake
date.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

import yaml

from ..config import ROOT
from ..utils.logging import get_logger

log = get_logger("ingestion.calendars")

_HIGH = "high"


@dataclass
class CalendarEvent:
    date: str                 # ISO yyyy-mm-dd
    kind: str                 # fomc | nfp | jobless_claims | cpi | earnings | ...
    title: str
    impact: str               # high | medium | low
    scope: str                # market | ticker
    ticker: Optional[str] = None
    source: str = ""
    days_away: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "date": self.date, "kind": self.kind, "title": self.title,
            "impact": self.impact, "scope": self.scope, "ticker": self.ticker,
            "source": self.source, "days_away": self.days_away,
        }


@lru_cache(maxsize=1)
def _curated() -> tuple[list[dict], str]:
    p = ROOT / "config" / "event_calendar.yml"
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return list(data.get("events", []) or []), str(data.get("source", "curated"))
    except Exception as exc:
        log.warning("event_calendar.yml unreadable: %s", exc)
        return [], "curated"


def _first_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    # weekday(): Mon=0 .. Sun=6; Friday=4
    return d + timedelta(days=(4 - d.weekday()) % 7)


def _rule_based(start: date, end: date) -> list[CalendarEvent]:
    """Deterministic recurring releases inside [start, end]."""
    out: list[CalendarEvent] = []
    # Monthly non-farm payrolls — first Friday of each month (high impact).
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        ff = _first_friday(y, m)
        if start <= ff <= end:
            out.append(CalendarEvent(
                date=ff.isoformat(), kind="nfp", title="Non-farm payrolls / jobs report",
                impact=_HIGH, scope="market", source="BLS schedule (first Friday rule)",
            ))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    # Weekly initial jobless claims — every Thursday (medium impact).
    d = start + timedelta(days=(3 - start.weekday()) % 7)  # next Thursday
    while d <= end:
        out.append(CalendarEvent(
            date=d.isoformat(), kind="jobless_claims", title="Initial jobless claims",
            impact="medium", scope="market", source="DOL weekly (Thursday rule)",
        ))
        d += timedelta(days=7)
    return out


def market_events(today: Optional[date] = None, days_ahead: int = 21) -> list[CalendarEvent]:
    """Economic + political (FOMC) market-wide events in the next ``days_ahead`` days."""
    today = today or date.today()
    end = today + timedelta(days=days_ahead)
    events: list[CalendarEvent] = []

    curated, src = _curated()
    for e in curated:
        try:
            y, mo, dd = (int(x) for x in str(e["date"]).split("-"))
            ed = date(y, mo, dd)
        except Exception:
            continue
        if today <= ed <= end:
            events.append(CalendarEvent(
                date=ed.isoformat(), kind=str(e.get("kind", "event")),
                title=str(e.get("title", e.get("kind", "event"))),
                impact=str(e.get("impact", "medium")), scope="market", source=src,
            ))
    events.extend(_rule_based(today, end))

    for ev in events:
        ev.days_away = (date.fromisoformat(ev.date) - today).days
    events.sort(key=lambda x: (x.date, x.impact != _HIGH))
    return events


def earnings_events(tickers: list[str], today: Optional[date] = None,
                    days_ahead: int = 45) -> list[CalendarEvent]:
    """Live (keyless) next-earnings dates for the given tickers, within window."""
    from .earnings import fetch_earnings  # local import avoids import cycle

    today = today or date.today()
    out: list[CalendarEvent] = []
    for t in tickers:
        info = fetch_earnings(t, today=today)
        if info.available and info.days_to_earnings is not None and 0 <= info.days_to_earnings <= days_ahead:
            out.append(CalendarEvent(
                date=info.next_earnings_date or "", kind="earnings",
                title=f"{t} earnings report" + (" (est.)" if info.is_estimate else ""),
                impact=_HIGH, scope="ticker", ticker=t, source=info.source,
                days_away=info.days_to_earnings,
            ))
    out.sort(key=lambda x: x.days_away if x.days_away is not None else 9999)
    return out


def upcoming_events(tickers: Optional[list[str]] = None, today: Optional[date] = None,
                    days_ahead: int = 21) -> list[dict]:
    """Combined market + (optional) earnings calendar as plain dicts for the API."""
    today = today or date.today()
    evs = market_events(today, days_ahead)
    if tickers:
        evs = evs + earnings_events(tickers, today, days_ahead)
    evs.sort(key=lambda x: (x.days_away if x.days_away is not None else 9999, x.impact != _HIGH))
    return [e.to_dict() for e in evs]


def events_within_horizon(horizon_days: int, today: Optional[date] = None,
                          days_to_earnings: Optional[int] = None,
                          ticker: Optional[str] = None) -> list[CalendarEvent]:
    """High/medium-impact events that fall inside a prediction horizon.

    ``days_to_earnings`` is passed in from the engine (already fetched there) so
    this does no extra network call. Market macro events are computed locally.
    """
    today = today or date.today()
    out = [e for e in market_events(today, horizon_days)
           if e.days_away is not None and 0 <= e.days_away <= horizon_days]
    if days_to_earnings is not None and 0 <= days_to_earnings <= horizon_days:
        out.append(CalendarEvent(
            date=(today + timedelta(days=days_to_earnings)).isoformat(),
            kind="earnings", title=f"{ticker or 'company'} earnings report",
            impact=_HIGH, scope="ticker", ticker=ticker,
            source="earnings connector", days_away=days_to_earnings,
        ))
    out.sort(key=lambda x: x.days_away if x.days_away is not None else 9999)
    return out
