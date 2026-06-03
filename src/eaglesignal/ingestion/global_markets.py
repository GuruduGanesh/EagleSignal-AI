"""SKILL-081 Global index collector (US + Europe + Asia).

Fetches major world index proxies through the same real-data provider chain used
for equities (no synthetic data). Used for cross-market correlation and a global
risk-on/risk-off regime read. Index symbols are Yahoo-style (`^`-prefixed); for
providers that don't carry index symbols the chain simply falls back until one
does (yfinance covers all of these).

Default coverage (override with the GLOBAL_INDEXES env var):

* US     — S&P 500 (^GSPC), Nasdaq 100 (^NDX), Dow (^DJI), Russell 2000 (^RUT), VIX (^VIX)
* Europe — DAX (^GDAXI), CAC 40 (^FCHI), FTSE 100 (^FTSE), Euro Stoxx 50 (^STOXX50E)
* Asia   — Nikkei 225 (^N225), Hang Seng (^HSI), Shanghai (000001.SS), NSE Nifty 50 (^NSEI), KOSPI (^KS11)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("ingestion.global_markets")

# name -> (yahoo symbol, region)
DEFAULT_INDEXES: dict[str, tuple[str, str]] = {
    "S&P 500": ("^GSPC", "US"),
    "Nasdaq 100": ("^NDX", "US"),
    "Dow Jones": ("^DJI", "US"),
    "Russell 2000": ("^RUT", "US"),
    "VIX": ("^VIX", "US"),
    "DAX": ("^GDAXI", "Europe"),
    "CAC 40": ("^FCHI", "Europe"),
    "FTSE 100": ("^FTSE", "Europe"),
    "Euro Stoxx 50": ("^STOXX50E", "Europe"),
    "Nikkei 225": ("^N225", "Asia"),
    "Hang Seng": ("^HSI", "Asia"),
    "Shanghai": ("000001.SS", "Asia"),
    "NSE Nifty 50": ("^NSEI", "Asia"),
    "KOSPI": ("^KS11", "Asia"),
}


@dataclass
class GlobalIndex:
    name: str
    symbol: str
    region: str
    bars: pd.DataFrame
    last: float | None = None
    day_change_pct: float | None = None


@dataclass
class GlobalMarketsSnapshot:
    indexes: dict[str, GlobalIndex] = field(default_factory=dict)
    available: bool = False
    advancers: int = 0
    decliners: int = 0
    regime_note: str = ""

    def bars_map(self) -> dict[str, pd.DataFrame]:
        return {name: gi.bars for name, gi in self.indexes.items() if gi.bars is not None and len(gi.bars) >= 30}


def _configured_indexes() -> dict[str, tuple[str, str]]:
    raw = (get_settings().global_indexes or "").strip()
    if not raw:
        return DEFAULT_INDEXES
    # Format: "Name=SYMBOL:Region, Name2=SYMBOL2:Region2"
    out: dict[str, tuple[str, str]] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, rest = part.partition("=")
        sym, _, region = rest.partition(":")
        out[name.strip()] = (sym.strip(), (region.strip() or "Global"))
    return out or DEFAULT_INDEXES


def fetch_global_indexes() -> GlobalMarketsSnapshot:
    from .market_data import fetch_history

    snap = GlobalMarketsSnapshot()
    for name, (symbol, region) in _configured_indexes().items():
        try:
            md = fetch_history(symbol)
            if not md.ok:
                continue
            last = md.current_price or md.last_close
            chg = md.day_change_pct
            snap.indexes[name] = GlobalIndex(
                name=name, symbol=symbol, region=region, bars=md.bars,
                last=round(float(last), 2) if last is not None else None,
                day_change_pct=round(float(chg), 2) if chg is not None else None,
            )
            if chg is not None and name != "VIX":
                if chg > 0:
                    snap.advancers += 1
                elif chg < 0:
                    snap.decliners += 1
        except Exception as exc:
            log.warning("Global index %s (%s) failed: %s", name, symbol, exc)
            continue

    snap.available = bool(snap.indexes)
    if snap.available:
        total = snap.advancers + snap.decliners
        breadth = (snap.advancers / total) if total else 0.5
        tone = "risk-on" if breadth > 0.6 else "risk-off" if breadth < 0.4 else "mixed"
        snap.regime_note = (
            f"{len(snap.indexes)} world indexes; {snap.advancers} up / {snap.decliners} down "
            f"({breadth:.0%} advancing) — global tape {tone}."
        )
    else:
        snap.regime_note = "Global index data unavailable."
    return snap
