"""SKILL — Earnings & corporate-event calendar (§0.4).

Fetches the next scheduled earnings date for a ticker (keyless, via yfinance) so
the options engine can flag IV-crush risk on any expiry that spans an earnings
event (§1.5). Real data only — returns ``available=False`` and degrades
gracefully when the provider has no date. It never fabricates a date.

This is intentionally lightweight and best-effort: the daily scan is already
network-bound, so a single per-ticker lookup is added behind a cache and wrapped
so a provider hiccup can never break a prediction.
"""
from __future__ import annotations

import concurrent.futures
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from ..utils.logging import get_logger

log = get_logger("ingestion.earnings")

# Tiny per-process cache so repeated calls in one scan (and the snapshot logger)
# do not re-hit the provider for the same ticker.
_CACHE: dict[str, "EarningsInfo"] = {}

# Hard wall-clock budget for the (network) earnings lookup. yfinance's
# get_earnings_dates/.calendar can hang or get throttled; without a ceiling that
# stalls a whole scan worker. On timeout we cache "unavailable" and move on.
_FETCH_TIMEOUT_S = float(os.environ.get("EARNINGS_FETCH_TIMEOUT", "6"))
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="earnings")


@dataclass
class EarningsInfo:
    ticker: str
    next_earnings_date: Optional[str] = None  # ISO yyyy-mm-dd
    days_to_earnings: Optional[int] = None
    is_estimate: bool = False
    source: str = "unavailable"
    available: bool = False

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "next_earnings_date": self.next_earnings_date,
            "days_to_earnings": self.days_to_earnings,
            "is_estimate": self.is_estimate,
            "source": self.source,
            "available": self.available,
        }


def _coerce_date(value) -> Optional[date]:
    """Accept the many shapes yfinance returns (date, datetime, Timestamp, str)."""
    if value is None:
        return None
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        # pandas.Timestamp has .date(); str parses below.
        if hasattr(value, "date") and callable(value.date):
            return value.date()
        s = str(value).strip()[:10]
        y, m, d = (int(x) for x in s.split("-"))
        return date(y, m, d)
    except Exception:
        return None


def _next_future_date(candidates: list[date], today: date) -> Optional[tuple[date, bool]]:
    """Pick the soonest date that is today or in the future; else the most recent
    past date flagged as an estimate (so the engine still knows roughly when)."""
    future = sorted(d for d in candidates if d >= today)
    if future:
        return future[0], False
    past = sorted((d for d in candidates if d < today), reverse=True)
    if past:
        return past[0], True
    return None


def fetch_earnings(ticker: str, today: Optional[date] = None) -> EarningsInfo:
    """Best-effort next-earnings lookup. Keyless. Never raises and never blocks a
    scan worker longer than ``EARNINGS_FETCH_TIMEOUT`` seconds."""
    sym = (ticker or "").strip().upper()
    if not sym:
        return EarningsInfo(ticker=ticker)
    if sym in _CACHE:
        return _CACHE[sym]

    today = today or date.today()
    try:
        info = _EXECUTOR.submit(_fetch_impl, sym, today).result(timeout=_FETCH_TIMEOUT_S)
    except concurrent.futures.TimeoutError:
        log.warning("earnings lookup for %s timed out after %.0fs; marking unavailable", sym, _FETCH_TIMEOUT_S)
        info = EarningsInfo(ticker=sym)
    except Exception as exc:
        log.warning("earnings lookup for %s failed: %s", sym, exc)
        info = EarningsInfo(ticker=sym)
    _CACHE[sym] = info
    return info


def _fetch_impl(sym: str, today: date) -> EarningsInfo:
    """The actual (network) lookup, run under a timeout by ``fetch_earnings``."""
    candidates: list[date] = []
    source = "unavailable"
    try:
        import yfinance as yf

        tk = yf.Ticker(sym)

        # 1) get_earnings_dates() — richest source (past + a few future rows).
        try:
            df = tk.get_earnings_dates(limit=12)  # type: ignore[attr-defined]
            if df is not None and not df.empty:
                for idx in df.index:
                    d = _coerce_date(idx)
                    if d:
                        candidates.append(d)
                if candidates:
                    source = "yfinance_earnings_dates"
        except Exception:
            pass

        # 2) .calendar — dict (new yfinance) or DataFrame (old).
        if not candidates:
            try:
                cal = tk.calendar
                raw: list = []
                if isinstance(cal, dict):
                    raw = cal.get("Earnings Date") or cal.get("Earnings Date High") or []
                    if not isinstance(raw, (list, tuple)):
                        raw = [raw]
                else:  # DataFrame
                    try:
                        row = cal.loc["Earnings Date"]
                        raw = list(row.values)
                    except Exception:
                        raw = []
                for v in raw:
                    d = _coerce_date(v)
                    if d:
                        candidates.append(d)
                if candidates:
                    source = "yfinance_calendar"
            except Exception:
                pass
    except Exception as exc:  # provider import/availability failure
        log.warning("earnings fetch failed for %s: %s", sym, exc)

    info = EarningsInfo(ticker=sym)
    picked = _next_future_date(candidates, today) if candidates else None
    if picked:
        d, is_est = picked
        info.next_earnings_date = d.isoformat()
        info.days_to_earnings = (d - today).days
        info.is_estimate = is_est
        info.source = source
        info.available = True
    return info
