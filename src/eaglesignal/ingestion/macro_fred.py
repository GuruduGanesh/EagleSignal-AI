"""SKILL-040 Macro/economic connector (FRED + keyless fallback).

Primary source is the Federal Reserve Bank of St. Louis FRED API when
FRED_API_KEY is configured. When no key is present we still pull a real macro
regime from **keyless live sources** (yfinance market proxies + U.S. Treasury
FiscalData), so the macro tab is never empty. Only genuinely unreachable data
degrades to a neutral snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("ingestion.macro")

# series_id -> friendly name
SERIES = {
    "DGS10": "treasury_10y",
    "DGS2": "treasury_2y",
    "T10Y2Y": "yield_curve_10y_2y",
    "FEDFUNDS": "fed_funds",
    "UNRATE": "unemployment",
    "CPIAUCSL": "cpi",
    "VIXCLS": "vix",
    "DCOILWTICO": "wti_oil",
}

# Keyless live market proxies (Yahoo Finance). Yahoo now quotes ^TNX/^FVX/^TYX
# directly as the percent yield (e.g. ^TNX = 4.45), so no scaling is needed.
YF_PROXIES = {
    "^TNX": ("treasury_10y", 1.0),
    "^FVX": ("treasury_5y", 1.0),
    "^TYX": ("treasury_30y", 1.0),
    "^VIX": ("vix", 1.0),
    "CL=F": ("wti_oil", 1.0),
    "DX-Y.NYB": ("dollar_index", 1.0),
}


@dataclass
class MacroSnapshot:
    values: dict[str, float] = field(default_factory=dict)
    available: bool = False
    note: str = ""
    source: str = ""
    as_of: str = ""


def _latest(series_id: str, api_key: str) -> Optional[float]:
    try:
        import requests

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,
        }
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return None
        for obs in resp.json().get("observations", []):
            if obs.get("value") not in (".", "", None):
                return float(obs["value"])
    except Exception as exc:
        log.warning("FRED %s failed: %s", series_id, exc)
    return None


def _yf_last(symbol: str) -> Optional[float]:
    """Latest close for a Yahoo Finance macro proxy (keyless)."""
    try:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(period="5d")
        if hist is None or hist.empty:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception as exc:
        log.warning("yfinance macro %s failed: %s", symbol, exc)
        return None


def _treasury_avg_rate() -> Optional[float]:
    """U.S. Treasury FiscalData average interest rate on total marketable debt
    (keyless, no token)."""
    try:
        import requests

        url = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
               "v2/accounting/od/avg_interest_rates")
        params = {"sort": "-record_date", "page[size]": "1",
                  "filter": "security_desc:eq:Total Marketable"}
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return None
        data = (resp.json() or {}).get("data", [])
        if data:
            return float(data[0]["avg_interest_rate_amt"])
    except Exception as exc:
        log.warning("Treasury avg rate failed: %s", exc)
    return None


def _fetch_keyless() -> MacroSnapshot:
    """Build a real macro snapshot without any API key."""
    from datetime import datetime, timezone

    values: dict[str, float] = {}
    for sym, (name, mult) in YF_PROXIES.items():
        v = _yf_last(sym)
        if v is not None:
            values[name] = round(v * mult, 4)

    # Derived 10y-5y curve proxy when both legs are present.
    if "treasury_10y" in values and "treasury_5y" in values:
        values["yield_curve_10y_5y"] = round(values["treasury_10y"] - values["treasury_5y"], 3)

    avg_rate = _treasury_avg_rate()
    if avg_rate is not None:
        values["treasury_avg_interest_rate"] = round(avg_rate, 3)

    if not values:
        return MacroSnapshot(available=False,
                             note="Macro sources unreachable from this host; neutral regime assumed.")
    return MacroSnapshot(
        values=values, available=True,
        source="keyless_live (yfinance proxies + Treasury FiscalData)",
        as_of=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        note="Live keyless macro (no FRED key). Set FRED_API_KEY for the full official series.",
    )


def fetch_macro() -> MacroSnapshot:
    from datetime import datetime, timezone

    key = get_settings().fred_api_key
    if not key:
        # No FRED key -> still pull real macro from keyless live sources.
        return _fetch_keyless()

    values: dict[str, float] = {}
    for sid, name in SERIES.items():
        v = _latest(sid, key)
        if v is not None:
            values[name] = v
    if values:
        return MacroSnapshot(
            values=values, available=True, source="fred",
            as_of=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    # FRED key set but unreachable -> fall back to keyless live sources.
    log.warning("FRED returned no data; falling back to keyless live macro.")
    return _fetch_keyless()
