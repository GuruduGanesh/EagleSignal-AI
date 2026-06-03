"""SKILL-072 X / Twitter connector (official API v2, terms-compliant).

X (Twitter) no longer allows free/unauthenticated reads, and scraping around that
violates their Terms of Service. This connector therefore uses ONLY the official
X API v2 recent-search endpoint and activates only when ``X_BEARER_TOKEN`` is set
(a paid X API plan). Without a token it returns nothing and reports
``available=False`` — it never scrapes or bypasses access controls.

Used by:
* ingestion/news.py   — company/cashtag tweets as news items
* ingestion/social.py — bull/bear sentiment over recent tweets
* ingestion/government.py — official government-handle / policy tweets
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("ingestion.x")

_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
# X API v2 pay-per-use list price (2026). Used only to estimate spend in notes.
_X_COST_PER_READ_USD = 0.005


def _usage_path():
    return get_settings().data_dir / "x_api_usage.json"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def x_usage_today() -> dict:
    """Return {date, reads, est_cost_usd} for the current UTC day."""
    try:
        data = json.loads(_usage_path().read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if data.get("date") != _today():
        data = {"date": _today(), "reads": 0}
    reads = int(data.get("reads", 0))
    return {"date": data.get("date", _today()), "reads": reads,
            "est_cost_usd": round(reads * _X_COST_PER_READ_USD, 4)}


def _record_read() -> None:
    """Increment today's X read counter (best-effort, never raises)."""
    try:
        path = _usage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        usage = x_usage_today()
        usage["reads"] = int(usage["reads"]) + 1
        path.write_text(json.dumps({"date": usage["date"], "reads": usage["reads"]}), encoding="utf-8")
    except Exception as exc:
        log.warning("X usage counter write failed: %s", exc)


def x_budget_exhausted() -> bool:
    """True when today's reads have hit the configured daily budget (cost guard).
    A budget of 0 disables the cap."""
    budget = int(getattr(get_settings(), "x_daily_read_budget", 0) or 0)
    if budget <= 0:
        return False
    return x_usage_today()["reads"] >= budget


@dataclass
class Tweet:
    id: str
    text: str
    author: str
    created_at: Optional[datetime]
    like_count: int = 0
    retweet_count: int = 0

    @property
    def url(self) -> str:
        return f"https://twitter.com/i/web/status/{self.id}"

    @property
    def engagement(self) -> int:
        return self.like_count + self.retweet_count


@dataclass
class XResult:
    tweets: list[Tweet] = field(default_factory=list)
    available: bool = False
    note: str = ""


def x_enabled() -> bool:
    return bool(get_settings().x_bearer_token)


def search_recent(query: str, max_results: int = 25) -> XResult:
    """Official X API v2 recent search (last 7 days). Key-gated; never scrapes."""
    token = get_settings().x_bearer_token
    if not token:
        return XResult(available=False, note="X_BEARER_TOKEN not set; X/Twitter disabled.")
    # Cost guard (§3.5): stop calling the paid API once the daily read budget is
    # hit, so an enabled token can never run up a surprise bill.
    if x_budget_exhausted():
        u = x_usage_today()
        return XResult(available=False,
                       note=f"X daily read budget reached ({u['reads']} reads, ~${u['est_cost_usd']}). "
                            "Raise X_DAILY_READ_BUDGET to allow more.")
    try:
        import requests

        resp = requests.get(
            _SEARCH_URL,
            params={
                "query": query,
                "max_results": max(10, min(100, max_results)),
                "tweet.fields": "created_at,public_metrics,lang",
                "expansions": "author_id",
                "user.fields": "username,verified",
            },
            headers={"Authorization": f"Bearer {token}", "User-Agent": "EagleSignal/0.1 research"},
            timeout=20,
        )
        # Any answered request consumes paid quota — count it before branching.
        _record_read()
        if resp.status_code == 429:
            return XResult(available=False, note="X API rate limit (429).")
        if resp.status_code != 200:
            return XResult(available=False, note=f"X API HTTP {resp.status_code}.")
        body = resp.json() or {}
        users = {u["id"]: u.get("username", "x") for u in body.get("includes", {}).get("users", [])}
        tweets: list[Tweet] = []
        for t in body.get("data", []):
            pm = t.get("public_metrics", {}) or {}
            pub = None
            if t.get("created_at"):
                try:
                    pub = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                except ValueError:
                    pub = None
            tweets.append(Tweet(
                id=t.get("id", ""), text=t.get("text", ""),
                author=users.get(t.get("author_id", ""), "x"), created_at=pub,
                like_count=int(pm.get("like_count", 0)), retweet_count=int(pm.get("retweet_count", 0)),
            ))
        # Most-engaged first.
        tweets.sort(key=lambda tw: tw.engagement, reverse=True)
        return XResult(tweets=tweets, available=bool(tweets),
                       note=f"{len(tweets)} tweets via X API v2." if tweets else "No tweets returned.")
    except Exception as exc:
        log.warning("X API search failed: %s", exc)
        return XResult(available=False, note=f"X API error: {exc}"[:120])


def company_query(ticker: str, company_name: str | None) -> str:
    base = f'("{company_name}" OR ${ticker})' if company_name else f"${ticker} OR {ticker}"
    return f"{base} -is:retweet lang:en"


def government_query() -> str:
    handles = "from:WhiteHouse OR from:federalreserve OR from:SECGov OR from:USTreasury OR from:TheJusticeDept OR from:FTC"
    topics = '"executive order" OR tariff OR sanctions OR antitrust'
    return f"({handles} OR {topics}) -is:retweet lang:en"
