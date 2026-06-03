"""SKILL-010/011/012 Market data collector.

Runtime rule: use real market data only. The provider chain is configurable via
``MARKET_DATA_PROVIDER_CHAIN`` and defaults to:

1. yfinance current/history (keyless)
2. Finnhub daily candles (FINNHUB_API_KEY)
3. Tiingo daily prices (TIINGO_API_KEY)
4. Alpha Vantage daily series (ALPHAVANTAGE_API_KEY)
5. Stooq downloaded daily history (keyless)
6. Local cache from a prior successful real-data download

Each attempt is recorded in ``provider_status`` so reports can show which source
won and which were skipped/failed. If all real sources fail, the result is marked
unavailable and the pipeline skips that ticker. No synthetic market prices are
ever used in runtime analysis (synthetic bars exist only as a test fixture).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd

from ..utils.logging import get_logger

log = get_logger("ingestion.market")


@dataclass
class MarketData:
    ticker: str
    bars: pd.DataFrame  # index=DatetimeIndex, cols: open, high, low, close, volume
    is_synthetic: bool = False
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_price: float | None = None
    previous_close: float | None = None
    day_change_pct: float | None = None
    source: str = "unavailable"
    provider_status: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.bars is not None and len(self.bars) >= 30

    @property
    def last_close(self) -> float:
        return float(self.bars["close"].iloc[-1])

    @property
    def last_volume(self) -> float:
        return float(self.bars["volume"].iloc[-1])


def _synthetic_bars(ticker: str, days: int = 400) -> pd.DataFrame:
    """Deterministic test fixture only. Never used by runtime fetch_history."""
    seed = abs(hash(ticker)) % (2**32)
    rng = np.random.default_rng(seed)
    n = days
    idx = pd.date_range(end=datetime.now(timezone.utc).date(), periods=n, freq="B")
    drift = rng.normal(0.0004, 0.0002)
    rets = rng.normal(drift, 0.018, n)
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.012, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.012, n)))
    open_ = close * (1 + rng.normal(0, 0.006, n))
    volume = rng.integers(2_000_000, 25_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _cache_path(ticker: str, period: str, interval: str) -> Path:
    from ..config import get_settings

    safe = quote(f"{ticker.upper()}_{period}_{interval}", safe="")
    return get_settings().data_dir / "market_cache" / f"{safe}.csv"


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"missing OHLCV columns: {missing}")
    out = df[required].dropna()
    out.index = pd.to_datetime(out.index)
    return out.sort_index()


def _snapshot(df: pd.DataFrame, current_price: float | None = None, previous_close: float | None = None) -> dict:
    current = float(current_price) if current_price is not None else float(df["close"].iloc[-1])
    prev = float(previous_close) if previous_close is not None else float(df["close"].iloc[-2] if len(df) > 1 else current)
    return {
        "current_price": current,
        "previous_close": prev,
        "day_change_pct": ((current / prev) - 1) * 100 if prev else None,
    }


def _save_cache(ticker: str, period: str, interval: str, df: pd.DataFrame) -> None:
    path = _cache_path(ticker, period, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index_label="date")


def _from_cache(ticker: str, period: str, interval: str, statuses: list[dict[str, str]]) -> MarketData | None:
    path = _cache_path(ticker, period, interval)
    if not path.exists():
        statuses.append({"provider": "local_cache", "status": "missing"})
        return None
    try:
        df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        df = _normalize_ohlcv(df)
        if len(df) < 30:
            statuses.append({"provider": "local_cache", "status": "insufficient_rows"})
            return None
        snap = _snapshot(df)
        statuses.append({"provider": "local_cache", "status": "ok"})
        return MarketData(
            ticker=ticker,
            bars=df,
            current_price=snap["current_price"],
            previous_close=snap["previous_close"],
            day_change_pct=snap["day_change_pct"],
            source="local_cache",
            provider_status=statuses,
        )
    except Exception as exc:
        statuses.append({"provider": "local_cache", "status": f"error: {exc}"[:160]})
        return None


def _from_yfinance(ticker: str, period: str, interval: str, statuses: list[dict[str, str]]) -> MarketData | None:
    try:
        import yfinance as yf

        tk = yf.Ticker(ticker)
        df = yf.download(
            ticker, period=period, interval=interval,
            auto_adjust=True, progress=False, threads=False,
        )
        if df is None or df.empty:
            statuses.append({"provider": "yfinance", "status": "empty"})
            return None
        df = _normalize_ohlcv(df)
        if len(df) < 30:
            statuses.append({"provider": "yfinance", "status": "insufficient_rows"})
            return None

        try:
            info = tk.fast_info
            current_price = float(info.get("last_price") or info.get("lastPrice") or df["close"].iloc[-1])
            previous_close = float(info.get("previous_close") or info.get("previousClose") or df["close"].iloc[-2])
        except Exception:
            current_price = float(df["close"].iloc[-1])
            previous_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
        snap = _snapshot(df, current_price, previous_close)
        _save_cache(ticker, period, interval, df)
        statuses.append({"provider": "yfinance", "status": "ok"})
        return MarketData(
            ticker=ticker,
            bars=df,
            current_price=snap["current_price"],
            previous_close=snap["previous_close"],
            day_change_pct=snap["day_change_pct"],
            source="yfinance",
            provider_status=statuses,
        )
    except Exception as exc:
        statuses.append({"provider": "yfinance", "status": f"error: {exc}"[:160]})
        return None


def _from_stooq(ticker: str, period: str, interval: str, statuses: list[dict[str, str]]) -> MarketData | None:
    if interval != "1d":
        statuses.append({"provider": "stooq", "status": "daily_only"})
        return None
    try:
        import requests
        from io import StringIO

        symbol = ticker.lower()
        if "." not in symbol:
            symbol = f"{symbol}.us"
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200 or not resp.text.strip() or resp.text.startswith("No data"):
            statuses.append({"provider": "stooq", "status": f"http_{resp.status_code}"})
            return None
        raw = pd.read_csv(StringIO(resp.text))
        if raw.empty:
            statuses.append({"provider": "stooq", "status": "empty"})
            return None
        raw = raw.rename(columns={"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        df = raw.set_index(pd.to_datetime(raw["date"]))[["open", "high", "low", "close", "volume"]].dropna()
        if period.endswith("y"):
            years = int(period[:-1])
            cutoff = pd.Timestamp.now(tz=None) - pd.DateOffset(years=years)
            df = df[df.index >= cutoff]
        elif period.endswith("mo"):
            months = int(period[:-2])
            cutoff = pd.Timestamp.now(tz=None) - pd.DateOffset(months=months)
            df = df[df.index >= cutoff]
        df = _normalize_ohlcv(df)
        if len(df) < 30:
            statuses.append({"provider": "stooq", "status": "insufficient_rows"})
            return None
        snap = _snapshot(df)
        _save_cache(ticker, period, interval, df)
        statuses.append({"provider": "stooq", "status": "ok"})
        return MarketData(
            ticker=ticker,
            bars=df,
            current_price=snap["current_price"],
            previous_close=snap["previous_close"],
            day_change_pct=snap["day_change_pct"],
            source="stooq",
            provider_status=statuses,
        )
    except Exception as exc:
        statuses.append({"provider": "stooq", "status": f"error: {exc}"[:160]})
        return None


def _period_to_days(period: str) -> int:
    if period.endswith("y"):
        return int(period[:-1]) * 365
    if period.endswith("mo"):
        return int(period[:-2]) * 31
    if period.endswith("d"):
        return int(period[:-1])
    return 365


def _build_md(ticker: str, df: pd.DataFrame, source: str, statuses: list[dict[str, str]]) -> MarketData:
    snap = _snapshot(df)
    return MarketData(
        ticker=ticker, bars=df,
        current_price=snap["current_price"], previous_close=snap["previous_close"],
        day_change_pct=snap["day_change_pct"], source=source, provider_status=statuses,
    )


def _from_finnhub(ticker: str, period: str, interval: str, statuses: list[dict[str, str]]) -> MarketData | None:
    from ..config import get_settings

    key = get_settings().finnhub_api_key
    if not key:
        statuses.append({"provider": "finnhub", "status": "no_api_key"})
        return None
    if interval != "1d":
        statuses.append({"provider": "finnhub", "status": "daily_only"})
        return None
    try:
        import time
        import requests

        now = int(time.time())
        start = now - _period_to_days(period) * 86400
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/candle",
            params={"symbol": ticker.upper(), "resolution": "D", "from": start, "to": now, "token": key},
            timeout=20,
        )
        if resp.status_code != 200:
            statuses.append({"provider": "finnhub", "status": f"http_{resp.status_code}"})
            return None
        j = resp.json()
        if j.get("s") != "ok" or not j.get("c"):
            statuses.append({"provider": "finnhub", "status": "no_data"})
            return None
        df = pd.DataFrame(
            {"open": j["o"], "high": j["h"], "low": j["l"], "close": j["c"], "volume": j["v"]},
            index=pd.to_datetime(j["t"], unit="s"),
        )
        df = _normalize_ohlcv(df)
        if len(df) < 30:
            statuses.append({"provider": "finnhub", "status": "insufficient_rows"})
            return None
        _save_cache(ticker, period, interval, df)
        statuses.append({"provider": "finnhub", "status": "ok"})
        return _build_md(ticker, df, "finnhub", statuses)
    except Exception as exc:
        statuses.append({"provider": "finnhub", "status": f"error: {exc}"[:160]})
        return None


def _from_tiingo(ticker: str, period: str, interval: str, statuses: list[dict[str, str]]) -> MarketData | None:
    from ..config import get_settings

    key = get_settings().tiingo_api_key
    if not key:
        statuses.append({"provider": "tiingo", "status": "no_api_key"})
        return None
    if interval != "1d":
        statuses.append({"provider": "tiingo", "status": "daily_only"})
        return None
    try:
        from datetime import date
        import requests

        start = (date.today() - timedelta(days=_period_to_days(period))).isoformat()
        resp = requests.get(
            f"https://api.tiingo.com/tiingo/daily/{ticker.lower()}/prices",
            params={"startDate": start, "token": key},
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        if resp.status_code != 200:
            statuses.append({"provider": "tiingo", "status": f"http_{resp.status_code}"})
            return None
        rows = resp.json()
        if not rows:
            statuses.append({"provider": "tiingo", "status": "no_data"})
            return None
        raw = pd.DataFrame(rows)
        raw.index = pd.to_datetime(raw["date"])
        # Prefer split/dividend-adjusted columns when present.
        cols = {"adjOpen": "open", "adjHigh": "high", "adjLow": "low", "adjClose": "close", "adjVolume": "volume"}
        if all(c in raw.columns for c in cols):
            df = raw[list(cols)].rename(columns=cols)
        else:
            df = raw[["open", "high", "low", "close", "volume"]]
        df = _normalize_ohlcv(df)
        if len(df) < 30:
            statuses.append({"provider": "tiingo", "status": "insufficient_rows"})
            return None
        _save_cache(ticker, period, interval, df)
        statuses.append({"provider": "tiingo", "status": "ok"})
        return _build_md(ticker, df, "tiingo", statuses)
    except Exception as exc:
        statuses.append({"provider": "tiingo", "status": f"error: {exc}"[:160]})
        return None


def _from_alpha_vantage(ticker: str, period: str, interval: str, statuses: list[dict[str, str]]) -> MarketData | None:
    from ..config import get_settings

    key = get_settings().alphavantage_api_key
    if not key:
        statuses.append({"provider": "alpha_vantage", "status": "no_api_key"})
        return None
    if interval != "1d":
        statuses.append({"provider": "alpha_vantage", "status": "daily_only"})
        return None
    try:
        import requests

        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": ticker.upper(),
                "outputsize": "full", "apikey": key,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            statuses.append({"provider": "alpha_vantage", "status": f"http_{resp.status_code}"})
            return None
        j = resp.json()
        series = j.get("Time Series (Daily)")
        if not series:
            # Rate-limit or premium-endpoint notice arrives as Note/Information.
            reason = j.get("Note") or j.get("Information") or j.get("Error Message") or "no_data"
            statuses.append({"provider": "alpha_vantage", "status": str(reason)[:80]})
            return None
        recs = {
            pd.to_datetime(d): {
                "open": float(v["1. open"]), "high": float(v["2. high"]),
                "low": float(v["3. low"]), "close": float(v.get("5. adjusted close", v["4. close"])),
                "volume": float(v["6. volume"]),
            }
            for d, v in series.items()
        }
        df = pd.DataFrame.from_dict(recs, orient="index").sort_index()
        df = df.tail(int(_period_to_days(period) / 365 * 252) + 30)
        df = _normalize_ohlcv(df)
        if len(df) < 30:
            statuses.append({"provider": "alpha_vantage", "status": "insufficient_rows"})
            return None
        _save_cache(ticker, period, interval, df)
        statuses.append({"provider": "alpha_vantage", "status": "ok"})
        return _build_md(ticker, df, "alpha_vantage", statuses)
    except Exception as exc:
        statuses.append({"provider": "alpha_vantage", "status": f"error: {exc}"[:160]})
        return None


_PROVIDERS = {
    "yfinance": _from_yfinance,
    "finnhub": _from_finnhub,
    "tiingo": _from_tiingo,
    "alpha_vantage": _from_alpha_vantage,
    "stooq": _from_stooq,
    "local_cache": _from_cache,
}


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> MarketData:
    """Fetch real OHLCV using the configured provider fallback chain.

    Tries each provider in MARKET_DATA_PROVIDER_CHAIN order and returns the first
    that yields >=30 usable bars. No synthetic fallback — if all real providers
    fail the ticker is marked unavailable and skipped downstream.
    """
    from ..config import get_settings

    chain = [p.strip() for p in get_settings().market_data_provider_chain.split(",") if p.strip()]
    providers = [_PROVIDERS[name] for name in chain if name in _PROVIDERS] or [_from_yfinance, _from_stooq, _from_cache]
    statuses: list[dict[str, str]] = []
    for provider in providers:
        data = provider(ticker, period, interval, statuses)
        if data and data.ok:
            return data
    log.warning("No real market data available for %s after provider fallback: %s", ticker, statuses)
    return MarketData(ticker=ticker, bars=pd.DataFrame(), source="unavailable", provider_status=statuses)
