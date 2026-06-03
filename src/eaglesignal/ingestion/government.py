"""SKILL-054/055/060 Government, policy, and fiscal connector.

Pulls market-relevant signals from official U.S. government sources. All sources
here are real and mostly keyless:

* U.S. Treasury FiscalData  (keyless) — average interest rate on the public debt
* Federal Register API      (keyless) — presidential & agency documents (policy risk)
* White House RSS           (keyless) — presidential actions directly from whitehouse.gov
* BLS public API            (BLS_API_KEY optional) — CPI + unemployment latest prints
* GDELT DOC 2.0             (keyless) — U.S. policy / government news headlines

Returns a GovSnapshot consumed by analysis/macro.py (regime nudge) and the
evidence store (policy headlines). Degrades to ``available=False`` offline; never
fabricates values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from typing import Optional
import xml.etree.ElementTree as ET

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("ingestion.government")

_UA = {"User-Agent": "EagleSignal/0.1 research"}

# BLS series we care about for a macro regime nudge.
_BLS_SERIES = {
    "CUUR0000SA0": "cpi_index",      # CPI-U, all items
    "LNS14000000": "unemployment",   # unemployment rate
}


@dataclass
class GovEvent:
    title: str
    source: str
    url: str
    published_at: Optional[datetime] = None
    kind: str = "policy"  # policy | fiscal | labor | fda | antitrust


@dataclass
class GovSnapshot:
    values: dict[str, float] = field(default_factory=dict)
    events: list[GovEvent] = field(default_factory=list)
    available: bool = False
    providers: list[str] = field(default_factory=list)
    note: str = ""


def _treasury_avg_rate() -> Optional[float]:
    try:
        import requests

        resp = requests.get(
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
            "/v2/accounting/od/avg_interest_rates",
            params={"sort": "-record_date", "page[size]": 1, "format": "json"},
            headers=_UA, timeout=20,
        )
        if resp.status_code != 200:
            return None
        rows = (resp.json() or {}).get("data", [])
        if rows and rows[0].get("avg_interest_rate_amt") not in (None, ""):
            return float(rows[0]["avg_interest_rate_amt"])
    except Exception as exc:
        log.warning("Treasury FiscalData failed: %s", exc)
    return None


def _federal_register(max_records: int = 8) -> list[GovEvent]:
    events: list[GovEvent] = []
    try:
        import requests

        since = (date.today() - timedelta(days=7)).isoformat()
        resp = requests.get(
            "https://www.federalregister.gov/api/v1/documents.json",
            params={
                "per_page": max_records,
                "order": "newest",
                "conditions[type][]": "PRESDOCU",
                "conditions[publication_date][gte]": since,
                "fields[]": ["title", "html_url", "publication_date", "type"],
            },
            headers=_UA, timeout=20,
        )
        if resp.status_code != 200:
            return events
        for d in (resp.json() or {}).get("results", []):
            pub = None
            if d.get("publication_date"):
                try:
                    pub = datetime.fromisoformat(d["publication_date"]).replace(tzinfo=timezone.utc)
                except ValueError:
                    pub = None
            events.append(
                GovEvent(title=d.get("title", ""), source="Federal Register",
                         url=d.get("html_url", ""), published_at=pub, kind="policy")
            )
    except Exception as exc:
        log.warning("Federal Register failed: %s", exc)
    return events


def _white_house_actions(max_records: int = 10) -> list[GovEvent]:
    """Direct White House presidential-actions RSS feed.

    This complements Federal Register because Federal Register can lag signed
    actions by a day or more, while the White House feed is closer to live.
    """
    events: list[GovEvent] = []
    try:
        import requests
        from email.utils import parsedate_to_datetime

        resp = requests.get(
            "https://www.whitehouse.gov/presidential-actions/feed/",
            headers=_UA,
            timeout=20,
        )
        if resp.status_code != 200:
            return events
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item")[:max_records]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_raw = item.findtext("pubDate") or ""
            pub = None
            if pub_raw:
                try:
                    pub = parsedate_to_datetime(pub_raw).astimezone(timezone.utc)
                except Exception:
                    pub = None
            kind = "trump_admin" if any(
                term in title.lower()
                for term in ("trump", "tariff", "executive order", "presidential action", "memorandum")
            ) else "policy"
            events.append(GovEvent(title=title, source="White House", url=link, published_at=pub, kind=kind))
    except Exception as exc:
        log.warning("White House presidential actions feed failed: %s", exc)
    return events


def _fda_enforcement(max_records: int = 6) -> list[GovEvent]:
    """openFDA enforcement (recalls) for drugs and devices — keyless, real,
    market-moving safety events. We surface the most recent classified recalls."""
    events: list[GovEvent] = []
    try:
        import requests

        for endpoint, label in (("drug", "FDA Drug Recall"), ("device", "FDA Device Recall")):
            resp = requests.get(
                f"https://api.fda.gov/{endpoint}/enforcement.json",
                params={"sort": "report_date:desc", "limit": max_records},
                headers=_UA, timeout=20,
            )
            if resp.status_code != 200:
                continue
            for r in (resp.json() or {}).get("results", []):
                firm = r.get("recalling_firm", "")
                cls = r.get("classification", "")
                reason = (r.get("reason_for_recall", "") or "")[:120]
                pub = None
                raw = r.get("report_date")
                if raw and len(raw) == 8:
                    try:
                        pub = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
                    except ValueError:
                        pub = None
                title = f"{cls} recall — {firm}: {reason}".strip(" —:")
                events.append(GovEvent(title=title, source=label, url="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
                                       published_at=pub, kind="fda"))
    except Exception as exc:
        log.warning("openFDA failed: %s", exc)
    return events


def _doj_ftc_actions(max_records: int = 6) -> list[GovEvent]:
    """DOJ Antitrust + FTC regulatory actions via the Federal Register agency
    filter (keyless). Antitrust/merger/consumer-protection actions move Big Tech,
    healthcare, finance, and consumer names."""
    events: list[GovEvent] = []
    try:
        import requests

        agencies = {
            "federal-trade-commission": "FTC",
            "antitrust-division": "DOJ Antitrust",
        }
        since = (date.today() - timedelta(days=30)).isoformat()
        for slug, label in agencies.items():
            resp = requests.get(
                "https://www.federalregister.gov/api/v1/documents.json",
                params={
                    "per_page": max_records, "order": "newest",
                    "conditions[agencies][]": slug,
                    "conditions[publication_date][gte]": since,
                    "fields[]": ["title", "html_url", "publication_date"],
                },
                headers=_UA, timeout=20,
            )
            if resp.status_code != 200:
                continue
            for d in (resp.json() or {}).get("results", []):
                pub = None
                if d.get("publication_date"):
                    try:
                        pub = datetime.fromisoformat(d["publication_date"]).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pub = None
                events.append(GovEvent(title=f"{label}: {d.get('title', '')}", source=label,
                                       url=d.get("html_url", ""), published_at=pub, kind="antitrust"))
    except Exception as exc:
        log.warning("DOJ/FTC Federal Register failed: %s", exc)
    return events


def _gdelt_policy(max_records: int = 8) -> list[GovEvent]:
    from .http_util import gdelt_doc

    events: list[GovEvent] = []
    articles = gdelt_doc(
        ('("Donald Trump" OR Trump OR "Trump administration" OR "White House" OR '
         '"executive order" OR tariff OR tariffs OR sanctions OR "export controls" OR '
         '"AI Action Plan" OR "data center" OR "CHIPS Act" OR "Federal Reserve" OR '
         'Treasury OR Congress OR DOJ OR FTC OR FDA OR "Department of Defense") '
         'sourcelang:english'),
        max_records=max_records,
    )
    for a in articles or []:
        pub = None
        if a.get("seendate"):
            try:
                pub = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                pub = None
        events.append(
            GovEvent(title=a.get("title", ""), source=a.get("domain", "GDELT"),
                     url=a.get("url", ""), published_at=pub, kind="trump_admin")
        )
    return events


def _bls_latest(api_key: Optional[str]) -> dict[str, float]:
    """BLS public API. v2 needs a key; v1 works keyless with tighter limits."""
    out: dict[str, float] = {}
    try:
        import requests

        payload: dict = {"seriesid": list(_BLS_SERIES.keys())}
        if api_key:
            payload["registrationkey"] = api_key
        resp = requests.post(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            json=payload, headers={**_UA, "Content-Type": "application/json"}, timeout=25,
        )
        if resp.status_code != 200:
            return out
        for s in (resp.json() or {}).get("Results", {}).get("series", []):
            name = _BLS_SERIES.get(s.get("seriesID", ""))
            data = s.get("data", [])
            if name and data and data[0].get("value") not in (None, ""):
                out[name] = float(data[0]["value"])
    except Exception as exc:
        log.warning("BLS failed: %s", exc)
    return out


def _x_government(max_records: int = 10) -> list[GovEvent]:
    """Official government-handle / policy tweets via the X API v2 (key-gated)."""
    from .x_twitter import government_query, search_recent, x_enabled

    if not x_enabled():
        return []
    res = search_recent(government_query(), max_results=max_records)
    events: list[GovEvent] = []
    for tw in res.tweets[:max_records]:
        events.append(GovEvent(title=tw.text[:200], source=f"X/@{tw.author}",
                               url=tw.url, published_at=tw.created_at, kind="policy"))
    return events


def fetch_government() -> GovSnapshot:
    settings = get_settings()
    if not settings.enable_government_feeds:
        return GovSnapshot(available=False, note="Government feeds disabled (ENABLE_GOVERNMENT_FEEDS=false).")

    values: dict[str, float] = {}
    events: list[GovEvent] = []
    providers: list[str] = []

    rate = _treasury_avg_rate()
    if rate is not None:
        values["treasury_avg_interest_rate"] = rate
        providers.append("treasury_fiscaldata")

    bls = _bls_latest(settings.bls_api_key)
    if bls:
        values.update(bls)
        providers.append("bls")

    fr = _federal_register()
    if fr:
        events.extend(fr)
        providers.append("federal_register")

    wh = _white_house_actions()
    if wh:
        events.extend(wh)
        providers.append("white_house")

    fda = _fda_enforcement()
    if fda:
        events.extend(fda)
        providers.append("openfda")

    dojftc = _doj_ftc_actions()
    if dojftc:
        events.extend(dojftc)
        providers.append("doj_ftc")

    pol = _gdelt_policy()
    if pol:
        events.extend(pol)
        providers.append("gdelt_policy")

    xgov = _x_government()
    if xgov:
        events.extend(xgov)
        providers.append("x_government")

    available = bool(values or events)
    return GovSnapshot(
        values=values, events=events, available=available, providers=providers,
        note="" if available else "No government data reachable; policy context neutral.",
    )
