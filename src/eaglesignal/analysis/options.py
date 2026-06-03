"""SKILL-030..038 Options intelligence engine.

Derives put/call ratio, IV proxy, expected move, liquidity, and unusual-volume
signals from a chain. Also computes a historical-volatility expected move from
price history as a fallback when no chain exists. Returns available=False with a
neutral score when there is nothing tradeable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import erf, exp, log, pi, sqrt
from typing import Optional

import numpy as np
import pandas as pd

from ..ingestion.options_chain import ExpiryChain, OptionsChain
from ..schemas import ExpectedMove, SignalComponent


@dataclass
class OptionsAnalytics:
    put_call_ratio: Optional[float] = None
    avg_iv: Optional[float] = None
    expected_move: ExpectedMove = None  # type: ignore[assignment]
    expiration: Optional[str] = None
    days_to_expiry: Optional[int] = None
    atm_strike: Optional[float] = None
    total_oi: int = 0
    total_volume: int = 0
    call_volume: int = 0
    put_volume: int = 0
    atm_call_symbol: Optional[str] = None
    atm_put_symbol: Optional[str] = None
    atm_call_last: Optional[float] = None
    atm_put_last: Optional[float] = None
    illiquid: bool = True
    unusual_volume: bool = False


def _expected_move_from_history(df: pd.DataFrame, horizon_days: int = 5) -> ExpectedMove:
    rets = np.log(df["close"] / df["close"].shift()).dropna()
    daily_vol = float(rets.std())
    move = daily_vol * np.sqrt(horizon_days) * 100  # 1-sigma % move
    return ExpectedMove(low_pct=round(-move, 1), high_pct=round(move, 1), basis=f"hist-vol {horizon_days}D 1σ")


def analyze_options(chain: OptionsChain, df: pd.DataFrame, horizon_days: int = 5) -> tuple[SignalComponent, OptionsAnalytics]:
    notes: list[str] = []
    analytics = OptionsAnalytics(expected_move=_expected_move_from_history(df, horizon_days))

    if not chain or not chain.available or chain.calls is None or chain.puts is None:
        notes.append("No options chain; expected move from historical volatility only.")
        comp = SignalComponent(name="options_intelligence", score=50.0, weight=0.0, available=False, rationale=notes)
        return comp, analytics

    calls, puts = chain.calls, chain.puts
    analytics.expiration = chain.expiration
    if chain.expiration:
        try:
            from datetime import date

            y, m, d = (int(x) for x in chain.expiration.split("-"))
            analytics.days_to_expiry = max(0, (date(y, m, d) - date.today()).days)
        except Exception:
            analytics.days_to_expiry = None
    call_vol = float(calls.get("volume", pd.Series(dtype=float)).fillna(0).sum())
    put_vol = float(puts.get("volume", pd.Series(dtype=float)).fillna(0).sum())
    analytics.call_volume = int(call_vol)
    analytics.put_volume = int(put_vol)
    analytics.total_volume = int(call_vol + put_vol)
    pcr = put_vol / call_vol if call_vol else None
    analytics.put_call_ratio = round(pcr, 2) if pcr is not None else None

    ivs = pd.concat([calls.get("impliedVolatility", pd.Series(dtype=float)),
                     puts.get("impliedVolatility", pd.Series(dtype=float))]).dropna()
    analytics.avg_iv = round(float(ivs.mean()) * 100, 1) if not ivs.empty else None

    total_oi = int(calls.get("openInterest", pd.Series(dtype=float)).fillna(0).sum()
                   + puts.get("openInterest", pd.Series(dtype=float)).fillna(0).sum())
    analytics.total_oi = total_oi
    analytics.illiquid = total_oi < 500

    # ATM straddle expected move (preferred over hist-vol when present)
    if chain.spot:
        calls2 = calls.assign(dist=(calls.get("strike", 0) - chain.spot).abs())
        puts2 = puts.assign(dist=(puts.get("strike", 0) - chain.spot).abs())
        try:
            atm_call = calls2.nsmallest(1, "dist").iloc[0]
            atm_put = puts2.nsmallest(1, "dist").iloc[0]
            straddle = float(atm_call.get("lastPrice", 0)) + float(atm_put.get("lastPrice", 0))
            analytics.atm_strike = round(float(atm_call.get("strike", 0)), 2) or None
            analytics.atm_call_symbol = str(atm_call.get("contractSymbol", "")) or None
            analytics.atm_put_symbol = str(atm_put.get("contractSymbol", "")) or None
            analytics.atm_call_last = round(float(atm_call.get("lastPrice", 0)), 4)
            analytics.atm_put_last = round(float(atm_put.get("lastPrice", 0)), 4)
            if straddle > 0:
                em = straddle / chain.spot * 100
                analytics.expected_move = ExpectedMove(low_pct=round(-em, 1), high_pct=round(em, 1), basis="ATM straddle")
        except (IndexError, KeyError):
            pass

    score = 50.0
    if pcr is not None:
        if pcr < 0.7:
            score += 8; notes.append(f"Put/call {pcr:.2f} (call-heavy, bullish positioning).")
        elif pcr > 1.3:
            score -= 8; notes.append(f"Put/call {pcr:.2f} (put-heavy, bearish/hedging).")
        else:
            notes.append(f"Put/call {pcr:.2f} (balanced).")
    if analytics.avg_iv is not None:
        notes.append(f"Average IV ~{analytics.avg_iv:.0f}%.")
        if analytics.avg_iv > 80:
            score -= 4; notes.append("Elevated IV: option buyers overpay / IV-crush risk.")
    if analytics.illiquid:
        score -= 6; notes.append(f"Thin options liquidity (total OI {total_oi}).")
    em = analytics.expected_move
    notes.append(f"Expected move ({em.basis}): {em.low_pct:+.1f}% / {em.high_pct:+.1f}%.")

    comp = SignalComponent(name="options_intelligence", score=max(0, min(100, score)), weight=0.0, rationale=notes)
    return comp, analytics


# --------------------------------------------------------------------------- #
# Multi-expiry ranking — pick the 3 highest-confidence expirations and state a
# clear BUY CALL / BUY PUT / NO TRADE with an up/down read and a traffic-light
# color. Directional conviction comes from the shared underlying analysis so the
# options view never contradicts the rest of the dashboard.
# --------------------------------------------------------------------------- #
@dataclass
class ExpiryIdea:
    expiration: str
    days_to_expiry: int
    action: str            # "BUY CALL" | "BUY PUT" | "NO TRADE"
    direction: str         # "up" | "down" | "neutral"
    arrow: str             # ▲ | ▼ | →
    confidence: float      # 0..100
    confidence_color: str  # green | orange | red
    action_color: str      # green | red | orange
    atm_strike: Optional[float] = None
    spread: Optional[dict] = None
    put_call_ratio: Optional[float] = None
    avg_iv: Optional[float] = None
    total_oi: int = 0
    total_volume: int = 0
    call_volume: int = 0
    put_volume: int = 0
    expected_move_pct: Optional[float] = None
    reference_contract: Optional[str] = None
    reference_option_price: Optional[float] = None
    reference_bid: Optional[float] = None
    reference_ask: Optional[float] = None
    reference_type: Optional[str] = None
    contract_multiplier: int = 100
    option_quality_score: Optional[float] = None
    liquidity_score: Optional[float] = None
    bid_ask_spread_pct: Optional[float] = None
    flow_alignment: str = "unknown"
    iv_risk: str = "unknown"
    readiness: str = "research"
    risk_gate: str = "research"
    exact_contract_volume: Optional[int] = None
    exact_contract_oi: Optional[int] = None
    breakeven_price: Optional[float] = None
    breakeven_pct: Optional[float] = None
    premium_pct_spot: Optional[float] = None
    realized_vol_20d: Optional[float] = None
    iv_realized_ratio: Optional[float] = None
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    iv_history_count: Optional[int] = None
    iv_history_scope: Optional[str] = None
    atm_iv_skew_pct: Optional[float] = None
    skew_label: str = "unknown"
    term_structure_slope_pct: Optional[float] = None
    term_structure_label: str = "unknown"
    volume_oi_ratio: Optional[float] = None
    unusual_activity_score: Optional[float] = None
    unusual_activity_label: str = "normal"
    previous_exact_contract_oi: Optional[int] = None
    oi_change: Optional[int] = None
    oi_change_pct: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta_per_day: Optional[float] = None
    vega_per_vol_point: Optional[float] = None
    earnings_in_window: bool = False
    days_to_earnings: Optional[int] = None
    next_earnings_date: Optional[str] = None
    strategy_label: Optional[str] = None     # plain-English best structure for this setup
    alt_structure: Optional[dict] = None      # premium-selling / multi-leg alternative
    confidence_formula: str = ""
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expiration": self.expiration,
            "days_to_expiry": self.days_to_expiry,
            "action": self.action,
            "direction": self.direction,
            "arrow": self.arrow,
            "confidence": self.confidence,
            "confidence_color": self.confidence_color,
            "action_color": self.action_color,
            "atm_strike": self.atm_strike,
            "spread": self.spread,
            "put_call_ratio": self.put_call_ratio,
            "avg_iv": self.avg_iv,
            "total_oi": self.total_oi,
            "total_volume": self.total_volume,
            "call_volume": self.call_volume,
            "put_volume": self.put_volume,
            "expected_move_pct": self.expected_move_pct,
            "reference_contract": self.reference_contract,
            "reference_option_price": self.reference_option_price,
            "reference_bid": self.reference_bid,
            "reference_ask": self.reference_ask,
            "reference_type": self.reference_type,
            "contract_multiplier": self.contract_multiplier,
            "option_quality_score": self.option_quality_score,
            "liquidity_score": self.liquidity_score,
            "bid_ask_spread_pct": self.bid_ask_spread_pct,
            "flow_alignment": self.flow_alignment,
            "iv_risk": self.iv_risk,
            "readiness": self.readiness,
            "risk_gate": self.risk_gate,
            "exact_contract_volume": self.exact_contract_volume,
            "exact_contract_oi": self.exact_contract_oi,
            "breakeven_price": self.breakeven_price,
            "breakeven_pct": self.breakeven_pct,
            "premium_pct_spot": self.premium_pct_spot,
            "realized_vol_20d": self.realized_vol_20d,
            "iv_realized_ratio": self.iv_realized_ratio,
            "iv_rank": self.iv_rank,
            "iv_percentile": self.iv_percentile,
            "iv_history_count": self.iv_history_count,
            "iv_history_scope": self.iv_history_scope,
            "atm_iv_skew_pct": self.atm_iv_skew_pct,
            "skew_label": self.skew_label,
            "term_structure_slope_pct": self.term_structure_slope_pct,
            "term_structure_label": self.term_structure_label,
            "volume_oi_ratio": self.volume_oi_ratio,
            "unusual_activity_score": self.unusual_activity_score,
            "unusual_activity_label": self.unusual_activity_label,
            "previous_exact_contract_oi": self.previous_exact_contract_oi,
            "oi_change": self.oi_change,
            "oi_change_pct": self.oi_change_pct,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta_per_day": self.theta_per_day,
            "vega_per_vol_point": self.vega_per_vol_point,
            "earnings_in_window": self.earnings_in_window,
            "days_to_earnings": self.days_to_earnings,
            "next_earnings_date": self.next_earnings_date,
            "strategy_label": self.strategy_label,
            "alt_structure": self.alt_structure,
            "confidence_formula": self.confidence_formula,
            "reasons": self.reasons,
        }


def _expiry_metrics(ec: ExpiryChain, spot: Optional[float]) -> dict:
    """Lightweight per-expiry metrics (pcr, iv, oi, atm strike/contract)."""
    calls, puts = ec.calls, ec.puts
    call_vol = float(calls.get("volume", pd.Series(dtype=float)).fillna(0).sum())
    put_vol = float(puts.get("volume", pd.Series(dtype=float)).fillna(0).sum())
    pcr = round(put_vol / call_vol, 2) if call_vol else None
    ivs = pd.concat([calls.get("impliedVolatility", pd.Series(dtype=float)),
                     puts.get("impliedVolatility", pd.Series(dtype=float))]).dropna()
    avg_iv = round(float(ivs.mean()) * 100, 1) if not ivs.empty else None
    total_oi = int(calls.get("openInterest", pd.Series(dtype=float)).fillna(0).sum()
                   + puts.get("openInterest", pd.Series(dtype=float)).fillna(0).sum())
    atm_strike = atm_call_sym = atm_put_sym = None
    atm_call_last = atm_put_last = atm_call_bid = atm_put_bid = atm_call_ask = atm_put_ask = None
    atm_call_vol = atm_put_vol = atm_call_oi = atm_put_oi = None
    atm_call_iv = atm_put_iv = None
    em_pct = None
    if spot:
        try:
            c2 = calls.assign(dist=(calls.get("strike", 0) - spot).abs())
            p2 = puts.assign(dist=(puts.get("strike", 0) - spot).abs())
            ac = c2.nsmallest(1, "dist").iloc[0]
            ap = p2.nsmallest(1, "dist").iloc[0]
            atm_strike = round(float(ac.get("strike", 0)), 2) or None
            atm_call_sym = str(ac.get("contractSymbol", "")) or None
            atm_put_sym = str(ap.get("contractSymbol", "")) or None
            atm_call_last = float(ac.get("lastPrice", 0) or 0)
            atm_put_last = float(ap.get("lastPrice", 0) or 0)
            atm_call_bid = float(ac.get("bid", 0) or 0)
            atm_put_bid = float(ap.get("bid", 0) or 0)
            atm_call_ask = float(ac.get("ask", 0) or 0)
            atm_put_ask = float(ap.get("ask", 0) or 0)
            atm_call_vol = int(float(ac.get("volume", 0) or 0))
            atm_put_vol = int(float(ap.get("volume", 0) or 0))
            atm_call_oi = int(float(ac.get("openInterest", 0) or 0))
            atm_put_oi = int(float(ap.get("openInterest", 0) or 0))
            atm_call_iv = float(ac.get("impliedVolatility", 0) or 0)
            atm_put_iv = float(ap.get("impliedVolatility", 0) or 0)
            straddle = atm_call_last + atm_put_last
            if straddle > 0:
                em_pct = round(straddle / spot * 100, 1)
        except (IndexError, KeyError, ValueError):
            pass
    return {
        "put_call_ratio": pcr, "avg_iv": avg_iv, "total_oi": total_oi,
        "total_volume": int(call_vol + put_vol), "call_volume": int(call_vol), "put_volume": int(put_vol),
        "atm_strike": atm_strike,
        "atm_call_symbol": atm_call_sym, "atm_put_symbol": atm_put_sym,
        "atm_call_last": round(atm_call_last, 4) if atm_call_last is not None else None,
        "atm_put_last": round(atm_put_last, 4) if atm_put_last is not None else None,
        "atm_call_bid": round(atm_call_bid, 4) if atm_call_bid is not None else None,
        "atm_put_bid": round(atm_put_bid, 4) if atm_put_bid is not None else None,
        "atm_call_ask": round(atm_call_ask, 4) if atm_call_ask is not None else None,
        "atm_put_ask": round(atm_put_ask, 4) if atm_put_ask is not None else None,
        "atm_call_volume": atm_call_vol,
        "atm_put_volume": atm_put_vol,
        "atm_call_oi": atm_call_oi,
        "atm_put_oi": atm_put_oi,
        "atm_call_iv": round(atm_call_iv * 100, 1) if atm_call_iv is not None else None,
        "atm_put_iv": round(atm_put_iv * 100, 1) if atm_put_iv is not None else None,
        "expected_move_pct": em_pct,
    }


def _avg_iv_pct(ec: ExpiryChain) -> Optional[float]:
    try:
        ivs = pd.concat([
            ec.calls.get("impliedVolatility", pd.Series(dtype=float)),
            ec.puts.get("impliedVolatility", pd.Series(dtype=float)),
        ]).dropna()
        if ivs.empty:
            return None
        return round(float(ivs.mean()) * 100.0, 1)
    except Exception:
        return None


def _term_structure_by_expiry(chains: list[ExpiryChain], min_dte: int) -> dict[str, dict]:
    rows = [
        {"expiration": ec.expiration, "dte": ec.days_to_expiry, "avg_iv": _avg_iv_pct(ec)}
        for ec in chains
        if ec.days_to_expiry >= min_dte
    ]
    rows = [r for r in rows if r["avg_iv"] is not None]
    rows.sort(key=lambda r: r["dte"])
    out: dict[str, dict] = {}
    for i, row in enumerate(rows):
        later = next((r for r in rows[i + 1:] if r["dte"] > row["dte"]), None)
        if not later:
            out[row["expiration"]] = {"slope_pct": None, "label": "single_expiry"}
            continue
        slope = round(float(later["avg_iv"]) - float(row["avg_iv"]), 1)
        if slope >= 5:
            label = "contango_longer_expiry_richer"
        elif slope <= -5:
            label = "backwardation_front_expiry_richer"
        else:
            label = "flat"
        out[row["expiration"]] = {
            "slope_pct": slope,
            "label": label,
            "next_expiration": later["expiration"],
            "next_dte": later["dte"],
        }
    return out


def _skew_metrics(m: dict) -> tuple[Optional[float], str]:
    call_iv = m.get("atm_call_iv")
    put_iv = m.get("atm_put_iv")
    if call_iv is None or put_iv is None:
        return None, "unknown"
    skew = round(float(put_iv) - float(call_iv), 1)
    if skew >= 5:
        return skew, "puts_richer_bearish_hedging"
    if skew <= -5:
        return skew, "calls_richer_bullish_demand"
    return skew, "balanced_atm_iv"


def _unusual_activity_metrics(
    *,
    exact_volume: Optional[int],
    exact_oi: Optional[int],
    total_volume: int,
    total_oi: int,
    previous_exact_oi: Optional[int],
) -> dict:
    vol = int(exact_volume or 0)
    oi = int(exact_oi or 0)
    volume_oi_ratio = round(vol / oi, 2) if oi > 0 else None
    total_ratio = total_volume / total_oi if total_oi > 0 else 0.0
    oi_change = oi_change_pct = None
    if previous_exact_oi is not None:
        oi_change = oi - int(previous_exact_oi)
        oi_change_pct = round((oi_change / previous_exact_oi) * 100.0, 1) if previous_exact_oi > 0 else None

    score = 0.0
    if volume_oi_ratio is not None:
        score += min(55.0, volume_oi_ratio * 35.0)
    score += min(25.0, total_ratio * 40.0)
    if oi_change is not None and oi_change > 0:
        score += min(20.0, (oi_change_pct or 0.0) / 2.0 if oi_change_pct else 5.0)
    score = round(min(100.0, score), 1)

    if score >= 75:
        label = "very_unusual_chain_activity"
    elif score >= 50:
        label = "unusual_chain_activity"
    elif score >= 30:
        label = "elevated_chain_activity"
    else:
        label = "normal"
    return {
        "volume_oi_ratio": volume_oi_ratio,
        "unusual_activity_score": score,
        "unusual_activity_label": label,
        "previous_exact_contract_oi": previous_exact_oi,
        "oi_change": oi_change,
        "oi_change_pct": oi_change_pct,
    }


def _dte_factor(dte: int) -> tuple[float, str]:
    if 7 <= dte <= 35:
        return 1.0, "ideal short-term window"
    if 3 <= dte < 7:
        return 0.85, "very near expiry"
    if 35 < dte <= 50:
        return 0.85, "slightly long for a short-term play"
    if dte < 3:
        return 0.55, "0-2 DTE: extreme gamma/theta risk"
    return 0.7, "longer-dated"


def _iv_factor(avg_iv: Optional[float]) -> tuple[float, str]:
    if avg_iv is None:
        return 0.65, "IV unavailable"
    if avg_iv <= 45:
        return 0.95, "reasonable IV"
    if avg_iv <= 70:
        return 0.85, "moderate IV"
    if avg_iv <= 90:
        return 0.65, "elevated IV"
    return 0.45, "very high IV"


def _spread_pct(bid: Optional[float], ask: Optional[float], last: Optional[float]) -> Optional[float]:
    try:
        b = float(bid or 0)
        a = float(ask or 0)
        px = float(last or 0)
    except Exception:
        return None
    if b <= 0 or a <= 0 or a < b:
        return None
    mark = (a + b) / 2.0
    basis = mark if mark > 0 else px
    if basis <= 0:
        return None
    return round((a - b) / basis * 100.0, 1)


def _spread_factor(spread_pct: Optional[float]) -> tuple[float, str]:
    if spread_pct is None:
        return 0.65, "spread unavailable"
    if spread_pct <= 8:
        return 1.0, f"tight spread {spread_pct:.1f}%"
    if spread_pct <= 15:
        return 0.85, f"acceptable spread {spread_pct:.1f}%"
    if spread_pct <= 25:
        return 0.55, f"wide spread {spread_pct:.1f}%"
    return 0.30, f"very wide spread {spread_pct:.1f}%"


def _flow_alignment(direction: str, pcr: Optional[float]) -> tuple[str, float]:
    if pcr is None:
        return "unknown", 0.55
    if direction == "up":
        if pcr < 0.9:
            return "supports_call", 1.0
        if pcr > 1.3:
            return "against_call", 0.35
        return "mixed", 0.65
    if direction == "down":
        if pcr > 1.1:
            return "supports_put", 1.0
        if pcr < 0.7:
            return "against_put", 0.35
        return "mixed", 0.65
    return "neutral", 0.45


def _iv_history_metric(iv_history: dict | None, expiration: str, avg_iv: Optional[float]) -> dict:
    if avg_iv is None:
        return {"available": False, "reason": "IV unavailable"}
    if not iv_history:
        return {"available": False, "reason": "IV history unavailable"}
    exact = (iv_history.get("by_expiration") or {}).get(expiration)
    if exact:
        return exact
    return iv_history.get("ticker", {"available": False, "reason": "insufficient IV history"})


def _readiness(confidence: float, oi: int, spread_pct: Optional[float], action: str) -> str:
    if action == "NO TRADE":
        return "no trade"
    if oi < 100:
        return "paper only"
    if spread_pct is not None and spread_pct > 25:
        return "paper only"
    if confidence >= 75:
        return "high"
    if confidence >= 55:
        return "medium"
    return "low"


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def _bs_greeks(
    *,
    spot: Optional[float],
    strike: Optional[float],
    premium: Optional[float],
    iv_pct: Optional[float],
    dte: int,
    option_type: str,
    rate: float = 0.045,
) -> dict:
    """Black-Scholes-style Greeks from provider IV.

    This is a transparent risk approximation, not a broker-grade options model.
    It is enough to quantify whether a long option must outrun daily theta and
    vega/IV risk before we let it look tradeable.
    """
    try:
        s = float(spot or 0)
        k = float(strike or 0)
        sigma = float(iv_pct or 0) / 100.0
        t = max(float(dte), 0.5) / 365.0
    except Exception:
        return {}
    if s <= 0 or k <= 0 or sigma <= 0 or t <= 0:
        return {}
    d1 = (log(s / k) + (rate + 0.5 * sigma * sigma) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)
    pdf = _norm_pdf(d1)
    if option_type == "put":
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -(s * pdf * sigma) / (2 * sqrt(t))
            + rate * k * exp(-rate * t) * _norm_cdf(-d2)
        ) / 365.0
        breakeven = k - float(premium or 0)
    else:
        delta = _norm_cdf(d1)
        theta = (
            -(s * pdf * sigma) / (2 * sqrt(t))
            - rate * k * exp(-rate * t) * _norm_cdf(d2)
        ) / 365.0
        breakeven = k + float(premium or 0)
    gamma = pdf / (s * sigma * sqrt(t))
    vega = s * pdf * sqrt(t) / 100.0
    return {
        "delta": round(delta, 3),
        "gamma": round(gamma, 5),
        "theta_per_day": round(theta, 3),
        "vega_per_vol_point": round(vega, 3),
        "breakeven_price": round(breakeven, 2),
        "breakeven_pct": round((breakeven / s - 1.0) * 100.0, 2),
    }


def _options_risk_gate(
    *,
    confidence: float,
    action: str,
    dte: int,
    avg_iv: Optional[float],
    exact_volume: Optional[int],
    exact_oi: Optional[int],
    spread_pct: Optional[float],
    premium_pct_spot: Optional[float],
    iv_realized_ratio: Optional[float],
    iv_rank: Optional[float],
    greeks: dict,
    reasons: list[str],
    earnings_in_window: bool = False,
    days_to_earnings: Optional[int] = None,
) -> tuple[float, str, str]:
    if action == "NO TRADE":
        return min(confidence, 25.0), "no trade", "no trade"

    gate = "high" if confidence >= 80 else "medium" if confidence >= 65 else "watch"
    cap: Optional[float] = None
    gate_rank = {"high": 0, "medium": 1, "watch": 2, "spread only": 3, "paper only": 4, "no trade": 5}

    def _cap(value: float, label: str, reason: str) -> None:
        nonlocal cap, gate
        cap = value if cap is None else min(cap, value)
        if gate_rank.get(label, 0) >= gate_rank.get(gate, 0):
            gate = label
        reasons.append(reason)

    if dte < 3:
        _cap(35.0, "paper only", "Options Risk Gate: 0-2 DTE has extreme gamma/theta risk.")
    elif dte < 7:
        _cap(60.0, "paper only", "Options Risk Gate: sub-7-DTE naked options are paper-only unless a separate intraday trigger confirms.")

    if exact_oi is not None and exact_oi < 100:
        _cap(45.0, "paper only", f"Options Risk Gate: exact contract OI {exact_oi} is too thin.")
    if exact_volume is not None and exact_volume < 50:
        _cap(50.0, "paper only", f"Options Risk Gate: exact contract volume {exact_volume} is too low.")

    if spread_pct is not None:
        if spread_pct > 25:
            _cap(45.0, "paper only", f"Options Risk Gate: very wide exact-contract spread {spread_pct:.1f}%.")
        elif spread_pct > 15:
            _cap(65.0, "spread only", f"Options Risk Gate: wide spread {spread_pct:.1f}% favors defined-risk spreads.")

    if avg_iv is not None:
        if avg_iv > 150 and dte < 21:
            _cap(65.0, "spread only", f"Options Risk Gate: extreme IV {avg_iv:.0f}% with short DTE; avoid naked long premium.")
        elif avg_iv > 100:
            _cap(72.0, "spread only", f"Options Risk Gate: very high IV {avg_iv:.0f}% favors debit spreads over naked options.")

    if premium_pct_spot is not None and premium_pct_spot > 8:
        _cap(70.0, "spread only", f"Options Risk Gate: premium is {premium_pct_spot:.1f}% of spot, too expensive for naked long calls.")
    if iv_realized_ratio is not None:
        if iv_realized_ratio > 3.0:
            _cap(58.0, "paper only", f"Options Risk Gate: IV is {iv_realized_ratio:.1f}x recent realized volatility.")
        elif iv_realized_ratio > 2.0:
            _cap(68.0, "spread only", f"Options Risk Gate: IV is {iv_realized_ratio:.1f}x recent realized volatility.")

    if iv_rank is not None:
        if iv_rank >= 85:
            _cap(62.0, "spread only", f"Options Risk Gate: IV Rank {iv_rank:.0f}% is very high; long premium has crush risk.")
        elif iv_rank >= 70:
            _cap(72.0, "spread only", f"Options Risk Gate: IV Rank {iv_rank:.0f}% is elevated; prefer defined-risk spreads.")

    # Earnings IV-crush (§1.5): a long-premium expiry that brackets the next
    # earnings date will likely lose value to the post-report IV collapse even if
    # direction is right. Cap to defined-risk spreads; very-near reports are harsher.
    if earnings_in_window:
        if days_to_earnings is not None and days_to_earnings <= 5:
            _cap(58.0, "spread only", f"Options Risk Gate: earnings in ~{days_to_earnings}d inside this expiry — high IV-crush risk on long premium.")
        else:
            _cap(66.0, "spread only", "Options Risk Gate: earnings falls before this expiry — IV-crush risk; prefer defined-risk/credit structures.")

    theta = greeks.get("theta_per_day")
    premium = greeks.get("premium")
    if theta is not None and premium:
        theta_pct = abs(float(theta)) / float(premium) * 100.0
        if theta_pct > 4:
            _cap(60.0, "paper only", f"Options Risk Gate: theta bleed ~{theta_pct:.1f}% of premium per day.")
        elif theta_pct > 2:
            _cap(70.0, "spread only", f"Options Risk Gate: theta bleed ~{theta_pct:.1f}% of premium per day.")

    if cap is not None:
        confidence = round(min(confidence, cap), 1)
    if gate == "high" and confidence < 80:
        gate = "medium" if confidence >= 65 else "watch"
    return confidence, gate, gate


def _build_structures(
    *,
    direction: str,
    atm_strike: Optional[float],
    expected_move_pct: Optional[float],
    long_premium: Optional[float],
    contract_multiplier: int,
    avg_iv: Optional[float],
    iv_rank: Optional[float],
    iv_realized_ratio: Optional[float],
    expiration: str,
) -> tuple[Optional[str], Optional[dict], Optional[dict]]:
    """Return (strategy_label, primary_spread, alt_structure).

    Research-only, approximate. Adds defined-risk verticals with max
    gain/loss/breakeven (§1.7) and, when volatility is rich, a credit/premium
    SELLING alternative (§1.6) — because for high-IV names you are usually paid
    more to sell premium than to buy it. Net debit/credit is a transparent
    heuristic from the 1σ expected-move width, not a live multi-leg quote.
    """
    if not atm_strike or not expected_move_pct:
        return None, None, None
    width = abs(float(expected_move_pct)) / 100.0 * float(atm_strike)
    if width <= 0:
        return None, None, None
    mult = contract_multiplier or 100
    # IV is "rich" when relative IV is high or IV >> realized vol.
    rich_iv = (
        (iv_rank is not None and iv_rank >= 60)
        or (avg_iv is not None and avg_iv >= 70)
        or (iv_realized_ratio is not None and iv_realized_ratio >= 1.6)
    )

    primary: Optional[dict] = None
    alt: Optional[dict] = None
    label: Optional[str] = None

    if direction == "up":
        long_k = round(float(atm_strike), 2)
        short_k = round(float(atm_strike) + width, 2)
        # Debit ~ long premium recovered partly by the short leg (~45%).
        debit = round(min(float(long_premium or width * 0.5), width * 0.9) * 0.55, 2) if long_premium else round(width * 0.45, 2)
        primary = {
            "type": "call_debit_spread", "direction": "bullish", "expiry": expiration,
            "long_strike": long_k, "short_strike": short_k,
            "est_net_debit": debit,
            "est_max_loss": round(debit * mult, 2),
            "est_max_gain": round(max(0.0, (short_k - long_k) - debit) * mult, 2),
            "breakeven": round(long_k + debit, 2),
            "note": "buy ATM call, sell OTM call — defined risk; est. values from 1σ width",
        }
        if rich_iv:
            sell_k = round(float(atm_strike) - width, 2)         # short put (below spot)
            buy_k = round(float(atm_strike) - 2 * width, 2)      # long protective put
            credit = round(width * 0.35, 2)
            alt = {
                "type": "bull_put_credit_spread", "direction": "bullish", "expiry": expiration,
                "short_strike": sell_k, "long_strike": buy_k,
                "est_net_credit": credit,
                "est_max_gain": round(credit * mult, 2),
                "est_max_loss": round(max(0.0, (sell_k - buy_k) - credit) * mult, 2),
                "breakeven": round(sell_k - credit, 2),
                "note": "high IV: SELL a put spread below price to collect premium instead of paying it",
            }
            label = "bullish + rich IV → favor bull-put credit spread (sell premium) over a long call"
        else:
            label = "bullish + reasonable IV → long call or call debit spread"
    elif direction == "down":
        long_k = round(float(atm_strike), 2)
        short_k = round(float(atm_strike) - width, 2)
        debit = round(min(float(long_premium or width * 0.5), width * 0.9) * 0.55, 2) if long_premium else round(width * 0.45, 2)
        primary = {
            "type": "put_debit_spread", "direction": "bearish", "expiry": expiration,
            "long_strike": long_k, "short_strike": short_k,
            "est_net_debit": debit,
            "est_max_loss": round(debit * mult, 2),
            "est_max_gain": round(max(0.0, (long_k - short_k) - debit) * mult, 2),
            "breakeven": round(long_k - debit, 2),
            "note": "buy ATM put, sell OTM put — defined risk; est. values from 1σ width",
        }
        if rich_iv:
            sell_k = round(float(atm_strike) + width, 2)         # short call (above spot)
            buy_k = round(float(atm_strike) + 2 * width, 2)      # long protective call
            credit = round(width * 0.35, 2)
            alt = {
                "type": "bear_call_credit_spread", "direction": "bearish", "expiry": expiration,
                "short_strike": sell_k, "long_strike": buy_k,
                "est_net_credit": credit,
                "est_max_gain": round(credit * mult, 2),
                "est_max_loss": round(max(0.0, (buy_k - sell_k) - credit) * mult, 2),
                "breakeven": round(sell_k + credit, 2),
                "note": "high IV: SELL a call spread above price to collect premium instead of paying it",
            }
            label = "bearish + rich IV → favor bear-call credit spread (sell premium) over a long put"
        else:
            label = "bearish + reasonable IV → long put or put debit spread"
    else:  # neutral
        if rich_iv:
            credit = round(width * 0.6, 2)
            alt = {
                "type": "iron_condor", "direction": "neutral", "expiry": expiration,
                "short_put": round(float(atm_strike) - width, 2),
                "long_put": round(float(atm_strike) - 2 * width, 2),
                "short_call": round(float(atm_strike) + width, 2),
                "long_call": round(float(atm_strike) + 2 * width, 2),
                "est_net_credit": credit,
                "est_max_gain": round(credit * mult, 2),
                "est_max_loss": round(max(0.0, width - credit) * mult, 2),
                "note": "neutral + high IV: iron condor collects premium if price stays within the 1σ range",
            }
            label = "neutral + rich IV → iron condor (range-bound premium sale)"
        else:
            label = "neutral + low IV → no clear options edge; wait for direction or an IV spike"
    return label, primary, alt


def analyze_expiries(chain: OptionsChain, signal: dict, top_n: int = 3) -> list[dict]:
    """Rank expirations by confidence and return the top ``top_n`` as dicts.

    ``signal`` carries the shared underlying read:
        direction      : 'up' | 'down' | 'neutral'
        conviction     : 0..1 directional conviction
        opportunity    : 0..100
        forecast_prob_up, news_tone : optional context for the rationale.
    """
    if not chain or not chain.available or not chain.chains:
        return []

    direction = signal.get("direction", "neutral")
    conviction = float(signal.get("conviction", 0.0) or 0.0)
    data_quality_factor = max(0.0, min(1.0, float(signal.get("data_quality", 50.0) or 50.0) / 100.0))
    algo_factor = max(0.0, min(1.0, float(signal.get("algo_confluence", 0.0) or 0.0) / 5.0))
    risk_score = float(signal.get("risk_score", 50.0) or 50.0)
    min_dte = int(signal.get("min_days_to_expiry", 5) or 5)
    option_history = signal.get("option_history") or {}
    term_by_expiry = _term_structure_by_expiry(chain.chains, min_dte)
    realized_vol_20d = signal.get("realized_vol_20d")
    iv_history = signal.get("iv_history") or {}
    try:
        realized_vol_20d = float(realized_vol_20d) if realized_vol_20d is not None else None
    except Exception:
        realized_vol_20d = None
    days_to_earnings = signal.get("days_to_earnings")
    next_earnings_date = signal.get("next_earnings_date")
    try:
        days_to_earnings = int(days_to_earnings) if days_to_earnings is not None else None
    except Exception:
        days_to_earnings = None
    spot = chain.spot
    bullish = direction == "up"
    bearish = direction == "down"

    ideas: list[ExpiryIdea] = []
    for ec in chain.chains:
        if ec.days_to_expiry < min_dte:
            continue
        m = _expiry_metrics(ec, spot)
        oi = m["total_oi"]
        avg_iv = m["avg_iv"]
        pcr = m["put_call_ratio"]
        reasons: list[str] = []

        # Base directional confidence from the shared analysis.
        base = conviction * 100.0

        liq = max(0.2, min(1.0, oi / 2000.0))
        if oi < 200:
            reasons.append(f"thin OI {oi}: paper/research only")
        ivf = 1.0
        if avg_iv is not None:
            if avg_iv > 90:
                ivf = 0.55; reasons.append(f"very high IV {avg_iv:.0f}% (buyers overpay / crush risk)")
            elif avg_iv > 70:
                ivf = 0.75; reasons.append(f"elevated IV {avg_iv:.0f}%: prefer spreads")
            else:
                reasons.append(f"IV {avg_iv:.0f}%")
        dtef, dte_note = _dte_factor(ec.days_to_expiry)
        reasons.append(f"{ec.days_to_expiry} DTE ({dte_note})")

        flow_bonus = 0.0
        if pcr is not None:
            if bullish and pcr < 0.9:
                flow_bonus = 6; reasons.append(f"call-heavy flow (P/C {pcr})")
            elif bearish and pcr > 1.1:
                flow_bonus = 6; reasons.append(f"put-heavy flow (P/C {pcr})")
            elif (bullish and pcr > 1.3) or (bearish and pcr < 0.7):
                flow_bonus = -6; reasons.append(f"flow disagrees (P/C {pcr})")
            else:
                reasons.append(f"P/C {pcr}")

        confidence = round(max(0.0, min(100.0, base * liq * ivf * dtef + flow_bonus)), 1)

        if bullish:
            action, ddir, arrow, action_color = "BUY CALL", "up", "▲", "green"
            ref = m["atm_call_symbol"]
            ref_price = m["atm_call_last"]
            ref_bid = m["atm_call_bid"]
            ref_ask = m["atm_call_ask"]
            ref_type = "call"
            ref_exact_vol = m["atm_call_volume"]
            ref_exact_oi = m["atm_call_oi"]
            ref_iv = m["atm_call_iv"] or avg_iv
        elif bearish:
            action, ddir, arrow, action_color = "BUY PUT", "down", "▼", "red"
            ref = m["atm_put_symbol"]
            ref_price = m["atm_put_last"]
            ref_bid = m["atm_put_bid"]
            ref_ask = m["atm_put_ask"]
            ref_type = "put"
            ref_exact_vol = m["atm_put_volume"]
            ref_exact_oi = m["atm_put_oi"]
            ref_iv = m["atm_put_iv"] or avg_iv
        else:
            action, ddir, arrow, action_color = "NO TRADE", "neutral", "→", "orange"
            ref = None
            ref_price = None
            ref_bid = None
            ref_ask = None
            ref_type = None
            ref_exact_vol = None
            ref_exact_oi = None
            ref_iv = None
            confidence = round(min(confidence, 25.0), 1)
            reasons.insert(0, "underlying is neutral — no directional options edge")

        prev_row = option_history.get(str(ref or "").upper()) if ref else None
        previous_exact_oi = None
        if prev_row and prev_row.get("exact_contract_oi") is not None:
            try:
                previous_exact_oi = int(float(prev_row.get("exact_contract_oi")))
            except Exception:
                previous_exact_oi = None
        unusual = _unusual_activity_metrics(
            exact_volume=ref_exact_vol,
            exact_oi=ref_exact_oi,
            total_volume=m["total_volume"],
            total_oi=oi,
            previous_exact_oi=previous_exact_oi,
        )
        atm_iv_skew_pct, skew_label = _skew_metrics(m)
        term = term_by_expiry.get(ec.expiration, {"slope_pct": None, "label": "unknown"})
        if unusual["unusual_activity_score"] is not None and unusual["unusual_activity_score"] >= 30:
            reasons.append(
                f"chain-derived unusual activity {unusual['unusual_activity_score']:.0f}/100 "
                f"({unusual['unusual_activity_label']}); volume/OI {unusual['volume_oi_ratio']}"
            )
        if unusual.get("oi_change") is not None:
            reasons.append(
                f"exact-contract OI change vs prior stored scan: {unusual['oi_change']:+d}"
                + (f" ({unusual['oi_change_pct']:+.1f}%)" if unusual.get("oi_change_pct") is not None else "")
            )
        if atm_iv_skew_pct is not None:
            reasons.append(f"ATM IV skew {atm_iv_skew_pct:+.1f} pts ({skew_label})")
        if term.get("slope_pct") is not None:
            reasons.append(f"term structure slope {term['slope_pct']:+.1f} IV pts ({term['label']})")

        spread_pct = _spread_pct(ref_bid, ref_ask, ref_price)
        spread_factor, spread_note = _spread_factor(spread_pct)
        iv_quality_factor, iv_risk = _iv_factor(avg_iv)
        flow_align, flow_factor = _flow_alignment(ddir, pcr)
        premium_pct_spot = round(float(ref_price) / float(spot) * 100.0, 2) if ref_price and spot else None
        iv_realized_ratio = (
            round(float(ref_iv) / realized_vol_20d, 2)
            if ref_iv is not None and realized_vol_20d and realized_vol_20d > 0
            else None
        )
        iv_hist = _iv_history_metric(iv_history, ec.expiration, avg_iv)
        iv_rank = iv_hist.get("iv_rank") if iv_hist.get("available") else None
        iv_percentile = iv_hist.get("iv_percentile") if iv_hist.get("available") else None
        iv_history_count = iv_hist.get("sample_count")
        iv_history_scope = iv_hist.get("scope")
        if iv_rank is not None and iv_percentile is not None:
            reasons.append(
                f"IV Rank {iv_rank:.0f}% / IV Percentile {iv_percentile:.0f}% "
                f"from {iv_history_count} stored snapshots"
            )
        elif iv_hist.get("sample_count") is not None:
            reasons.append(
                f"IV Rank unavailable: {iv_hist.get('sample_count')} stored IV snapshots "
                f"(needs {iv_hist.get('min_samples', 20)})"
            )
        greeks = _bs_greeks(
            spot=spot,
            strike=m["atm_strike"],
            premium=ref_price,
            iv_pct=ref_iv or avg_iv,
            dte=ec.days_to_expiry,
            option_type=ref_type or "call",
        )
        if ref_price:
            greeks["premium"] = float(ref_price)
        oi_factor = max(0.0, min(1.0, oi / 2500.0))
        volume_factor = max(0.0, min(1.0, m["total_volume"] / 1000.0))
        liquidity_factor = max(0.05, min(1.0, 0.65 * oi_factor + 0.35 * volume_factor))
        option_quality = round(
            100.0 * (
                0.26 * liquidity_factor
                + 0.20 * dtef
                + 0.18 * iv_quality_factor
                + 0.20 * flow_factor
                + 0.16 * spread_factor
            ),
            1,
        )
        if action != "NO TRADE" and unusual["unusual_activity_score"] is not None:
            option_quality = round(min(100.0, option_quality + min(6.0, unusual["unusual_activity_score"] * 0.06)), 1)

        if action != "NO TRADE":
            # Contract-level confidence is less punitive than the legacy
            # multiplicative score: it rewards deep, agreeing evidence while
            # still capping weak liquidity, wide spreads, or high-risk setups.
            confidence = round(
                max(
                    confidence,
                    100.0 * (
                        0.46 * conviction
                        + 0.16 * data_quality_factor
                        + 0.14 * algo_factor
                        + 0.24 * (option_quality / 100.0)
                    ),
                ),
                1,
            )
            if risk_score >= 80:
                confidence = min(confidence, 55.0)
                reasons.append("risk score is extreme: confidence capped")
            elif risk_score >= 65:
                confidence = min(confidence, 70.0)
                reasons.append("risk score is high: confidence capped")
            if oi < 100:
                confidence = min(confidence, 55.0)
            if not ref or ref_price is None or float(ref_price or 0) <= 0:
                confidence = min(confidence, 50.0)
                reasons.append("reference contract price missing: verify manually")
            if spread_pct is not None and spread_pct > 25:
                confidence = min(confidence, 60.0)
        else:
            option_quality = min(option_quality, 45.0)

        earnings_in_window = (
            days_to_earnings is not None and 0 <= days_to_earnings <= ec.days_to_expiry
        )
        if earnings_in_window:
            reasons.append(
                f"earnings ~{next_earnings_date} ({days_to_earnings}d) falls before this expiry — IV-crush risk"
            )

        confidence, gate, readiness = _options_risk_gate(
            confidence=confidence,
            action=action,
            dte=ec.days_to_expiry,
            avg_iv=avg_iv,
            exact_volume=ref_exact_vol,
            exact_oi=ref_exact_oi,
            spread_pct=spread_pct,
            premium_pct_spot=premium_pct_spot,
            iv_realized_ratio=iv_realized_ratio,
            iv_rank=iv_rank,
            greeks=greeks,
            reasons=reasons,
            earnings_in_window=earnings_in_window,
            days_to_earnings=days_to_earnings,
        )

        conf_color = "green" if gate == "high" and confidence >= 80 else "orange" if confidence >= 60 else "red"
        if gate in ("high", "medium", "watch"):
            readiness = _readiness(confidence, int(ref_exact_oi or oi), spread_pct, action)
        reasons.insert(
            0,
            "Options Risk Gate blends direction, data quality, algo confluence, exact-contract liquidity, DTE, IV/realized vol, Greeks/theta, flow, and bid/ask spread",
        )
        if spread_note not in reasons:
            reasons.append(spread_note)

        strategy_label, spread, alt_structure = _build_structures(
            direction=ddir,
            atm_strike=m["atm_strike"],
            expected_move_pct=m["expected_move_pct"],
            long_premium=ref_price,
            contract_multiplier=100,
            avg_iv=avg_iv,
            iv_rank=iv_rank,
            iv_realized_ratio=iv_realized_ratio,
            expiration=ec.expiration,
        )
        # Earnings IV-crush or rich-IV gate steers buyers toward the selling/spread
        # alternative — surface it as the headline structure when one exists.
        if alt_structure and (earnings_in_window or gate in ("spread only",)):
            strategy_label = (strategy_label or "") + " — gate prefers the defined-risk/credit structure"
        if strategy_label:
            reasons.append(f"structure: {strategy_label}")

        ideas.append(ExpiryIdea(
            expiration=ec.expiration, days_to_expiry=ec.days_to_expiry, action=action,
            direction=ddir, arrow=arrow, confidence=confidence, confidence_color=conf_color,
            action_color=action_color, atm_strike=m["atm_strike"], spread=spread,
            put_call_ratio=pcr, avg_iv=avg_iv, total_oi=oi, total_volume=m["total_volume"],
            call_volume=m["call_volume"], put_volume=m["put_volume"],
            expected_move_pct=m["expected_move_pct"], reference_contract=ref,
            reference_option_price=ref_price, reference_bid=ref_bid, reference_ask=ref_ask,
            reference_type=ref_type, option_quality_score=option_quality,
            liquidity_score=round(liquidity_factor * 100.0, 1),
            bid_ask_spread_pct=spread_pct, flow_alignment=flow_align,
            iv_risk=iv_risk, readiness=readiness, risk_gate=gate,
            exact_contract_volume=ref_exact_vol, exact_contract_oi=ref_exact_oi,
            breakeven_price=greeks.get("breakeven_price"),
            breakeven_pct=greeks.get("breakeven_pct"),
            premium_pct_spot=premium_pct_spot,
            realized_vol_20d=round(realized_vol_20d, 1) if realized_vol_20d is not None else None,
            iv_realized_ratio=iv_realized_ratio,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            iv_history_count=iv_history_count,
            iv_history_scope=iv_history_scope,
            atm_iv_skew_pct=atm_iv_skew_pct,
            skew_label=skew_label,
            term_structure_slope_pct=term.get("slope_pct"),
            term_structure_label=term.get("label", "unknown"),
            volume_oi_ratio=unusual.get("volume_oi_ratio"),
            unusual_activity_score=unusual.get("unusual_activity_score"),
            unusual_activity_label=unusual.get("unusual_activity_label", "normal"),
            previous_exact_contract_oi=unusual.get("previous_exact_contract_oi"),
            oi_change=unusual.get("oi_change"),
            oi_change_pct=unusual.get("oi_change_pct"),
            delta=greeks.get("delta"), gamma=greeks.get("gamma"),
            theta_per_day=greeks.get("theta_per_day"),
            vega_per_vol_point=greeks.get("vega_per_vol_point"),
            earnings_in_window=earnings_in_window,
            days_to_earnings=days_to_earnings,
            next_earnings_date=next_earnings_date,
            strategy_label=strategy_label,
            alt_structure=alt_structure,
            confidence_formula=(
                "max(legacy_score, 46% directional + 16% data_quality + "
                "14% algo + 24% option_quality), then capped by Options Risk Gate"
            ),
            reasons=reasons,
        ))

    ideas.sort(key=lambda x: x.confidence, reverse=True)
    return [i.to_dict() for i in ideas[:top_n]]
