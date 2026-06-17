"""Canonical universe for tradeable index-option underlyings.

Equity research can still score stocks, but option trade recommendations are
restricted to these cash-settled/index products so stock tickers do not leak
into execution tabs.
"""
from __future__ import annotations

from ..schemas import AssetEntity, AssetType


INDEX_OPTION_UNDERLYINGS: dict[str, str] = {
    "SPX": "S&P 500 Index options",
    "XSP": "Mini S&P 500 Index options",
    "NDX": "Nasdaq-100 Index options",
    "XND": "Mini Nasdaq-100 Index options",
    "RUT": "Russell 2000 Index options",
    "VIX": "Cboe Volatility Index options",
    "DJX": "Dow Jones Industrial Average Index options",
    "OEX": "S&P 100 Index options",
}


INDEX_MARKET_ALIASES: dict[str, str] = {
    "SPX": "^GSPC",
    "XSP": "^GSPC",
    "NDX": "^NDX",
    "XND": "^NDX",
    "RUT": "^RUT",
    "VIX": "^VIX",
    "DJX": "^DJI",
    "OEX": "^OEX",
}


# Mini/scaled index tickers quote at a fraction of their parent index used for
# market data (the alias above points to the parent). Scale parent OHLCV down to
# the mini's quoted level so the underlying matches the mini option strikes.
#   XSP = SPX / 10 ; XND = NDX / 100 ; DJX = DJIA / 100
INDEX_PRICE_SCALE: dict[str, float] = {"XSP": 0.1, "XND": 0.01, "DJX": 0.01}


def index_price_scale(ticker: str | None) -> float:
    return INDEX_PRICE_SCALE.get((ticker or "").upper(), 1.0)


def is_index_option_ticker(ticker: str | None) -> bool:
    return bool(ticker) and ticker.upper() in INDEX_OPTION_UNDERLYINGS


def is_index_option_asset(asset: AssetEntity | object) -> bool:
    ticker = getattr(asset, "ticker", None)
    asset_type = getattr(asset, "asset_type", None)
    return is_index_option_ticker(ticker) or asset_type == AssetType.index or str(asset_type) == "index"


def market_data_symbol(ticker: str) -> str:
    return INDEX_MARKET_ALIASES.get(ticker.upper(), ticker)
