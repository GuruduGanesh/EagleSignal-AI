"""SKILL-130 Prediction engine — combines every component into one
PredictionResult with separate opportunity / confidence / risk scores, a
direction, expected move, catalysts, invalidation levels, and severity.
"""
from __future__ import annotations

import uuid
from typing import Optional

import numpy as np
import pandas as pd

from .. import __version__
from ..analysis import scoring
from ..analysis.cross_market import cross_market_signal
from ..analysis.event_radar import detect_event_radar
from ..analysis.forecast import forecast_signal
from ..analysis.global_correlation import global_correlations
from ..analysis.impact import map_impacts
from ..analysis.fundamentals import fundamental_signal
from ..analysis.macro import macro_signal
from ..analysis.options import OptionsAnalytics, analyze_expiries, analyze_options
from ..analysis.patterns import pattern_bias
from ..analysis.sentiment import sentiment_signal
from ..analysis.technical import atr, price_volume_signal, technical_signal
from ..config import Settings
from ..historical_store import iv_rank_metrics, load_option_contract_history
from ..ingestion.calendars import events_within_horizon
from ..ingestion.earnings import EarningsInfo, fetch_earnings
from ..ingestion.government import GovSnapshot
from ..ingestion.macro_fred import MacroSnapshot
from ..ingestion.market_data import MarketData
from ..ingestion.news import fetch_news
from ..ingestion.options_chain import OptionsChain
from ..ingestion.sec_edgar import SecData
from ..ingestion.social import fetch_social
from ..risk.manager import assess_risk
from ..schemas import (
    AssetEntity,
    Direction,
    Forecast,
    PredictionResult,
    Severity,
)
from ..utils.evidence import EvidenceStore


def _severity(opportunity: float, confidence: float, risk, threshold: int) -> Severity:
    if risk.block_trade:
        return Severity.P3
    strong = (opportunity >= 70 or opportunity <= 30) and confidence >= threshold
    if strong and risk.risk_level.value in ("low", "medium"):
        return Severity.P1
    if opportunity >= 60 or opportunity <= 40:
        return Severity.P2
    return Severity.P3


def _invalidation(df: pd.DataFrame, direction: Direction) -> list[str]:
    price = float(df["close"].iloc[-1])
    a = float(atr(df).iloc[-1])
    if direction in (Direction.bullish, Direction.neutral_to_bullish):
        return [f"Close below {price - 1.5 * a:,.2f} (1.5x ATR stop) invalidates the bullish thesis."]
    if direction in (Direction.bearish, Direction.neutral_to_bearish):
        return [f"Close above {price + 1.5 * a:,.2f} (1.5x ATR stop) invalidates the bearish thesis."]
    return ["No directional edge; revisit on a decisive break of recent range."]


def _confidence_trace(components, conf: float, ev_count: int, source_links: list[str],
                      freshness: dict, direction: str, data_quality: float, conviction: float) -> dict:
    available = [c for c in components if c.available]
    missing = [c for c in components if not c.available]
    scores = [c.score for c in available]
    dispersion = float(np.std(scores)) if scores else 0.0
    agreement = max(0.0, 1 - dispersion / 35)
    coverage = len(available) / max(1, len(components))
    actionable = direction in ("bullish", "neutral_to_bullish", "bearish", "neutral_to_bearish")
    call = ("BUY / long bias" if direction in ("bullish", "neutral_to_bullish")
            else "SELL / short bias" if direction in ("bearish", "neutral_to_bearish")
            else "AVOID — risk blocked" if direction == "avoid"
            else "NO TRADE — neutral, no edge")
    return {
        "confidence_score": conf,
        "applies_to": call,
        "is_actionable": actionable,
        "meaning": (
            "Confidence = conviction in this BUY/SELL call (data quality x directional "
            "conviction). A neutral 'no edge' call is capped low on purpose — high "
            "confidence is only possible for a clear buy or sell. Not a profit guarantee."
        ),
        "direction": direction,
        "directional_conviction_pct": round(conviction * 100, 1),
        "data_quality_pct": round(data_quality, 1),
        "coverage_pct": round(coverage * 100, 1),
        "agreement_pct": round(agreement * 100, 1),
        "available_engines": [c.name for c in available],
        "missing_engines": [c.name for c in missing],
        "component_scores": {c.name: round(c.score, 1) for c in components},
        "component_weights": {c.name: round(c.weight, 3) for c in components},
        "evidence_count": ev_count,
        "freshness": freshness,
        "top_source_links": source_links[:8],
        "formula": "confidence = data_quality(coverage+agreement) x (0.15 + 0.85 x directional_conviction)",
    }


