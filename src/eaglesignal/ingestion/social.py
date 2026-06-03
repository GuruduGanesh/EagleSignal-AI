"""SKILL-073/074 Social sentiment collector + analyzer (legal sources only).

StockTwits exposes a public, terms-permitted symbol stream where many messages
carry an explicit Bullish/Bearish label. We use those labels (not opaque text
mining) to compute a transparent social mood and a message-volume read. Social
is deliberately capped downstream so a viral post can never dominate a signal
(DATA_SOURCES.md section 4; MASTER_AI_PROMPT non-negotiables).

X/Twitter and Reddit remain behind their own keys/flags and are documented but
not enabled by default. Nothing here is fabricated — if the stream is
unreachable the result is simply ``available=False``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("ingestion.social")


# Minimal local lexicon (kept here to avoid a circular import with analysis).
_POS = {"buy", "bull", "bullish", "long", "calls", "up", "moon", "beat", "beats",
        "breakout", "rally", "surge", "strong", "upgrade", "gain", "gains", "win"}
_NEG = {"sell", "bear", "bearish", "short", "puts", "down", "crash", "dump", "miss",
        "misses", "weak", "downgrade", "loss", "drop", "fall", "fear", "lawsuit"}


@dataclass
class SocialSnapshot:
    ticker: str
    message_count: int = 0
    bullish: int = 0
    bearish: int = 0
    net_sentiment: float = 0.0  # -1 .. +1 from labelled messages
    available: bool = False
    source: str = ""
    sample_titles: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)
    note: str = ""


def _from_stocktwits(ticker: str, token: Optional[str]) -> Optional[SocialSnapshot]:
    from .http_util import throttled_get

    try:
        params = {"access_token": token} if token else None
        resp = throttled_get(
            "stocktwits",
            f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json",
            params=params,
            headers={"Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"},
            min_interval=1.0, timeout=8,
        )
        if resp is None or resp.status_code != 200:
            return None
        messages = (resp.json() or {}).get("messages", [])
        if not messages:
            return None
        bull = bear = 0
        samples: list[str] = []
        for m in messages:
            ent = (m.get("entities") or {}).get("sentiment") or {}
            basic = ent.get("basic") if isinstance(ent, dict) else None
            if basic == "Bullish":
                bull += 1
            elif basic == "Bearish":
                bear += 1
            if len(samples) < 5 and m.get("body"):
                samples.append(m["body"][:160])
        labelled = bull + bear
        net = (bull - bear) / labelled if labelled else 0.0
        return SocialSnapshot(
            ticker=ticker.upper(), message_count=len(messages), bullish=bull, bearish=bear,
            net_sentiment=round(net, 3), available=True, source="stocktwits",
            sample_titles=samples,
            note=f"{len(messages)} recent messages; {labelled} carried an explicit bull/bear label.",
        )
    except Exception as exc:
        log.warning("StockTwits social failed for %s: %s", ticker, exc)
        return None


def _classify(text: str) -> int:
    words = {w.strip(".,!?:;\"'()$#").lower() for w in text.split()}
    pos = len(words & _POS)
    neg = len(words & _NEG)
    return 1 if pos > neg else -1 if neg > pos else 0


def _from_reddit(ticker: str) -> Optional[SocialSnapshot]:
    """Reddit public search JSON (keyless, light read). Classifies post titles
    with a small bull/bear lexicon. Reddit terms permit low-volume reads with a
    descriptive User-Agent; we never authenticate-bypass or scrape private data."""
    from .http_util import throttled_get

    try:
        resp = throttled_get(
            "reddit",
            "https://www.reddit.com/search.json",
            params={"q": f"${ticker} OR {ticker}", "sort": "new", "limit": 40, "t": "week"},
            headers={"Accept": "application/json"},
            min_interval=2.0, timeout=8,
        )
        if resp is None or resp.status_code != 200:
            return None
        children = (resp.json() or {}).get("data", {}).get("children", [])
        if not children:
            return None
        bull = bear = 0
        samples: list[str] = []
        for c in children:
            title = (c.get("data") or {}).get("title", "")
            if not title:
                continue
            v = _classify(title)
            if v > 0:
                bull += 1
            elif v < 0:
                bear += 1
            if len(samples) < 5:
                samples.append(title[:160])
        labelled = bull + bear
        net = (bull - bear) / labelled if labelled else 0.0
        return SocialSnapshot(
            ticker=ticker.upper(), message_count=len(children), bullish=bull, bearish=bear,
            net_sentiment=round(net, 3), available=True, source="reddit", sample_titles=samples,
            note=f"{len(children)} recent Reddit posts; {labelled} classified bull/bear by lexicon.",
        )
    except Exception as exc:
        log.warning("Reddit social failed for %s: %s", ticker, exc)
        return None


def _from_bluesky(ticker: str, company_name: Optional[str] = None) -> Optional[SocialSnapshot]:
    """Bluesky (AT Protocol) public post search — KEYLESS and terms-permitted.

    Bluesky exposes an unauthenticated public search endpoint on its app view
    (``app.bsky.feed.searchPosts``). Many finance/journalist/breaking-news
    accounts that historically posted to X now cross-post here, so this is the
    best *legal, keyless* real-time microblog substitute for X. We never scrape
    or bypass any access control."""
    from .http_util import throttled_get

    query = f'"{company_name}"' if company_name else f"${ticker}"
    try:
        resp = throttled_get(
            "bluesky",
            "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
            params={"q": query, "limit": 50, "sort": "latest"},
            headers={"Accept": "application/json"},
            min_interval=1.0, timeout=10,
        )
        if resp is None or resp.status_code != 200:
            return None
        posts = (resp.json() or {}).get("posts", [])
        if not posts:
            return None
        bull = bear = 0
        samples: list[str] = []
        latest = None
        for p in posts:
            rec = p.get("record", {}) or {}
            text = rec.get("text", "")
            if not text:
                continue
            v = _classify(text)
            if v > 0:
                bull += 1
            elif v < 0:
                bear += 1
            if len(samples) < 5:
                samples.append(text[:160])
            ca = rec.get("createdAt")
            if ca and (latest is None or ca > latest):
                latest = ca
        labelled = bull + bear
        net = (bull - bear) / labelled if labelled else 0.0
        note = f"{len(posts)} recent Bluesky posts; {labelled} classified bull/bear."
        if latest:
            note += f" Latest {latest}."
        return SocialSnapshot(
            ticker=ticker.upper(), message_count=len(posts), bullish=bull, bearish=bear,
            net_sentiment=round(net, 3), available=True, source="bluesky", sample_titles=samples,
            note=note,
        )
    except Exception as exc:
        log.warning("Bluesky social failed for %s: %s", ticker, exc)
        return None


def _from_mastodon(ticker: str, company_name: Optional[str] = None) -> Optional[SocialSnapshot]:
    """Mastodon public hashtag timeline — KEYLESS and terms-permitted.

    The flagship instance ``mastodon.social`` exposes an unauthenticated public
    timeline per hashtag. We read the cashtag/ticker hashtag and classify toots
    with the same transparent lexicon. Public endpoint only — no auth bypass."""
    from .http_util import throttled_get

    tag = ticker.lower()
    try:
        resp = throttled_get(
            "mastodon",
            f"https://mastodon.social/api/v1/timelines/tag/{tag}",
            params={"limit": 40},
            headers={"Accept": "application/json"},
            min_interval=1.0, timeout=10,
        )
        if resp is None or resp.status_code != 200:
            return None
        import re

        toots = resp.json() or []
        if not toots:
            return None
        bull = bear = 0
        samples: list[str] = []
        latest = None
        for t in toots:
            # content is HTML; strip tags for the lexicon.
            text = re.sub(r"<[^>]+>", " ", t.get("content", ""))
            if not text.strip():
                continue
            v = _classify(text)
            if v > 0:
                bull += 1
            elif v < 0:
                bear += 1
            if len(samples) < 5:
                samples.append(text.strip()[:160])
            ca = t.get("created_at")
            if ca and (latest is None or ca > latest):
                latest = ca
        labelled = bull + bear
        net = (bull - bear) / labelled if labelled else 0.0
        note = f"{len(toots)} recent Mastodon posts on #{tag}; {labelled} classified bull/bear."
        if latest:
            note += f" Latest {latest}."
        return SocialSnapshot(
            ticker=ticker.upper(), message_count=len(toots), bullish=bull, bearish=bear,
            net_sentiment=round(net, 3), available=True, source="mastodon", sample_titles=samples,
            note=note,
        )
    except Exception as exc:
        log.warning("Mastodon social failed for %s: %s", ticker, exc)
        return None


def _from_x(ticker: str, company_name: Optional[str] = None) -> Optional[SocialSnapshot]:
    """Bull/bear sentiment over recent company tweets via the official X API v2."""
    from .x_twitter import company_query, search_recent, x_enabled

    if not x_enabled():
        return None
    res = search_recent(company_query(ticker, company_name), max_results=50)
    if not res.available or not res.tweets:
        return None
    bull = bear = 0
    samples: list[str] = []
    for tw in res.tweets:
        v = _classify(tw.text)
        if v > 0:
            bull += 1
        elif v < 0:
            bear += 1
        if len(samples) < 5:
            samples.append(tw.text[:160])
    labelled = bull + bear
    net = (bull - bear) / labelled if labelled else 0.0
    return SocialSnapshot(
        ticker=ticker.upper(), message_count=len(res.tweets), bullish=bull, bearish=bear,
        net_sentiment=round(net, 3), available=True, source="x_twitter", sample_titles=samples,
        note=f"{len(res.tweets)} recent tweets via X API v2; {labelled} classified bull/bear by lexicon.",
    )


def _from_news(ticker: str, company_name: Optional[str] = None) -> Optional[SocialSnapshot]:
    """Keyless fallback: derive a transparent sentiment read from the live
    multi-source news headlines (Google/Yahoo/GDELT/Finnhub/yfinance). This never
    leaves the Sentiment category empty just because StockTwits/Reddit block
    datacenter IPs — it reflects what the real, recent news flow is saying.
    Capped and clearly labelled as news-derived, not retail-chatter."""
    try:
        from .news import fetch_news

        res = fetch_news(ticker, company_name)
        if not res or not res.items:
            return None
        pos = neg = 0
        latest: Optional[datetime] = None
        for it in res.items:
            s = _classify(it.title or "")
            if s > 0:
                pos += 1
            elif s < 0:
                neg += 1
            if getattr(it, "published_at", None):
                if latest is None or it.published_at > latest:
                    latest = it.published_at
        total = len(res.items)
        labelled = pos + neg
        net = round((pos - neg) / labelled, 3) if labelled else 0.0
        snap = SocialSnapshot(
            ticker=ticker.upper(), message_count=total, bullish=pos, bearish=neg,
            net_sentiment=net, available=True,
            source=f"news_derived ({', '.join(res.providers)})",
            sample_titles=[it.title[:120] for it in res.items[:3]],
            note="Sentiment derived from live news headline polarity (keyless fallback when social streams are blocked).",
        )
        if latest is not None:
            snap.note += f" Latest item {latest.isoformat()}."
        return snap
    except Exception as exc:
        log.warning("news-derived sentiment failed for %s: %s", ticker, exc)
        return None


# Short-TTL in-process cache so a single collection run (parallel refresh phase +
# the prediction pipeline) fetches each ticker's social mood ONCE instead of twice.
# Without this the refresh phase exhausts Bluesky/StockTwits rate limits and the
# pipeline that follows is throttled down to the news-derived fallback.
_SOCIAL_TTL = 900.0  # seconds (15 min) — covers one refresh+analyze cycle
_social_cache: dict[str, tuple[float, "SocialSnapshot"]] = {}


def fetch_social(ticker: str, company_name: Optional[str] = None) -> SocialSnapshot:
    import time

    key = ticker.upper()
    now = time.time()
    hit = _social_cache.get(key)
    # Reuse a recent LIVE read (don't pin a degraded news_derived fallback — let
    # later calls retry a real social source once the rate-limit window resets).
    if hit and (now - hit[0]) < _SOCIAL_TTL and hit[1].available and not hit[1].source.startswith("news_derived"):
        return hit[1]
    snap = _fetch_social_uncached(ticker, company_name)
    if snap.available:
        _social_cache[key] = (now, snap)
    return snap


def _fetch_social_uncached(ticker: str, company_name: Optional[str] = None) -> SocialSnapshot:
    settings = get_settings()
    # Even with social streams disabled we still produce a real, news-derived
    # sentiment so the Sentiment signal is always populated and considered.
    attempts: list[str] = []
    sources = []
    # X first when a token is configured (highest signal), then keyless streams.
    if settings.x_bearer_token:
        sources.append(("x_twitter", lambda: _from_x(ticker, company_name)))
    if settings.enable_social_sentiment:
        sources += [("stocktwits", lambda: _from_stocktwits(ticker, settings.stocktwits_token)),
                    ("bluesky", lambda: _from_bluesky(ticker, company_name)),
                    ("mastodon", lambda: _from_mastodon(ticker, company_name)),
                    ("reddit", lambda: _from_reddit(ticker))]
    # Always-available keyless fallback last.
    sources.append(("news_derived", lambda: _from_news(ticker, company_name)))

    for name, fn in sources:
        snap = fn()
        if snap and snap.available:
            snap.attempts = attempts + [f"{name}=ok"]
            return snap
        attempts.append(f"{name}=blocked_or_empty")

    return SocialSnapshot(
        ticker=ticker.upper(), attempts=attempts,
        note=("No sentiment source reachable (social streams blocked and no news items). "
              "Set STOCKTWITS_TOKEN / X_BEARER_TOKEN or run from a residential IP."),
    )
