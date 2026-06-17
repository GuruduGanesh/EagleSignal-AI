"""Configuration: environment settings, watchlist loader, scoring weights.

Secrets only ever come from environment variables (.env -> os.environ).
Nothing here ever hard-codes an API key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from .schemas import AssetEntity, AssetType

# Repo root = three parents up from this file (src/eaglesignal/config.py).
ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Best-effort .env loader (no hard dependency on python-dotenv)."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(ROOT / ".env")
    except Exception:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


@dataclass
class Settings:
    app_env: str = "development"
    log_level: str = "INFO"
    timezone: str = "America/New_York"
    watchlist_file: str = "config/watchlist.yml"
    weights_file: str = "config/weights.yml"
    strict_watchlist_only: bool = True

    market_data_provider: str = "yfinance"
    # Ordered real-data fallback chain (no synthetic prices ever).
    market_data_provider_chain: str = "yfinance,finnhub,tiingo,alpha_vantage,stooq,local_cache"
    sec_user_agent: str = "EagleSignal research your-email@example.com"
    sec_base_url: str = "https://data.sec.gov"

    fred_api_key: Optional[str] = None
    bls_api_key: Optional[str] = None
    bea_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    # Extra market-data providers (all key-gated, all real data).
    finnhub_api_key: Optional[str] = None
    tiingo_api_key: Optional[str] = None
    alphavantage_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Social sentiment (legal sources only; off by default).
    stocktwits_token: Optional[str] = None
    x_bearer_token: Optional[str] = None  # official X API v2 (paid); enables X news+sentiment
    enable_social_sentiment: bool = True  # StockTwits public stream is keyless
    enable_government_feeds: bool = True  # Treasury/Federal Register/GDELT are keyless
    enable_forecast: bool = True  # Monte-Carlo + trend-agent ensemble
    enable_gpu_monte_carlo: bool = False  # optional CuPy acceleration; CPU fallback always works
    monte_carlo_paths: int = 4000

    # Global markets (US + Europe + Asia). Blank => built-in default index set.
    enable_global_markets: bool = True
    global_indexes: str = ""

    # AI advisor (research-only). Uses an LLM when configured, else rule-based.
    advisor_provider: str = "auto"  # auto | openai | anthropic | ollama | rules
    advisor_model: str = ""
    ollama_base_url: str = ""

    # Optional extra news providers (key-gated).
    marketaux_api_key: Optional[str] = None
    fmp_api_key: Optional[str] = None

    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None

    # Risk thresholds (RISK manager + alert gating)
    min_equity_daily_volume: int = 1_000_000
    min_option_open_interest: int = 100
    max_option_bid_ask_spread_pct: float = 12.0
    min_option_days_to_expiry: int = 5
    min_index_option_move_points: float = 50.0
    # Minimum worthwhile option profit potential as a percent of option premium.
    # Trades below this are flagged "low potential" and should not be promoted.
    min_option_profit_pct: float = 10.0
    confidence_threshold: int = 65
    pipeline_max_workers: int = 16
    per_ticker_retries: int = 1
    per_ticker_retry_delay_seconds: float = 2.0
    enable_historical_snapshots: bool = True
    historical_snapshots_dir: str = "data/historical_snapshots"
    enable_earnings_calendar: bool = True  # keyless next-earnings lookup for IV-crush gating
    enable_llm_sentiment: bool = False  # use local Ollama (GPU) to classify headline sentiment; lexicon fallback
    # Remote-access auth: enforce HTTP Basic login on LAN devices too (not just via
    # the Cloudflare tunnel). localhost/loopback stays exempt either way.
    require_login_on_lan: bool = False
    # X/Twitter official API daily read budget (cost guard); 0 disables the cap.
    x_daily_read_budget: int = 50

    reports_dir: Path = field(default=ROOT / "reports")
    data_dir: Path = field(default=ROOT / "data")

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        g = os.environ.get

        def as_int(name: str, default: int) -> int:
            try:
                return int(g(name, default))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default

        def as_float(name: str, default: float) -> float:
            try:
                return float(g(name, default))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default

        def as_bool(name: str, default: bool) -> bool:
            raw = g(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            app_env=g("APP_ENV", "development"),
            log_level=g("LOG_LEVEL", "INFO"),
            timezone=g("TIMEZONE", "America/New_York"),
            watchlist_file=g("WATCHLIST_FILE", "config/watchlist.yml"),
            weights_file=g("WEIGHTS_FILE", "config/weights.yml"),
            strict_watchlist_only=as_bool("STRICT_WATCHLIST_ONLY", True),
            market_data_provider=g("MARKET_DATA_PROVIDER", "yfinance"),
            market_data_provider_chain=g(
                "MARKET_DATA_PROVIDER_CHAIN",
                "yfinance,finnhub,tiingo,alpha_vantage,stooq,local_cache",
            ),
            sec_user_agent=g("SEC_USER_AGENT", "EagleSignal research your-email@example.com"),
            sec_base_url=g("SEC_BASE_URL", "https://data.sec.gov"),
            fred_api_key=g("FRED_API_KEY") or None,
            bls_api_key=g("BLS_API_KEY") or None,
            bea_api_key=g("BEA_API_KEY") or None,
            news_api_key=g("NEWS_API_KEY") or None,
            finnhub_api_key=g("FINNHUB_API_KEY") or None,
            tiingo_api_key=g("TIINGO_API_KEY") or None,
            alphavantage_api_key=g("ALPHAVANTAGE_API_KEY") or g("ALPHA_VANTAGE_API_KEY") or None,
            openai_api_key=g("OPENAI_API_KEY") or None,
            anthropic_api_key=g("ANTHROPIC_API_KEY") or None,
            stocktwits_token=g("STOCKTWITS_TOKEN") or None,
            x_bearer_token=g("X_BEARER_TOKEN") or g("TWITTER_BEARER_TOKEN") or None,
            enable_social_sentiment=as_bool("ENABLE_SOCIAL_SENTIMENT", True),
            enable_government_feeds=as_bool("ENABLE_GOVERNMENT_FEEDS", True),
            enable_forecast=as_bool("ENABLE_FORECAST", True),
            enable_gpu_monte_carlo=as_bool("ENABLE_GPU_MONTE_CARLO", False),
            monte_carlo_paths=as_int("MONTE_CARLO_PATHS", 4000),
            enable_global_markets=as_bool("ENABLE_GLOBAL_MARKETS", True),
            global_indexes=g("GLOBAL_INDEXES", "") or "",
            advisor_provider=g("ADVISOR_PROVIDER", "auto"),
            advisor_model=g("ADVISOR_MODEL", "") or "",
            ollama_base_url=g("OLLAMA_BASE_URL", "") or "",
            marketaux_api_key=g("MARKETAUX_API_KEY") or None,
            fmp_api_key=g("FMP_API_KEY") or None,
            slack_webhook_url=g("SLACK_WEBHOOK_URL") or None,
            discord_webhook_url=g("DISCORD_WEBHOOK_URL") or None,
            min_equity_daily_volume=as_int("MIN_EQUITY_DAILY_VOLUME", 1_000_000),
            min_option_open_interest=as_int("MIN_OPTION_OPEN_INTEREST", 100),
            max_option_bid_ask_spread_pct=as_float("MAX_OPTION_BID_ASK_SPREAD_PCT", 12.0),
            min_option_days_to_expiry=as_int("MIN_OPTION_DAYS_TO_EXPIRY", 5),
            min_index_option_move_points=as_float("MIN_INDEX_OPTION_MOVE_POINTS", 50.0),
            min_option_profit_pct=as_float("MIN_OPTION_PROFIT_PCT", 10.0),
            confidence_threshold=as_int("DEFAULT_CONFIDENCE_THRESHOLD", 65),
            pipeline_max_workers=as_int("PIPELINE_MAX_WORKERS", 16),
            per_ticker_retries=as_int("PER_TICKER_RETRIES", 1),
            per_ticker_retry_delay_seconds=as_float("PER_TICKER_RETRY_DELAY_SECONDS", 2.0),
            enable_historical_snapshots=as_bool("ENABLE_HISTORICAL_SNAPSHOTS", True),
            historical_snapshots_dir=g("HISTORICAL_SNAPSHOTS_DIR", "data/historical_snapshots"),
            enable_earnings_calendar=as_bool("ENABLE_EARNINGS_CALENDAR", True),
            enable_llm_sentiment=as_bool("ENABLE_LLM_SENTIMENT", False),
            require_login_on_lan=as_bool("DASHBOARD_REQUIRE_LOGIN_ON_LAN", False),
            x_daily_read_budget=as_int("X_DAILY_READ_BUDGET", 50),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def load_watchlist(path: Optional[str | Path] = None) -> tuple[list[AssetEntity], dict]:
    """SKILL-001 Watchlist Loader. Returns (assets, strategies dict)."""
    settings = get_settings()
    p = Path(path) if path else ROOT / settings.watchlist_file
    if not p.is_absolute():
        p = ROOT / p
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    assets: list[AssetEntity] = []
    seen: set[str] = set()
    for raw in data.get("assets", []):
        ticker = str(raw.get("ticker", "")).strip().upper()
        if not ticker or ticker in seen:
            continue  # skip blanks/dupes, per SKILL-001 validation
        seen.add(ticker)
        try:
            asset_type = AssetType(raw.get("asset_type", "equity"))
        except ValueError:
            asset_type = AssetType.equity
        assets.append(
            AssetEntity(
                ticker=ticker,
                asset_type=asset_type,
                company_name=raw.get("company_name"),
                exchange=raw.get("exchange"),
                sector=raw.get("sector"),
                industry=raw.get("industry"),
                strategy_tags=list(raw.get("strategy_tags", [])),
                related_etfs=list(raw.get("related_etfs", [])),
            )
        )
    return assets, data.get("strategies", {})


def load_weights(profile: str = "swing", path: Optional[str | Path] = None) -> dict[str, float]:
    """Load and normalize scoring weights for a strategy profile.

    Prefers ADR-002 backtest-fitted weights (``config/weights.fitted.yml``) when
    that file exists and contains this profile — unless ``EAGLESIGNAL_USE_FITTED``
    is set to 0/false. An explicit ``path`` always wins (used by the tuner itself
    to read the hand-set prior). Falls back to ``config/weights.yml`` otherwise.
    """
    settings = get_settings()

    def _norm(d: dict[str, float]) -> dict[str, float]:
        total = sum(d.values()) or 1.0
        return {k: v / total for k, v in d.items()}

    if path is None and os.environ.get("EAGLESIGNAL_USE_FITTED", "1").lower() not in ("0", "false", "no"):
        fitted = ROOT / "config" / "weights.fitted.yml"
        if fitted.exists():
            try:
                fdata = yaml.safe_load(fitted.read_text(encoding="utf-8")) or {}
                fprof = (fdata.get("profiles") or {}).get(profile)
                if fprof:
                    w = dict(fdata.get("default", {}))
                    w.update(fprof)
                    return _norm(w)
            except Exception:
                pass  # fall through to hand-set weights on any parse error

    p = Path(path) if path else ROOT / settings.weights_file
    if not p.is_absolute():
        p = ROOT / p
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    weights = dict(data.get("default", {}))
    weights.update(data.get("profiles", {}).get(profile, {}))
    return _norm(weights)