def _algo_confluence(direction: Direction, algo: dict) -> tuple[int, str, list[str]]:
    """Lightweight algorithmic confluence: count how many independent quant
    signals (trend/technical, momentum, ensemble forecast, options positioning,
    blended opportunity) agree with the chosen direction. 0..5 votes."""
    bullish = direction in (Direction.bullish, Direction.neutral_to_bullish)
    bearish = direction in (Direction.bearish, Direction.neutral_to_bearish)
    votes = 0
    notes: list[str] = []

    def _check(name: str, score: Optional[float], hi: float = 55, lo: float = 45):
        nonlocal votes
        if score is None:
            return
        if bullish and score >= hi:
            votes += 1; notes.append(f"{name} bullish ({score:.0f})")
        elif bearish and score <= lo:
            votes += 1; notes.append(f"{name} bearish ({score:.0f})")

    _check("trend/technical", algo.get("technical"))
    _check("momentum", algo.get("momentum"))
    _check("blended opportunity", algo.get("opportunity"), hi=58, lo=42)
    pu = algo.get("forecast_prob_up")
    if pu is not None:
        if bullish and pu >= 0.55:
            votes += 1; notes.append(f"forecast P(up) {pu:.0%}")
        elif bearish and pu <= 0.45:
            votes += 1; notes.append(f"forecast P(down) {1 - pu:.0%}")
    pcr = algo.get("put_call_ratio")
    if pcr is not None:
        if bullish and pcr < 0.9:
            votes += 1; notes.append(f"call-heavy flow (P/C {pcr})")
        elif bearish and pcr > 1.1:
            votes += 1; notes.append(f"put-heavy flow (P/C {pcr})")
    label = "strong" if votes >= 4 else "moderate" if votes >= 2 else "weak"
    return votes, label, notes


def _spread_legs(analytics: OptionsAnalytics, bias: str) -> Optional[dict]:
    """Suggest defined-risk vertical spread strikes from the ATM strike and the
    1-sigma expected move (research only — not an order)."""
    strike = analytics.atm_strike
    em = analytics.expected_move
    if not strike or not em or em.high_pct is None:
        return None
    width = abs(em.high_pct) / 100.0 * strike
    if bias == "bullish":
        return {"type": "call_debit_spread", "long_strike": round(strike, 2),
                "short_strike": round(strike + width, 2), "expiry": analytics.expiration}
    if bias == "bearish":
        return {"type": "put_debit_spread", "long_strike": round(strike, 2),
                "short_strike": round(strike - width, 2), "expiry": analytics.expiration}
    return None


