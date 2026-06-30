"""SKILL-050/051 Multi-source news connector.

Aggregates many *legal, public* sources and merges them into one deduplicated
feed so a single outlet can't dominate sentiment:

* NewsAPI              (NEWS_API_KEY)   — reputable financial/general news
* Finnhub company news (FINNHUB_API_KEY)— company-tagged headlines
* Google News RSS      (keyless)        — top-source aggregator (publisher-attributed)
* Yahoo Finance RSS    (keyless)        — quote-page headline feed
* Hacker News RSS      (keyless)        — tech/AI/semis/geopolitical clue stream
* Seeking Alpha Market News RSS (keyless)— market-wide breaking news
* Seeking Alpha All Articles RSS (keyless) — latest analysis/editorial stream
* GDELT DOC 2.0        (keyless)        — broad global news/event coverage
* yfinance headlines   (keyless)        — quote-page company headlines
* StockTwits stream    (keyless)        — exchange-tagged retail news/links

Each item carries source, published timestamp, and a source_type used for the
evidence store's reliability + freshness scoring (DATA_SOURCES.md sections 3, 7).
Order of trust is preserved on dedupe: news API > Google/Yahoo publisher > GDELT >
yfinance > social. Only public RSS/APIs are used — no scraping behind paywalls or
logins, and no private/non-public sources.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from xml.etree import ElementTree as ET

from ..config import get_settings
from ..analysis.index_options import is_index_option_ticker
from ..utils.logging import get_logger

log = get_logger("ingestion.news")


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published_at: Optional[datetime] = None
    source_type: str = "news"


@dataclass
class NewsResult:
    items: list[NewsItem] = field(default_factory=list)
    available: bool = False
    providers: list[str] = field(default_factory=list)


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()[:90]


def _from_yfinance(ticker: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        import yfinance as yf

        for n in (yf.Ticker(ticker).news or [])[:15]:
            content = n.get("content", n)  # yfinance schema shifted over versions
            title = content.get("title") or n.get("title", "")
            if not title:
                continue
            ts = n.get("providerPublishTime")
            pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            prov = content.get("provider", {})
            source = (prov.get("displayName") if isinstance(prov, dict) else None) or n.get("publisher", "yfinance")
            url = (content.get("canonicalUrl", {}) or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else n.get("link", "")
            items.append(NewsItem(title=title, source=source, url=url or "", published_at=pub))
    except Exception as exc:
        log.warning("yfinance news failed for %s: %s", ticker, exc)
    return items


def _from_newsapi(ticker: str, api_key: str, company_name: str | None = None) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        import requests

        query = f'("{ticker}" OR "{company_name}")' if company_name else ticker
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "sortBy": "publishedAt", "language": "en", "pageSize": 15, "apiKey": api_key},
            timeout=20,
        )
        if resp.status_code == 200:
            for a in resp.json().get("articles", []):
                pub = None
                if a.get("publishedAt"):
                    try:
                        pub = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                    except ValueError:
                        pub = None
                items.append(
                    NewsItem(
                        title=a.get("title", ""),
                        source=(a.get("source") or {}).get("name", "NewsAPI"),
                        url=a.get("url", ""),
                        published_at=pub,
                    )
                )
    except Exception as exc:
        log.warning("NewsAPI failed for %s: %s", ticker, exc)
    return items


def _parse_rss(xml_text: str, default_source: str, source_type: str = "news") -> list[NewsItem]:
    """Parse an RSS 2.0 feed (stdlib only) into NewsItems."""
    items: list[NewsItem] = []
    try:
        from email.utils import parsedate_to_datetime

        root = ET.fromstring(xml_text)
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            if not title:
                continue
            link = (it.findtext("link") or "").strip()
            pub = None
            raw = it.findtext("pubDate")
            if raw:
                try:
                    pub = parsedate_to_datetime(raw)
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pub = None
            # Google News attributes the originating publisher in <source>.
            src_el = it.find("source")
            source = (src_el.text.strip() if src_el is not None and src_el.text else default_source)
            items.append(NewsItem(title=title, source=source, url=link, published_at=pub, source_type=source_type))
    except ET.ParseError:
        pass
    return items


def _from_google_news(ticker: str, company_name: str | None = None) -> list[NewsItem]:
    """Google News RSS — keyless aggregator across top publishers (attributed)."""
    from .http_util import throttled_get

    query = f'"{company_name}" stock' if company_name else f"{ticker} stock"
    resp = throttled_get(
        "google_news", "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        min_interval=0.5, timeout=12,
    )
    if resp is None or resp.status_code != 200:
        return []
    return _parse_rss(resp.text, "Google News", "news")[:15]


def _from_yahoo_rss(ticker: str) -> list[NewsItem]:
    """Yahoo Finance per-symbol headline RSS — keyless."""
    from .http_util import throttled_get

    resp = throttled_get(
        "yahoo_rss", "https://feeds.finance.yahoo.com/rss/2.0/headline",
        params={"s": ticker.upper(), "region": "US", "lang": "en-US"},
        min_interval=0.5, timeout=12,
    )
    if resp is None or resp.status_code != 200:
        return []
    return _parse_rss(resp.text, "Yahoo Finance", "news")[:15]


def _last_n_days(items: list[NewsItem], days: int = 2) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        item for item in items
        if item.published_at is None or item.published_at >= cutoff
    ]


def _last_n_hours(items: list[NewsItem], hours: int = 24, *, require_timestamp: bool = True) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: list[NewsItem] = []
    for item in items:
        if item.published_at is None:
            if not require_timestamp:
                out.append(item)
            continue
        if item.published_at >= cutoff:
            out.append(item)
    return out


_MARKET_CLUE_TERMS = (
    "stock", "market", "nasdaq", "s&p", "dow", "fed", "rates", "jobs", "inflation",
    "tariff", "sanction", "oil", "war", "israel", "iran", "russia", "ukraine",
    "china", "taiwan", "chip", "semiconductor", "ai", "gpu", "data center",
    "nvidia", "amd", "intel", "microsoft", "amazon", "google", "meta", "apple",
)


def _market_relevant(items: list[NewsItem]) -> list[NewsItem]:
    out = []
    for item in items:
        title = item.title.lower()
        if any(term in title for term in _MARKET_CLUE_TERMS):
            out.append(item)
    return out


_COMPANY_STOPWORDS = {
    "inc", "inc.", "corp", "corp.", "corporation", "company", "co", "co.",
    "holdings", "holding", "group", "class", "plc", "limited", "ltd", "technology",
    "technologies", "common", "stock", "shares", "systems",
}


def _contains_symbol(text: str, symbol: str) -> bool:
    if not text or not symbol:
        return False
    return re.search(rf"(?<![A-Z0-9]){re.escape(symbol.upper())}(?![A-Z0-9])", text.upper()) is not None


def _entity_relevant(items: list[NewsItem], ticker: str, company_name: str | None = None) -> list[NewsItem]:
    symbol = (ticker or "").strip().upper()
    name = (company_name or "").strip().lower()
    name_tokens = [
        tok for tok in re.findall(r"[a-z0-9&]+", name)
        if len(tok) >= 4 and tok not in _COMPANY_STOPWORDS
    ]
    out: list[NewsItem] = []
    for item in items:
        text = " ".join(x for x in (item.title, item.url) if x)
        tl = text.lower()
        if symbol and _contains_symbol(text, symbol):
            out.append(item)
            continue
        if company_name and any(tok in tl for tok in name_tokens):
            out.append(item)
    return out


def _is_market_context(ticker: str, company_name: str | None = None) -> bool:
    t = ticker.upper()
    name = (company_name or "").lower()
    return (
        is_index_option_ticker(t)
        or t in {"SPY", "QQQ", "DIA", "IWM"}
        or "index" in name
        or "s&p" in name
        or "nasdaq" in name
        or "russell" in name
        or "dow jones" in name
    )


def _from_hacker_news_market(days: int = 2) -> list[NewsItem]:
    """Hacker News front-page RSS, filtered to recent market/tech catalyst clues."""
    from .http_util import throttled_get

    resp = throttled_get("hacker_news", "https://news.ycombinator.com/rss", min_interval=1.0, timeout=12)
    if resp is None or resp.status_code != 200:
        return []
    return _market_relevant(_last_n_days(_parse_rss(resp.text, "Hacker News", "aggregator"), days))[:20]


def _from_seeking_alpha_market_news(days: int = 2) -> list[NewsItem]:
    """Seeking Alpha market-news RSS — public market-wide headlines only."""
    from .http_util import throttled_get

    resp = throttled_get("seeking_alpha_market", "https://seekingalpha.com/market-news.xml", min_interval=1.0, timeout=12)
    if resp is None or resp.status_code != 200:
        return []
    return _last_n_days(_parse_rss(resp.text, "Seeking Alpha Market News", "news"), days)[:25]


def _from_seeking_alpha_latest_articles(
    ticker: str,
    company_name: str | None = None,
    *,
    hours: int = 24,
    market_context: bool = False,
) -> list[NewsItem]:
    """Seeking Alpha official latest-articles feed (no HTML scraping)."""
    from .http_util import throttled_get

    resp = throttled_get("seeking_alpha_articles", "https://seekingalpha.com/feed.xml", min_interval=1.0, timeout=12)
    if resp is None or resp.status_code != 200:
        return []
    items = _last_n_hours(_parse_rss(resp.text, "Seeking Alpha Latest Articles", "analysis"), hours)
    if market_context:
        return _market_relevant(items)[:25]
    return _entity_relevant(items, ticker, company_name)[:15]


def _from_finnhub_news(ticker: str, api_key: str) -> list[NewsItem]:
    """Finnhub company-news API (key-gated, reputable financial coverage)."""
    items: list[NewsItem] = []
    try:
        import requests

        today = datetime.now(timezone.utc).date()
        resp = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker.upper(),
                    "from": (today - timedelta(days=14)).isoformat(),
                    "to": today.isoformat(), "token": api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            return items
        for a in (resp.json() or [])[:15]:
            headline = a.get("headline", "")
            if not headline:
                continue
            ts = a.get("datetime")
            pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            items.append(NewsItem(title=headline, source=a.get("source", "Finnhub"),
                                  url=a.get("url", ""), published_at=pub))
    except Exception as exc:
        log.warning("Finnhub news failed for %s: %s", ticker, exc)
    return items


def _from_x(ticker: str, company_name: str | None = None) -> list[NewsItem]:
    """High-engagement company tweets via the official X API v2 (key-gated)."""
    from .x_twitter import company_query, search_recent, x_enabled

    if not x_enabled():
        return []
    res = search_recent(company_query(ticker, company_name), max_results=25)
    items: list[NewsItem] = []
    for tw in res.tweets[:15]:
        items.append(NewsItem(
            title=tw.text[:200], source=f"X/@{tw.author}", url=tw.url,
            published_at=tw.created_at, source_type="social",
        ))
    return items


def _from_bluesky(ticker: str, company_name: str | None = None) -> list[NewsItem]:
    """Breaking posts from Bluesky's KEYLESS public search (AT Protocol).

    Captures real-time microblog chatter — including breaking-news/journalist
    accounts that cross-post from X — without any API key, scraping, or ToS
    bypass. This is our legal real-time substitute for unauthenticated X reads."""
    from datetime import datetime

    from .http_util import throttled_get

    query = f'"{company_name}"' if company_name else f"${ticker}"
    resp = throttled_get(
        "bluesky", "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
        params={"q": query, "limit": 25, "sort": "latest"},
        headers={"Accept": "application/json"}, min_interval=1.0, timeout=10,
    )
    if resp is None or resp.status_code != 200:
        return []
    items: list[NewsItem] = []
    for p in (resp.json() or {}).get("posts", [])[:15]:
        rec = p.get("record", {}) or {}
        text = rec.get("text", "")
        if not text:
            continue
        handle = (p.get("author", {}) or {}).get("handle", "bsky")
        pub = None
        ca = rec.get("createdAt")
        if ca:
            try:
                pub = datetime.fromisoformat(ca.replace("Z", "+00:00"))
            except ValueError:
                pub = None
        uri = p.get("uri", "")
        rkey = uri.split("/")[-1] if uri else ""
        url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""
        items.append(NewsItem(
            title=text[:200], source=f"Bluesky/@{handle}", url=url,
            published_at=pub, source_type="social",
        ))
    return items


def _from_gdelt(ticker: str, company_name: str | None = None) -> list[NewsItem]:
    """GDELT DOC 2.0 — keyless broad news/event coverage. Quote the company name
    when known (a bare ticker is too noisy for a global news index)."""
    from .http_util import gdelt_doc

    items: list[NewsItem] = []
    query = f'"{company_name}"' if company_name else ticker
    articles = gdelt_doc(f"{query} sourcelang:english", max_records=15)
    for a in articles or []:
        pub = None
        raw = a.get("seendate")
        if raw:
            try:
                pub = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                pub = None
        items.append(
            NewsItem(
                title=a.get("title", ""),
                source=a.get("domain", "GDELT"),
                url=a.get("url", ""),
                published_at=pub,
                source_type="aggregator",
            )
        )
    return items


def _from_stocktwits(ticker: str) -> list[NewsItem]:
    """StockTwits messages that carry a link become exchange-tagged news items.
    (Sentiment scoring of the stream lives in ingestion/social.py.)"""
    from .http_util import throttled_get

    items: list[NewsItem] = []
    try:
        resp = throttled_get(
            "stocktwits",
            f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json",
            headers={"Accept": "application/json", "Accept-Language": "en-US,en;q=0.9"},
            min_interval=1.0, timeout=8,
        )
        if resp is None or resp.status_code != 200:
            return items
        for m in (resp.json() or {}).get("messages", [])[:20]:
            links = m.get("links") or []
            if not links:
                continue
            pub = None
            if m.get("created_at"):
                try:
                    pub = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))
                except ValueError:
                    pub = None
            link = links[0]
            items.append(
                NewsItem(
                    title=(link.get("title") or m.get("body", ""))[:200],
                    source=link.get("source", {}).get("name", "StockTwits") if isinstance(link.get("source"), dict) else "StockTwits",
                    url=link.get("url", ""),
                    published_at=pub,
                    source_type="social",
                )
            )
    except Exception as exc:
        log.warning("StockTwits news failed for %s: %s", ticker, exc)
    return items


# Short-TTL in-process cache so the parallel refresh phase and the prediction
# pipeline that immediately follows fetch each ticker's news ONCE per run instead
# of twice — this halves load on Bluesky/GDELT/etc. and keeps live microblog
# sources from being rate-limited away before the analysis runs.
_NEWS_TTL = 900.0  # seconds (15 min)
_news_cache: dict[str, tuple[float, "NewsResult"]] = {}


def fetch_news(ticker: str, company_name: str | None = None) -> NewsResult:
    import time

    key = ticker.upper()
    now = time.time()
    hit = _news_cache.get(key)
    if hit and (now - hit[0]) < _NEWS_TTL and hit[1].available:
        return hit[1]
    res = _fetch_news_uncached(ticker, company_name)
    if res.available:
        _news_cache[key] = (now, res)
    return res


def _fetch_news_uncached(ticker: str, company_name: str | None = None) -> NewsResult:
    """Merge every available source, newest first, deduped by normalized title."""
    settings = get_settings()
    max_age_hours = max(1, int(getattr(settings, "news_max_age_hours", 24) or 24))
    market_context = _is_market_context(ticker, company_name)
    collected: list[tuple[str, list[NewsItem]]] = []

    if settings.news_api_key:
        collected.append(("newsapi", _from_newsapi(ticker, settings.news_api_key, company_name)))
    if settings.finnhub_api_key:
        collected.append(("finnhub", _from_finnhub_news(ticker, settings.finnhub_api_key)))
    collected.append(("google_news", _from_google_news(ticker, company_name)))
    collected.append(("yahoo_rss", _from_yahoo_rss(ticker)))
    collected.append((
        "seeking_alpha_latest_articles_24h",
        _from_seeking_alpha_latest_articles(ticker, company_name, hours=max_age_hours, market_context=market_context),
    ))
    if market_context:
        collected.append(("hacker_news_2d", _from_hacker_news_market(days=2)))
        collected.append(("seeking_alpha_market_2d", _from_seeking_alpha_market_news(days=2)))
    collected.append(("gdelt", _from_gdelt(ticker, company_name)))
    collected.append(("yfinance", _from_yfinance(ticker)))
    if settings.x_bearer_token:
        collected.append(("x_twitter", _from_x(ticker, company_name)))
    # Keyless real-time microblog (legal X substitute) — always on.
    collected.append(("bluesky", _from_bluesky(ticker, company_name)))
    if settings.enable_social_sentiment:
        collected.append(("stocktwits", _from_stocktwits(ticker)))

    merged: list[NewsItem] = []
    seen: set[str] = set()
    providers: list[str] = []
    for name, items in collected:
        if items:
            providers.append(name)
        for it in items:
            key = _norm_title(it.title)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(it)

    merged = _last_n_hours(merged, max_age_hours)
    merged.sort(key=lambda i: i.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return NewsResult(items=merged, available=bool(merged), providers=providers)
