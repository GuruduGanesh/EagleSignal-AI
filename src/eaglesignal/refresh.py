"""Parallel live-data refresh jobs (SKILL-172 + WORKFLOW.md section 2).

The dashboard's Jobs tab needs *fast* refreshes. Instead of one slow end-to-end
re-scan, this module splits the work into independent **category jobs** that run
concurrently in a thread pool:

    market   - latest real prices for the watchlist (provider fallback chain)
    news     - multi-source company news merge (NewsAPI/Google/Yahoo/GDELT/...)
    social   - StockTwits/Reddit bull-bear sentiment
    xtwitter - official X/Twitter API v2 (company + government), key-gated
    government - Treasury/BLS/Federal Register/openFDA/DOJ-FTC/GDELT policy
    trump    - Trump administration / White House / executive-action news
    political  - geopolitical / policy news via GDELT
    macro    - FRED/Treasury macro regime
    global   - US/Europe/Asia index levels (geopolitical risk-on/off)
    official_economic - BLS/BEA/Census/FRED/Treasury/Fed/EIA/OFAC/Congress status
    company_events - SEC filings + earnings/calendar/IR source coverage
    options_volatility - options chains + Cboe/VIX/sentiment source coverage
    reference_dashboards - TradingView/Investing.com/Finviz/Koyfin/Reuters status
    automation_apis - Alpha Vantage/FMP/Nasdaq Data Link/Polygon API status
    paid_platforms - Bloomberg/LSEG/FactSet/Capital IQ licensed-upgrade status
    source_registry - complete source registry summary

Each job is read-only against the network and returns a compact JSON summary, so
running them in parallel is thread-safe (no shared mutable evidence store). The
``analyze`` step then runs the full prediction pipeline and writes fresh reports
("the post should analyze"). ``refresh_all`` fans every category out at once and
optionally chains the analysis at the end.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import ROOT, Settings, get_settings, load_watchlist
from .utils.logging import get_logger

log = get_logger("refresh")

STATUS_FILE = "refresh_status.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _watch_tickers(settings: Settings, limit: int | None = None) -> list[str]:
    assets, _ = load_watchlist()
    tickers = [a.ticker for a in assets]
    return tickers[:limit] if limit else tickers


def _source_registry() -> dict[str, Any]:
    import yaml

    path = ROOT / "config" / "analysis_source_registry.yml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _env_has_any(keys: list[str] | None) -> bool:
    import os

    if not keys:
        return False
    return any(bool(os.environ.get(k)) for k in keys)


def _registry_group_summary(group_names: list[str]) -> dict[str, Any]:
    registry = _source_registry()
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for group in group_names:
        entries = registry.get(group, {}) or {}
        for name, meta in entries.items():
            status = str(meta.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
            env_keys = list(meta.get("env_keys", []) or [])
            rows.append({
                "source": name,
                "group": group,
                "status": status,
                "access": meta.get("access", ""),
                "reliability_rank": meta.get("reliability_rank"),
                "best_for": meta.get("best_for", []),
                "env_keys": env_keys,
                "has_key": _env_has_any(env_keys),
                "notes": meta.get("notes", ""),
            })
    rows.sort(key=lambda r: (-(r.get("reliability_rank") or 0), r["group"], r["source"]))
    return {
        "groups": group_names,
        "source_count": len(rows),
        "status_counts": counts,
        "sources": rows,
    }


# --------------------------------------------------------------------------- #
# Individual category jobs — each returns a compact summary dict.
# --------------------------------------------------------------------------- #
def refresh_market(settings: Settings) -> dict[str, Any]:
    from .ingestion.market_data import fetch_history

    tickers = _watch_tickers(settings)
    prices: dict[str, dict] = {}
    ok = 0
    for t in tickers:
        try:
            md = fetch_history(t)
            if md.ok:
                ok += 1
                prices[t] = {
                    "current_price": round(float(md.current_price or md.last_close), 4),
                    "day_change_pct": round(md.day_change_pct, 2) if md.day_change_pct is not None else None,
                    "source": md.source,
                }
        except Exception as exc:
            log.warning("market refresh %s failed: %s", t, exc)
    movers = sorted(
        ((t, p["day_change_pct"]) for t, p in prices.items() if p.get("day_change_pct") is not None),
        key=lambda x: abs(x[1]), reverse=True,
    )[:5]
    return {
        "category": "market", "checked": len(tickers), "live": ok,
        "top_movers": [{"ticker": t, "day_change_pct": c} for t, c in movers],
        "prices": prices,
    }


def refresh_news(settings: Settings) -> dict[str, Any]:
    from .ingestion.news import fetch_news

    tickers = _watch_tickers(settings)
    total = 0
    providers: set[str] = set()
    per_ticker: dict[str, int] = {}
    headlines: list[dict] = []
    latest = None
    for t in tickers:
        try:
            res = fetch_news(t)
            per_ticker[t] = len(res.items)
            total += len(res.items)
            providers.update(res.providers)
            for it in res.items[:2]:
                pub = getattr(it, "published_at", None)
                if pub and (latest is None or pub > latest):
                    latest = pub
                headlines.append({"ticker": t, "title": it.title[:140],
                                  "source": getattr(it, "source", ""),
                                  "published_at": pub.isoformat() if pub else None,
                                  "url": getattr(it, "url", "")})
        except Exception as exc:
            log.warning("news refresh %s failed: %s", t, exc)
    return {
        "category": "news", "tickers": len(tickers), "total_items": total,
        "providers": sorted(providers), "headlines": headlines[:20],
        "latest_published": latest.isoformat() if latest else None,
        "busiest": sorted(per_ticker.items(), key=lambda x: x[1], reverse=True)[:5],
    }


def refresh_social(settings: Settings) -> dict[str, Any]:
    from .ingestion.social import fetch_social

    tickers = _watch_tickers(settings)
    available = 0
    sources_used: set[str] = set()
    rows: list[dict] = []
    for t in tickers:
        try:
            s = fetch_social(t)
            if s and s.available:
                available += 1
                sources_used.add((s.source or "").split(" ")[0])
                rows.append({"ticker": t, "source": s.source,
                             "net_sentiment": round(s.net_sentiment, 3),
                             "bullish": s.bullish, "bearish": s.bearish})
        except Exception as exc:
            log.warning("social refresh %s failed: %s", t, exc)
    rows.sort(key=lambda r: abs(r["net_sentiment"]), reverse=True)
    return {"category": "social", "tickers": len(tickers), "available": available,
            "sources": sorted(s for s in sources_used if s), "top_sentiment": rows[:10]}


def refresh_xtwitter(settings: Settings) -> dict[str, Any]:
    from .ingestion.x_twitter import company_query, government_query, search_recent, x_enabled

    if not x_enabled():
        return {"category": "xtwitter", "enabled": False,
                "note": "X/Twitter API v2 is key-gated (set X_BEARER_TOKEN, paid plan). Skipped cleanly — we never scrape."}
    tickers = _watch_tickers(settings, limit=8)
    company_hits = 0
    samples: list[dict] = []
    latest = None
    for t in tickers:
        try:
            r = search_recent(company_query(t, None), max_results=10)
            company_hits += len(r.tweets)
            for tw in r.tweets[:1]:
                ca = getattr(tw, "created_at", None)
                if ca and (latest is None or ca > latest):
                    latest = ca
                samples.append({"ticker": t, "text": getattr(tw, "text", "")[:140],
                                "created_at": ca.isoformat() if ca else None})
        except Exception as exc:
            log.warning("X refresh %s failed: %s", t, exc)
    gov_hits = 0
    try:
        gov = search_recent(government_query(), max_results=15)
        gov_hits = len(gov.tweets)
        for tw in gov.tweets:
            ca = getattr(tw, "created_at", None)
            if ca and (latest is None or ca > latest):
                latest = ca
    except Exception as exc:
        log.warning("X gov refresh failed: %s", exc)
    return {"category": "xtwitter", "enabled": True, "company_tweets": company_hits,
            "government_tweets": gov_hits, "samples": samples[:10],
            "latest_published": latest.isoformat() if latest else None}


# The government fetch is the slowest call (GDELT is throttled to 1 req / 6s) and
# three categories derive from it. Cache one snapshot for a short window so a
# parallel "refresh all" does ONE government fetch instead of three.
_GOV_CACHE: dict[str, Any] = {"snap": None, "at": 0.0}
_GOV_LOCK = __import__("threading").Lock()
_GOV_TTL = 90.0  # seconds


def _shared_government():
    from .ingestion.government import fetch_government

    with _GOV_LOCK:
        now = time.monotonic()
        snap = _GOV_CACHE["snap"]
        if snap is not None and (now - _GOV_CACHE["at"]) < _GOV_TTL:
            return snap
        snap = fetch_government()
        _GOV_CACHE["snap"] = snap
        _GOV_CACHE["at"] = now
        return snap


def _gov_summary(label: str, kinds: tuple[str, ...] | None = None) -> dict[str, Any]:
    snap = _shared_government()
    events = snap.events
    if kinds:
        events = [e for e in events if e.kind in kinds]
    by_kind: dict[str, int] = {}
    latest = None
    for e in snap.events:
        by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
        pub = getattr(e, "published_at", None)
        if pub and (latest is None or pub > latest):
            latest = pub
    return {
        "category": label, "available": snap.available, "providers": snap.providers,
        "total_events": len(snap.events), "by_kind": by_kind,
        "matched_events": len(events),
        "latest_published": latest.isoformat() if latest else None,
        "items": [{"title": e.title[:160], "source": e.source, "kind": e.kind,
                   "published_at": e.published_at.isoformat() if getattr(e, "published_at", None) else None,
                   "url": e.url}
                  for e in events[:12]],
        "values": snap.values,
    }


def refresh_government(settings: Settings) -> dict[str, Any]:
    return _gov_summary("government")


def refresh_trump(settings: Settings) -> dict[str, Any]:
    # Trump administration / White House / executive actions live in these kinds.
    return _gov_summary("trump", kinds=("trump_admin", "policy"))


def refresh_political(settings: Settings) -> dict[str, Any]:
    # Geopolitical + regulatory/policy reads (antitrust, FDA, policy, GDELT).
    return _gov_summary("political", kinds=("policy", "antitrust", "fda", "trump_admin", "fiscal", "labor"))


def refresh_macro(settings: Settings) -> dict[str, Any]:
    from .ingestion.macro_fred import fetch_macro

    m = fetch_macro()
    return {"category": "macro", "available": m.available, "values": m.values,
            "source": getattr(m, "source", ""), "as_of": getattr(m, "as_of", ""),
            "note": getattr(m, "note", "")}


def refresh_global(settings: Settings) -> dict[str, Any]:
    from .ingestion.global_markets import fetch_global_indexes

    snap = fetch_global_indexes()
    idx = [{"name": gi.name, "region": gi.region, "symbol": gi.symbol,
            "last": gi.last, "day_change_pct": gi.day_change_pct}
           for gi in snap.indexes.values()] if snap.available else []
    return {"category": "global", "available": snap.available,
            "regime": getattr(snap, "regime_note", ""),
            "advancers": getattr(snap, "advancers", None),
            "decliners": getattr(snap, "decliners", None),
            "indexes": idx}


def refresh_official_economic(settings: Settings) -> dict[str, Any]:
    """Grouped official macro/government sources.

    Pull implemented live official sources and list planned/API-gated sources so
    every important group is visible instead of being silently skipped.
    """
    macro = refresh_macro(settings)
    government = refresh_government(settings)
    registry = _registry_group_summary(["official_primary_sources"])
    return {
        "category": "official_economic",
        "macro": macro,
        "government": government,
        "registry": registry,
    }


def refresh_company_events(settings: Settings) -> dict[str, Any]:
    """SEC filings + earnings/calendar/IR source coverage for the focused list."""
    from .ingestion.sec_edgar import fetch_sec

    tickers = _watch_tickers(settings)
    rows: list[dict[str, Any]] = []
    filings = 0

    def _fetch(ticker: str) -> dict[str, Any]:
        try:
            sec = fetch_sec(ticker)
            recent = [{"form": f.form, "filed": f.filed, "title": f.title, "url": f.url}
                      for f in sec.recent_filings[:5]]
            return {
                "ticker": ticker,
                "available": sec.available,
                "company_name": sec.company_name,
                "filing_count": len(sec.recent_filings),
                "recent_filings": recent,
            }
        except Exception as exc:
            log.warning("company-events refresh %s failed: %s", ticker, exc)
            return {"ticker": ticker, "available": False, "filing_count": 0,
                    "recent_filings": [], "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(tickers)))) as pool:
        for fut in as_completed({pool.submit(_fetch, t): t for t in tickers}):
            row = fut.result()
            filings += row["filing_count"]
            rows.append(row)
    rows.sort(key=lambda r: r["filing_count"], reverse=True)
    return {
        "category": "company_events",
        "tickers": len(tickers),
        "with_sec_data": sum(1 for r in rows if r["available"]),
        "recent_filing_count": filings,
        "top_filing_names": rows[:8],
        "registry": _registry_group_summary(["company_and_events"]),
    }


def refresh_options_volatility(settings: Settings) -> dict[str, Any]:
    """Options chain, Cboe/VIX, and options sentiment source coverage."""
    from .ingestion.options_chain import fetch_options

    tickers = _watch_tickers(settings)
    rows: list[dict[str, Any]] = []

    def _fetch(ticker: str) -> dict[str, Any]:
        try:
            chain = fetch_options(ticker, max_expiries=3, min_days=settings.min_option_days_to_expiry)
            return {
                "ticker": ticker,
                "available": chain.available,
                "source": chain.source,
                "expiration_count": len(chain.chains),
                "expirations": [c.expiration for c in chain.chains[:3]],
            }
        except Exception as exc:
            log.warning("options/volatility refresh %s failed: %s", ticker, exc)
            return {"ticker": ticker, "available": False, "source": "failed",
                    "expiration_count": 0, "expirations": [],
                    "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(tickers)))) as pool:
        for fut in as_completed({pool.submit(_fetch, t): t for t in tickers}):
            rows.append(fut.result())
    rows.sort(key=lambda r: (not r["available"], r["ticker"]))
    by_source: dict[str, int] = {}
    for row in rows:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    return {
        "category": "options_volatility",
        "tickers": len(tickers),
        "with_options": sum(1 for r in rows if r["available"]),
        "by_source": by_source,
        "chains": rows,
        "registry": _registry_group_summary(["options_volatility_sentiment"]),
    }


def refresh_reference_dashboards(settings: Settings) -> dict[str, Any]:
    return {
        "category": "reference_dashboards",
        "note": "Manual/licensed dashboard references only; no uncontrolled scraping. Use to verify visually, not as sole trade truth.",
        "registry": _registry_group_summary(["dashboard_and_research_platforms", "news_flow"]),
    }


def refresh_automation_apis(settings: Settings) -> dict[str, Any]:
    return {
        "category": "automation_apis",
        "note": "API-gated automation sources. A source with no key is considered, marked missing, and skipped cleanly.",
        "registry": _registry_group_summary(["automation_apis"]),
    }


def refresh_paid_platforms(settings: Settings) -> dict[str, Any]:
    return {
        "category": "paid_platforms",
        "note": "Optional institutional upgrades. Use only through licensed terminal/API access.",
        "registry": _registry_group_summary(["professional_paid_platforms"]),
    }


def refresh_source_registry(settings: Settings) -> dict[str, Any]:
    registry = _source_registry()
    group_names = [
        "dashboard_and_research_platforms",
        "official_primary_sources",
        "company_and_events",
        "options_volatility_sentiment",
        "news_flow",
        "professional_paid_platforms",
        "automation_apis",
    ]
    groups = _registry_group_summary(group_names)
    return {
        "category": "source_registry",
        "minimum_daily_stack": registry.get("minimum_daily_stack", []),
        "source_priority_rules": registry.get("source_priority_rules", []),
        "market_day_workflow": registry.get("market_day_workflow", {}),
        "registry": groups,
    }


# Registry of fast, network-read-only category jobs.
CATEGORY_JOBS: dict[str, Callable[[Settings], dict[str, Any]]] = {
    "market": refresh_market,
    "news": refresh_news,
    "social": refresh_social,
    "xtwitter": refresh_xtwitter,
    "government": refresh_government,
    "trump": refresh_trump,
    "political": refresh_political,
    "macro": refresh_macro,
    "global": refresh_global,
    "official_economic": refresh_official_economic,
    "company_events": refresh_company_events,
    "options_volatility": refresh_options_volatility,
    "reference_dashboards": refresh_reference_dashboards,
    "automation_apis": refresh_automation_apis,
    "paid_platforms": refresh_paid_platforms,
    "source_registry": refresh_source_registry,
}


# --------------------------------------------------------------------------- #
# Status persistence so the Jobs tab can show last-refresh per category.
# --------------------------------------------------------------------------- #
def _status_path(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / STATUS_FILE


def load_refresh_status(settings: Settings | None = None) -> dict[str, Any]:
    import json

    settings = settings or get_settings()
    path = _status_path(settings)
    if not path.exists():
        return {"categories": {}, "last_run": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"categories": {}, "last_run": None}


def _save_status(settings: Settings, results: dict[str, dict]) -> None:
    import json

    data = load_refresh_status(settings)
    cats = data.get("categories", {})
    for name, res in results.items():
        cats[name] = {
            "status": res.get("status", "ok"),
            "finished_at": res.get("finished_at"),
            "elapsed_sec": res.get("elapsed_sec"),
            "summary": res.get("summary"),
            "error": res.get("error"),
        }
    data = {"categories": cats, "last_run": _now()}
    _status_path(settings).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _one_line(category: str, payload: dict[str, Any]) -> str:
    """A short human summary used in the Jobs tab cell."""
    c = category
    if c == "market":
        mv = ", ".join(f"{m['ticker']} {m['day_change_pct']:+.2f}%" for m in payload.get("top_movers", [])[:3])
        return f"{payload.get('live', 0)}/{payload.get('checked', 0)} live · movers: {mv or 'n/a'}"
    if c == "news":
        prov = ", ".join(payload.get("providers", [])) or "none"
        latest = payload.get("latest_published")
        when = f" · latest {latest[:16].replace('T', ' ')} UTC" if latest else ""
        return f"{payload.get('total_items', 0)} live items from [{prov}]{when}"
    if c == "social":
        srcs = ", ".join(payload.get("sources", [])) or "none"
        return f"{payload.get('available', 0)}/{payload.get('tickers', 0)} names with sentiment via [{srcs}]"
    if c == "xtwitter":
        if not payload.get("enabled"):
            return "key-gated (set X_BEARER_TOKEN, paid plan) — skipped, never scraped"
        latest = payload.get("latest_published")
        when = f" · latest {latest[:16].replace('T', ' ')} UTC" if latest else ""
        return f"{payload.get('company_tweets', 0)} company + {payload.get('government_tweets', 0)} gov tweets{when}"
    if c in ("government", "trump", "political"):
        bk = payload.get("by_kind", {})
        kinds = ", ".join(f"{k}:{v}" for k, v in bk.items()) or "none"
        latest = payload.get("latest_published")
        when = f" · latest {latest[:16].replace('T', ' ')} UTC" if latest else ""
        return f"{payload.get('matched_events', 0)} relevant of {payload.get('total_events', 0)} events ({kinds}){when}"
    if c == "macro":
        if payload.get("available"):
            src = payload.get("source") or "fred"
            n = len(payload.get("values", {}))
            return f"{n} live macro series via [{src}]"
        return payload.get("note") or "unavailable"
    if c == "global":
        return f"{payload.get('regime', 'n/a')} ({len(payload.get('indexes', []))} indexes)"
    if c == "official_economic":
        reg = payload.get("registry", {})
        macro = payload.get("macro", {})
        gov = payload.get("government", {})
        return (f"official macro/government grouped · macro={macro.get('available')} "
                f"· events={gov.get('total_events', 0)} · sources={reg.get('source_count', 0)}")
    if c == "company_events":
        return (f"{payload.get('with_sec_data', 0)}/{payload.get('tickers', 0)} SEC-covered "
                f"· {payload.get('recent_filing_count', 0)} recent filings · earnings/IR registry included")
    if c == "options_volatility":
        src = ", ".join(f"{k}:{v}" for k, v in (payload.get("by_source") or {}).items()) or "none"
        return f"{payload.get('with_options', 0)}/{payload.get('tickers', 0)} chains · sources {src} · Cboe/VIX registry included"
    if c in ("reference_dashboards", "automation_apis", "paid_platforms"):
        reg = payload.get("registry", {})
        counts = ", ".join(f"{k}:{v}" for k, v in (reg.get("status_counts") or {}).items()) or "none"
        return f"{reg.get('source_count', 0)} sources considered ({counts})"
    if c == "source_registry":
        reg = payload.get("registry", {})
        stack = ", ".join(payload.get("minimum_daily_stack", [])[:5])
        return f"{reg.get('source_count', 0)} registered sources · minimum stack: {stack}..."
    return "done"


def run_refresh_jobs(
    categories: list[str] | None = None,
    *,
    settings: Settings | None = None,
    max_workers: int = 8,
) -> dict[str, Any]:
    """Run the requested category jobs IN PARALLEL (one thread each) and return
    per-category results. Defaults to every category."""
    settings = settings or get_settings()
    cats = categories or list(CATEGORY_JOBS.keys())
    cats = [c for c in cats if c in CATEGORY_JOBS]
    started = time.monotonic()
    results: dict[str, dict] = {}

    def _timed(c: str) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            payload = CATEGORY_JOBS[c](settings)
            return {
                "status": "ok",
                "finished_at": _now(),
                "elapsed_sec": round(time.monotonic() - t0, 2),
                "summary": _one_line(c, payload),
                "data": payload,
            }
        except Exception as exc:
            log.warning("refresh job %s failed: %s", c, exc)
            return {"status": "failed", "finished_at": _now(),
                    "elapsed_sec": round(time.monotonic() - t0, 2),
                    "error": f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(cats)))) as pool:
        future_to_cat = {pool.submit(_timed, c): c for c in cats}
        for fut in as_completed(future_to_cat):
            c = future_to_cat[fut]
            results[c] = fut.result()

    _save_status(settings, results)
    return {
        "ran": cats,
        "elapsed_sec": round(time.monotonic() - started, 2),
        "parallel": True,
        "results": results,
        "as_of": _now(),
    }


def run_refresh_and_analyze(
    *,
    settings: Settings | None = None,
    strategy: str = "swing",
    horizon: str = "5D",
) -> dict[str, Any]:
    """Refresh ALL categories in parallel, then run the full prediction pipeline
    so the dashboard reflects freshly analyzed data ("the post should analyze")."""
    settings = settings or get_settings()
    refreshed = run_refresh_jobs(settings=settings)
    analysis: dict[str, Any]
    try:
        from .alerts.dispatcher import dispatch_alerts
        from .pipeline import run_pipeline
        from .reports.generator import write_reports

        result = run_pipeline(strategy=strategy, horizon=horizon, settings=settings)
        written = write_reports(result, settings.reports_dir)
        fired = dispatch_alerts(result.predictions, settings, settings.data_dir)
        analysis = {"status": "success", "predictions": len(result.predictions),
                    "alerts": len(fired), "reports": {k: str(v) for k, v in written.items()}}
    except Exception as exc:
        log.warning("analyze step failed: %s", exc)
        analysis = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    return {"refresh": refreshed, "analyze": analysis, "as_of": _now()}