def _options_trade_idea(direction: Direction, analytics: OptionsAnalytics, forecast: Forecast | None,
                        strategy: str, algo: Optional[dict] = None) -> dict:
    bias = "neutral"
    if direction in (Direction.bullish, Direction.neutral_to_bullish):
        bias = "bullish"
    elif direction in (Direction.bearish, Direction.neutral_to_bearish):
        bias = "bearish"
    if direction == Direction.avoid:
        bias = "avoid"

    high_iv = analytics.avg_iv is not None and analytics.avg_iv >= 70
    low_liquidity = analytics.illiquid or analytics.total_oi < 500
    if bias == "bullish":
        idea = "call_debit_spread" if high_iv else "long_call_or_call_debit_spread"
        contract = analytics.atm_call_symbol
    elif bias == "bearish":
        idea = "put_debit_spread" if high_iv else "long_put_or_put_debit_spread"
        contract = analytics.atm_put_symbol
    else:
        idea = "no_short_term_options_edge"
        contract = None
    if low_liquidity:
        idea = "avoid_or_paper_only_due_to_low_options_liquidity"

    algo_votes, algo_label, algo_notes = _algo_confluence(direction, algo or {})
    spread = _spread_legs(analytics, bias)
    dte = analytics.days_to_expiry

    rationale: list[str] = []
    if dte is not None:
        rationale.append(f"{dte} days to expiry ({analytics.expiration})")
    rationale.append(f"algo confluence {algo_votes}/5 ({algo_label})")
    rationale.extend(algo_notes)
    if analytics.put_call_ratio is not None:
        rationale.append(f"put/call {analytics.put_call_ratio}")
    if analytics.avg_iv is not None:
        rationale.append(f"avg IV {analytics.avg_iv}%")
    if forecast and forecast.prob_up is not None:
        rationale.append(f"forecast P(up) {forecast.prob_up:.0%}")
    if analytics.expected_move:
        rationale.append(
            f"expected move {analytics.expected_move.low_pct:+.1f}%/{analytics.expected_move.high_pct:+.1f}% "
            f"({analytics.expected_move.basis})"
        )
    if spread:
        rationale.append(
            f"defined-risk {spread['type']}: long {spread['long_strike']} / short {spread['short_strike']}"
        )
    if high_iv:
        rationale.append("high IV favors defined-risk spreads over naked long options")
    if low_liquidity:
        rationale.append("thin options liquidity: paper/research only unless spreads are acceptable")
    if dte is not None and dte <= 2:
        rationale.append("very short DTE: gamma/theta risk is extreme — size tiny or skip")

    return {
        "mode": "research_only_no_broker_order",
        "horizon": "short_term_options",
        "bias": bias,
        "strategy": idea,
        "nearest_expiration": analytics.expiration,
        "days_to_expiry": dte,
        "atm_strike": analytics.atm_strike,
        "suggested_spread": spread,
        "algo_confluence": algo_votes,
        "algo_confluence_label": algo_label,
        "reference_contract": contract,
        "atm_call": analytics.atm_call_symbol,
        "atm_put": analytics.atm_put_symbol,
        "atm_call_last": analytics.atm_call_last,
        "atm_put_last": analytics.atm_put_last,
        "put_call_ratio": analytics.put_call_ratio,
        "avg_iv": analytics.avg_iv,
        "total_open_interest": analytics.total_oi,
        "total_volume": analytics.total_volume,
        "warning": "Research only. Verify bid/ask, spread, Greeks, IV rank, earnings date, and liquidity before any real trade.",
        "rationale": rationale,
        "strategy_profile": strategy,
    }


