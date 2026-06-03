"""SKILL-030 Options chain collector (multi-source, multi-expiry).

Pulls several short-dated expirations so the engine can compare expiries and pick
the highest-confidence ones. Real data only — returns ``available=False`` (never
fabricated data) when no chain exists.

Source fallback chain (all real, delayed/EOD market data):
  1. yfinance option_chain (primary)
  2. CBOE delayed-quote JSON (https://cdn.cboe.com/api/global/delayed_quotes/options/<SYM>.json)

If both fail the chain degrades to ``available=False`` and the options engine
falls back to a historical-volatility expected move.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from ..utils.logging import get_logger
from .http_util import throttled_get

log = get_logger("ingestion.options")


@dataclass
class ExpiryChain:
    """One expiration's calls/puts plus its days-to-expiry."""

    expiration: str
    days_to_expiry: int
    calls: pd.DataFrame
    puts: pd.DataFrame


@dataclass
class OptionsChain:
    ticker: str
    expiration: Optional[str] = None  # nearest selected expiry (back-compat)
    expirations: list[str] = field(default_factory=list)  # all listed expiries
    spot: Optional[float] = None
    calls: Optional[pd.DataFrame] = None  # nearest expiry calls (back-compat)
    puts: Optional[pd.DataFrame] = None  # nearest expiry puts (back-compat)
    chains: list[ExpiryChain] = field(default_factory=list)  # several expiries
    source: str = "unavailable"
    available: bool = False


def _dte(expiry: str) -> Optional[int]:
    try:
        y, m, d = (int(x) for x in expiry.split("-"))
        return (date(y, m, d) - date.today()).days
    except Exception:
        return None


def _select_expiries(expirations: list[str], max_n: int = 5,
                     min_days: int = 5, max_days: int = 60) -> list[str]:
    """Pick up to ``max_n`` short-dated expiries while respecting the minimum DTE.

    The product is focused on short-term options, but not contracts with fewer
    than ``min_days`` calendar days remaining. If the preferred 5-60D window is
    empty, use the next future expiries at or above ``min_days``; never fall back
    to under-minimum DTE for recommendations.
    """
    parsed = sorted((d, e) for e in expirations if (d := _dte(e)) is not None)
    if not parsed:
        return expirations[:max_n]
    window = [e for d, e in parsed if min_days <= d <= max_days]
    if len(window) >= 1:
        return window[:max_n]
    future = [e for d, e in parsed if d >= min_days]
    return future[:max_n]


# --------------------------------------------------------------------------- #
# Source 1 — yfinance
# --------------------------------------------------------------------------- #
def _fetch_yfinance(ticker: str, spot: Optional[float], max_expiries: int, min_days: int) -> Optional[OptionsChain]:
    try:
        import yfinance as yf

        tk = yf.Ticker(ticker)
        expirations = list(tk.options or [])
        if not expirations:
            return None
        selected = _select_expiries(expirations, max_n=max_expiries, min_days=min_days)
        if not selected:
            return None
        chains: list[ExpiryChain] = []
        for exp in selected:
            try:
                oc = tk.option_chain(exp)
                if oc.calls is None or oc.puts is None or (oc.calls.empty and oc.puts.empty):
                    continue
                chains.append(ExpiryChain(
                    expiration=exp, days_to_expiry=_dte(exp) or 0,
                    calls=oc.calls, puts=oc.puts,
                ))
            except Exception as exc:
                log.warning("yfinance expiry %s for %s failed: %s", exp, ticker, exc)
                continue
        if not chains:
            return None
        first = chains[0]
        return OptionsChain(
            ticker=ticker, expiration=first.expiration, expirations=expirations,
            spot=spot, calls=first.calls, puts=first.puts, chains=chains,
            source="yfinance", available=True,
        )
    except Exception as exc:
        log.warning("yfinance options fetch failed for %s: %s", ticker, exc)
        return None


