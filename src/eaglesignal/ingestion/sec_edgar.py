"""SKILL-002/020/021 SEC EDGAR connector.

Uses the official, key-free SEC APIs (data.sec.gov / www.sec.gov). Per SEC fair
access policy a descriptive User-Agent with contact email is required and the
request rate is kept modest. Network failures degrade gracefully to empty
results (the pipeline marks fundamentals/filings as missing, never invented).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Optional

from ..config import get_settings
from ..utils.logging import get_logger

log = get_logger("ingestion.sec")

_TICKER_CIK_CACHE: dict[str, str] = {}
_LAST_CALL = 0.0
_THROTTLE_LOCK = Lock()


def _throttle(rate_per_sec: float = 5.0) -> None:
    global _LAST_CALL
    with _THROTTLE_LOCK:
        min_gap = 1.0 / rate_per_sec
        delta = time.monotonic() - _LAST_CALL
        if delta < min_gap:
            time.sleep(min_gap - delta)
        _LAST_CALL = time.monotonic()


def _get(url: str) -> Optional[dict]:
    try:
        import requests

        _throttle()
        headers = {"User-Agent": get_settings().sec_user_agent, "Accept-Encoding": "gzip, deflate"}
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()
        log.warning("SEC %s -> HTTP %s", url, resp.status_code)
    except Exception as exc:
        log.warning("SEC request failed (%s): %s", url, exc)
    return None


@dataclass
class Filing:
    form: str
    filed: str
    title: str
    url: str


@dataclass
class SecData:
    ticker: str
    cik: Optional[str] = None
    company_name: Optional[str] = None
    recent_filings: list[Filing] = field(default_factory=list)
    facts: dict = field(default_factory=dict)  # selected XBRL company facts
    available: bool = False


def resolve_cik(ticker: str) -> Optional[str]:
    """SKILL-002 entity resolution: ticker -> 10-digit zero-padded CIK."""
    ticker = ticker.upper()
    if not _TICKER_CIK_CACHE:
        data = _get("https://www.sec.gov/files/company_tickers.json")
        if data:
            for row in data.values():
                _TICKER_CIK_CACHE[str(row["ticker"]).upper()] = str(row["cik_str"]).zfill(10)
    return _TICKER_CIK_CACHE.get(ticker)


def _extract_fact(facts: dict, tag: str) -> Optional[float]:
    """Latest USD value for a us-gaap concept, if present."""
    try:
        units = facts["facts"]["us-gaap"][tag]["units"]
        series = units.get("USD") or next(iter(units.values()))
        latest = max(series, key=lambda r: r.get("end", ""))
        return float(latest["val"])
    except Exception:
        return None


def fetch_sec(ticker: str) -> SecData:
    cik = resolve_cik(ticker)
    out = SecData(ticker=ticker, cik=cik)
    if not cik:
        return out

    subs = _get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if subs:
        out.company_name = subs.get("name")
        recent = subs.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accs = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        material = {"10-K", "10-Q", "8-K", "S-1", "DEF 14A", "13F-HR", "4"}
        for i in range(min(len(forms), 40)):
            if forms[i] in material and len(out.recent_filings) < 12:
                acc = accs[i].replace("-", "")
                url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{docs[i]}"
                    if i < len(docs) and docs[i]
                    else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
                )
                out.recent_filings.append(
                    Filing(form=forms[i], filed=dates[i], title=f"{forms[i]} filed {dates[i]}", url=url)
                )

    facts = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    if facts:
        out.facts = {
            "revenue": _extract_fact(facts, "Revenues")
            or _extract_fact(facts, "RevenueFromContractWithCustomerExcludingAssessedTax"),
            "net_income": _extract_fact(facts, "NetIncomeLoss"),
            "assets": _extract_fact(facts, "Assets"),
            "liabilities": _extract_fact(facts, "Liabilities"),
            "stockholders_equity": _extract_fact(facts, "StockholdersEquity"),
            "cash": _extract_fact(facts, "CashAndCashEquivalentsAtCarryingValue"),
        }
    out.available = bool(out.recent_filings or out.facts)
    return out
