"""SKILL-200 AI investment advisor (research only, not financial advice).

A conversational layer over the latest EagleSignal run. It NEVER invents prices
or facts: it reasons only over the predictions/evidence the pipeline already
produced from real data. Two backends:

* LLM-backed   — when OPENAI_API_KEY, ANTHROPIC_API_KEY, or opt-in local Ollama is
  configured, the model is given a strict research-only system prompt plus a
  compact, factual context built from the latest signals. It explains and
  summarizes; it does not place trades and is told to surface uncertainty, risk,
  and invalidation.
* Rule-based   — deterministic fallback that ranks/explains signals directly from
  the report JSON. Always available, no key required, fully offline-safe.

Every answer carries the research-only disclaimer. The advisor will not promise
returns, will not use non-public information, and will recommend "no trade" when
confidence is low or risk blocks the setup.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from . import __disclaimer__
from .config import Settings, get_settings
from .utils.logging import get_logger

log = get_logger("advisor")

SYSTEM_PROMPT = (
    "You are EagleSignal AI, a research-only market analysis assistant for U.S., "
    "European, and Asian equities, ETFs, and indexes. You are NOT a financial "
    "advisor and must never promise returns. Reason ONLY from the structured "
    "signal context provided; never invent prices, news, or numbers. For every "
    "view, state direction, confidence, risk, expected move, and an invalidation "
    "condition. Prefer 'no trade' when confidence is low or risk is high. Never "
    "use or claim access to insider/non-public information. End with a one-line "
    "reminder that this is research, not financial advice."
)


def load_latest_predictions(settings: Optional[Settings] = None) -> list[dict]:
    settings = settings or get_settings()
    base = settings.reports_dir
    if not base.exists():
        return []
    for day in sorted([d for d in base.iterdir() if d.is_dir()], reverse=True):
        f = day / "signals.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return []
    return []


def _compact(p: dict) -> dict:
    f = p.get("forecast", {}) or {}
    em = p.get("expected_move", {}) or {}
    oi = p.get("options_trade_idea", {}) or {}
    top_options = []
    for ex in (oi.get("top_expiries") or [])[:3]:
        top_options.append({
            "expiration": ex.get("expiration"),
            "action": ex.get("action"),
            "confidence": ex.get("confidence"),
            "readiness": ex.get("readiness"),
            "contract": ex.get("reference_contract"),
            "premium": ex.get("reference_option_price"),
            "bid": ex.get("reference_bid"),
            "ask": ex.get("reference_ask"),
            "option_quality": ex.get("option_quality_score"),
            "spread_pct": ex.get("bid_ask_spread_pct"),
            "why": (ex.get("reasons") or [])[:3],
        })
    return {
        "ticker": p.get("ticker"),
        "direction": p.get("direction"),
        "opportunity": p.get("opportunity_score"),
        "confidence": p.get("confidence_score"),
        "risk": p.get("risk_score"),
        "risk_level": (p.get("risk") or {}).get("risk_level"),
        "severity": p.get("severity"),
        "expected_move_pct": [em.get("low_pct"), em.get("high_pct")],
        "forecast_prob_up": f.get("prob_up"),
        "forecast_band_pct": [f.get("p05_return_pct"), f.get("p95_return_pct")],
        "catalysts": (p.get("catalysts") or [])[:3],
        "policy_impacts": (p.get("policy_impacts") or [])[:2],
        "global_correlations": dict(list((p.get("global_correlations") or {}).items())[:4]),
        "invalidation": (p.get("invalidation_conditions") or [])[:1],
        "price": (p.get("market_snapshot") or {}).get("current_price"),
        "warnings": (p.get("risk") or {}).get("warnings", [])[:2],
        "options": {
            "bias": oi.get("bias"),
            "strategy": oi.get("strategy"),
            "data_source": oi.get("data_source"),
            "algo_confluence": oi.get("algo_confluence"),
            "top_expiries": top_options,
        },
    }


# --------------------------------------------------------------------------- #
# Rule-based backend
# --------------------------------------------------------------------------- #
def _fmt_pick(c: dict) -> str:
    em = c["expected_move_pct"]
    em_txt = f"{em[0]:+.1f}%/{em[1]:+.1f}%" if em and em[0] is not None else "n/a"
    pup = f"{c['forecast_prob_up']:.0%}" if c.get("forecast_prob_up") is not None else "n/a"
    return (f"- {c['ticker']}: {c['direction']} | opp {c['opportunity']:.0f} · conf "
            f"{c['confidence']:.0f} · risk {c['risk']:.0f} ({c['risk_level']}) · P(up) {pup} · "
            f"move {em_txt}. Invalidation: {c['invalidation'][0] if c['invalidation'] else 'n/a'}")


def _rule_based(message: str, comps: list[dict], threshold: int, portfolio: Optional[list[dict]]) -> str:
    msg = message.lower()
    by_ticker = {c["ticker"]: c for c in comps}

    # Intent: explain a specific ticker.
    m = re.search(r"\b([A-Z]{1,5})\b", message)
    if m and m.group(1) in by_ticker and any(w in msg for w in ("why", "explain", "tell me about", "what about", "should i")):
        c = by_ticker[m.group(1)]
        lines = [f"**{c['ticker']} — research view (not advice)**", _fmt_pick(c)]
        if c["catalysts"]:
            lines.append("Catalysts: " + "; ".join(c["catalysts"]))
        if c["policy_impacts"]:
            lines.append("Policy links: " + "; ".join(c["policy_impacts"]))
        if c["global_correlations"]:
            lines.append("Global linkage: " + ", ".join(f"{k} {v:+.2f}" for k, v in c["global_correlations"].items()))
        if c["warnings"]:
            lines.append("Warnings: " + "; ".join(c["warnings"]))
        return "\n".join(lines)

    # Intent: portfolio review.
    if portfolio or any(w in msg for w in ("portfolio", "review", "my holdings", "i hold", "i own")):
        if not portfolio:
            return ("Share your holdings as ticker/quantity pairs (e.g. AAPL:10, MSFT:5) and I'll review each "
                    "against the latest signals. " + _foot())
        lines = ["**Portfolio review (research only)**"]
        for h in portfolio:
            t = str(h.get("ticker", "")).upper()
            c = by_ticker.get(t)
            if not c:
                lines.append(f"- {t}: no current signal in the latest run; can't comment on fresh data.")
                continue
            stance = "consider trimming/avoid" if c["direction"] in ("bearish", "neutral_to_bearish", "avoid") else (
                "supported by signals" if c["confidence"] >= threshold and c["direction"] in ("bullish", "neutral_to_bullish")
                else "hold / watch — mixed signal")
            lines.append(f"- {t} (qty {h.get('quantity', '?')}): {stance}. " + _fmt_pick(c)[2:])
        return "\n".join(lines)

    # Intent: what to buy / top ideas.
    if any(w in msg for w in ("buy", "best", "top", "idea", "pick", "opportunit", "recommend")):
        cands = [c for c in comps if c["direction"] in ("bullish", "neutral_to_bullish")
                 and c["confidence"] >= threshold and c["risk_level"] in ("low", "medium")]
        cands.sort(key=lambda c: c["opportunity"], reverse=True)
        if not cands:
            return ("No setup currently clears the confidence/risk bar, so the research-supported stance is "
                    "**no trade / wait**. " + _foot())
        lines = [f"**Top research-supported ideas (conf >= {threshold}, risk <= medium):**"]
        lines += [_fmt_pick(c) for c in cands[:5]]
        return "\n".join(lines)

    # Default: market summary.
    ranked = sorted(comps, key=lambda c: c["opportunity"], reverse=True)
    lines = [f"**Latest run covers {len(comps)} names. Top by opportunity:**"]
    lines += [_fmt_pick(c) for c in ranked[:5]]
    return "\n".join(lines)


def _foot() -> str:
    return f"_{__disclaimer__}_"


# --------------------------------------------------------------------------- #
# LLM backends (optional, key-gated)
# --------------------------------------------------------------------------- #
def _llm_answer(message: str, comps: list[dict], settings: Settings) -> Optional[str]:
    provider = settings.advisor_provider
    context = json.dumps(comps, default=str)[:12000]
    user = f"Signal context (JSON, from real data):\n{context}\n\nUser question: {message}"

    use_anthropic = settings.anthropic_api_key and provider in ("auto", "anthropic")
    use_openai = settings.openai_api_key and provider in ("auto", "openai")
    use_ollama = provider == "ollama" or (provider == "auto" and bool(settings.ollama_base_url))

    try:
        import requests

        if use_anthropic:
            model = settings.advisor_model or "claude-3-5-sonnet-latest"
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": model, "max_tokens": 900, "system": SYSTEM_PROMPT,
                      "messages": [{"role": "user", "content": user}]},
                timeout=60,
            )
            if r.status_code == 200:
                return "".join(b.get("text", "") for b in r.json().get("content", []))
            log.warning("Anthropic advisor HTTP %s", r.status_code)
        if use_openai:
            model = settings.advisor_model or "gpt-4o-mini"
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 900,
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": user}]},
                timeout=60,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            log.warning("OpenAI advisor HTTP %s", r.status_code)
        if use_ollama:
            model = settings.advisor_model or "llama3.1"
            base = (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
            prompt = f"{SYSTEM_PROMPT}\n\n{user}"
            r = requests.post(
                f"{base}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=90,
            )
            if r.status_code == 200:
                return r.json().get("response")
            log.warning("Ollama advisor HTTP %s", r.status_code)
    except Exception as exc:
        log.warning("LLM advisor failed, falling back to rules: %s", exc)
    return None


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def advise(
    message: str,
    *,
    settings: Optional[Settings] = None,
    predictions: Optional[list[dict]] = None,
    portfolio: Optional[list[dict]] = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    preds = predictions if predictions is not None else load_latest_predictions(settings)
    if not preds:
        return {"answer": "No signals available yet — run a scan first (POST /run or `eaglesignal run`).",
                "backend": "none", "used_signals": 0, "disclaimer": __disclaimer__}

    comps = [_compact(p) for p in preds]
    threshold = settings.confidence_threshold

    backend = "rules"
    answer: Optional[str] = None
    if settings.advisor_provider != "rules" and (
        settings.openai_api_key or settings.anthropic_api_key
        or settings.advisor_provider == "ollama" or settings.ollama_base_url
    ):
        answer = _llm_answer(message, comps, settings)
        if answer:
            backend = "llm"
    if answer is None:
        answer = _rule_based(message, comps, threshold, portfolio)

    if __disclaimer__.split(",")[0].lower() not in answer.lower():
        answer = f"{answer}\n\n{_foot()}"
    return {"answer": answer, "backend": backend, "used_signals": len(comps), "disclaimer": __disclaimer__}


def ollama_status(settings: Optional[Settings] = None) -> dict:
    """Probe the local Ollama (GPU) server so the user can verify it is live.

    Reports whether Ollama is configured, reachable, and which models are pulled.
    Never raises — a missing server just returns ``reachable: False``.
    """
    settings = settings or get_settings()
    base = settings.ollama_base_url or (
        "http://localhost:11434" if settings.advisor_provider == "ollama" else ""
    )
    base = base.rstrip("/")
    if not base:
        return {"configured": False, "reachable": False, "base_url": None, "models": [],
                "note": "Set OLLAMA_BASE_URL or ADVISOR_PROVIDER=ollama to enable the local LLM."}
    try:
        import requests

        r = requests.get(f"{base}/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m.get("name") for m in (r.json().get("models") or []) if m.get("name")]
            return {"configured": True, "reachable": True, "base_url": base, "models": models,
                    "advisor_model": settings.advisor_model or "llama3.1",
                    "note": "Ollama reachable." if models else "Ollama reachable but no models pulled (run `ollama pull llama3.1`)."}
        return {"configured": True, "reachable": False, "base_url": base, "models": [],
                "note": f"Ollama HTTP {r.status_code}."}
    except Exception as exc:
        return {"configured": True, "reachable": False, "base_url": base, "models": [],
                "note": f"Ollama unreachable: {exc}"[:140]}


def advisor_health(settings: Optional[Settings] = None) -> dict:
    """Which AI backends are available right now (advisor + GPU sentiment)."""
    settings = settings or get_settings()
    if settings.anthropic_api_key and settings.advisor_provider in ("auto", "anthropic"):
        active = "anthropic"
    elif settings.openai_api_key and settings.advisor_provider in ("auto", "openai"):
        active = "openai"
    elif settings.advisor_provider == "ollama" or settings.ollama_base_url:
        active = "ollama"
    else:
        active = "rules"
    oll = ollama_status(settings)
    llm_sentiment = bool(getattr(settings, "enable_llm_sentiment", False)) and oll.get("reachable", False)
    return {
        "advisor_provider": settings.advisor_provider,
        "active_backend": active,
        "ollama": oll,
        "llm_sentiment_enabled": getattr(settings, "enable_llm_sentiment", False),
        "llm_sentiment_active": llm_sentiment,
        "disclaimer": __disclaimer__,
    }


def parse_portfolio(text: Optional[str]) -> list[dict]:
    """Parse 'AAPL:10, MSFT:5' or 'AAPL 10; MSFT 5' into holdings."""
    if not text:
        return []
    holdings: list[dict] = []
    for part in re.split(r"[,;]", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"([A-Za-z.\-]{1,6})\s*[:= ]\s*([0-9]*\.?[0-9]+)", part)
        if m:
            holdings.append({"ticker": m.group(1).upper(), "quantity": float(m.group(2))})
    return holdings