# --------------------------------------------------------------------------- #
# Source 2 — CBOE delayed quotes (keyless JSON, real delayed data)
# --------------------------------------------------------------------------- #
def _fetch_cboe(ticker: str, spot: Optional[float], max_expiries: int, min_days: int) -> Optional[OptionsChain]:
    """CBOE publishes a delayed-quote JSON per symbol. Each option carries an
    embedded expiry/right/strike in its ``option`` id (e.g. AAPL240920C00190000).
    We group by expiry and rebuild yfinance-shaped calls/puts frames so the rest
    of the pipeline is source-agnostic."""
    sym = ticker.strip().upper()
    for url in (
        f"https://cdn.cboe.com/api/global/delayed_quotes/options/{sym}.json",
        f"https://cdn.cboe.com/api/global/delayed_quotes/options/_{sym}.json",  # index symbols
    ):
        try:
            resp = throttled_get("cboe", url, min_interval=1.0, timeout=15, retries=1)
            if resp is None or resp.status_code != 200:
                continue
            payload = resp.json().get("data", {})
            options = payload.get("options", [])
            if not options:
                continue
            cboe_spot = payload.get("current_price") or spot
            rows_by_expiry: dict[str, dict[str, list]] = {}
            for o in options:
                oid = str(o.get("option", ""))
                # Format: <ROOT><YYMMDD><C|P><strike*1000 padded 8>
                if len(oid) < 16:
                    continue
                body = oid[len(sym):] if oid.startswith(sym) else oid
                # find the date+right+strike tail (last 15 chars: 6 date,1 right,8 strike)
                tail = oid[-15:]
                yy, mm, dd = tail[0:2], tail[2:4], tail[4:6]
                right = tail[6]
                try:
                    strike = int(tail[7:]) / 1000.0
                    expiry = f"20{yy}-{mm}-{dd}"
                except Exception:
                    continue
                rec = {
                    "contractSymbol": oid,
                    "strike": strike,
                    "lastPrice": o.get("last_trade_price", 0.0),
                    "bid": o.get("bid", 0.0),
                    "ask": o.get("ask", 0.0),
                    "volume": o.get("volume", 0) or 0,
                    "openInterest": o.get("open_interest", 0) or 0,
                    "impliedVolatility": o.get("iv", 0.0) or 0.0,
                }
                bucket = rows_by_expiry.setdefault(expiry, {"C": [], "P": []})
                if right in ("C", "P"):
                    bucket[right].append(rec)
            if not rows_by_expiry:
                continue
            selected = _select_expiries(list(rows_by_expiry.keys()), max_n=max_expiries, min_days=min_days)
            if not selected:
                continue
            chains: list[ExpiryChain] = []
            for exp in selected:
                b = rows_by_expiry.get(exp)
                if not b:
                    continue
                calls = pd.DataFrame(b["C"]) if b["C"] else pd.DataFrame()
                puts = pd.DataFrame(b["P"]) if b["P"] else pd.DataFrame()
                if calls.empty and puts.empty:
                    continue
                chains.append(ExpiryChain(
                    expiration=exp, days_to_expiry=_dte(exp) or 0, calls=calls, puts=puts,
                ))
            if not chains:
                continue
            first = chains[0]
            return OptionsChain(
                ticker=ticker, expiration=first.expiration,
                expirations=sorted(rows_by_expiry.keys()), spot=cboe_spot,
                calls=first.calls, puts=first.puts, chains=chains,
                source="cboe_delayed", available=True,
            )
        except Exception as exc:
            log.warning("CBOE options fetch failed for %s: %s", ticker, exc)
            continue
    return None


def fetch_options(
    ticker: str,
    spot: Optional[float] = None,
    max_expiries: int = 5,
    min_days: int = 5,
) -> OptionsChain:
    """Fetch up to ``max_expiries`` short-dated chains, trying each real source in
    order. Never fabricates data."""
    for fetcher in (_fetch_yfinance, _fetch_cboe):
        chain = fetcher(ticker, spot, max_expiries, min_days)
        if chain and chain.available and chain.chains:
            log.info("options for %s via %s (%d expiries)", ticker, chain.source, len(chain.chains))
            return chain
    return OptionsChain(ticker=ticker, available=False)
