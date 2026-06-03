"""SKILL-050/070 News + social sentiment engine.

Scores recent headlines with a transparent finance lexicon (no opaque model).
News is the primary, reliable source; social is intentionally capped so a single
viral post can never dominate (per MASTER_AI_PROMPT non-negotiables). Each
headline becomes an evidence record with polarity and reliability.
"""
from __future__ import annotations

from typing import Optional

from ..config import Settings
from ..ingestion.news import NewsResult
from ..ingestion.social import SocialSnapshot
from ..schemas import SignalComponent
from ..utils.evidence import EvidenceStore

POSITIVE = {
    "beat", "beats", "surge", "soar", "record", "upgrade", "outperform", "strong",
    "growth", "approval", "approved", "wins", "win", "contract", "raises", "raised",
    "bullish", "rally", "profit", "expansion", "buyback", "dividend", "breakthrough",
}
NEGATIVE = {
    "miss", "misses", "plunge", "plummet", "downgrade", "underperform", "weak",
    "lawsuit", "probe", "investigation", "recall", "cut", "cuts", "warning", "warns",
    "bearish", "selloff", "loss", "layoff", "layoffs", "fraud", "decline", "halt",
    "bankruptcy", "default", "delay", "rejected", "antitrust",
}


def _headline_polarity(title: str) -> float:
    words = {w.strip(".,!?:;\"'()").lower() for w in title.split()}
    pos = len(words & POSITIVE)
    neg = len(words & NEGATIVE)
    if pos == neg:
        return 0.0
    return max(-1.0, min(1.0, (pos - neg) / max(1, pos + neg)))


def sentiment_signal(
    ticker: str,
    news: NewsResult,
    store: EvidenceStore,
    social: Optional[SocialSnapshot] = None,
    settings: Optional[Settings] = None,
) -> SignalComponent:
    notes: list[str] = []
    has_news = news.available and bool(news.items)
    has_social = social is not None and social.available and (social.bullish + social.bearish) > 0

    if not has_news and not has_social:
        return SignalComponent(
            name="sentiment", score=50.0, weight=0.0, available=False,
            rationale=["No recent news headlines or social signal available."],
        )

    news_score: Optional[float] = None
    if has_news:
        items = news.items[:15]
        titles = [item.title for item in items]
        # Prefer the local-LLM (GPU/Ollama) classifier when enabled+reachable;
        # otherwise fall back to the transparent lexicon. Same ±35 swing either way.
        llm_scores = None
        method = "lexicon"
        try:
            from .llm_sentiment import classify_headlines

            llm_scores = classify_headlines(titles, settings)
            if llm_scores is not None:
                method = "local-LLM (Ollama)"
        except Exception:
            llm_scores = None
        polarities: list[float] = []
        for idx, item in enumerate(items):
            pol = float(llm_scores[idx]) if llm_scores is not None else _headline_polarity(item.title)
            polarities.append(pol)
            store.add(
                entity=ticker, source_name=item.source, source_type=item.source_type,
                claim=item.title, url=item.url, published_at=item.published_at,
                polarity=pol, data_type="news",
            )
        avg = sum(polarities) / len(polarities)
        news_score = 50 + avg * 35  # +/-35 max swing from headlines
        pos_n = sum(1 for p in polarities if p > 0)
        neg_n = sum(1 for p in polarities if p < 0)
        srcs = ", ".join(news.providers) if news.providers else "news"
        notes.append(f"{len(polarities)} headlines ({srcs}) via {method}: {pos_n} positive, {neg_n} negative (avg polarity {avg:+.2f}).")

    social_score: Optional[float] = None
    if has_social:
        # Capped contribution: social can move the blend by at most +/-15 points.
        social_score = 50 + max(-1.0, min(1.0, social.net_sentiment)) * 15
        store.add(
            entity=ticker, source_name="StockTwits", source_type="social",
            claim=f"Social mood {social.bullish} bull / {social.bearish} bear of {social.message_count} msgs",
            url=f"https://stocktwits.com/symbol/{ticker}", polarity=social.net_sentiment, data_type="social",
        )
        notes.append(
            f"Social (StockTwits): {social.bullish} bullish / {social.bearish} bearish "
            f"of {social.message_count} msgs (net {social.net_sentiment:+.2f}, capped)."
        )

    # News dominates (0.75) over social (0.25); social alone is allowed but weak.
    if news_score is not None and social_score is not None:
        score = 0.75 * news_score + 0.25 * social_score
    elif news_score is not None:
        score = news_score
    else:
        score = social_score  # social-only, intentionally near-neutral range
    return SignalComponent(name="sentiment", score=max(0, min(100, score)), weight=0.0, rationale=notes)
