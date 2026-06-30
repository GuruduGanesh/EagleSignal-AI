"""Shared HTTP helpers + per-host throttling (SKILL-172 Rate-Limit Manager).

Some free endpoints enforce strict spacing (GDELT asks for one request every 5
seconds). Because several connectors hit the same host within one run, we keep a
process-wide last-call clock per host and sleep just enough to stay compliant —
respecting the source's terms instead of hammering it.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

from ..utils.logging import get_logger

log = get_logger("ingestion.http")


def _proxies() -> Optional[dict]:
    """Optional outbound proxy for free endpoints that block datacenter IPs.

    The API container runs from a datacenter IP, so Cloudflare-fronted sources
    (StockTwits) and Reddit refuse it and we fall back to news-derived sentiment.
    Pointing ``EAGLESIGNAL_HTTP_PROXY`` at a residential/ISP proxy routes these
    requests through an allowed IP. This is a transport change only — it never
    bypasses a bot challenge, login, or paywall (still terms-compliant). When the
    var is unset, requests also honors the standard HTTP_PROXY/HTTPS_PROXY vars.
    """
    p = os.environ.get("EAGLESIGNAL_HTTP_PROXY") or os.environ.get("EAGLESIGNAL_PROXY")
    return {"http": p, "https": p} if p else None

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 EagleSignal/0.1 (research)"
)

_lock = threading.Lock()
_last_call: dict[str, float] = {}


def _throttle(host: str, min_interval: float) -> None:
    with _lock:
        now = time.monotonic()
        last = _last_call.get(host, 0.0)
        wait = min_interval - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


def throttled_get(host_key: str, url: str, *, params=None, headers=None,
                  min_interval: float = 0.0, timeout: int = 20, retries: int = 1):
    """GET with per-host spacing and one polite retry on HTTP 429."""
    import requests

    hdrs = {"User-Agent": _BROWSER_UA}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries + 1):
        if min_interval:
            _throttle(host_key, min_interval)
        try:
            resp = requests.get(url, params=params, headers=hdrs, timeout=timeout,
                                 proxies=_proxies())
        except Exception as exc:
            # Retry transient network errors (timeout / connection reset) with
            # backoff — important under scan concurrency where flaky endpoints
            # (e.g. CBOE delayed quotes) intermittently time out.
            if attempt < retries:
                time.sleep(min(2.0 * (attempt + 1), 6.0))
                continue
            log.warning("GET %s failed after %d attempts: %s", host_key, attempt + 1, exc)
            return None
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(max(min_interval, 3.0 * (attempt + 1)))
            continue
        return resp
    return None


def gdelt_doc(query: str, *, max_records: int = 15) -> Optional[list]:
    """Throttled GDELT DOC 2.0 ArtList query (>=5s spacing, retry once on 429)."""
    resp = throttled_get(
        "gdelt", "https://api.gdeltproject.org/api/v2/doc/doc",
        params={"query": query, "mode": "ArtList", "maxrecords": max_records,
                "format": "json", "sort": "DateDesc"},
        min_interval=6.0, timeout=25, retries=2,
    )
    if resp is None or resp.status_code != 200:
        return None
    try:
        return (resp.json() or {}).get("articles", [])
    except Exception:
        return None