def predict(
    asset: AssetEntity,
    market: MarketData,
    sec: SecData,
    macro: MacroSnapshot,
    options_chain: OptionsChain,
    benchmark: Optional[pd.DataFrame],
    store: EvidenceStore,
    settings: Settings,
    weights: dict[str, float],
    horizon: str = "5D",
    strategy: str = "swing",
    gov: Optional[GovSnapshot] = None,
    global_index_bars: Optional[dict] = None,
) -> PredictionResult:
    df = market.bars
    horizon_days = {"intraday": 1, "1D": 1, "5D": 5, "20D": 20}.get(horizon, 5)
    is_option_setup = strategy in ("options_buying", "options_selling") or "options" in asset.strategy_tags

    # --- component engines -------------------------------------------------
    tech = technical_signal(df)
    pv = price_volume_signal(df)
    pbias, pnotes = pattern_bias(df)
    tech.score = float(np.clip(tech.score + pbias * 6, 0, 100))
    tech.rationale.extend(pnotes)

    fund = fundamental_signal(sec)
    opt_comp, opt_analytics = analyze_options(options_chain, df, horizon_days)
    mac = macro_signal(macro, gov)
    news = fetch_news(asset.ticker, asset.company_name)
    social = (
        fetch_social(asset.ticker, asset.company_name)
        if (settings.enable_social_sentiment or settings.x_bearer_token) else None
    )
    sent = sentiment_signal(asset.ticker, news, store, social, settings)
    xmkt = cross_market_signal(df, benchmark)
    fcomp, forecast = (
        forecast_signal(
            df,
            horizon_days,
            n_paths=settings.monte_carlo_paths,
            use_gpu=settings.enable_gpu_monte_carlo,
        ) if settings.enable_forecast
        else (None, None)
    )
    short_horizon_forecasts: dict[str, Forecast] = {}
    if settings.enable_forecast:
        for short_days in (2, 3):
            _short_comp, short_fc = forecast_signal(
                df,
                short_days,
                n_paths=settings.monte_carlo_paths,
                use_gpu=settings.enable_gpu_monte_carlo,
            )
            if short_fc and short_fc.available:
                short_horizon_forecasts[f"{short_days}D"] = short_fc
    g_corr = global_correlations(df, global_index_bars) if global_index_bars else {}

    # SKILL-056 — link market-wide government events to this specific ticker.
    impacts = map_impacts(asset, gov)
    policy_impacts: list[str] = []
    for imp in impacts:
        ev_obj = imp.event
        store.add(
            entity=asset.ticker, source_name=ev_obj.source, source_type="official",
            claim=ev_obj.title, url=ev_obj.url, published_at=ev_obj.published_at,
            polarity=imp.polarity, data_type="news",
        )
        tag = "direct" if imp.match_kind == "direct" else imp.match_kind
        policy_impacts.append(f"[{ev_obj.kind}/{tag}] {ev_obj.source}: {ev_obj.title[:110]}")

    components = [tech, pv, fund, opt_comp, mac, sent, xmkt]
    if fcomp is not None:
        components.append(fcomp)
    components = scoring.apply_weights(components, weights)

    opp = scoring.opportunity_score(components)
    # Data-quality (coverage + agreement) drives the risk manager's evidence
    # check. It is NOT the user-facing confidence — that is computed below from
    # the final direction so a "neutral / no edge" call can never score high.
    data_quality = scoring.evidence_quality(components)

    # --- risk --------------------------------------------------------------
    risk_decision, risk_penalty = assess_risk(
        settings, market, components, opt_analytics, data_quality, is_option_setup
    )
    # Direct, company-named regulatory actions are an event risk (SKILL-132).
    direct_reg = [i for i in impacts if i.match_kind == "direct" and i.event.kind in ("fda", "antitrust")]
    for i in direct_reg:
        risk_decision.warnings.append(
            f"Direct {i.event.kind} action names this company: {i.event.title[:90]}"
        )

    # Apply configured risk-penalty weight to the opportunity score.
    rp_weight = weights.get("risk_penalty_adjustment", 0.05)
    opp_adj = round(opp * (1 - rp_weight * risk_penalty), 1)
    direction = scoring.to_direction(opp_adj)
    if risk_decision.block_trade:
        direction = Direction.avoid

    # Confidence = conviction in an ACTIONABLE buy/sell call. Neutral / avoid have
    # no tradeable edge, so they are capped low no matter how clean the data is.
    conviction = scoring.conviction(opp_adj)
    conf = scoring.confidence_score(components, opp_adj)
    if direction == Direction.avoid:
        conf = round(min(conf, 30.0), 1)
    elif direction == Direction.neutral:
        conf = round(min(conf, 40.0), 1)

    # --- event-risk awareness (§2 "measured, not guessed") -----------------
    # A high-impact scheduled event (FOMC / jobs report / earnings) inside the
    # prediction horizon makes the outcome more binary, so we HONESTLY reduce
    # confidence and flag it rather than pretend the read is as clean as usual.
    earnings = (
        fetch_earnings(asset.ticker)
        if getattr(settings, "enable_earnings_calendar", True)
        else EarningsInfo(ticker=asset.ticker)
    )
    horizon_events = events_within_horizon(
        horizon_days, days_to_earnings=earnings.days_to_earnings, ticker=asset.ticker
    )
    high_impact_events = [e for e in horizon_events if e.impact == "high"]
    event_notes: list[str] = []
    if high_impact_events and direction != Direction.avoid:
        conf = round(conf * 0.85, 1)
        event_notes = [f"{e.title} in {e.days_away}d ({e.date})" for e in high_impact_events[:3]]
        risk_decision.warnings.append(
            "Event risk: " + "; ".join(event_notes)
            + " — inside the horizon; confidence reduced (expect a more binary move)."
        )

    # --- evidence references for the memo ----------------------------------
    ev = store.for_entity(asset.ticker)
    bull = [e.evidence_id for e in ev if e.polarity > 0.1][:5]
    bear = [e.evidence_id for e in ev if e.polarity < -0.1][:5]

    catalysts: list[str] = []
    for f in sec.recent_filings[:3]:
        catalysts.append(f"SEC {f.form} filed {f.filed}")
    for item in news.items[:3]:
        catalysts.append(item.title)
    avg_news_polarity = 0.0
    ticker_evidence = store.for_entity(asset.ticker)
    if ticker_evidence:
        avg_news_polarity = sum(e.polarity for e in ticker_evidence) / len(ticker_evidence)

    freshness = {
        "market_data": market.source if market.source != "unavailable" else "missing",
        "sec": "available" if sec.available else "missing",
        "macro": "available" if macro.available else "missing",
        "government": "available" if (gov and gov.available) else "missing",
        "options": "available" if options_chain.available else "missing",
        "news_items": len(news.items),
        "news_providers": news.providers,
        "social": social.source if (social and social.available) else "missing",
    }
    missing = [k for k, comp in {
        "fundamentals": fund, "options": opt_comp, "macro": mac,
        "sentiment": sent, "cross_market": xmkt,
    }.items() if not comp.available]
    if market.source == "unavailable":
        missing.append("live_market_data")

    severity = _severity(opp_adj, conf, risk_decision, settings.confidence_threshold)

    # Build a concise trend-impact summary from only the parts that carry signal
    # (so an always-zero field like "policy links 0" never clutters the row).
    trend_parts: list[str] = []
    if market.day_change_pct is not None:
        trend_parts.append(f"price {market.day_change_pct:+.2f}% today")
    trend_parts.append(f"{len(news.items)} news ({', '.join(news.providers) or 'none'})")
    if news.items:
        mood = "bullish" if avg_news_polarity > 0.1 else "bearish" if avg_news_polarity < -0.1 else "mixed"
        trend_parts.append(f"news tone {avg_news_polarity:+.2f} ({mood})")
    if social and social.available:
        trend_parts.append(f"social {social.source} {social.net_sentiment:+.2f}")
    if forecast and forecast.prob_up is not None:
        trend_parts.append(f"P(up) {forecast.prob_up:.0%}")
    if policy_impacts:
        trend_parts.append(f"{len(policy_impacts)} policy link(s)")
    trend_summary = " · ".join(trend_parts)
    event_radar = detect_event_radar(df, news_items=len(news.items), policy_links=len(policy_impacts))
    final_label = direction.value
    verdict_reasons: list[str] = []
    if direction in (Direction.bullish, Direction.neutral_to_bullish):
        final_label = "bullish_research_candidate"
        verdict_reasons.append("weighted opportunity score leans bullish")
    elif direction in (Direction.bearish, Direction.neutral_to_bearish):
        final_label = "bearish_or_short_research_candidate"
        verdict_reasons.append("weighted opportunity score leans bearish")
    elif direction == Direction.avoid:
        final_label = "avoid_for_now"
        verdict_reasons.append("risk manager blocked the setup")
    else:
        verdict_reasons.append("signals are mixed or not strong enough")
    if event_radar.get("verdict") in ("bullish_event_watch", "early_event_watch"):
        verdict_reasons.append(f"event radar: {event_radar.get('verdict')}")
    if event_radar.get("verdict") == "bearish_exhaustion_watch":
        verdict_reasons.append("event radar warns about exhaustion/reversal risk")
    if forecast and forecast.prob_up is not None:
        if forecast.prob_up >= 0.58:
            verdict_reasons.append(f"forecast P(up) {forecast.prob_up:.0%}")
        elif forecast.prob_up <= 0.42:
            verdict_reasons.append(f"forecast P(down) {1 - forecast.prob_up:.0%}")
    # Trump/administration & regulatory clues are treated as first-class tips.
    trump_links = [i for i in impacts if i.event.kind in ("trump_admin", "policy")]
    reg_links = [i for i in impacts if i.event.kind in ("fda", "antitrust", "fiscal", "labor")]
    if trump_links:
        verdict_reasons.append(
            f"Trump/admin & policy news clue: {trump_links[0].event.title[:80]}"
        )
    if reg_links:
        verdict_reasons.append(
            f"regulatory/macro clue ({reg_links[0].event.kind}): {reg_links[0].event.title[:70]}"
        )
    if direction == Direction.neutral and (
        opp_adj <= 48
        or (forecast and forecast.prob_up is not None and forecast.prob_up <= 0.45)
        or event_radar.get("verdict") == "bearish_exhaustion_watch"
    ):
        final_label = "bearish_watch_candidate"
        verdict_reasons.insert(0, "bearish pressure is not strong enough for a full bearish score, but deserves short/put research")
    if event_notes:
        verdict_reasons.append("scheduled event risk inside horizon: " + "; ".join(event_notes))
    source_links = [e.url for e in ev if e.url][:10]
    option_direction = Direction.neutral_to_bearish if final_label == "bearish_watch_candidate" else direction
    algo_inputs = {
        "technical": tech.score,
        "momentum": pv.score,
        "opportunity": opp_adj,
        "forecast_prob_up": forecast.prob_up if forecast else None,
        "put_call_ratio": opt_analytics.put_call_ratio,
    }
    realized_vol_20d = None
    try:
        realized_vol_20d = float(np.log(df["close"] / df["close"].shift()).dropna().tail(20).std() * np.sqrt(252) * 100)
    except Exception:
        realized_vol_20d = None
    # Earnings (§0.4) was fetched above for event-risk; reused here for IV-crush.
    options_idea = _options_trade_idea(option_direction, opt_analytics, forecast, strategy, algo_inputs)
    # Multi-expiry ranking: the 3 highest-confidence expirations with a clear
    # BUY CALL / BUY PUT / NO TRADE, up/down read, and traffic-light color.
    opt_dir_word = (
        "up" if option_direction in (Direction.bullish, Direction.neutral_to_bullish)
        else "down" if option_direction in (Direction.bearish, Direction.neutral_to_bearish)
        else "neutral"
    )
    iv_history = {
        "by_expiration": {},
        "ticker": {"available": False, "reason": "no current IV"},
    }
    option_history = load_option_contract_history(settings, asset.ticker)
    try:
        current_ivs = [
            float((pd.concat([
                ec.calls.get("impliedVolatility", pd.Series(dtype=float)),
                ec.puts.get("impliedVolatility", pd.Series(dtype=float)),
            ]).dropna().mean()) * 100)
            for ec in options_chain.chains
            if ec.calls is not None and ec.puts is not None
        ]
        current_ivs = [v for v in current_ivs if not np.isnan(v)]
        if current_ivs:
            iv_history["ticker"] = iv_rank_metrics(settings, asset.ticker, float(np.mean(current_ivs)))
        for ec in options_chain.chains:
            ivs = pd.concat([
                ec.calls.get("impliedVolatility", pd.Series(dtype=float)),
                ec.puts.get("impliedVolatility", pd.Series(dtype=float)),
            ]).dropna()
            if not ivs.empty:
                iv_history["by_expiration"][ec.expiration] = iv_rank_metrics(
                    settings, asset.ticker, float(ivs.mean()) * 100, expiration=ec.expiration
                )
    except Exception:
        pass
    all_expiry_snapshots = analyze_expiries(
        options_chain,
        {
            "direction": opt_dir_word,
            "conviction": conviction,
            "opportunity": opp_adj,
            "forecast_prob_up": forecast.prob_up if forecast else None,
            "data_quality": data_quality,
            "algo_confluence": options_idea.get("algo_confluence", 0),
            "risk_score": risk_decision.risk_score,
            "realized_vol_20d": realized_vol_20d,
            "iv_history": iv_history,
            "option_history": option_history,
            "days_to_earnings": earnings.days_to_earnings,
            "next_earnings_date": earnings.next_earnings_date,
            "min_days_to_expiry": settings.min_option_days_to_expiry,
        },
        top_n=10,
    )
    options_idea["top_expiries"] = all_expiry_snapshots[:3]
    options_idea["all_expiry_snapshots"] = all_expiry_snapshots
    options_idea["data_source"] = options_chain.source
    options_idea["available_expirations"] = len(options_chain.chains)
    options_idea["available_expiration_list"] = [ec.expiration for ec in options_chain.chains]
    options_idea["iv_history"] = iv_history
    options_idea["earnings"] = earnings.to_dict()
    if earnings.available and earnings.days_to_earnings is not None:
        options_idea.setdefault("rationale", []).append(
            f"next earnings ~{earnings.next_earnings_date} ({earnings.days_to_earnings}d): "
            "expiries spanning it carry IV-crush risk"
        )

    conf_trace = _confidence_trace(
        components, conf, len(ev), source_links, freshness,
        direction.value, data_quality, conviction,
    )
    conf_trace["event_calendar"] = [e.to_dict() for e in horizon_events[:6]]
    conf_trace["event_risk_applied"] = bool(high_impact_events) and direction != Direction.avoid
    if conf_trace["event_risk_applied"]:
        conf_trace["event_risk_note"] = (
            "High-impact scheduled event inside the horizon — confidence multiplied by 0.85 "
            "to reflect the more binary outcome."
        )

    return PredictionResult(
        prediction_id=str(uuid.uuid4()),
        ticker=asset.ticker,
        asset_type=asset.asset_type,
        horizon=horizon,
        strategy=strategy,
        direction=direction,
        opportunity_score=opp_adj,
        confidence_score=conf,
        risk_score=risk_decision.risk_score,
        component_scores={c.name: round(c.score, 1) for c in components},
        component_weights={c.name: round(c.weight, 3) for c in components},
        expected_move=opt_analytics.expected_move,
        forecast=forecast or Forecast(horizon_days=horizon_days, available=False),
        short_horizon_forecasts=short_horizon_forecasts,
        market_snapshot={
            "current_price": round(market.current_price or market.last_close, 4),
            "previous_close": round(market.previous_close or market.last_close, 4),
            "day_change_pct": round(market.day_change_pct, 2) if market.day_change_pct is not None else None,
            "last_volume": round(market.last_volume, 0),
            "retrieved_at": market.retrieved_at.isoformat(),
            "source": market.source,
            "provider_status": market.provider_status,
        },
        options_trade_idea=options_idea,
        key_bullish_evidence=bull,
        key_bearish_evidence=bear,
        catalysts=catalysts,
        policy_impacts=policy_impacts,
        trend_impact={
            "price_day_change_pct": round(market.day_change_pct, 2) if market.day_change_pct is not None else None,
            "news_items": len(news.items),
            "news_providers": news.providers,
            "avg_evidence_polarity": round(avg_news_polarity, 3),
            "policy_event_count": len(policy_impacts),
            "social_source": social.source if (social and social.available) else None,
            "social_net_sentiment": social.net_sentiment if (social and social.available) else None,
            "forecast_prob_up": forecast.prob_up if forecast else None,
            "forecast_expected_return_pct": forecast.expected_return_pct if forecast else None,
            "forecast_2d_expected_return_pct": (
                short_horizon_forecasts["2D"].expected_return_pct
                if "2D" in short_horizon_forecasts else None
            ),
            "forecast_3d_expected_return_pct": (
                short_horizon_forecasts["3D"].expected_return_pct
                if "3D" in short_horizon_forecasts else None
            ),
            "summary": trend_summary,
        },
        event_radar=event_radar,
        final_verdict={
            "label": final_label,
            "research_action": (
                "research_long_setup" if final_label == "bullish_research_candidate"
                else "research_short_or_put_setup" if final_label in ("bearish_or_short_research_candidate", "bearish_watch_candidate")
                else "wait_or_avoid" if final_label == "avoid_for_now"
                else "watch_only"
            ),
            "reasons": verdict_reasons[:6],
        },
        global_correlations=g_corr,
        invalidation_conditions=_invalidation(df, direction),
        risk=risk_decision,
        severity=severity,
        data_freshness=freshness,
        missing_data=missing,
        source_links=source_links,
        confidence_trace=conf_trace,
        model_version=f"v{__version__}",
    )
