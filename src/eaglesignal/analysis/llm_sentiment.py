"""GPU/LLM news-sentiment classifier (§3.3, G.3) — research only.

Upgrades the crude bag-of-words lexicon to a real language model when a **local
Ollama** server (GPU-accelerated on this laptop) is available. It is strictly
opt-in (``ENABLE_LLM_SENTIMENT=true`` + a reachable Ollama) and ALWAYS degrades
to the deterministic lexicon when Ollama is absent, slow, or returns junk — so
the daily scan never blocks on it and offline behavior is unchanged.

The model only scores the *polarity* of already-collected real headlines; it
never invents news and is capped downstream exactly like the lexicon, so a
chatty model can't dominate a signal.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Optional

from ..config import Settings, get_settings
from ..utils.logging import get_logger

log = get_logger("analysis.llm_sentiment")

_CLASSIFY_SYSTEM = (
    "You are a financial news sentiment classifier. For each numbered headline, "
    "judge its likely short-term impact on the mentioned stock and return ONLY a "
    "compact JSON array of objects {\"i\": <index>, \"s\": <score>} where score is a "
    "float from -1.0 (very bearish) to 1.0 (very bullish), 0 for neutral. No prose."
)


def _ollama_base(settings: Settings) -> Optional[str]:
    if settings.advisor_provider == "ollama" or settings.ollama_base_url:
        return (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
    return None


@lru_cache(maxsize=1)
def _ollama_reachable(base: str, model: str) -> bool:
    """Cheap one-shot reachability probe (cached for the process)."""
    try:
        import requests

        r = requests.get(f"{base}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def llm_sentiment_enabled(settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    if not getattr(settings, "enable_llm_sentiment", False):
        return False
    base = _ollama_base(settings)
    if not base:
        return False
    model = settings.advisor_model or "llama3.1"
    return _ollama_reachable(base, model)


def classify_headlines(titles: list[str], settings: Optional[Settings] = None) -> Optional[list[float]]:
    """Return a polarity in [-1,1] per headline via local Ollama, or None to fall
    back to the lexicon. Never raises."""
    settings = settings or get_settings()
    if not titles or not llm_sentiment_enabled(settings):
        return None
    base = _ollama_base(settings)
    model = settings.advisor_model or "llama3.1"
    capped = titles[:15]
    numbered = "\n".join(f"{i}. {t[:200]}" for i, t in enumerate(capped))
    prompt = f"{_CLASSIFY_SYSTEM}\n\nHeadlines:\n{numbered}\n\nJSON array:"
    try:
        import requests

        r = requests.post(
            f"{base}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0}},
            timeout=45,
        )
        if r.status_code != 200:
            log.warning("Ollama sentiment HTTP %s; using lexicon", r.status_code)
            return None
        raw = r.json().get("response", "")
        scores = _parse_scores(raw, len(capped))
        if scores is None:
            log.warning("Ollama sentiment parse failed; using lexicon")
            return None
        # Pad to the original length with neutral so callers can zip safely.
        scores += [0.0] * (len(titles) - len(scores))
        return scores[: len(titles)]
    except Exception as exc:
        log.warning("Ollama sentiment failed (%s); using lexicon", exc)
        return None


def _parse_scores(raw: str, n: int) -> Optional[list[float]]:
    """Extract a per-headline score array from the model's JSON-ish response."""
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    scores = [0.0] * n
    got = False
    for item in data:
        try:
            if isinstance(item, dict):
                i = int(item.get("i"))
                s = float(item.get("s"))
            else:  # bare number array
                i = data.index(item)
                s = float(item)
            if 0 <= i < n:
                scores[i] = max(-1.0, min(1.0, s))
                got = True
        except Exception:
            continue
    return scores if got else None
