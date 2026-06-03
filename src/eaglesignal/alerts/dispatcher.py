"""SKILL-170 Alerting engine.

Sends only high-priority (P0/P1), fresh, non-duplicate signals — targeted
monitoring rather than noisy broadcasts. Deduplicates by (ticker, direction,
severity, day). Channels: console (always), Slack/Discord webhooks (optional).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings
from ..schemas import PredictionResult, Severity
from ..utils.logging import get_logger

log = get_logger("alerts")


def _dedupe_key(p: PredictionResult) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{day}|{p.ticker}|{p.direction.value}|{p.severity.value}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _load_sent(state_file: Path) -> set[str]:
    if state_file.exists():
        try:
            return set(json.loads(state_file.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_sent(state_file: Path, keys: set[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(sorted(keys)), encoding="utf-8")


def _format(p: PredictionResult) -> str:
    em = p.expected_move
    em_txt = f"{em.low_pct:+.1f}%/{em.high_pct:+.1f}%" if em and em.low_pct is not None else "n/a"
    return (
        f"[{p.severity.value}] {p.ticker} {p.direction.value} | opp {p.opportunity_score:.0f} "
        f"conf {p.confidence_score:.0f} risk {p.risk_score:.0f} | move {em_txt}"
    )


def _post_webhook(url: str, text: str, kind: str) -> None:
    try:
        import requests

        payload = {"content": text} if kind == "discord" else {"text": text}
        requests.post(url, json=payload, timeout=10)
    except Exception as exc:
        log.warning("%s webhook failed: %s", kind, exc)


def dispatch_alerts(predictions: list[PredictionResult], settings: Settings, state_dir: Path) -> list[str]:
    state_file = state_dir / "alert_state.json"
    sent = _load_sent(state_file)
    fired: list[str] = []

    for p in predictions:
        if p.severity not in (Severity.P0, Severity.P1):
            continue
        if p.risk.block_trade:
            continue
        key = _dedupe_key(p)
        if key in sent:
            log.info("Suppressed duplicate alert for %s", p.ticker)
            continue
        msg = _format(p)
        log.info("ALERT %s", msg)
        if settings.slack_webhook_url:
            _post_webhook(settings.slack_webhook_url, f"🦅 EagleSignal {msg}", "slack")
        if settings.discord_webhook_url:
            _post_webhook(settings.discord_webhook_url, f"🦅 EagleSignal {msg}", "discord")
        sent.add(key)
        fired.append(msg)

    _save_sent(state_file, sent)
    return fired
