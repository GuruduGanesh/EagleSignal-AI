"""FastAPI service (ARCHITECTURE.md 2.x). Endpoints expose the latest signals and
allow on-demand runs. Run with: uvicorn eaglesignal.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import base64
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
except Exception as exc:  # FastAPI optional at import time
    raise RuntimeError("FastAPI is required for the API service: pip install fastapi uvicorn") from exc

from . import __disclaimer__, __product__, __version__
from .advisor import advise, parse_portfolio
from .config import get_settings
from .historical_store import load_snapshot_status
from .ingestion.global_markets import fetch_global_indexes
from .jobs import load_job_status, run_research_job, run_tuning_job
from .manual_trading import (
    add_manual_trade,
    delete_manual_trade,
    fetch_option_contract_quote,
    load_manual_trades,
    refresh_live_prices,
    update_manual_trade,
)
from .pipeline import run_pipeline
from .refresh import (
    CATEGORY_JOBS,
    load_refresh_status,
    run_refresh_and_analyze,
    run_refresh_jobs,
)
from .reliability import build_reliability_scorecard
from .reports.generator import render_html, write_reports

app = FastAPI(title=f"{__product__} API", version=__version__)


@app.middleware("http")
async def _require_login(request, call_next):
    """Optional HTTP Basic gate for public exposure (Cloudflare Tunnel, etc.).

    Enabled ONLY when ``DASHBOARD_PASSWORD`` is set — then every route (dashboard,
    API, and the mutating /run, /jobs/*, /manual-trades endpoints) requires the
    login. ``/health`` stays open for tunnel/uptime checks. With no password set,
    behavior is unchanged (local + private-VPN use needs no auth).

    LOCALHOST/LAN EXEMPTION: the login is enforced ONLY for requests that arrive
    through the public tunnel. Cloudflare always injects ``cf-ray`` /
    ``cf-connecting-ip`` (and a proxy adds ``x-forwarded-for``); these cannot be
    forged by an external client coming through Cloudflare. Direct access from the
    laptop's own browser (or the LAN) carries none of them and is left open — so
    ``http://localhost:8000`` never prompts, while the public URL always does.
    (We can't key on the client IP: inside Docker the published port rewrites the
    source to the bridge gateway for both local and tunnel traffic alike.)
    """
    password = os.environ.get("DASHBOARD_PASSWORD")
    via_tunnel = bool(
        request.headers.get("cf-ray")
        or request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for")
    )
    # §5.6 LAN lockdown (opt-in): when DASHBOARD_REQUIRE_LOGIN_ON_LAN is set, also
    # require the login for non-loopback LAN devices — not just tunnel traffic.
    # Loopback (the laptop's own browser) stays exempt so localhost never prompts.
    lan_lock = os.environ.get("DASHBOARD_REQUIRE_LOGIN_ON_LAN", "").strip().lower() in {"1", "true", "yes", "on"}
    client_host = (request.client.host if request.client else "") or ""
    is_loopback = client_host in {"127.0.0.1", "::1", "localhost"}
    needs_auth = via_tunnel or (lan_lock and not is_loopback)
    if password and needs_auth and request.url.path != "/health":
        user = os.environ.get("DASHBOARD_USER", "admin")
        header = request.headers.get("Authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                u, _, p = decoded.partition(":")
                ok = secrets.compare_digest(u, user) and secrets.compare_digest(p, password)
            except Exception:
                ok = False
        if not ok:
            from starlette.responses import Response

            return Response(status_code=401, content="Authentication required.",
                            headers={"WWW-Authenticate": 'Basic realm="EagleSignal"'})
    return await call_next(request)


class ManualTradeRequest(BaseModel):
    ticker: str
    side: str
    entry_price: float
    quantity: float
    note: str = ""
    instrument_type: str = "equity"
    underlying: str | None = None
    option_contract: str | None = None
    option_expiration: str | None = None
    option_type: str | None = None
    option_strike: float | None = None
    contract_multiplier: float | None = None


class ManualTradeUpdate(BaseModel):
    ticker: str | None = None
    side: str | None = None
    entry_price: float | None = None
    quantity: float | None = None
    note: str | None = None
    instrument_type: str | None = None
    underlying: str | None = None
    option_contract: str | None = None
    option_expiration: str | None = None
    option_type: str | None = None
    option_strike: float | None = None
    contract_multiplier: float | None = None


class AdvisorRequest(BaseModel):
    message: str
    portfolio: str | None = None  # e.g. "AAPL:10, MSFT:5"


class JobRunRequest(BaseModel):
    strategy: str = "swing"
    horizon: str = "5D"
    tickers: str | None = None
    retries: int = 2
    retry_delay_seconds: int = 60


class RefreshRequest(BaseModel):
    categories: list[str] | None = None  # None => all categories
    analyze: bool = False  # run the full prediction pipeline after refreshing


class TuneJobRequest(BaseModel):
    profiles: list[str] | None = None
    horizon_days: int = 5
    period: str = "2y"
    step: int = 5
    max_tickers: int = 25
    dry_run: bool = False


@app.get("/")
def root() -> dict:
    return {"product": __product__, "version": __version__, "disclaimer": __disclaimer__,
            "endpoints": ["/health", "/run", "/signals", "/ticker/{symbol}", "/dashboard",
                          "/manual-trades", "/advisor", "/markets", "/prices/refresh",
                          "/options/quote", "/snapshots/status", "/reliability/scorecard",
                          "/jobs/run", "/jobs/status", "/jobs/refresh-all",
                          "/jobs/tune", "/jobs/refresh/{category}", "/jobs/refresh-status"]}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/run")
def run(strategy: str = "swing", horizon: str = "5D", tickers: str | None = None) -> dict:
    settings = get_settings()
    tlist = [t.strip() for t in tickers.split(",")] if tickers else None
    result = run_pipeline(strategy=strategy, horizon=horizon, tickers=tlist, settings=settings)
    write_reports(result, settings.reports_dir)
    return {"count": len(result.predictions),
            "predictions": [p.model_dump(mode="json") for p in result.predictions]}


def _latest_signals_path() -> Path | None:
    base = get_settings().reports_dir
    if not base.exists():
        return None
    days = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
    for d in days:
        f = d / "signals.json"
        if f.exists():
            return f
    return None


def _latest_dashboard_path() -> Path | None:
    base = get_settings().reports_dir
    if not base.exists():
        return None
    days = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
    for d in days:
        f = d / "dashboard.html"
        if f.exists():
            return f
    return None


@app.get("/signals")
def signals() -> dict:
    path = _latest_signals_path()
    if not path:
        raise HTTPException(404, "No reports yet. POST /run first.")
    return {"source": str(path), "predictions": json.loads(path.read_text(encoding="utf-8"))}


@app.get("/ticker/{symbol}")
def ticker(symbol: str) -> dict:
    path = _latest_signals_path()
    if not path:
        raise HTTPException(404, "No reports yet. POST /run first.")
    preds = json.loads(path.read_text(encoding="utf-8"))
    match = [p for p in preds if p["ticker"].upper() == symbol.upper()]
    if not match:
        raise HTTPException(404, f"{symbol} not in latest report.")
    return match[0]


@app.get("/manual-trades")
def manual_trades(live: bool = True) -> dict:
    data_dir = get_settings().data_dir
    if live:
        # Mark each open trade against the latest real market price on demand.
        return refresh_live_prices(data_dir)
    return load_manual_trades(data_dir)


@app.post("/manual-trades")
def create_manual_trade(req: ManualTradeRequest) -> dict:
    try:
        trade = add_manual_trade(
            get_settings().data_dir,
            ticker=req.ticker,
            side=req.side,
            entry_price=req.entry_price,
            quantity=req.quantity,
            note=req.note,
            instrument_type=req.instrument_type,
            underlying=req.underlying,
            option_contract=req.option_contract,
            option_expiration=req.option_expiration,
            option_type=req.option_type,
            option_strike=req.option_strike,
            contract_multiplier=req.contract_multiplier,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"trade": trade, "ledger": load_manual_trades(get_settings().data_dir)}


@app.put("/manual-trades/{trade_id}")
def edit_manual_trade(trade_id: str, req: ManualTradeUpdate) -> dict:
    try:
        trade = update_manual_trade(
            get_settings().data_dir, trade_id,
            ticker=req.ticker, side=req.side, entry_price=req.entry_price,
            quantity=req.quantity, note=req.note,
            instrument_type=req.instrument_type, underlying=req.underlying,
            option_contract=req.option_contract, option_expiration=req.option_expiration,
            option_type=req.option_type, option_strike=req.option_strike,
            contract_multiplier=req.contract_multiplier,
        )
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 400, str(exc)) from exc
    return {"trade": trade, "ledger": load_manual_trades(get_settings().data_dir)}


@app.delete("/manual-trades/{trade_id}")
def remove_manual_trade(trade_id: str) -> dict:
    try:
        deleted = delete_manual_trade(get_settings().data_dir, trade_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"deleted": deleted, "ledger": load_manual_trades(get_settings().data_dir)}


@app.get("/options/quote")
def options_quote(underlying: str, contract: str) -> dict:
    """Latest real/delayed premium for one exact option contract/expiry."""
    quote = fetch_option_contract_quote(underlying.upper(), contract.upper())
    if not quote:
        raise HTTPException(404, f"No live/delayed quote found for {contract} under {underlying}")
    quote["underlying"] = underlying.upper()
    quote["disclaimer"] = __disclaimer__
    return quote


@app.post("/advisor")
def advisor(req: AdvisorRequest) -> dict:
    """AI investment advisor (research only). LLM-backed if a key is set, else rule-based."""
    return advise(req.message, settings=get_settings(), portfolio=parse_portfolio(req.portfolio))


@app.get("/advisor/health")
def advisor_health_endpoint() -> dict:
    """Which AI backends are live (advisor + local Ollama/GPU sentiment)."""
    from .advisor import advisor_health

    return advisor_health(get_settings())


@app.get("/calendar")
def calendar(days: int = 21, include_earnings: bool = False) -> dict:
    """Upcoming market-moving events: FOMC + rule-based macro releases.

    Market/macro events are instant (no network). Pass ``include_earnings=true``
    to also fetch live watchlist earnings dates — that does one network lookup per
    ticker, so use a longer client timeout. Earnings are also available per-ticker
    on each prediction's ``options_trade_idea.earnings``.
    """
    from .ingestion.calendars import upcoming_events

    tickers: list[str] = []
    if include_earnings:
        from .config import load_watchlist

        try:
            assets, _ = load_watchlist()
            tickers = [a.ticker for a in assets]
        except Exception:
            tickers = []
    return {
        "days_ahead": days,
        "include_earnings": include_earnings,
        "events": upcoming_events(tickers=tickers, days_ahead=days),
        "disclaimer": __disclaimer__,
    }


@app.get("/markets")
def markets() -> dict:
    """Live US/Europe/Asia index levels, day change, and global risk-on/off read."""
    snap = fetch_global_indexes()
    return {
        "available": snap.available,
        "regime": snap.regime_note,
        "advancers": snap.advancers,
        "decliners": snap.decliners,
        "indexes": [
            {"name": gi.name, "symbol": gi.symbol, "region": gi.region,
             "last": gi.last, "day_change_pct": gi.day_change_pct}
            for gi in snap.indexes.values()
        ],
        "disclaimer": __disclaimer__,
    }


@app.get("/jobs/status")
def jobs_status() -> dict:
    return load_job_status(get_settings())


@app.get("/snapshots/status")
def snapshots_status() -> dict:
    """Historical point-in-time data accumulation status."""
    return load_snapshot_status(get_settings())


@app.get("/reliability/scorecard")
def reliability_scorecard(limit: int = 250) -> dict:
    """Measured post-recommendation hit-rate scorecard from stored snapshots."""
    return build_reliability_scorecard(get_settings(), limit=limit)


@app.post("/jobs/run")
def jobs_run(req: JobRunRequest, background_tasks: BackgroundTasks) -> dict:
    tlist = [t.strip().upper() for t in req.tickers.split(",")] if req.tickers else None
    background_tasks.add_task(
        run_research_job,
        strategy=req.strategy,
        horizon=req.horizon,
        tickers=tlist,
        retries=req.retries,
        retry_delay_seconds=req.retry_delay_seconds,
        settings=get_settings(),
    )
    return {
        "status": "queued",
        "message": "Research collection job queued. Check /jobs/status or refresh the dashboard after it completes.",
        "tickers": tlist,
        "strategy": req.strategy,
        "horizon": req.horizon,
    }


@app.post("/jobs/tune")
def jobs_tune(req: TuneJobRequest, background_tasks: BackgroundTasks) -> dict:
    """Queue the weekly-style ADR-002 retune job."""
    background_tasks.add_task(
        run_tuning_job,
        profiles=req.profiles,
        horizon_days=req.horizon_days,
        period=req.period,
        step=req.step,
        max_tickers=req.max_tickers,
        dry_run=req.dry_run,
        settings=get_settings(),
    )
    return {
        "status": "queued",
        "mode": "weekly_auto_retune",
        "profiles": req.profiles or ["swing", "intraday", "options_buying"],
        "message": "Retune job queued. Check /jobs/status for the result.",
    }


@app.get("/jobs/refresh/categories")
def refresh_categories() -> dict:
    """List the parallel refresh categories the Jobs tab can run."""
    return {"categories": list(CATEGORY_JOBS.keys())}


@app.get("/jobs/refresh-status")
def refresh_status() -> dict:
    """Last-refresh time + one-line summary per category."""
    return load_refresh_status(get_settings())


@app.post("/jobs/refresh/{category}")
def refresh_one(category: str) -> dict:
    """Refresh a SINGLE category (e.g. news, market, trump). Fast and synchronous."""
    if category not in CATEGORY_JOBS:
        raise HTTPException(404, f"Unknown category '{category}'. Options: {list(CATEGORY_JOBS)}")
    return run_refresh_jobs([category], settings=get_settings())


@app.post("/jobs/refresh-all")
def refresh_all(req: RefreshRequest, background_tasks: BackgroundTasks) -> dict:
    """Refresh many categories IN PARALLEL (one thread each) from a single call.

    This is the dashboard's "Refresh ALL" button. With ``analyze=true`` the full
    prediction pipeline runs after the parallel fetch and fresh reports are
    written (kicked to the background so the click returns immediately)."""
    settings = get_settings()
    cats = req.categories or list(CATEGORY_JOBS.keys())
    if req.analyze:
        background_tasks.add_task(run_refresh_and_analyze, settings=settings)
        return {"status": "queued", "mode": "refresh_all_then_analyze", "parallel": True,
                "categories": cats,
                "message": "Refreshing all sources in parallel, then re-analyzing. Check /jobs/refresh-status and reload the dashboard shortly."}
    # Synchronous parallel refresh (no full re-analysis) — returns the summaries.
    return run_refresh_jobs(cats, settings=settings)


@app.get("/prices/refresh")
def prices_refresh() -> dict:
    """Fast on-demand live-price refresh for the tickers in the latest report.

    Lets the dashboard update current price + day change without waiting for a
    full multi-minute re-scan. Uses the same real-data provider chain.
    """
    from .ingestion.market_data import fetch_history

    path = _latest_signals_path()
    tickers: list[str] = []
    if path:
        try:
            preds = json.loads(path.read_text(encoding="utf-8"))
            tickers = [p["ticker"] for p in preds]
        except Exception:
            tickers = []
    def quote(ticker: str) -> tuple[str, dict | None]:
        try:
            md = fetch_history(ticker)
            if md.ok:
                return ticker, {
                    "current_price": round(float(md.current_price or md.last_close), 4),
                    "day_change_pct": round(md.day_change_pct, 2) if md.day_change_pct is not None else None,
                    "source": md.source,
                }
        except Exception:
            return ticker, None
        return ticker, None

    prices: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(tickers)))) as pool:
        futures = [pool.submit(quote, t) for t in tickers]
        for fut in as_completed(futures):
            ticker, q = fut.result()
            if q:
                prices[ticker] = q
    return {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(prices), "prices": prices, "disclaimer": __disclaimer__}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    path = _latest_dashboard_path()
    if path:
        return path.read_text(encoding="utf-8")
    settings = get_settings()
    result = run_pipeline(settings=settings)
    write_reports(result, settings.reports_dir)
    return render_html(result)
