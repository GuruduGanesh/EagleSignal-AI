"""SKILL-160 Report generator.

Writes reports/YYYY-MM-DD/{report.md, signals.json, summary.csv, dashboard.html,
audit_log.jsonl} (naming per WORKFLOW.md section 13). Every artifact carries the
research-only disclaimer and a missing-data section.
"""
from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .. import __disclaimer__, __product__
from ..config import get_settings
from ..pipeline import RunResult
from ..schemas import PredictionResult

DISCLAIMER = f"> **{__disclaimer__}** Every signal includes uncertainty, evidence, and invalidation levels."
ROOT = Path(__file__).resolve().parents[3]


def _infer_option_type(contract: str, fallback: str | None = None) -> str:
    """Infer call/put from an OCC-style option symbol when source data omits it."""
    c = (contract or "").strip().upper()
    if len(c) >= 15:
        right = c[-9]
        if right == "C":
            return "call"
        if right == "P":
            return "put"
    return (fallback or "").strip().lower()


def _theme_tables(result: RunResult | None = None) -> str:
    path = ROOT / "config" / "policy_theme_watchlists.yml"
    if not path.exists():
        return "<p>No policy theme watchlist file found.</p>"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pred_map = {p.ticker: p for p in (result.predictions if result else [])}

    def live_cols(ticker: str) -> str:
        p = pred_map.get((ticker or "").upper())
        if not p:
            return ("<td>not_scored</td><td>add to config/watchlist.yml to score</td>"
                    "<td>n/a</td><td>n/a</td><td>n/a</td>")
        verdict = p.final_verdict.get("label", p.direction.value)
        action = p.final_verdict.get("research_action", "watch_only")
        trend = p.trend_impact.get("summary", "")
        pup = p.forecast.prob_up if p.forecast and p.forecast.available else None
        pup_txt = f"{pup:.0%}" if pup is not None else "n/a"
        pup_color = "#16a34a" if pup is not None and pup >= 0.55 else "#dc2626" if pup is not None and pup <= 0.45 else "#6b7280"
        d = p.direction.value
        color = "#16a34a" if d in ("bullish", "neutral_to_bullish") else "#dc2626" if d in ("bearish", "neutral_to_bearish") else "#6b7280"
        # Actionable only when there is a directional call with real conviction.
        actionable = (
            "TRADE-WORTHY" if d not in ("neutral", "avoid") and p.confidence_score >= 55
            else "watch only"
        )
        return (
            f"<td style='color:{color};font-weight:700'>{verdict}</td>"
            f"<td>{action}<br><small>{actionable}</small></td>"
            f"<td>{p.opportunity_score:.0f}/<b>{p.confidence_score:.0f}</b>/{p.risk_score:.0f}</td>"
            f"<td style='color:{pup_color};font-weight:700'>{pup_txt}</td>"
            f"<td>{trend}</td>"
        )

    trump_rows = ""
    for item in data.get("trump_and_administration_policy", {}).get("direct_trump_business", []):
        trump_rows += (
            f"<tr><td>{item.get('ticker')}</td><td>{item.get('company')}</td>"
            f"<td>direct_trump_business</td><td>{item.get('rationale', '')}</td>{live_cols(item.get('ticker'))}</tr>"
        )
    for item in data.get("trump_and_administration_policy", {}).get("policy_adjacency", []):
        trump_rows += (
            f"<tr><td>{item.get('ticker')}</td><td>{item.get('company')}</td>"
            f"<td>{item.get('theme')}</td><td>Policy-adjacent public stock/proxy.</td>{live_cols(item.get('ticker'))}</tr>"
        )

    top_rows = ""
    for i, item in enumerate(data.get("top_15_ai_gpu_compute_storage_semis_robotics_space", {}).get("names", []), 1):
        top_rows += (
            f"<tr><td>{i}</td><td>{item.get('ticker')}</td><td>{item.get('company')}</td>"
            f"<td>{', '.join(item.get('themes', []))}</td>{live_cols(item.get('ticker'))}</tr>"
        )
    additional_rows = ""
    for i, item in enumerate(data.get("additional_focused_ai_context", {}).get("public_active_targets", []), 1):
        additional_rows += (
            f"<tr><td>{i}</td><td>{item.get('ticker')}</td><td>{item.get('company')}</td>"
            f"<td>{', '.join(item.get('themes', []))}</td>{live_cols(item.get('ticker'))}</tr>"
        )
    return (
        "<section class='panel' style='background:#f0f6ff'><h3>How To Read Theme Watchlists</h3>"
        "<p>These baskets are context lists, not automatic buys. Only symbols present in "
        "<code>config/watchlist.yml</code> receive live scoring; the rest stay as research context.</p>"
        "<ul style='margin:6px 0 0;font-size:13px'>"
        "<li><b>Opp/Conf/Risk</b> = opportunity / confidence / risk. Opportunity above 50 leans bullish, below 50 leans bearish. Confidence is conviction in a buy/sell call, so neutral names stay low on purpose. Risk is danger: higher means less tradeable.</li>"
        "<li><b>P(up)</b> = the ensemble forecast probability that the underlying price is higher at the selected horizon, simulated from real historical returns and trend agents. It is a probability-style model input, not a guarantee.</li>"
        "<li><b>Trend</b> merges today's price move, news volume/provider coverage, evidence tone, social signal, forecast tilt, and policy/Trump-admin links when present.</li>"
        "</ul></section>"
        "<section class='panel'><h3>Trump/Admin Policy Basket</h3>"
        "<p>Context list only. Add tickers to config/watchlist.yml when you want active scoring.</p>"
        "<table><thead><tr><th>Ticker</th><th>Company</th><th>Theme</th><th>Why</th>"
        "<th>Live verdict</th><th>Research action</th><th>Opp/Conf/Risk</th><th>P(up)</th><th>Trend</th></tr></thead>"
        f"<tbody>{trump_rows}</tbody></table></section>"
        "<section class='panel'><h3>Priority AI / GPU / Storage / Chips / Robots / Space</h3>"
        "<table><thead><tr><th>#</th><th>Ticker</th><th>Company</th><th>Themes</th>"
        "<th>Live verdict</th><th>Research action</th><th>Opp/Conf/Risk</th><th>P(up)</th><th>Trend</th></tr></thead>"
        f"<tbody>{top_rows}</tbody></table></section>"
        "<section class='panel'><h3>Additional Focused AI / Quantum / Software Targets</h3>"
        "<table><thead><tr><th>#</th><th>Ticker</th><th>Company</th><th>Themes</th>"
        "<th>Live verdict</th><th>Research action</th><th>Opp/Conf/Risk</th><th>P(up)</th><th>Trend</th></tr></thead>"
        f"<tbody>{additional_rows}</tbody></table></section>"
    )


def _emoji(p: PredictionResult) -> str:
    return {
        "bullish": "🟢", "neutral_to_bullish": "🟢", "neutral": "⚪",
        "neutral_to_bearish": "🔴", "bearish": "🔴", "avoid": "⛔",
    }.get(p.direction.value, "⚪")


def _move_class(value: object) -> str:
    try:
        v = float(value)  # type: ignore[arg-type]
    except Exception:
        return "neutral"
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "neutral"


def _signal_side(direction: str, action: str) -> str:
    txt = f"{direction} {action}".lower()
    if "bearish" in txt or "short" in txt or "put" in txt or "sell" in txt:
        return "short"
    return "long"


def _attr(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _safe_float(value: object, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}"


def _forecast_for_strategy(p: PredictionResult, side: str) -> tuple[int, float | None, float | None, float | None]:
    """Return target horizon, side-aligned expected return, prob(side), and p05.

    The dashboard is short-term/options-first, so the 3D forecast drives the
    strategy tab when available. We fall back to the canonical 5D forecast.
    """
    f3 = (p.short_horizon_forecasts or {}).get("3D")
    f = f3 if f3 and f3.available else p.forecast
    if not f or not f.available:
        return (3, None, None, None)
    days = int(getattr(f, "horizon_days", 3) or 3)
    ret = _safe_float(getattr(f, "expected_return_pct", None))
    prob_up = _safe_float(getattr(f, "prob_up", None))
    p05 = _safe_float(getattr(f, "p05_return_pct", None))
    if ret is not None and side == "short" and ret > 0:
        ret = -ret
    prob_side = None
    if prob_up is not None:
        prob_side = prob_up * 100 if side != "short" else (1 - prob_up) * 100
    return (days, ret, prob_side, p05)


MAX_STRATEGY_OPTION_PRICE = 50.0


def _strategy_expiry_rank(ex: dict) -> tuple[float, float, float, float]:
    spread = _safe_float(ex.get("bid_ask_spread_pct"), 99.0) or 99.0
    gate = str(ex.get("risk_gate") or ex.get("readiness") or "").lower()
    gate_bonus = {"high": 20, "spread only": 10, "watch": 4, "paper only": -8}.get(gate, 0)
    spread_bonus = 12 if spread <= 8 else 6 if spread <= 12 else -8
    price = _safe_float(ex.get("reference_option_price"), 999.0) or 999.0
    price_bonus = 10 if price <= MAX_STRATEGY_OPTION_PRICE else -40
    return (
        float(ex.get("confidence") or 0) + gate_bonus + spread_bonus + price_bonus,
        float(ex.get("option_quality_score") or 0),
        -spread,
        -price,
    )


def _tradeable_strategy_expiries(
    p: PredictionResult,
    min_dte: int,
    max_price: float = MAX_STRATEGY_OPTION_PRICE,
    limit: int = 3,
) -> list[dict]:
    """Return practical option expiries for the execution-style strategy tabs.

    Options Edge can still show broader chain context, but the strategy views
    promote only quoted contracts that satisfy the user's tradeability guardrails:
    DTE >= min_dte, action present, and premium <= max_price.
    """
    expiries = []
    for ex in (p.options_trade_idea or {}).get("top_expiries", []):
        price = _safe_float(ex.get("reference_option_price"))
        if int(ex.get("days_to_expiry") or 0) < min_dte:
            continue
        if ex.get("action") == "NO TRADE":
            continue
        if price is None or price <= 0 or price > max_price:
            continue
        expiries.append(ex)
    return sorted(expiries, key=_strategy_expiry_rank, reverse=True)[:limit]


def _best_strategy_expiry(p: PredictionResult, min_dte: int) -> dict:
    expiries = _tradeable_strategy_expiries(p, min_dte, limit=1)
    return expiries[0] if expiries else {}


def _strategy_sort_key(p: PredictionResult, min_dte: int) -> tuple[float, float, float, float]:
    """Soft rank: actionable, confident, liquid setups float to the top."""
    ex = _best_strategy_expiry(p, min_dte)
    gate = str(ex.get("risk_gate") or ex.get("readiness") or "").lower()
    action = str(ex.get("action") or (p.final_verdict or {}).get("research_action", "")).lower()
    direction = p.direction.value
    directional = 1.0 if direction not in ("neutral", "avoid") else 0.0
    blocked = -40.0 if p.risk.block_trade or direction == "avoid" else 0.0
    option_bonus = 12.0 if ex else 0.0
    gate_bonus = {"high": 22.0, "spread only": 12.0, "paper only": -8.0, "watch": 0.0}.get(gate, 0.0)
    side_bonus = 8.0 if any(x in action for x in ("call", "put", "long", "short", "buy", "sell")) else 0.0
    spread = _safe_float(ex.get("bid_ask_spread_pct"), 99.0) if ex else 99.0
    liquidity = float(ex.get("option_quality_score") or 0.0) if ex else 0.0
    score = (
        p.confidence_score * 0.45
        + p.opportunity_score * 0.25
        - p.risk_score * 0.22
        + directional * 10.0
        + option_bonus
        + gate_bonus
        + side_bonus
        + blocked
    )
    if spread is not None and spread <= 8:
        score += 5.0
    elif spread is not None and spread > 20:
        score -= 8.0
    return (score, p.confidence_score, liquidity, -p.risk_score)


def _strategy_summary_row(p: PredictionResult, min_dte: int) -> str:
    snap = p.market_snapshot or {}
    current = _safe_float(snap.get("current_price"))
    expiries = _tradeable_strategy_expiries(p, min_dte, limit=3)
    best_ex = expiries[0] if expiries else {}
    final = p.final_verdict or {}
    action = best_ex.get("action") or final.get("research_action", "watch_only")
    side = _signal_side(p.direction.value, str(action))
    days, expected_ret, prob_side, p05 = _forecast_for_strategy(p, side)
    target = current * (1 + expected_ret / 100) if current is not None and expected_ret is not None else None
    downside = abs(p05 or 0) / 100 * 0.75 if p05 is not None else 0.045
    stop_pct = min(max(downside, 0.035), 0.095)
    stop = None
    if current is not None:
        stop = current * (1 + stop_pct) if side == "short" else current * (1 - stop_pct)

    side_color = "#16a34a" if side == "long" else "#dc2626" if side == "short" else "#6b7280"
    rank = _strategy_sort_key(p, min_dte)[0]
    prob_txt = f"{prob_side:.1f}%" if prob_side is not None else "n/a"
    expected_txt = f"{expected_ret:+.2f}%" if expected_ret is not None else "n/a"

    why = []
    if final.get("label"):
        why.append(str(final.get("label")))
    if p.trend_impact.get("summary"):
        why.append(str(p.trend_impact.get("summary")))
    if best_ex.get("iv_risk"):
        why.append(str(best_ex.get("iv_risk")))
    why_txt = "; ".join(why[:3]) or "No strong summary reason captured."
    option_details = (
        f"<button type='button' class='summary-toggle' data-summary-group='{p.ticker}' "
        f"aria-expanded='false'>+ {len(expiries)} tradeable expiries</button><br>"
        f"<small>DTE ≥ {min_dte}, premium ≤ ${MAX_STRATEGY_OPTION_PRICE:.0f}, sorted best first.</small>"
        if expiries else
        f"Stock only — no qualifying option ≤ ${MAX_STRATEGY_OPTION_PRICE:.0f} with DTE ≥ {min_dte}."
    )

    parent = (
        f"<tr id='trade_summary-{p.ticker}' class='summary-parent strategy-row' data-summary-group='{p.ticker}' data-side='{side}' "
        f"data-er='{_attr(expected_ret if expected_ret is not None else '')}' "
        f"data-stop-pct='{stop_pct:.5f}' data-delta='' data-option-entry=''>"
        f"<td><b>{p.ticker}</b><br><small>rank {rank:.1f}</small></td>"
        f"<td style='color:{side_color};font-weight:800'>{side}</td>"
        f"<td>{'stock + options' if expiries else 'stock'}</td>"
        f"<td>{p.opportunity_score:.0f}/{p.confidence_score:.0f}/{p.risk_score:.0f}<br>"
        f"<small>{prob_txt} · {expected_txt}</small></td>"
        f"<td class='px strategy-current' data-role='current' data-tk='{p.ticker}'>{_fmt_money(current)}</td>"
        f"<td data-role='target'>{_fmt_money(target)}</td><td>{days}</td>"
        f"<td data-role='stop'>{_fmt_money(stop)}</td><td data-role='exit'>{_fmt_money(target)}</td>"
        f"<td>{option_details}</td><td>{why_txt}</td><td>—</td></tr>"
    )

    child_rows = []
    for idx, ex in enumerate(expiries, 1):
        opt_price = _safe_float(ex.get("reference_option_price"))
        delta = _safe_float(ex.get("delta"))
        opt_stop = opt_price * 0.65 if opt_price is not None else None
        opt_exit = None
        if opt_price is not None and delta is not None and current is not None and target is not None:
            opt_exit = opt_price + abs(delta) * abs(target - current)
        elif opt_price is not None:
            opt_exit = opt_price * 1.25

        gate = ex.get("risk_gate") or ex.get("readiness") or "watch"
        readiness = ex.get("readiness", "research")
        contract = ex.get("reference_contract") or ""
        opt_type = _infer_option_type(str(contract), ex.get("reference_type")) if contract else ""
        child_action = ex.get("action") or action
        child_side = _signal_side(p.direction.value, str(child_action))
        child_side_color = "#16a34a" if child_side == "long" else "#dc2626" if child_side == "short" else "#6b7280"
        option_details_child = (
            f"<b>{contract}</b><br>"
            f"<small>expiry {ex.get('expiration', '—')} · DTE {ex.get('days_to_expiry', '—')} · "
            f"strike {ex.get('atm_strike', '—')} · entry {_fmt_money(opt_price)} · "
            f"stop {_fmt_money(opt_stop)} · exit {_fmt_money(opt_exit)}</small><br>"
            f"<small>readiness {readiness} · gate {gate} · spread {ex.get('bid_ask_spread_pct', '—')}% · "
            f"vol/OI {ex.get('exact_contract_volume', '—')}/{ex.get('exact_contract_oi', '—')} · "
            f"IV Rank {ex.get('iv_rank', '—')} · Δ/Θ {ex.get('delta', '—')}/{ex.get('theta_per_day', '—')}</small>"
        )
        note = (
            f"TRADE SUMMARY {p.ticker}: {child_action}; underlying entry {current}; "
            f"target {target}; stop {stop}; option {contract}; expiry {ex.get('expiration')}; "
            f"option entry {opt_price}; option target {opt_exit}; option stop {opt_stop}; "
            f"DTE {ex.get('days_to_expiry')}; premium cap {MAX_STRATEGY_OPTION_PRICE}; research only."
        )
        option_trade = (
            f"<button class='tab signal-add-trade' data-instrument='option' data-tk='{_attr(contract)}' "
            f"data-underlying='{_attr(p.ticker)}' data-contract='{_attr(contract)}' data-side='long' "
            f"data-expiry='{_attr(ex.get('expiration'))}' data-option-type='{_attr(opt_type)}' "
            f"data-strike='{_attr(ex.get('atm_strike') or '')}' data-price='{_attr(opt_price)}' data-qty='1' "
            f"data-multiplier='{_attr(ex.get('contract_multiplier') or 100)}' data-note='{_attr(note)}'>Add option</button>"
        )
        child_why = []
        if ex.get("confidence") is not None:
            child_why.append(f"option confidence {float(ex.get('confidence')):.0f}")
        if ex.get("iv_risk"):
            child_why.append(str(ex.get("iv_risk")))
        if ex.get("flow_alignment"):
            child_why.append(f"flow {ex.get('flow_alignment')}")
        if ex.get("reasons"):
            child_why.extend(str(x) for x in (ex.get("reasons") or [])[:2])
        child_why_txt = "; ".join(child_why[:4]) or why_txt
        child_rows.append(
            f"<tr id='trade_summary-{p.ticker}-{idx}' class='summary-child strategy-row collapsed' "
            f"data-summary-parent='{p.ticker}' data-side='{child_side}' "
            f"data-er='{_attr(expected_ret if expected_ret is not None else '')}' "
            f"data-stop-pct='{stop_pct:.5f}' data-delta='{_attr(delta if delta is not None else '')}' "
            f"data-option-entry='{_attr(opt_price if opt_price is not None else '')}'>"
            f"<td><small>↳ {p.ticker} · {ex.get('expiration')}</small></td>"
            f"<td style='color:{child_side_color};font-weight:800'>{child_side}</td>"
            f"<td>option</td>"
            f"<td>{p.opportunity_score:.0f}/{p.confidence_score:.0f}/{p.risk_score:.0f}<br>"
            f"<small>{prob_txt} · {expected_txt}</small></td>"
            f"<td class='px strategy-current' data-role='current' data-tk='{p.ticker}'>{_fmt_money(current)}</td>"
            f"<td data-role='target'>{_fmt_money(target)}</td><td>{days}</td>"
            f"<td data-role='stop'>{_fmt_money(stop)}</td><td data-role='exit'>{_fmt_money(target)}</td>"
            f"<td>{option_details_child}</td><td>{child_why_txt}</td><td>{option_trade}</td></tr>"
        )

    return parent + "".join(child_rows)


def _trade_strategy_row(p: PredictionResult, min_dte: int) -> str:
    snap = p.market_snapshot or {}
    current = _safe_float(snap.get("current_price"))
    ex = _best_strategy_expiry(p, min_dte)
    final = p.final_verdict or {}
    action = ex.get("action") or final.get("research_action", "watch_only")
    side = _signal_side(p.direction.value, str(action))
    days, expected_ret, prob_side, p05 = _forecast_for_strategy(p, side)
    target = current * (1 + expected_ret / 100) if current is not None and expected_ret is not None else None

    downside = abs(p05 or 0) / 100 * 0.75 if p05 is not None else 0.045
    stop_pct = min(max(downside, 0.035), 0.095)
    stop = None
    if current is not None:
        stop = current * (1 + stop_pct) if side == "short" else current * (1 - stop_pct)

    opt_price = _safe_float(ex.get("reference_option_price"))
    delta = _safe_float(ex.get("delta"))
    opt_exit = None
    opt_stop = opt_price * 0.65 if opt_price is not None else None
    if opt_price is not None and delta is not None and current is not None and target is not None:
        opt_exit = opt_price + abs(delta) * abs(target - current)
    elif opt_price is not None:
        opt_exit = opt_price * 1.25

    spread = _safe_float(ex.get("bid_ask_spread_pct"))
    gate = ex.get("risk_gate") or ex.get("readiness") or "watch"
    readiness = ex.get("readiness", "research")
    strategy_action = "paper only"
    if p.risk.block_trade or p.direction.value in ("neutral", "avoid"):
        strategy_action = "wait"
    elif gate == "high" and p.confidence_score >= 55 and side in ("long", "short"):
        strategy_action = "tradeable research"
    elif gate == "spread only" and side in ("long", "short"):
        strategy_action = "defined-risk spread"
    elif side in ("long", "short"):
        strategy_action = "paper/watch"

    risk_color = "#16a34a" if p.risk_score <= 35 else "#f59e0b" if p.risk_score <= 55 else "#dc2626"
    side_color = "#16a34a" if side == "long" else "#dc2626" if side == "short" else "#6b7280"
    action_color = "#16a34a" if strategy_action == "tradeable research" else "#b45309" if strategy_action == "defined-risk spread" else "#dc2626" if strategy_action == "wait" else "#6b7280"
    prob_txt = f"{prob_side:.1f}%" if prob_side is not None else "n/a"
    expected_txt = f"{expected_ret:+.2f}%" if expected_ret is not None else "n/a"
    contract = ex.get("reference_contract") or "—"
    opt_type = _infer_option_type(str(contract), ex.get("reference_type")) if contract != "—" else ""
    note = (
        f"TRADE STRATEGY {p.ticker}: {action}; strategy {strategy_action}; "
        f"underlying entry {current}; target {target}; stop {stop}; "
        f"option {contract}; expiry {ex.get('expiration')}; option entry {opt_price}; "
        f"option target {opt_exit}; option stop {opt_stop}; research only."
    )
    option_btn = "—"
    if contract != "—" and opt_price is not None and action != "NO TRADE":
        option_btn = (
            f"<button class='tab signal-add-trade' data-instrument='option' data-tk='{_attr(contract)}' "
            f"data-underlying='{_attr(p.ticker)}' data-contract='{_attr(contract)}' data-side='long' "
            f"data-expiry='{_attr(ex.get('expiration'))}' data-option-type='{_attr(opt_type)}' "
            f"data-strike='{_attr(ex.get('atm_strike') or '')}' data-price='{_attr(opt_price)}' data-qty='1' "
            f"data-multiplier='{_attr(ex.get('contract_multiplier') or 100)}' data-note='{_attr(note)}'>Add option</button>"
        )

    reasons = []
    if p.trend_impact.get("summary"):
        reasons.append(str(p.trend_impact.get("summary")))
    if ex.get("flow_alignment"):
        reasons.append(f"flow {ex.get('flow_alignment')}")
    if ex.get("iv_risk"):
        reasons.append(str(ex.get("iv_risk")))
    if final.get("reasons"):
        reasons.extend(str(x) for x in final.get("reasons", [])[:2])
    why = "; ".join(reasons[:4]) or "No strong strategy reason captured."

    return (
        f"<tr id='strategy-{p.ticker}' class='strategy-row' data-side='{side}' "
        f"data-er='{_attr(expected_ret if expected_ret is not None else '')}' "
        f"data-stop-pct='{stop_pct:.5f}' data-delta='{_attr(delta if delta is not None else '')}' "
        f"data-option-entry='{_attr(opt_price if opt_price is not None else '')}'>"
        f"<td><b>{p.ticker}</b><br><small>{final.get('label', p.direction.value)}</small></td>"
        f"<td style='color:{side_color};font-weight:700'>{side}</td>"
        f"<td style='color:{action_color};font-weight:700'>{strategy_action}</td>"
        f"<td>{p.opportunity_score:.0f}/{p.confidence_score:.0f}/{p.risk_score:.0f}</td>"
        f"<td style='color:{risk_color};font-weight:700'>{p.risk.risk_level.value}</td>"
        f"<td class='px strategy-current' data-role='current' data-tk='{p.ticker}'>{_fmt_money(current)}</td>"
        f"<td>{prob_txt}</td><td>{expected_txt}</td><td>{days}</td>"
        f"<td data-role='target'>{_fmt_money(target)}</td>"
        f"<td data-role='stop'>{_fmt_money(stop)}</td>"
        f"<td data-role='exit'>{_fmt_money(target)}</td>"
        f"<td>{ex.get('expiration', '—')}</td><td>{ex.get('days_to_expiry', '—')}</td>"
        f"<td>{contract}</td><td>{ex.get('atm_strike', '—')}</td>"
        f"<td data-role='option-entry'>{_fmt_money(opt_price)}</td>"
        f"<td data-role='option-stop'>{_fmt_money(opt_stop)}</td>"
        f"<td data-role='option-exit'>{_fmt_money(opt_exit)}</td>"
        f"<td>{ex.get('confidence', '—')}</td><td>{readiness}</td><td>{gate}</td>"
        f"<td>{spread if spread is not None else '—'}</td>"
        f"<td>{ex.get('exact_contract_volume', '—')} / {ex.get('exact_contract_oi', '—')}</td>"
        f"<td>{ex.get('iv_rank', '—')}</td><td>{ex.get('delta', '—')} / {ex.get('theta_per_day', '—')}</td>"
        f"<td>{why}</td><td>{option_btn}</td></tr>"
    )


def _opt_verdict(action: str, gate: str) -> tuple[str, str, str]:
    """Consolidate the gate into ONE plain tradeability verdict for the Options
    Edge row. Returns (label, color, plain-English meaning)."""
    if action == "NO TRADE":
        return ("🚫 NO TRADE", "#6b7280",
                "No directional edge right now — stay out of options on this name.")
    g = (gate or "").lower()
    if g == "high":
        return ("✅ TRADEABLE", "#16a34a",
                "Clears the full risk gate — the listed option is tradeable (defined risk is still wise).")
    if g == "spread only":
        return ("⚠️ TRADE AS A SPREAD", "#b45309",
                "Do NOT buy the naked option — rich IV / earnings / wide-spread risk would bleed a long premium. "
                "Trade the defined-risk spread shown below instead (you cap cost and crush risk).")
    if g == "paper only":
        return ("📝 PAPER ONLY", "#dc2626",
                "Track on paper only — thin liquidity, very short DTE, or high IV-crush risk make real money unwise here.")
    return ("👀 WATCH", "#f59e0b",
            "Borderline setup — watch for cleaner liquidity/IV before committing real capital.")


def _opt_structure_html(ex: dict) -> str:
    """Plain summary of the recommended option structure with est. max gain/loss/breakeven."""
    def _fmt(s: dict) -> str:
        legs = []
        for k in ("long_strike", "short_strike", "short_put", "long_put", "short_call", "long_call"):
            if s.get(k) is not None:
                legs.append(f"{k.replace('_', ' ')} {s[k]}")
        nums = []
        if s.get("est_net_debit") is not None:
            nums.append(f"net debit ~${s['est_net_debit']}")
        if s.get("est_net_credit") is not None:
            nums.append(f"net credit ~${s['est_net_credit']}")
        if s.get("est_max_gain") is not None:
            nums.append(f"max gain ~${s['est_max_gain']}")
        if s.get("est_max_loss") is not None:
            nums.append(f"max loss ~${s['est_max_loss']}")
        if s.get("breakeven") is not None:
            nums.append(f"breakeven {s['breakeven']}")
        name = str(s.get("type", "spread")).replace("_", " ")
        tail = (" — " + ", ".join(nums)) if nums else ""
        return f"{name}: {', '.join(legs)}{tail}"

    parts = []
    sp = ex.get("spread") or {}
    if sp:
        parts.append("<b>Defined-risk:</b> " + _fmt(sp))
    alt = ex.get("alt_structure") or {}
    if alt:
        parts.append("<b>Premium-selling alt:</b> " + _fmt(alt))
    if not parts:
        return "—"
    return " &nbsp;·&nbsp; ".join(parts) + " <i>(research-only estimates from the 1σ move, not live multi-leg quotes)</i>"


def render_markdown(result: RunResult) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    macro = result.macro
    lines = [
        f"# {__product__} — Daily Market Brief",
        f"_Generated {now} · strategy `{result.strategy}` · horizon `{result.horizon}`_",
        "",
        DISCLAIMER,
        "",
        "## Market Regime",
    ]
    if macro.available:
        kv = ", ".join(f"{k}={v}" for k, v in macro.values.items())
        lines.append(f"- Macro snapshot: {kv}")
    else:
        lines.append(f"- {macro.note or 'Macro data unavailable; neutral regime assumed.'}")
    gov = result.government
    if gov.available:
        if gov.values:
            gkv = ", ".join(f"{k}={v}" for k, v in gov.values.items())
            lines.append(f"- Government/fiscal: {gkv}")
        by_kind: dict[str, int] = {}
        for ev in gov.events:
            by_kind[ev.kind] = by_kind.get(ev.kind, 0) + 1
        kind_txt = ", ".join(f"{k}:{n}" for k, n in by_kind.items()) or "none"
        lines.append(f"- Government sources: {', '.join(gov.providers)} ({len(gov.events)} items — {kind_txt}).")
        # Show up to two events per category so FDA/antitrust aren't crowded out.
        shown: dict[str, int] = {}
        for ev in gov.events:
            if shown.get(ev.kind, 0) >= 2:
                continue
            shown[ev.kind] = shown.get(ev.kind, 0) + 1
            lines.append(f"  - [{ev.source}] {ev.title[:120]}" + (f" ({ev.url})" if ev.url else ""))
    else:
        lines.append(f"- {gov.note or 'Government data unavailable; policy context neutral.'}")

    gm = getattr(result, "global_markets", None)
    if gm is not None and getattr(gm, "available", False):
        lines += ["", "## Global Markets (US · Europe · Asia)", f"- {gm.regime_note}"]
        by_region: dict[str, list[str]] = {}
        for gi in gm.indexes.values():
            chg = f"{gi.day_change_pct:+.2f}%" if gi.day_change_pct is not None else "n/a"
            by_region.setdefault(gi.region, []).append(f"{gi.name} {gi.last} ({chg})")
        for region in ("US", "Europe", "Asia"):
            if by_region.get(region):
                lines.append(f"- **{region}:** " + " · ".join(by_region[region]))

    lines += ["", "## Ranked Signals", "",
              "| # | Ticker | Type | Dir | Opp | Conf | Risk | Sev | Expected Move |",
              "|--:|--------|------|-----|----:|-----:|-----:|-----|---------------|"]
    for i, p in enumerate(result.predictions, 1):
        em = p.expected_move
        em_txt = f"{em.low_pct:+.1f}% / {em.high_pct:+.1f}%" if em and em.low_pct is not None else "n/a"
        lines.append(
            f"| {i} | **{p.ticker}** | {p.asset_type.value} | {_emoji(p)} {p.direction.value} "
            f"| {p.opportunity_score:.0f} | {p.confidence_score:.0f} | {p.risk_score:.0f} "
            f"| {p.severity.value} | {em_txt} |"
        )

    lines += ["", "## Detailed Analysis", ""]
    for p in result.predictions:
        lines.append(f"### {_emoji(p)} {p.ticker} — {p.direction.value.replace('_', ' ').title()}")
        lines.append(
            f"- **Scores:** opportunity {p.opportunity_score:.0f} · confidence {p.confidence_score:.0f} "
            f"· risk {p.risk_score:.0f} ({p.risk.risk_level.value}) · severity {p.severity.value}"
        )
        comp = " · ".join(f"{k}:{v:.0f}(w{p.component_weights.get(k,0):.2f})" for k, v in p.component_scores.items())
        lines.append(f"- **Components:** {comp}")
        em = p.expected_move
        if em and em.low_pct is not None:
            lines.append(f"- **Expected move ({em.basis}):** {em.low_pct:+.1f}% to {em.high_pct:+.1f}%")
        f = p.forecast
        if f and f.available and f.prob_up is not None:
            votes = ", ".join(f"{k}:{v}" for k, v in f.agent_votes.items()) or "n/a"
            lines.append(
                f"- **Forecast ({f.horizon_days}D, {f.method}):** P(up) {f.prob_up:.0%}, "
                f"median {f.expected_return_pct:+.1f}%, band [{f.p05_return_pct:+.1f}%, {f.p95_return_pct:+.1f}%] "
                f"· agents: {votes}"
            )
        snap = p.market_snapshot
        if snap:
            change = snap.get("day_change_pct")
            change_txt = f"{change:+.2f}%" if change is not None else "n/a"
            lines.append(
                f"- **Current market price:** {snap.get('current_price')} "
                f"({change_txt} today, source {snap.get('source')})"
            )
        if p.paper_trade:
            lines.append(
                f"- **Dummy paper trade:** {p.paper_trade.get('side')} from {p.paper_trade.get('entry_price')} "
                f"-> {p.paper_trade.get('current_price')} "
                f"({p.paper_trade.get('unrealized_pnl_pct'):+.2f}%, "
                f"${p.paper_trade.get('unrealized_pnl_dollars'):+.2f})"
            )
        if p.catalysts:
            lines.append("- **Catalysts:** " + "; ".join(p.catalysts[:4]))
        if p.policy_impacts:
            lines.append("- **Policy/government impact:**")
            for pi in p.policy_impacts[:4]:
                lines.append(f"  - {pi}")
        if p.global_correlations:
            gc = " · ".join(f"{k} {v:+.2f}" for k, v in list(p.global_correlations.items())[:5])
            lines.append(f"- **Global correlations (60d):** {gc}")
        if p.risk.penalties:
            lines.append("- **Risk penalties:** " + "; ".join(p.risk.penalties))
        if p.risk.warnings:
            lines.append("- **Warnings:** " + "; ".join(p.risk.warnings))
        lines.append("- **Invalidation:** " + "; ".join(p.invalidation_conditions))
        if p.missing_data:
            lines.append("- **Missing/limited data:** " + ", ".join(p.missing_data))
        # evidence
        ev_lines = []
        for eid in (p.key_bullish_evidence + p.key_bearish_evidence)[:4]:
            e = result.evidence.get(eid)
            if e:
                tag = "🟢" if e.polarity > 0 else "🔴"
                ev_lines.append(f"  - {tag} [{e.source_name}] {e.claim[:120]}" + (f" ({e.url})" if e.url else ""))
        if ev_lines:
            lines.append("- **Evidence:**")
            lines.extend(ev_lines)
        lines.append("")

    lines += ["---", DISCLAIMER]
    return "\n".join(lines)


def render_json(result: RunResult) -> str:
    return json.dumps([p.model_dump(mode="json") for p in result.predictions], indent=2, default=str)


def render_csv(result: RunResult) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ticker", "asset_type", "direction", "opportunity", "confidence", "risk",
                "risk_level", "severity", "horizon", "strategy"])
    for p in result.predictions:
        w.writerow([p.ticker, p.asset_type.value, p.direction.value, p.opportunity_score,
                    p.confidence_score, p.risk_score, p.risk.risk_level.value, p.severity.value,
                    p.horizon, p.strategy])
    return buf.getvalue()


def render_html(result: RunResult) -> str:
    min_option_dte = max(5, int(getattr(get_settings(), "min_option_days_to_expiry", 5) or 5))
    rows = ""
    price_rows = ""
    why_cards = ""
    news_cards = ""
    paper_rows = ""
    manual_rows = ""
    trend_rows = ""
    verdict_rows = ""
    event_rows = ""
    confidence_rows = ""
    options_rows = ""
    strategy_rows = ""
    strategy_summary_rows = ""
    strategy_predictions = sorted(
        result.predictions,
        key=lambda pred: _strategy_sort_key(pred, min_option_dte),
        reverse=True,
    )
    strategy_summary_rows = "".join(_strategy_summary_row(p, min_option_dte) for p in strategy_predictions)
    strategy_rows = "".join(_trade_strategy_row(p, min_option_dte) for p in strategy_predictions)
    for i, p in enumerate(result.predictions, 1):
        color = {"bullish": "#16a34a", "neutral_to_bullish": "#22c55e", "neutral": "#9ca3af",
                 "neutral_to_bearish": "#f87171", "bearish": "#dc2626", "avoid": "#6b7280"}.get(p.direction.value, "#999")
        snap = p.market_snapshot
        day_change = snap.get("day_change_pct") if snap else None
        day_change_txt = f"{day_change:+.2f}%" if day_change is not None else "n/a"
        day_class = _move_class(day_change)
        current_price = snap.get("current_price", "n/a") if snap else "n/a"
        source = snap.get("source", "unknown") if snap else "unknown"
        em = p.expected_move
        em_txt = f"{em.low_pct:+.1f}% / {em.high_pct:+.1f}%" if em and em.low_pct is not None else "n/a"
        final = p.final_verdict or {}
        action = final.get("research_action", "watch_only")
        signal_side = _signal_side(p.direction.value, action)
        price_attr = current_price if isinstance(current_price, (int, float)) else ""
        signal_note = (
            f"{p.ticker} dashboard signal: {action}; direction {p.direction.value}; "
            f"confidence {p.confidence_score:.0f}; options thesis available in Options Edge."
        )
        signal_trade_btn = (
            f"<button class='tab signal-add-trade' data-tk='{p.ticker}' data-side='{signal_side}' "
            f"data-price='{price_attr}' data-note='{signal_note}'>Add trade</button>"
        )
        rows += (
            f"<tr><td>{i}</td><td><b>{p.ticker}</b></td><td>{p.asset_type.value}</td>"
            f"<td style='color:{color};font-weight:600'>{p.direction.value}</td>"
            f"<td>{p.opportunity_score:.0f}</td><td>{p.confidence_score:.0f}</td>"
            f"<td>{p.risk_score:.0f}</td><td>{p.severity.value}</td>"
            f"<td class='px' data-tk='{p.ticker}'>{current_price}</td>"
            f"<td class='daypx {day_class}' data-tk='{p.ticker}'>{day_change_txt}</td>"
            f"<td>{p.trend_impact.get('summary', '')}</td><td>{signal_trade_btn}</td></tr>"
        )
        side_color = "#16a34a" if "long" in action else "#dc2626" if "short" in action else "#6b7280"
        verdict_rows += (
            f"<tr id='verdicts-{p.ticker}'><td><b>{p.ticker}</b></td><td style='color:{side_color};font-weight:700'>{final.get('label', p.direction.value)}</td>"
            f"<td>{action}</td><td>{p.opportunity_score:.0f}</td><td>{p.confidence_score:.0f}</td>"
            f"<td>{p.risk_score:.0f}</td><td>{'; '.join(final.get('reasons', []) or [])}</td></tr>"
        )
        er = p.event_radar or {}
        returns = er.get("returns", {}) if er.get("available") else {}
        event_rows += (
            f"<tr id='events-{p.ticker}'><td><b>{p.ticker}</b></td><td>{er.get('verdict', er.get('reason', 'n/a'))}</td>"
            f"<td>{er.get('breakout_score', 'n/a')}</td><td>{er.get('exhaustion_score', 'n/a')}</td>"
            f"<td>{returns.get('20d_pct', 'n/a')}</td><td>{returns.get('60d_pct', 'n/a')}</td>"
            f"<td>{returns.get('252d_pct', 'n/a')}</td><td>{er.get('volume_ratio_20d', 'n/a')}</td>"
            f"<td>{'; '.join(er.get('bullish_clues', [])[:4])}</td>"
            f"<td>{'; '.join(er.get('bearish_clues', [])[:4])}</td></tr>"
        )
        trend = p.trend_impact or {}
        trace = p.confidence_trace or {}
        trace_links = "".join(
            f"<a href='{url}' target='_blank'>source</a> "
            for url in trace.get("top_source_links", [])[:4]
        ) or "n/a"
        call = trace.get("applies_to", "n/a")
        call_color = "#16a34a" if "BUY" in call else "#dc2626" if "SELL" in call else "#6b7280"
        cal = trace.get("calibration") or {}
        if cal.get("available"):
            adj = cal.get("adjustment", 0)
            cal_txt = (
                f"{cal.get('raw_confidence', p.confidence_score):.0f} → "
                f"{cal.get('calibrated_confidence', p.confidence_score):.0f} "
                f"({adj:+.1f}; {cal.get('sample_count', 0)} samples)"
            )
        else:
            cal_txt = f"raw {trace.get('raw_confidence_score', p.confidence_score):.0f}; {cal.get('reason', 'not enough matured outcomes')}"
        confidence_rows += (
            f"<tr id='confidence-{p.ticker}'><td><b>{p.ticker}</b></td>"
            f"<td style='color:{call_color};font-weight:700'>{call}</td>"
            f"<td><b>{p.confidence_score:.0f}</b></td>"
            f"<td><small>{cal_txt}</small></td>"
            f"<td>{trace.get('directional_conviction_pct', 'n/a')}</td>"
            f"<td>{trace.get('data_quality_pct', 'n/a')}</td>"
            f"<td>{trace.get('agreement_pct', 'n/a')}</td>"
            f"<td>{trace.get('evidence_count', 0)}</td>"
            f"<td>{', '.join(trace.get('missing_engines', []) or []) or 'none'}</td>"
            f"<td><a href='/ticker/{p.ticker}' target='_blank'>signal JSON</a> · "
            f"<a href='/signals' target='_blank'>all signals</a> · "
            f"<a href='#' data-goto='why' data-ticker='{p.ticker}'>why</a> · "
            f"<a href='#' data-goto='news' data-ticker='{p.ticker}'>news</a> · {trace_links}</td></tr>"
        )
        oi = p.options_trade_idea or {}
        top_exp = [
            ex for ex in (oi.get("top_expiries") or [])
            if int(ex.get("days_to_expiry") or 0) >= min_option_dte
        ]
        src = oi.get("data_source", "n/a")
        _cmap = {"green": "#16a34a", "orange": "#f59e0b", "red": "#dc2626"}
        algo_txt = f"{oi.get('algo_confluence', 'n/a')}/5 ({oi.get('algo_confluence_label', 'n/a')})"
        if not top_exp:
            options_rows += (
                f"<tr id='options-{p.ticker}' class='opt-parent'><td><b>{p.ticker}</b><br><small>{src}</small></td>"
                f"<td colspan='30'>No live options chain available from yfinance or CBOE for this name. "
                f"Underlying bias: {oi.get('bias', 'n/a')} · algo confluence {algo_txt}.</td></tr>"
            )
        else:
            for j, ex in enumerate(top_exp):
                ac = _cmap.get(ex.get("action_color"), "#6b7280")
                cc = _cmap.get(ex.get("confidence_color"), "#6b7280")
                sp = ex.get("spread") or {}
                sp_txt = (f"{sp.get('type')} {sp.get('long_strike')}/{sp.get('short_strike')}"
                          if sp else "—")
                if j == 0:
                    more_count = max(0, len(top_exp) - 1)
                    row_meta = f" id='options-{p.ticker}' class='opt-parent opt-data' data-option-group='{p.ticker}'"
                    why_meta = f" class='opt-why' data-option-parent='{p.ticker}'"
                    tk_cell = (
                        f"<button type='button' class='opt-toggle' data-option-group='{p.ticker}' "
                        f"aria-expanded='false'>+ {p.ticker}</button><br>"
                        f"<small>{src} · algo {algo_txt} · {len(top_exp)} ranked expiries"
                        f"{' · click to show ' + str(more_count) + ' more' if more_count else ''}</small>"
                    )
                else:
                    row_meta = f" class='opt-child opt-data collapsed' data-option-parent='{p.ticker}'"
                    why_meta = f" class='opt-child opt-why collapsed' data-option-parent='{p.ticker}'"
                    tk_cell = f"<small>↳ {p.ticker} · expiry {ex.get('expiration')}</small>"
                iv_txt = f"{ex.get('avg_iv')}%" if ex.get("avg_iv") is not None else "—"
                pcr_txt = ex.get("put_call_ratio") if ex.get("put_call_ratio") is not None else "—"
                opt_contract = ex.get("reference_contract") or ""
                opt_price = ex.get("reference_option_price")
                if opt_price is None and opt_contract and opt_contract == oi.get("reference_contract"):
                    opt_price = oi.get("atm_call_last") if ex.get("action") == "BUY CALL" else oi.get("atm_put_last")
                opt_price_txt = f"{float(opt_price):.2f}" if opt_price is not None else "—"
                bid = ex.get("reference_bid")
                ask = ex.get("reference_ask")
                ba_txt = (
                    f"{float(bid):.2f} / {float(ask):.2f}"
                    if bid is not None and ask is not None and (float(bid) > 0 or float(ask) > 0)
                    else "—"
                )
                spread_pct = ex.get("bid_ask_spread_pct")
                spread_pct_txt = f"{float(spread_pct):.1f}%" if spread_pct is not None else "—"
                spread_color = "#16a34a" if spread_pct is not None and float(spread_pct) <= 15 else "#dc2626" if spread_pct is not None and float(spread_pct) > 25 else "#f59e0b"
                quality = ex.get("option_quality_score")
                quality_txt = f"{float(quality):.0f}" if quality is not None else "—"
                ready = ex.get("readiness", "research")
                gate = ex.get("risk_gate") or ready
                ready_color = "#16a34a" if gate == "high" else "#f59e0b" if gate in ("medium", "watch", "spread only", "low", "research") else "#dc2626"
                exact_liq = (
                    f"{ex.get('exact_contract_volume', '—')} / {ex.get('exact_contract_oi', '—')}"
                    if ex.get("exact_contract_volume") is not None or ex.get("exact_contract_oi") is not None
                    else "—"
                )
                greeks_txt = (
                    f"Δ {ex.get('delta', '—')} · Θ {ex.get('theta_per_day', '—')} · V {ex.get('vega_per_vol_point', '—')}"
                    if ex.get("delta") is not None else "—"
                )
                breakeven_txt = (
                    f"{float(ex.get('breakeven_price')):.2f} ({float(ex.get('breakeven_pct')):+.1f}%)"
                    if ex.get("breakeven_price") is not None and ex.get("breakeven_pct") is not None
                    else "—"
                )
                premium_pct_txt = f"{float(ex.get('premium_pct_spot')):.1f}%" if ex.get("premium_pct_spot") is not None else "—"
                ivrv_txt = f"{float(ex.get('iv_realized_ratio')):.1f}x" if ex.get("iv_realized_ratio") is not None else "—"
                ivrank_txt = (
                    f"{float(ex.get('iv_rank')):.0f}% / {float(ex.get('iv_percentile')):.0f}%"
                    if ex.get("iv_rank") is not None and ex.get("iv_percentile") is not None
                    else f"need {ex.get('iv_history_count', 0)}/20" if ex.get("iv_history_count") is not None else "—"
                )
                ivrank_color = "#dc2626" if ex.get("iv_rank") is not None and float(ex.get("iv_rank")) >= 70 else "#16a34a" if ex.get("iv_rank") is not None and float(ex.get("iv_rank")) <= 30 else "#6b7280"
                skew_txt = (
                    f"{float(ex.get('atm_iv_skew_pct')):+.1f} · {ex.get('term_structure_slope_pct'):+.1f}"
                    if ex.get("atm_iv_skew_pct") is not None and ex.get("term_structure_slope_pct") is not None
                    else f"{float(ex.get('atm_iv_skew_pct')):+.1f} · —" if ex.get("atm_iv_skew_pct") is not None
                    else "—"
                )
                skew_title = f"{ex.get('skew_label', 'unknown')} / {ex.get('term_structure_label', 'unknown')}"
                uoa_txt = (
                    f"{float(ex.get('unusual_activity_score')):.0f} · "
                    f"{ex.get('oi_change'):+d}" if ex.get("unusual_activity_score") is not None and ex.get("oi_change") is not None
                    else f"{float(ex.get('unusual_activity_score')):.0f} · —" if ex.get("unusual_activity_score") is not None
                    else "—"
                )
                uoa_color = "#dc2626" if ex.get("unusual_activity_score") is not None and float(ex.get("unusual_activity_score")) >= 75 else "#b45309" if ex.get("unusual_activity_score") is not None and float(ex.get("unusual_activity_score")) >= 50 else "#6b7280"
                multiplier = ex.get("contract_multiplier") or 100
                opt_type = _infer_option_type(opt_contract, ex.get("reference_type"))
                verdict_label, verdict_color, verdict_meaning = _opt_verdict(ex.get("action"), gate)
                # Add-trade button on EVERY actionable row (not just gate=high).
                # The label tells you HOW to trade it; clicking adds it to Manual
                # Trades (the handler switches to that tab). For 'spread only' we
                # add the long leg of the suggested spread; for paper/watch it is
                # tracked, not advised as real money.
                btn_label = {
                    "high": "Add option",
                    "spread only": "Add (spread leg)",
                    "paper only": "Add (paper)",
                }.get(gate, "Add (watch)")
                opt_note = (
                    f"OPTIONS {p.ticker}: {ex.get('action')} {opt_contract}; "
                    f"expiry {ex.get('expiration')}; DTE {ex.get('days_to_expiry')}; "
                    f"type {opt_type or 'n/a'}; ATM {ex.get('atm_strike')}; confidence {ex.get('confidence')}; "
                    f"verdict {verdict_label}; gate {gate}; underlying {current_price}; "
                    f"lot {multiplier} shares/contract."
                )
                if opt_contract and ex.get("action") != "NO TRADE":
                    option_btn = (
                        f"<button class='tab signal-add-trade' data-instrument='option' data-tk='{opt_contract}' "
                        f"data-underlying='{p.ticker}' data-contract='{opt_contract}' data-side='long' "
                        f"data-expiry='{ex.get('expiration')}' data-option-type='{opt_type}' "
                        f"data-strike='{ex.get('atm_strike') or ''}' data-price='{opt_price if opt_price is not None else ''}' data-qty='1' "
                        f"data-multiplier='{multiplier}' data-note='{opt_note}'>{btn_label}</button>"
                    )
                else:
                    option_btn = "<small class='neutral'>no trade</small>"

                # Row 1 — the metrics (29 cells, Why moved to row 2).
                options_rows += (
                    f"<tr{row_meta}><td>{tk_cell}</td>"
                    f"<td class='px' data-tk='{p.ticker}'>{current_price}</td>"
                    f"<td>{ex.get('expiration')}</td><td>{ex.get('days_to_expiry')}</td>"
                    f"<td style='background:{ac};color:#fff;font-weight:700;text-align:center'>{ex.get('action')}</td>"
                    f"<td style='color:{ac};font-weight:700;font-size:15px'>{ex.get('arrow')} {ex.get('direction')}</td>"
                    f"<td style='background:{cc};color:#fff;font-weight:700;text-align:center' title='Consolidated 0-100 score from direction, data quality, algo confluence, liquidity, IV, Greeks/theta, spread, and event risk'>{ex.get('confidence'):.0f}</td>"
                    f"<td style='color:{ready_color};font-weight:700'>{ready}</td>"
                    f"<td style='color:{ready_color};font-weight:700'>{gate}</td>"
                    f"<td>{quality_txt}</td>"
                    f"<td>{opt_contract or '—'}</td><td>{opt_price_txt}</td><td>{ba_txt}</td>"
                    f"<td style='color:{spread_color};font-weight:700'>{spread_pct_txt}</td>"
                    f"<td>{exact_liq}</td><td>{greeks_txt}</td><td>{breakeven_txt}</td>"
                    f"<td>{premium_pct_txt}</td><td>{ivrv_txt}</td>"
                    f"<td style='color:{ivrank_color};font-weight:700'>{ivrank_txt}</td>"
                    f"<td title='{skew_title}'>{skew_txt}</td>"
                    f"<td style='color:{uoa_color};font-weight:700' title='{ex.get('unusual_activity_label', 'normal')} · volume/OI {ex.get('volume_oi_ratio', '—')}'>"
                    f"{uoa_txt}</td>"
                    f"<td>{multiplier}</td><td>{ex.get('atm_strike') or '—'}</td><td>{sp_txt}</td>"
                    f"<td>{iv_txt}</td><td>{ex.get('total_volume')}</td>"
                    f"<td>{ex.get('call_volume', '—')} / {ex.get('put_volume', '—')}</td>"
                    f"<td>{ex.get('total_oi')}</td><td>{pcr_txt}</td>"
                    f"<td>{option_btn}</td></tr>"
                )
                # Row 2 — consolidated verdict + recommended structure + full Why.
                strategy_label = ex.get("strategy_label") or ""
                structure_html = _opt_structure_html(ex)
                reasons_html = "; ".join(ex.get("reasons", []) or []) or "—"
                struct_line = ""
                if strategy_label or structure_html != "—":
                    struct_line = (
                        f"<br><b>Best structure:</b> {strategy_label}"
                        f"{' &nbsp;·&nbsp; ' + structure_html if structure_html != '—' else ''}"
                    )
                options_rows += (
                    f"<tr{why_meta}><td colspan='31'>"
                    f"<span class='verdict-badge' style='color:{verdict_color}'>{verdict_label}</span> "
                    f"— {verdict_meaning}"
                    f"{struct_line}"
                    f"<br><b>Why (evidence):</b> {reasons_html}"
                    f"</td></tr>"
                )
        trend_rows += (
            f"<tr id='trends-{p.ticker}'><td><b>{p.ticker}</b></td><td class='{day_class}'>{day_change_txt}</td>"
            f"<td>{trend.get('news_items', 0)}</td><td>{', '.join(trend.get('news_providers', []) or [])}</td>"
            f"<td>{trend.get('avg_evidence_polarity', 'n/a')}</td><td>{trend.get('policy_event_count', 0)}</td>"
            f"<td>{trend.get('social_net_sentiment', 'n/a')}</td>"
            f"<td>{trend.get('forecast_prob_up', 'n/a')}</td>"
            f"<td>{trend.get('forecast_expected_return_pct', 'n/a')}</td>"
            f"<td>{trend.get('summary', '')}</td></tr>"
        )
        price_rows += (
            f"<tr><td><b>{p.ticker}</b></td>"
            f"<td class='px' data-tk='{p.ticker}'>{current_price}</td>"
            f"<td class='daypx {day_class}' data-tk='{p.ticker}'>{day_change_txt}</td>"
            f"<td>{snap.get('previous_close', 'n/a') if snap else 'n/a'}</td>"
            f"<td>{snap.get('last_volume', 'n/a') if snap else 'n/a'}</td>"
            f"<td>{source}</td><td>{snap.get('retrieved_at', 'n/a') if snap else 'n/a'}</td></tr>"
        )
        provider_list = snap.get("provider_status", []) if snap else []
        provider_text = "; ".join(f"{pstat.get('provider')}={pstat.get('status')}" for pstat in provider_list) or "n/a"
        component_rows = "".join(
            f"<tr><td>{name}</td><td>{score:.0f}</td><td>{p.component_weights.get(name, 0):.2f}</td></tr>"
            for name, score in p.component_scores.items()
        )
        reasons = "".join(f"<li>{c}</li>" for c in p.catalysts[:6]) or "<li>No fresh catalysts captured.</li>"
        missing = ", ".join(p.missing_data) if p.missing_data else "None flagged"
        f = p.forecast
        forecast_html = ""
        if f and f.available and f.prob_up is not None:
            votes = ", ".join(f"{k}:{v}" for k, v in f.agent_votes.items()) or "n/a"
            short_lines = ""
            for label in ("2D", "3D"):
                sf = (p.short_horizon_forecasts or {}).get(label)
                if sf and sf.available and sf.prob_up is not None:
                    short_lines += (
                        f"<br><small><b>{label} near-term:</b> P(up) {sf.prob_up:.0%}, "
                        f"median {sf.expected_return_pct:+.1f}%, "
                        f"band [{sf.p05_return_pct:+.1f}%, {sf.p95_return_pct:+.1f}%]</small>"
                    )
            forecast_html = (
                f"<p><b>Ensemble forecast ({f.horizon_days}D):</b> P(up) {f.prob_up:.0%}, "
                f"median {f.expected_return_pct:+.1f}%, band [{f.p05_return_pct:+.1f}%, {f.p95_return_pct:+.1f}%] "
                f"{short_lines}"
                f"<br><small>method: {f.method}; trend agents: {votes}. Monte-Carlo paths are a forward "
                f"simulation of uncertainty from real returns, not observed prices.</small></p>"
            )
        policy_html = (
            f"<h4>Policy / government / Trump-admin impact</h4><ul>{''.join(f'<li>{pi}</li>' for pi in p.policy_impacts[:6])}</ul>"
            if p.policy_impacts else ""
        )
        # Deep + summarized digest of every news/evidence item and its source.
        ev_items = list(result.evidence.for_entity(p.ticker))
        bull_ct = sum(1 for e in ev_items if e.polarity > 0.1)
        bear_ct = sum(1 for e in ev_items if e.polarity < -0.1)
        news_summary_items = ""
        for e in ev_items[:10]:
            tag = "🟢" if e.polarity > 0.1 else "🔴" if e.polarity < -0.1 else "⚪"
            link = f" <a href='{e.url}' target='_blank'>source</a>" if e.url else ""
            news_summary_items += (
                f"<li>{tag} <small>[{e.source_name} · {e.source_type}]</small> {e.claim[:170]}{link}</li>"
            )
        if not news_summary_items:
            news_summary_items = "<li>No fresh news/evidence captured for this name in this run.</li>"
        news_digest_html = (
            f"<h4>News, events &amp; sources — deep digest</h4>"
            f"<p><b>Summary:</b> <small>{trend.get('summary', '')}</small><br>"
            f"<b>{len(ev_items)} evidence items</b> · 🟢 {bull_ct} bullish · 🔴 {bear_ct} bearish · "
            f"avg tone {trend.get('avg_evidence_polarity', 'n/a')} · "
            f"providers: {', '.join(trend.get('news_providers', []) or ['n/a'])}</p>"
            f"<ul>{news_summary_items}</ul>"
        )
        gc_html = ""
        if p.global_correlations:
            gc = " · ".join(f"{k} {v:+.2f}" for k, v in list(p.global_correlations.items())[:6])
            gc_html = f"<p><b>Global market linkage (60d corr):</b> {gc}</p>"
        nav_html = (
            f"<p style='background:#f0f6ff;padding:6px 8px;border-radius:6px'><b>See this ticker in every tab:</b> "
            f"<a href='#' data-goto='news' data-ticker='{p.ticker}'>News &amp; Evidence</a> · "
            f"<a href='#' data-goto='trends' data-ticker='{p.ticker}'>Trends &amp; Impact</a> · "
            f"<a href='#' data-goto='confidence' data-ticker='{p.ticker}'>Confidence Trace</a> · "
            f"<a href='#' data-goto='trade_summary' data-ticker='{p.ticker}'>Trade Summary</a> · "
            f"<a href='#' data-goto='strategy' data-ticker='{p.ticker}'>Trade Strategy</a> · "
            f"<a href='#' data-goto='options' data-ticker='{p.ticker}'>Options Edge</a> · "
            f"<a href='#' data-goto='verdicts' data-ticker='{p.ticker}'>Bull/Bear Verdict</a> · "
            f"<a href='#' data-goto='events' data-ticker='{p.ticker}'>Event Radar</a> · "
            f"<a href='/ticker/{p.ticker}' target='_blank'>raw signal JSON</a></p>"
        )
        why_cards += (
            f"<section class='panel' id='why-{p.ticker}'><h3>{p.ticker}: why this suggestion?</h3>"
            f"{nav_html}"
            f"<p><b>Final verdict:</b> {final.get('label', p.direction.value)} · "
            f"<b>Action:</b> {action} · <b>Confidence in call:</b> {p.confidence_score:.0f}/100 · "
            f"{'; '.join(final.get('reasons', []) or [])}</p>"
            f"<p><b>Direction:</b> {p.direction.value} · <b>Expected move:</b> {em_txt} · "
            f"<b>Invalidation:</b> {'; '.join(p.invalidation_conditions)}</p>"
            f"{forecast_html}"
            f"{news_digest_html}"
            f"{policy_html}"
            f"{gc_html}"
            f"<h4>Engine components (the shared deep analysis behind every tab)</h4>"
            f"<table><thead><tr><th>Component</th><th>Score</th><th>Weight</th></tr></thead>"
            f"<tbody>{component_rows}</tbody></table>"
            f"<h4>Catalysts</h4><ul>{reasons}</ul>"
            f"<p><b>Risk:</b> {p.risk.risk_level.value} ({p.risk_score:.0f}). "
            f"{'; '.join(p.risk.penalties + p.risk.warnings) or 'No major penalties.'}</p>"
            f"<p><b>Market data fallback:</b> {provider_text}</p>"
            f"<p><b>Missing/limited data:</b> {missing}</p></section>"
        )
        ev_rows = ""
        for ev in result.evidence.for_entity(p.ticker):
            url = f"<a href='{ev.url}' target='_blank'>source</a>" if ev.url else ""
            ev_rows += (
                f"<tr><td>{ev.source_name}</td><td>{ev.source_type}</td>"
                f"<td>{ev.freshness_score}</td><td>{ev.reliability_score}</td>"
                f"<td>{ev.claim[:220]}</td><td>{url}</td></tr>"
            )
        if not ev_rows:
            ev_rows = "<tr><td colspan='6'>No news/evidence captured for this ticker in this run.</td></tr>"
        news_cards += (
            f"<section class='panel' id='news-{p.ticker}'><h3>{p.ticker}: latest evidence and news</h3>"
            f"<p><a href='#' data-goto='why' data-ticker='{p.ticker}'>&larr; back to Why Suggested</a></p>"
            f"<table><thead><tr><th>Source</th><th>Type</th><th>Fresh</th><th>Reliability</th>"
            f"<th>Claim/headline</th><th>Link</th></tr></thead><tbody>{ev_rows}</tbody></table></section>"
        )
        trade = p.paper_trade
        if trade:
            act = trade.get("simulated_action", trade.get("side", ""))
            act_color = "#16a34a" if "BUY" in act else "#dc2626"
            paper_rows += (
                f"<tr><td><b>{p.ticker}</b></td>"
                f"<td style='color:{act_color};font-weight:700'>{act}</td>"
                f"<td>{trade.get('entry_price')}</td><td>{trade.get('current_price')}</td>"
                f"<td title='{trade.get('quantity_basis','')}'>{trade.get('quantity')}</td>"
                f"<td>${trade.get('notional')}</td>"
                f"<td>{trade.get('unrealized_pnl_pct'):+.2f}%</td>"
                f"<td>${trade.get('unrealized_pnl_dollars'):+.2f}</td>"
                f"<td>{trade.get('opened_at')}</td>"
                f"<td>{trade.get('actor')}</td></tr>"
            )
        for trade in p.manual_trade.get("open_trades", []):
            pnl_pct = trade.get("unrealized_pnl_pct", "n/a")
            pnl_dol = trade.get("unrealized_pnl_dollars", "n/a")
            pnl_class = _move_class(pnl_dol)
            inst = trade.get("instrument_type", "equity")
            manual_rows += (
                f"<tr><td><b>{trade.get('ticker')}</b></td><td>{inst}</td>"
                f"<td>{trade.get('underlying') or trade.get('ticker')}</td><td>{trade.get('option_expiration') or '—'}</td>"
                f"<td>{trade.get('option_type') or '—'}</td>"
                f"<td class='{'bull' if trade.get('side') == 'long' else 'bear'}'>{trade.get('side')}</td>"
                f"<td>{trade.get('entry_price')}</td><td>{trade.get('current_price', 'n/a')}</td>"
                f"<td>{trade.get('quantity')}</td><td>{trade.get('contract_multiplier', 1)}</td><td>{trade.get('notional')}</td>"
                f"<td class='{pnl_class}'>{pnl_pct}</td>"
                f"<td class='{pnl_class}'>{pnl_dol}</td>"
                f"<td>{trade.get('note', '')}</td><td>{trade.get('opened_at')}</td>"
                f"<td><button class='tab mt-edit' data-id='{trade.get('id', '')}'>edit</button> "
                f"<button class='tab mt-del' data-id='{trade.get('id', '')}' style='border-color:#dc2626;color:#dc2626'>delete</button></td></tr>"
            )
    if not paper_rows:
        paper_rows = "<tr><td colspan='10'>No simulated test trades opened because no directional, non-blocked signals were available.</td></tr>"
    if not manual_rows:
        manual_rows = "<tr><td colspan='16'>No manual trades marked yet. Add one below, or use Add trade from Overview/Options Edge to capture the current displayed price.</td></tr>"
    validation_rows = "".join(
        f"<tr><td>{name}</td><td>{status}</td><td>{note}</td></tr>"
        for name, status, note in [
            ("Watchlist-only analysis", "Implemented", "STRICT_WATCHLIST_ONLY defaults to true; ad-hoc tickers are ignored unless disabled."),
            ("Current market price", "Implemented", "Each prediction carries current/previous price, day change, volume, winning provider, retrieved time."),
            ("Parallel refresh + analysis", "Implemented", "Jobs fan source groups out in parallel, /prices/refresh fetches watchlist prices concurrently, and the prediction pipeline analyzes focused tickers with parallel workers."),
            ("Live price cadence", "Implemented", "Dashboard live prices auto-refresh every 10 minutes while open; Windows refresh/analyze tasks run grouped refresh + analysis every 2 hours."),
            ("Market-data fallback", "Implemented", "Provider chain is yfinance -> Finnhub -> Tiingo -> Alpha Vantage -> Stooq -> local cache; no synthetic runtime prices are used."),
            ("Trump/admin policy monitoring", "Implemented", "Government connector follows White House/Federal Register/GDELT policy terms including Trump, executive orders, tariffs, export controls, DOJ/FTC/FDA/DoD."),
            ("Why suggested", "Implemented", "Dashboard shows component scores, weights, ensemble forecast, catalysts, risk, invalidation, trend impact, and missing data."),
            ("Trends and news impact", "Implemented", "Trends tab merges price move, news count/providers, evidence polarity, social signal, forecast, and policy links."),
            ("Sortable tables", "Implemented", "Every dashboard table header can be clicked to sort ascending/descending across all tabs."),
            ("Confidence = buy/sell conviction", "Implemented", "Confidence now means conviction in an actionable buy/sell. Neutral/avoid are capped low so a 'no edge' call can never read 90; high confidence requires a clear directional lean plus good data."),
            ("Confidence trace links + cross-tab nav", "Implemented", "Confidence Traces shows the call (buy/sell/no-trade), conviction %, data quality %, and links to signal JSON, evidence, and the same ticker in other tabs."),
            ("Short-term options edge + algorithm", "Implemented", "Options Edge picks short/medium-dated expiries with a default 5-DTE minimum, shows DTE, ATM strike, defined-risk spread strikes from the 1-sigma move, an algorithmic confluence score (0-5), put/call, IV, OI."),
            ("Trade summary tab", "Implemented", "Best-first compact trade-plan summary shows stock-only plans without option clutter; option-qualified plans include expiry, DTE, contract, strike, entry/stop/exit, liquidity, IV, and Greeks context."),
            ("Trade strategy tab", "Implemented", "Trade Strategy turns the shared prediction/options analysis into a concise research plan: current price, target days, target price, stop loss, option expiry, contract, option stop, and option exit. Live price refresh recalculates target/stop cells in-place."),
            ("One shared deep analysis", "Implemented", "Every tab (overview, why, news, trends, confidence, options, verdicts, events, themes) is a different view of the same PredictionResult — not a separate analysis."),
            ("Bullish and bearish final verdict", "Implemented", "Bull/Bear Verdicts tab separates long research candidates, short/put research candidates, wait-only names, and risk-blocked setups."),
            ("SNDK-style event detection", "Implemented", "Event Radar tab flags abnormal acceleration, volume expansion, catalyst density, exhaustion risk, and drawdown from recent highs."),
            ("Paper trade clarity", "Implemented", "Paper Trades tab states the actor is EagleSignal simulated paper ledger, not insider/company buying; quantity is fixed-notional fractional shares."),
            ("Manual trade journal", "Implemented", "Manual Trades tab lets you enter, edit, delete, and auto-add rows from Overview/Options Edge using the current displayed entry price."),
            ("Latest news/evidence", "Implemented", "Multi-source merge (NewsAPI + GDELT + yfinance + StockTwits), deduped, with SEC evidence; X/Twitter remains key-gated."),
            ("Social sentiment", "Implemented", "StockTwits public bull/bear stream, capped contribution so a viral post cannot dominate."),
            ("Ensemble forecast", "Implemented", "Monte-Carlo bands + trend-agent votes (turtle/MA/momentum) from real history; direction/magnitude/uncertainty separated."),
            ("Dummy live trade", "Implemented", "Paper ledger marks positions against latest fetched price; no broker order is sent."),
            ("Options analysis", "Implemented+", "Multi-expiry yfinance + CBOE fallback, put/call, IV, expected move, IV/RV, IV Rank when enough snapshots exist, Greeks, skew, term slope, chain-derived UOA/OI-change, 5-DTE floor, and spread/earnings gates. Paid unusual-flow/gamma vendors and full every-strike history remain future upgrades."),
            ("Government/macro", "Implemented", "FRED + keyless Treasury FiscalData, Federal Register, GDELT policy news, optional BLS; folded into regime + evidence."),
            ("Feature/label store", "Implemented", "Successful scans now write point-in-time feature_snapshots.jsonl rows; /reliability/labels joins them to matured forward labels without lookahead."),
            ("Option premium scorecard", "Implemented", "/reliability/options-scorecard measures option-premium P/L from later stored marks for the same contract; rows stay pending until future scans exist."),
            ("Confidence calibration", "Implemented", "Confidence traces preserve raw confidence and apply historical bucket calibration only when enough matured outcomes exist."),
            ("Backtesting", "Partial+", "Technical walk-forward backtest exists; feature/label store and calibration endpoints are live, while full GPU ML and paid institutional options-flow calibration remain future work."),
        ]
    )
    gm = getattr(result, "global_markets", None)
    global_rows = ""
    global_regime = "Global market data unavailable."
    if gm is not None and getattr(gm, "available", False):
        global_regime = gm.regime_note
        for gi in gm.indexes.values():
            chg = gi.day_change_pct
            color = "#16a34a" if (chg or 0) > 0 else "#dc2626" if (chg or 0) < 0 else "#6b7280"
            chg_txt = f"{chg:+.2f}%" if chg is not None else "n/a"
            global_rows += (
                f"<tr><td>{gi.region}</td><td><b>{gi.name}</b></td><td>{gi.symbol}</td>"
                f"<td>{gi.last}</td><td style='color:{color};font-weight:600'>{chg_txt}</td></tr>"
            )
    if not global_rows:
        global_rows = "<tr><td colspan='5'>Global index data unavailable in this run.</td></tr>"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{__product__} Dashboard</title>
<style>
 body{{font-family:system-ui,Segoe UI,Arial;margin:0;background:#f6f7f9;color:#111827}}
 header{{padding:20px 28px;background:#111827;color:#f9fafb}}
 h1{{margin:0 0 4px}} .meta{{color:#cbd5e1}}
 nav{{display:flex;gap:6px;flex-wrap:wrap;padding:12px 28px;background:#ffffff;border-bottom:1px solid #d1d5db;position:sticky;top:0}}
 button.tab{{border:1px solid #cbd5e1;background:#f8fafc;padding:8px 12px;border-radius:6px;cursor:pointer}}
 button.tab.active{{background:#111827;color:#fff;border-color:#111827}}
 button.rbtn{{border:1px solid #2563eb;background:#2563eb;color:#fff;padding:8px 10px;border-radius:6px;cursor:pointer;font-size:13px}}
 button.rbtn:hover{{background:#1d4ed8}} #refreshStatus,#dataAsOf{{align-self:center}}
  main{{padding:20px 28px}} .view{{display:none}} .view.active{{display:block}}
  table{{border-collapse:collapse;width:100%;background:#fff}} th,td{{padding:8px 10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}
  th{{background:#eef2f7;font-size:13px;cursor:pointer;user-select:none}} th.sorted-asc::after{{content:" ▲"}} th.sorted-desc::after{{content:" ▼"}} .panel{{background:#fff;border:1px solid #d8dee8;border-radius:8px;padding:16px;margin:0 0 16px}}
  .up,.profit,.bull{{color:#16a34a;font-weight:700}} .down,.loss,.bear{{color:#dc2626;font-weight:700}} .neutral{{color:#6b7280;font-weight:700}} .warn{{color:#f59e0b;font-weight:700}}
  .signal-add-trade{{white-space:nowrap;font-size:12px;padding:6px 9px}}
  .opt-toggle,.summary-toggle{{border:0;background:transparent;color:#1d4ed8;font-weight:800;cursor:pointer;padding:0;font:inherit}}
  .opt-child.collapsed,.summary-child.collapsed{{display:none}}
  .opt-child td:first-child,.summary-child td:first-child{{padding-left:26px;background:#f8fafc}}
  .summary-child td{{background:#fbfdff}}
  .opt-why td{{background:#f8fbff;border-top:0;font-size:12px;color:#334155;line-height:1.55;padding:4px 12px 12px}}
  .opt-why.opt-child td{{background:#f3f7fc}}
  .verdict-badge{{font-weight:800;font-size:13px;white-space:nowrap}}
  .opt-data td{{border-bottom:0}}
  .disc{{margin-top:20px;color:#92400e;font-size:13px}} a{{color:#1d4ed8}}
</style></head><body>
<header><h1>{__product__}</h1>
<div class="meta">Generated {now} · strategy {result.strategy} · horizon {result.horizon}</div></header>
<nav>
<button class="tab active" data-tab="overview">Overview</button>
<button class="tab" data-tab="prices">Current Prices</button>
<button class="tab" data-tab="why">Why Suggested</button>
<button class="tab" data-tab="news">News & Evidence</button>
<button class="tab" data-tab="trends">Trends & Impact</button>
<button class="tab" data-tab="confidence">Confidence Traces</button>
<button class="tab" data-tab="trade_summary">Trade Summary</button>
<button class="tab" data-tab="strategy">Trade Strategy</button>
<button class="tab" data-tab="options">Options Edge</button>
<button class="tab" data-tab="verdicts">Bull/Bear Verdicts</button>
<button class="tab" data-tab="events">Event Radar</button>
<button class="tab" data-tab="markets">Global Markets</button>
<button class="tab" data-tab="advisor">AI Advisor</button>
<button class="tab" data-tab="paper">Paper Trades</button>
<button class="tab" data-tab="manual">Manual Trades</button>
<button class="tab" data-tab="jobs">Jobs</button>
<button class="tab" data-tab="themes">Theme Watchlists</button>
<button class="tab" data-tab="validation">MD Validation</button>
<span style="flex:1 1 auto"></span>
<span id="marketClock" title="US equities regular session (NYSE/Nasdaq), times in America/New_York. Excludes 2026 market holidays." style="align-self:center;font-size:12px;font-weight:700;padding:4px 10px;border-radius:6px;background:#374151;color:#e5e7eb">⏳ Market…</span>
<span id="dataAsOf" class="meta" style="color:#374151;font-size:12px"></span>
<button class="rbtn" id="reloadKeep" title="Reload this page and stay on the current tab">↻ Reload</button>
<button class="rbtn" id="refreshPrices" title="Fetch the latest live prices now (no full re-scan)">⟳ Live prices</button>
<button class="rbtn" id="rescanLive" title="Run a full live re-scan of all data (takes a few minutes)">▶ Re-scan</button>
<span id="refreshStatus" style="font-size:12px;color:#374151"></span>
</nav>
<main>
<section id="overview" class="view active">
<div class="panel" style="background:#f0f6ff">
<b>How to read this table</b> — research only, not financial advice. <b>Every tab below is one shared deep analysis</b> of the same signal — different views, not separate models.
<ul style="margin:6px 0 0;font-size:13px">
<li><b>Direction</b> = what to do: <b>bullish</b> = research a BUY/long · <b>bearish</b> = research a SELL/short or put · <b>neutral</b> = no edge, <i>do not trade</i> · <b>avoid</b> = risk blocked it.</li>
<li><b>Opportunity (0–100)</b>: how attractive the setup looks. 50 = neutral, higher = more bullish edge, lower = more bearish.</li>
<li><b>Confidence (0–100)</b>: <b>conviction in the buy/sell call</b> (data quality × how far from neutral). <b>Neutral is capped low on purpose</b> — high confidence is only possible for a clear buy or sell. Not a profit guarantee.</li>
<li><b>Risk (0–100)</b>: how dangerous — higher is riskier (liquidity, conflicting signals, high IV, stale/synthetic data).</li>
<li><b>Severity</b>: alert priority — P0 urgent · P1 strong · P2 watch · P3 info only.</li>
<li><b>Current</b>: latest real market price · <b>Day</b>: % change vs previous close.</li>
<li><b>Trend &amp; news impact</b>: today's move + news count/tone + social + forecast P(up) + any government / Trump-admin policy links to this name.</li>
<li><b>How to act</b>: trade only names where Direction is bullish/bearish <i>and</i> Confidence clears your threshold and Risk is acceptable. Skip neutral.</li>
</ul></div>
<div class="panel"><table><thead><tr>
<th>#</th><th>Ticker</th><th>Type</th>
<th title="bullish / neutral / bearish / avoid">Direction</th>
<th title="How attractive the setup is (0-100, 50=neutral)">Opportunity</th>
<th title="Conviction in the BUY/SELL call (0-100). Neutral is capped low on purpose. Not a profit probability">Confidence</th>
<th title="How dangerous the setup is (0-100; higher = riskier)">Risk</th>
<th title="Alert priority: P0 urgent, P1 strong, P2 watch, P3 info">Severity</th>
<th title="Latest real market price">Current price</th>
<th title="Percent change vs previous close">Day %</th>
<th title="Today's move, news volume/tone, social, forecast tilt, and policy links">Trend &amp; news impact</th>
<th title="Create a Manual Trade row using the current displayed entry price">Manual</th>
</tr></thead><tbody>{rows}</tbody></table></div></section>
<section id="prices" class="view"><div class="panel"><table><thead><tr><th>Ticker</th><th>Current</th><th>Day change</th><th>Previous close</th><th>Volume</th><th>Source</th><th>Retrieved</th></tr></thead><tbody>{price_rows}</tbody></table></div></section>
<section id="why" class="view">{why_cards}</section>
<section id="news" class="view">{news_cards}</section>
<section id="trends" class="view"><div class="panel"><h3>Trends & News Impact</h3><table><thead><tr><th>Ticker</th><th>Day</th><th>News</th><th>Providers</th><th>Evidence polarity</th><th>Policy links</th><th>Social</th><th>P(up)</th><th>Forecast %</th><th>Summary</th></tr></thead><tbody>{trend_rows}</tbody></table></div></section>
<section id="confidence" class="view"><div class="panel"><h3>Confidence Traces — why we trust each BUY/SELL call</h3>
<p><b>Confidence answers: "how convinced are we in the buy or sell?"</b> It is <b>data quality × directional conviction</b>. The <b>Call</b> column says whether the confidence is for a BUY (long), a SELL (short/put), or <b>NO TRADE</b> (neutral — no edge, so confidence is low by design). It is not a profit guarantee. Click a header to sort; use the links to inspect raw signal JSON, source evidence, and jump to the Why/News tabs.</p>
<table><thead><tr><th>Ticker</th><th title="Is this confidence for a buy, a sell, or no trade?">Call</th><th title="Conviction in the buy/sell call (0-100)">Confidence</th><th title="Raw confidence and historical bucket calibration">Calibration</th><th title="How far the setup is from neutral (0=neutral, 100=clear buy/sell)">Conviction %</th><th title="Data coverage + engine agreement">Data quality %</th><th title="Engine agreement only">Agreement %</th><th>Evidence count</th><th>Missing engines</th><th>Trace links</th></tr></thead><tbody>{confidence_rows}</tbody></table></div></section>
<section id="trade_summary" class="view"><div class="panel"><h3>Trade Summary — best plans first</h3>
<p><b>Research only, not financial advice.</b> This compact view is sorted with the strongest actionable setups at the top. Ticker rows are grouped: click a ticker's expiry count to expand practical option ideas. Option rows are limited to <b>DTE ≥ {min_option_dte}</b> and <b>premium ≤ ${MAX_STRATEGY_OPTION_PRICE:.0f}</b>, sorted best-first, with expiry, DTE, contract, strike, option entry/stop/exit, confidence/readiness/risk/liquidity/IV/Greeks context, and an <b>Add option</b> button. Stock-only rows appear when no lower-priced qualifying option is available.</p>
<table id="tradeSummaryTable"><thead><tr>
<th>Ticker</th><th>Bias</th><th>Instrument</th><th>Opp/Conf/Risk</th><th>Current price</th><th>Target price</th><th>Target days</th><th>Stop loss</th><th>Exit price</th><th>Option details</th><th>Summary</th><th>Trade</th>
</tr></thead><tbody>{strategy_summary_rows}</tbody></table>
<p class="disc">Live-price refresh recalculates current/target/stop/exit in this table and the detailed Trade Strategy table.</p></div></section>
<section id="strategy" class="view"><div class="panel"><h3>Trade Strategy — target, stop, option expiry, and exit plan</h3>
<p><b>Research only, not financial advice.</b> This tab converts the same dashboard analysis into a trade-plan view. It uses the latest signal price, 3D forecast when available, minimum {min_option_dte}-DTE options with quoted premium at or below ${MAX_STRATEGY_OPTION_PRICE:.0f}, risk/readiness gates, exact option contract liquidity, IV risk, and confidence trace. Favor <b>defined-risk spreads</b> when IV is elevated or the gate says spread only.</p>
<table id="strategyTable"><thead><tr>
<th>Ticker</th><th>Bias</th><th>Strategy action</th><th>Opp/Conf/Risk</th><th>Risk level</th>
<th title="Current underlying price from the latest report/live refresh">Current</th>
<th title="Probability of the selected side from the near-term forecast">P(side)</th>
<th title="Expected return used to compute target">Forecast %</th>
<th title="Number of days for the target price">Target days</th>
<th title="Underlying target price">Target price</th>
<th title="Underlying invalidation/stop level">Stop loss</th>
<th title="Underlying exit price for this plan">Exit price</th>
<th>Expiry</th><th>DTE</th><th>Option contract</th><th>Strike</th>
<th>Option entry</th><th>Option stop</th><th>Option exit</th>
<th>Opt conf</th><th>Readiness</th><th>Gate</th><th>Spread %</th><th>Vol/OI</th><th>IV Rank</th><th>Delta/Theta</th><th>Why</th><th>Trade</th>
</tr></thead><tbody>{strategy_rows}</tbody></table>
<p class="disc">Targets are model-derived research levels, not guarantees. Option exit is estimated from premium plus delta-adjusted underlying move; verify live bid/ask before any real order.</p></div></section>
<section id="options" class="view"><div class="panel"><h3>Short-Term Options Edge <span style="font-weight:400;font-size:13px">(multi-source live chains, top 3 expirations, research only)</span></h3>
<p>For each name we pull <b>live option chains from yfinance with a keyless CBOE delayed-quotes fallback</b> (the <i>source</i> is shown under the ticker), score every short/medium-dated expiration with a <b>default 5-DTE minimum</b>, and surface the <b>3 highest-confidence expirations</b>. The call is stated plainly: <b style="color:#16a34a">BUY CALL</b> = we expect the stock to go <b>UP ▲</b>; <b style="color:#dc2626">BUY PUT</b> = we expect it to go <b>DOWN ▼</b>; <b style="color:#f59e0b">NO TRADE</b> = neutral, no edge. The <b>Options Risk Gate</b> now deep-scores direction, data quality, algo confluence, exact-contract liquidity, DTE, IV/realized vol, Greeks/theta, flow, premium cost, and bid/ask spread. Direct <b>Add option</b> appears only for <b>high</b> gate rows. Click a ticker to expand/collapse its ranked expiries; header sorting keeps each ticker and its expiries grouped together.</p>
<div class="panel" style="background:#f0f6ff;font-size:13px;line-height:1.6">
<b>Key metrics, in plain terms:</b><br>
<b>IV</b> (implied volatility) — the market's expected price swing. <b>High IV = expensive options + IV-crush risk</b> after the event; prefer defined-risk spreads.<br>
<b>C/P Vol</b> (call volume / put volume) — how many call vs put contracts traded today. <b>More calls = bullish flow, more puts = bearish/hedging flow.</b><br>
<b>OI</b> (open interest) — total contracts currently outstanding. <b>Higher OI = more liquidity</b> (tighter spreads, easier to exit); very low OI = research/paper only.<br>
<b>P/C</b> (put/call ratio) — puts ÷ calls by volume. <b>&lt;1 = call-heavy (bullish positioning), &gt;1 = put-heavy (bearish/hedging).</b>
<br><b>Confidence (0–100)</b> is the <b>single consolidated score</b> — it already blends direction, data quality, algo confluence, exact-contract liquidity, DTE, IV vs realized vol, Greeks/theta, options flow, bid/ask spread, IV-Rank, and event/earnings risk. You do not need to read every column; Confidence + the Verdict below summarise them.
<br><b>Readiness / Gate</b> — tradeability filters. <b>Spread %</b> is bid/ask width; wide spreads can erase option gains. <b>Greeks</b>: Δ delta, Θ daily theta, V vega per 1 IV point.
<br><b>Skew/Term</b> = ATM put IV minus call IV, then next-expiry IV minus current-expiry IV. <b>UOA/OI Δ</b> = chain-derived unusual activity score and exact-contract OI change vs the prior stored scan; it is not a paid unusual-flow feed.
<br><b>Each entry is now TWO lines:</b> line 1 = the numbers + the <b>Add trade</b> button (it drops the idea into the <b>Manual Trades</b> tab); line 2 = the plain <b>Verdict</b>, the recommended <b>structure</b>, and the full <b>Why (evidence)</b>.
<br><b>What the Verdict means:</b>
 <b style="color:#16a34a">✅ TRADEABLE</b> = clears the gate, the listed option is fine to trade ·
 <b style="color:#b45309">⚠️ TRADE AS A SPREAD</b> = <b>do NOT buy the naked option</b> (rich IV / earnings / wide spread would bleed it) — use the defined-risk <i>spread</i> shown on line 2 instead ·
 <b style="color:#dc2626">📝 PAPER ONLY</b> = track it, don't risk real money (thin liquidity / very short DTE / high IV-crush) ·
 <b style="color:#6b7280">🚫 NO TRADE</b> = no directional edge.
</div>
<table id="optionsTable"><thead><tr><th>Ticker / source</th><th title="Current underlying market price">Underlying current</th><th title="Option expiration date">Expiry</th><th title="Days to expiry">DTE</th><th title="Plain call: buy a call, buy a put, or stay out">Action</th><th title="Expected direction of the underlying">Trend</th><th title="Confidence in this options call (0-100)">Confidence</th><th title="High/medium/low/paper-only based on confidence, liquidity, risk, and spread">Readiness</th><th title="Final execution gate: high / spread only / paper only / no trade">Gate</th><th title="Contract quality from liquidity, DTE, IV, flow, and spread">Opt quality</th><th title="Reference option contract for the action">Contract</th><th title="Latest option premium from the chain">Option price</th><th title="Bid / ask from the chain when available">Bid / Ask</th><th title="Bid/ask width as % of midpoint">Spread %</th><th title="Exact contract volume / exact contract open interest">Exact Vol/OI</th><th title="Black-Scholes approximation: delta, daily theta, vega per 1 IV point">Greeks</th><th title="Price needed at expiration to break even">Breakeven</th><th title="Premium as percent of underlying spot">Premium % spot</th><th title="Implied volatility divided by 20-day realized volatility">IV/RV</th><th title="IV Rank / Percentile from accumulated point-in-time snapshots">IV Rank</th><th title="ATM put-call IV skew / next-expiry term slope, in IV percentage points">Skew/Term</th><th title="Chain-derived unusual activity score / exact-contract OI change since prior stored scan">UOA/OI Δ</th><th title="Option contract multiplier">Lot</th><th title="At-the-money strike">ATM</th><th title="Defined-risk vertical spread (long/short)">Spread</th><th title="Average implied volatility">IV</th><th title="Total option volume for this expiry">Volume</th><th title="Call volume / put volume">C/P Vol</th><th title="Total open interest (liquidity)">OI</th><th title="Put/Call volume ratio">P/C</th><th title="Add this option idea to the Manual Trades tab">Trade</th></tr></thead><tbody>{options_rows}</tbody></table>
<p class="disc">Live/delayed data only — no fabricated option prices. Add option records use premium × contracts × lot size (usually 100). Always verify bid/ask, spread width, Greeks, IV rank, and earnings date before any real trade.</p></div></section>
<section id="verdicts" class="view"><div class="panel"><h3>Bullish and Bearish Research Verdicts</h3><table><thead><tr><th>Ticker</th><th>Final verdict</th><th>Research action</th><th>Opp</th><th>Conf</th><th>Risk</th><th>Why</th></tr></thead><tbody>{verdict_rows}</tbody></table></div></section>
<section id="events" class="view"><div class="panel"><h3>Event Radar — Breakout and Exhaustion Watch</h3><p>Designed to catch SNDK-style event moves early and to flag when a crowded winner may be turning bearish.</p><table><thead><tr><th>Ticker</th><th>Radar verdict</th><th>Breakout</th><th>Exhaustion</th><th>20D %</th><th>60D %</th><th>252D %</th><th>Volume x20D</th><th>Bullish clues</th><th>Bearish clues</th></tr></thead><tbody>{event_rows}</tbody></table></div></section>
<section id="markets" class="view"><div class="panel"><h3>Global Markets — US · Europe · Asia</h3>
<p>{global_regime}</p>
<table><thead><tr><th>Region</th><th>Index</th><th>Symbol</th><th>Last</th><th>Day change</th></tr></thead><tbody>{global_rows}</tbody></table>
<p class="disc">Index levels via the real-data provider chain. Per-ticker rolling correlations to these indexes appear under "Why Suggested".</p></div></section>
<section id="advisor" class="view"><div class="panel"><h3>AI Investment Advisor <span style="font-weight:400;font-size:13px">(research only — not financial advice)</span></h3>
<p>Ask about the latest signals, or paste holdings to review (e.g. <code>AAPL:10, MSFT:5</code>).</p>
<div><textarea id="advisorMsg" rows="2" style="width:100%" placeholder="What should I buy? Why is NVDA neutral? Review my portfolio."></textarea></div>
<div style="margin:6px 0"><input id="advisorPortfolio" style="width:60%" placeholder="Optional holdings: AAPL:10, MSFT:5">
<button id="advisorSend" class="tab">Ask Advisor</button><span id="advisorStatus"></span></div>
<pre id="advisorAnswer" style="white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:12px;min-height:60px"></pre></div></section>
<section id="paper" class="view"><div class="panel"><h3>System Paper Trades — EagleSignal grading its OWN calls</h3>
<div class="panel" style="background:#f0f6ff;font-size:13px">
<b>What is this?</b> When the model issues a bullish or bearish call, it opens a <b>hypothetical (paper) position against itself</b> so you can see whether its research actually makes money over time. <b>This is the system testing itself.</b><br>
It is <b>NOT</b>: a company buying its own stock · <b>NOT</b> insider buying · <b>NOT</b> another investor's trade · <b>NOT</b> a real broker order.<br>
<b>Simulated action</b>: <span style="color:#16a34a;font-weight:700">SIMULATED BUY</span> = the model went long to test a bullish call · <span style="color:#dc2626;font-weight:700">SIMULATED SELL/SHORT</span> = the model shorted to test a bearish call.<br>
<b>Qty is fractional</b> because the ledger always risks a fixed <b>$1,000 test notional</b> ÷ entry price (hover the Qty cell for the exact math). It is not "1 share" — it is whatever $1,000 buys.
</div>
<table><thead><tr><th>Ticker</th><th title="Did the system simulate a buy or a sell to test its call?">Simulated action</th><th>Entry</th><th>Current</th><th title="Fractional: $1,000 test notional / entry price">Qty</th><th>Notional</th><th>P/L %</th><th>P/L $</th><th>Opened</th><th>By</th></tr></thead><tbody>{paper_rows}</tbody></table></div><p class="disc">Simulated self-test trades only. No broker order is ever created.</p></section>
<section id="manual" class="view"><div class="panel"><h3>Manual Trade Journal</h3><form id="manualTradeForm">
<input type="hidden" name="edit_id" id="manualEditId" value="">
<label>Ticker <input name="ticker" required placeholder="NVDA"></label>
<label>Side <select name="side"><option value="long">long</option><option value="short">short</option></select></label>
<label>Entry price <input name="entry_price" type="number" step="0.0001" min="0.0001" required></label>
<label>Quantity <input name="quantity" type="number" step="0.000001" min="0.000001" required></label>
<label>Note <input name="note" placeholder="Why I entered"></label>
<button type="submit" class="tab" id="manualSubmitBtn">Add Trade</button>
<button type="button" class="tab" id="manualCancelBtn" style="display:none">Cancel edit</button>
<span id="manualTradeStatus"></span></form>
<table><thead><tr><th>Ticker / Contract</th><th>Instrument</th><th>Underlying</th><th>Expiry</th><th>Option</th><th>Side</th><th>Entry</th><th>Current</th><th>Qty</th><th>Lot</th><th>Notional</th><th>P/L %</th><th>P/L $</th><th>Note</th><th>Opened</th><th>Actions</th></tr></thead><tbody id="manualTradeRows">{manual_rows}</tbody></table></div><p class="disc">Add, <b>edit</b>, or <b>delete</b> trades here — for tracking your own analysis only. Option rows track the exact contract/expiry premium; notional and P/L use premium × contracts × lot size. Edit updates the entry/quantity and re-marks live P/L; delete removes the row. No broker order is ever sent.</p></section>
<section id="jobs" class="view">
<div class="panel"><h3>Parallel Live-Data Refresh Jobs</h3>
<p>Each source group is its own <b>fast, independent job</b>. Click <b>Generate from newest data</b> to fan every group out <b>in parallel threads</b>, then re-run the full prediction pipeline and write a fresh dashboard. Use <b>Refresh ALL</b> when you only want to update the source cache/status table. Manual/reference, paid, and API-gated sources are still listed so the trace shows what was considered, skipped, or needs keys.</p>
<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
<button id="generateFreshDashboard" class="rbtn" style="font-size:14px;padding:10px 16px">▶ Generate from newest data</button>
<button id="refreshAllJobs" class="tab" style="font-size:14px;padding:10px 16px">⟳ Refresh ALL source cache</button>
<label style="font-size:13px"><input type="checkbox" id="refreshAnalyze" checked> + analyze (re-run predictions)</label>
<button id="refreshStatusBtn" class="tab">Refresh status table</button>
<span id="refreshAllStatus" style="font-size:13px;color:#374151"></span>
</div>
<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
<button class="tab catbtn" data-cat="market">Market data</button>
<button class="tab catbtn" data-cat="news">News</button>
<button class="tab catbtn" data-cat="social">Sentiment</button>
<button class="tab catbtn" data-cat="xtwitter">X / Twitter</button>
<button class="tab catbtn" data-cat="government">Government</button>
<button class="tab catbtn" data-cat="trump">Trump / Admin</button>
<button class="tab catbtn" data-cat="political">Political / Geopolitical</button>
<button class="tab catbtn" data-cat="macro">Macro</button>
<button class="tab catbtn" data-cat="global">Global markets</button>
<button class="tab catbtn" data-cat="official_economic">Official economic</button>
<button class="tab catbtn" data-cat="company_events">Company events</button>
<button class="tab catbtn" data-cat="options_volatility">Options / Volatility</button>
<button class="tab catbtn" data-cat="reference_dashboards">Dashboards / News refs</button>
<button class="tab catbtn" data-cat="automation_apis">Automation APIs</button>
<button class="tab catbtn" data-cat="paid_platforms">Paid platforms</button>
<button class="tab catbtn" data-cat="source_registry">Source registry</button>
</div>
<table><thead><tr><th>Source / job</th><th>Status</th><th>Last refresh</th><th>Elapsed</th><th>Summary</th><th>Run</th></tr></thead>
<tbody id="refreshTableBody"><tr><td colspan="6">Click <b>Refresh status table</b> or run a refresh to populate.</td></tr></tbody></table>
<p class="disc">Jobs run read-only and concurrently. Browser automation refreshes live prices every 10 minutes. The Windows scheduled task refreshes all source groups, re-analyzes, and writes fresh reports every 2 hours when the laptop is on. "+ analyze" then re-runs the full prediction pipeline and writes fresh reports.</p>
</div>
<div class="panel"><h3>Full Collection Job (single end-to-end scan)</h3>
<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
<button id="jobRun" class="tab">Run Now</button>
<button id="jobStatusRefresh" class="tab">Refresh Status</button>
<button id="tuneRun" class="tab">Run Weekly Retune</button>
<button id="snapshotStatusRefresh" class="tab">Snapshot Status</button>
<button id="scorecardRefresh" class="tab">Reliability Scorecard</button>
<button id="optionsScorecardRefresh" class="tab">Options P/L Scorecard</button>
<button id="calibrationRefresh" class="tab">Confidence Calibration</button>
<button id="labelsRefresh" class="tab">Feature Labels</button>
<span id="jobRunStatus"></span></div>
<pre id="jobStatus" style="white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:12px;min-height:80px"></pre>
<p class="disc">Install the Windows scheduled tasks with <code>scripts/install_windows_tasks_split.ps1</code> (run once from PowerShell). It registers small independent jobs: an 08:35 full morning scan, a 20:35 full evening scan, a grouped parallel refresh + analysis every 2 hours, and a weekly ADR-002 retune. A single-task installer (<code>scripts/install_windows_task.ps1</code>) is also available.</p>
</div></section>
<section id="themes" class="view">{_theme_tables(result)}</section>
<section id="validation" class="view"><div class="panel"><table><thead><tr><th>MD requirement</th><th>Status</th><th>Notes</th></tr></thead><tbody>{validation_rows}</tbody></table></div></section>
<div class="disc">{__disclaimer__}</div>
</main>
<script>
function activateTab(name) {{
  const btn = document.querySelector('button.tab[data-tab="' + name + '"]');
  const view = document.getElementById(name);
  if (!btn || !view) return false;
  document.querySelectorAll('button.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  btn.classList.add('active');
  view.classList.add('active');
  try {{ localStorage.setItem('eagleTab', name); }} catch (e) {{}}
  if (history.replaceState) history.replaceState(null, '', '#' + name);
  return true;
}}
document.querySelectorAll('button.tab').forEach(btn =>
  btn.addEventListener('click', () => activateTab(btn.dataset.tab)));
// Restore the last tab on load (URL hash wins, then localStorage) so a refresh
// keeps you exactly where you were instead of snapping back to Overview.
(function restoreTab() {{
  let want = (location.hash || '').replace('#', '');
  if (!want) {{ try {{ want = localStorage.getItem('eagleTab') || ''; }} catch (e) {{}} }}
  if (want) activateTab(want);
}})();
// Cross-tab deep links: jump to the same ticker in another tab and highlight it.
document.querySelectorAll('a[data-goto]').forEach(el => el.addEventListener('click', (e) => {{
  e.preventDefault();
  const tab = el.dataset.goto, tk = el.dataset.ticker;
  const btn = document.querySelector('button.tab[data-tab="' + tab + '"]');
  if (btn) btn.click();
  if (tk) {{
    const target = document.getElementById(tab + '-' + tk);
    if (target) {{
      target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
      const old = target.style.background;
      target.style.background = '#fef9c3';
      setTimeout(() => {{ target.style.background = old; }}, 2200);
    }}
  }}
}}));
function sortTable(table, colIndex, asc) {{
  const tbody = table.tBodies[0];
  if (!tbody) return;
  const parse = (txt) => {{
    const clean = txt.replace(/[$,%]/g, '').replace(/,/g, '').trim();
    const num = Number(clean);
    return Number.isFinite(num) && clean !== '' ? num : txt.toLowerCase();
  }};
  if (table.id === 'optionsTable' || table.id === 'tradeSummaryTable') {{
    const parentClass = table.id === 'optionsTable' ? 'opt-parent' : 'summary-parent';
    const groups = [];
    let current = null;
    Array.from(tbody.rows).forEach(row => {{
      // A group starts at a parent DATA row (or any standalone row like the
      // no-chain message). Every following row — the parent's Why row and all
      // child expiry data/Why rows — attaches to the current group so the two
      // physical rows per expiry always sort and move together.
      if (row.classList.contains(parentClass) || !current) {{
        current = {{ parent: row, children: [] }};
        groups.push(current);
      }} else {{
        current.children.push(row);
      }}
    }});
    groups.sort((a, b) => {{
      const av = parse(a.parent.cells[colIndex]?.innerText || '');
      const bv = parse(b.parent.cells[colIndex]?.innerText || '');
      if (typeof av === 'number' && typeof bv === 'number') return asc ? av - bv : bv - av;
      return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    }});
    groups.forEach(g => {{
      tbody.appendChild(g.parent);
      g.children.forEach(child => tbody.appendChild(child));
    }});
    return;
  }}
  const rows = Array.from(tbody.rows);
  rows.sort((a, b) => {{
    const av = parse(a.cells[colIndex]?.innerText || '');
    const bv = parse(b.cells[colIndex]?.innerText || '');
    if (typeof av === 'number' && typeof bv === 'number') return asc ? av - bv : bv - av;
    return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
function setOptionGroup(group, expanded) {{
  document.querySelectorAll('tr.opt-child[data-option-parent="' + group + '"]').forEach(row => {{
    row.classList.toggle('collapsed', !expanded);
  }});
  document.querySelectorAll('.opt-toggle[data-option-group="' + group + '"]').forEach(btn => {{
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    const ticker = group || btn.textContent.replace(/^[-+]\\s*/, '').trim();
    btn.textContent = (expanded ? '- ' : '+ ') + ticker;
  }});
}}
document.querySelectorAll('.opt-toggle').forEach(btn => {{
  btn.addEventListener('click', (e) => {{
    e.preventDefault();
    e.stopPropagation();
    const group = btn.dataset.optionGroup;
    const expanded = btn.getAttribute('aria-expanded') !== 'true';
    setOptionGroup(group, expanded);
  }});
}});
function setSummaryGroup(group, expanded) {{
  document.querySelectorAll('tr.summary-child[data-summary-parent="' + group + '"]').forEach(row => {{
    row.classList.toggle('collapsed', !expanded);
  }});
  document.querySelectorAll('.summary-toggle[data-summary-group="' + group + '"]').forEach(btn => {{
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    const count = (btn.textContent.match(/\\d+/) || ['0'])[0];
    btn.textContent = (expanded ? '- ' : '+ ') + count + ' tradeable expiries';
  }});
}}
document.querySelectorAll('.summary-toggle').forEach(btn => {{
  btn.addEventListener('click', (e) => {{
    e.preventDefault();
    e.stopPropagation();
    const group = btn.dataset.summaryGroup;
    const expanded = btn.getAttribute('aria-expanded') !== 'true';
    setSummaryGroup(group, expanded);
  }});
}});
document.querySelectorAll('table').forEach(table => {{
  table.querySelectorAll('th').forEach((th, idx) => {{
    th.title = th.title || 'Click to sort ascending/descending';
    th.addEventListener('click', () => {{
      const asc = th.dataset.sortDir !== 'asc';
      table.querySelectorAll('th').forEach(h => {{ h.classList.remove('sorted-asc', 'sorted-desc'); h.dataset.sortDir = ''; }});
      th.dataset.sortDir = asc ? 'asc' : 'desc';
      th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
      sortTable(table, idx, asc);
    }});
  }});
}});
function valueClass(v) {{
  const n = Number(String(v ?? '').replace(/[$,%]/g, '').replace(/,/g, '').trim());
  if (!Number.isFinite(n)) return 'neutral';
  return n > 0 ? 'profit' : n < 0 ? 'loss' : 'neutral';
}}
function fmtPct(v) {{
  const n = Number(v);
  return Number.isFinite(n) ? (n >= 0 ? '+' : '') + n.toFixed(2) + '%' : 'n/a';
}}
function fmtMoney(v) {{
  const n = Number(v);
  return Number.isFinite(n) ? '$' + n.toFixed(2) : 'n/a';
}}
function fmtPlainMoney(v) {{
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : '—';
}}
function updateStrategyRows(prices) {{
  document.querySelectorAll('tr.strategy-row').forEach(row => {{
    const currentCell = row.querySelector('[data-role="current"]');
    const ticker = currentCell?.dataset.tk;
    const q = prices && ticker ? prices[ticker] : null;
    const price = q && q.current_price != null ? Number(q.current_price) : Number((currentCell?.textContent || '').replace(/[$,]/g, ''));
    const er = Number(row.dataset.er);
    const stopPct = Number(row.dataset.stopPct);
    const side = row.dataset.side || 'long';
    const optionEntry = Number(row.dataset.optionEntry);
    const delta = Number(row.dataset.delta);
    if (!Number.isFinite(price)) return;
    if (currentCell) currentCell.textContent = fmtPlainMoney(price);
    if (Number.isFinite(er)) {{
      const target = price * (1 + er / 100);
      const stop = side === 'short' ? price * (1 + stopPct) : price * (1 - stopPct);
      const targetCell = row.querySelector('[data-role="target"]');
      const stopCell = row.querySelector('[data-role="stop"]');
      const exitCell = row.querySelector('[data-role="exit"]');
      if (targetCell) targetCell.textContent = fmtPlainMoney(target);
      if (stopCell) stopCell.textContent = fmtPlainMoney(stop);
      if (exitCell) exitCell.textContent = fmtPlainMoney(target);
      if (Number.isFinite(optionEntry) && Number.isFinite(delta)) {{
        const optExit = optionEntry + Math.abs(delta) * Math.abs(target - price);
        const optStop = Math.max(0.01, optionEntry * 0.65);
        const optExitCell = row.querySelector('[data-role="option-exit"]');
        const optStopCell = row.querySelector('[data-role="option-stop"]');
        if (optExitCell) optExitCell.textContent = fmtPlainMoney(optExit);
        if (optStopCell) optStopCell.textContent = fmtPlainMoney(optStop);
      }}
    }}
  }});
}}
window.__manualTrades = [];
async function refreshManualTrades() {{
  try {{
    const resp = await fetch('/manual-trades');
    if (!resp.ok) return;
    const data = await resp.json();
    window.__manualTrades = data.open || [];
    const rows = window.__manualTrades.map(t => {{
      const cls = valueClass(t.unrealized_pnl_dollars);
      const sideCls = t.side === 'long' ? 'bull' : 'bear';
      const inst = t.instrument_type || 'equity';
      return `<tr><td><b>${{t.ticker}}</b></td><td>${{inst}}</td><td>${{t.underlying || t.ticker}}</td><td>${{t.option_expiration || '—'}}</td><td>${{t.option_type || '—'}}</td><td class="${{sideCls}}">${{t.side}}</td><td>${{t.entry_price}}</td><td>${{t.current_price ?? 'n/a'}}</td><td>${{t.quantity}}</td><td>${{t.contract_multiplier || 1}}</td><td>${{t.notional}}</td><td class="${{cls}}">${{fmtPct(t.unrealized_pnl_pct)}}</td><td class="${{cls}}">${{fmtMoney(t.unrealized_pnl_dollars)}}</td><td>${{t.note || ''}}</td><td>${{t.opened_at}}</td><td><button class="tab mt-edit" data-id="${{t.id}}">edit</button> <button class="tab mt-del" data-id="${{t.id}}" style="border-color:#dc2626;color:#dc2626">delete</button></td></tr>`;
    }}).join('');
    document.getElementById('manualTradeRows').innerHTML = rows || '<tr><td colspan="16">No manual trades yet. Add one above.</td></tr>';
    bindManualRowButtons();
  }} catch (err) {{}}
}}
function bindSignalTradeButtons() {{
  document.querySelectorAll('.signal-add-trade').forEach(b => b.onclick = async () => {{
    const status = document.getElementById('refreshStatus') || document.getElementById('manualTradeStatus');
    const ticker = b.dataset.tk;
    const instrument = b.dataset.instrument || 'equity';
    const inferOptionType = (contract) => {{
      const c = String(contract || '').toUpperCase();
      if (c.length >= 15) {{
        const right = c.charAt(c.length - 9);
        if (right === 'C') return 'call';
        if (right === 'P') return 'put';
      }}
      return '';
    }};
    let price = Number(b.dataset.price);
    if (instrument === 'option' && (!Number.isFinite(price) || price <= 0)) {{
      try {{
        if (status) status.textContent = ' fetching option premium for ' + ticker + '...';
        const url = '/options/quote?underlying=' + encodeURIComponent(b.dataset.underlying || '') + '&contract=' + encodeURIComponent(b.dataset.contract || ticker);
        const resp = await fetch(url);
        if (resp.ok) {{
          const q = await resp.json();
          price = Number(q.mark || q.current_price || q.last);
          if (q.option_expiration) b.dataset.expiry = q.option_expiration;
          if (q.option_type) b.dataset.optionType = q.option_type;
          if (q.option_strike) b.dataset.strike = q.option_strike;
          if (q.contract_multiplier) b.dataset.multiplier = q.contract_multiplier;
        }}
      }} catch (e) {{}}
    }}
    if (instrument !== 'option' && (!Number.isFinite(price) || price <= 0)) {{
      try {{
        if (status) status.textContent = ' fetching latest entry price for ' + ticker + '...';
        const resp = await fetch('/prices/refresh');
        const data = await resp.json();
        const q = (data.prices || {{}})[ticker];
        price = q && q.current_price ? Number(q.current_price) : price;
      }} catch (e) {{}}
    }}
    if (!Number.isFinite(price) || price <= 0) {{
      if (status) status.textContent = ' no live/current price available for ' + ticker + '.';
      return;
    }}
    const payload = {{
      ticker,
      side: b.dataset.side || 'long',
      entry_price: price,
      quantity: Number(b.dataset.qty || 1),
      note: b.dataset.note || ('Added from dashboard signal at current price for ' + ticker)
    }};
    if (instrument === 'option') {{
      payload.instrument_type = 'option';
      payload.underlying = b.dataset.underlying || '';
      payload.option_contract = b.dataset.contract || ticker;
      payload.option_expiration = b.dataset.expiry || '';
      payload.option_type = b.dataset.optionType || inferOptionType(payload.option_contract);
      payload.option_strike = b.dataset.strike ? Number(b.dataset.strike) : null;
      payload.contract_multiplier = Number(b.dataset.multiplier || 100);
    }}
    if (status) status.textContent = ' adding ' + ticker + ' to Manual Trades...';
    const resp = await fetch('/manual-trades', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)}});
    if (resp.ok) {{
      if (status) status.textContent = ticker + ' added to Manual Trades at ' + price + '.';
      activateTab('manual');
      await refreshManualTrades();
    }} else if (status) {{
      status.textContent = ' failed to add ' + ticker + '.';
    }}
  }});
}}
function manualResetForm() {{
  const form = document.getElementById('manualTradeForm');
  form.reset();
  document.getElementById('manualEditId').value = '';
  document.getElementById('manualSubmitBtn').textContent = 'Add Trade';
  document.getElementById('manualCancelBtn').style.display = 'none';
}}
function bindManualRowButtons() {{
  document.querySelectorAll('.mt-edit').forEach(b => b.onclick = () => {{
    const t = (window.__manualTrades || []).find(x => x.id === b.dataset.id);
    if (!t) return;
    const form = document.getElementById('manualTradeForm');
    form.edit_id.value = t.id;
    form.ticker.value = t.ticker;
    form.side.value = t.side;
    form.entry_price.value = t.entry_price;
    form.quantity.value = t.quantity;
    form.note.value = t.note || '';
    document.getElementById('manualSubmitBtn').textContent = 'Update Trade';
    document.getElementById('manualCancelBtn').style.display = '';
    document.getElementById('manualTradeStatus').textContent = ' editing ' + t.ticker + '...';
    form.scrollIntoView({{behavior:'smooth', block:'center'}});
  }});
  document.querySelectorAll('.mt-del').forEach(b => b.onclick = async () => {{
    const t = (window.__manualTrades || []).find(x => x.id === b.dataset.id);
    if (!confirm('Delete ' + (t ? t.ticker : 'this') + ' manual trade?')) return;
    const status = document.getElementById('manualTradeStatus');
    status.textContent = ' deleting...';
    const resp = await fetch('/manual-trades/' + b.dataset.id, {{method:'DELETE'}});
    status.textContent = resp.ok ? ' deleted.' : ' delete failed.';
    if (resp.ok) await refreshManualTrades();
  }});
}}
document.getElementById('manualCancelBtn')?.addEventListener('click', manualResetForm);
document.getElementById('manualTradeForm')?.addEventListener('submit', async (ev) => {{
  ev.preventDefault();
  const form = ev.currentTarget;
  const payload = Object.fromEntries(new FormData(form).entries());
  const editId = payload.edit_id;
  delete payload.edit_id;
  payload.entry_price = Number(payload.entry_price);
  payload.quantity = Number(payload.quantity);
  const status = document.getElementById('manualTradeStatus');
  status.textContent = editId ? ' updating...' : ' saving...';
  const url = editId ? '/manual-trades/' + editId : '/manual-trades';
  const method = editId ? 'PUT' : 'POST';
  const resp = await fetch(url, {{method, headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)}});
  status.textContent = resp.ok ? (editId ? ' updated with live P/L.' : ' saved with live P/L.') : ' failed.';
  if (resp.ok) {{ manualResetForm(); await refreshManualTrades(); }}
}});
bindSignalTradeButtons();
refreshManualTrades();
document.getElementById('advisorSend')?.addEventListener('click', async () => {{
  const msg = document.getElementById('advisorMsg').value.trim();
  const portfolio = document.getElementById('advisorPortfolio').value.trim();
  const status = document.getElementById('advisorStatus');
  const out = document.getElementById('advisorAnswer');
  if (!msg) {{ status.textContent = ' enter a question first.'; return; }}
  status.textContent = ' thinking...';
  try {{
    const resp = await fetch('/advisor', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{message: msg, portfolio: portfolio || null}})}});
    const data = await resp.json();
    out.textContent = (data.answer || 'No answer.') + '\\n\\n[backend: ' + (data.backend||'?') + ', signals: ' + (data.used_signals||0) + ']';
    status.textContent = '';
  }} catch (err) {{ status.textContent = ' advisor unavailable (start the API server).'; }}
}});
async function refreshJobStatus() {{
  const out = document.getElementById('jobStatus');
  if (!out) return;
  try {{
    const resp = await fetch('/jobs/status');
    const data = await resp.json();
    out.textContent = JSON.stringify(data.latest || data, null, 2);
  }} catch (err) {{ out.textContent = 'Job status unavailable. Start the API server first.'; }}
}}
document.getElementById('jobStatusRefresh')?.addEventListener('click', refreshJobStatus);
document.getElementById('jobRun')?.addEventListener('click', async () => {{
  const status = document.getElementById('jobRunStatus');
  status.textContent = ' queuing...';
  try {{
    const resp = await fetch('/jobs/run', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{strategy:'swing', horizon:'5D', retries:2, retry_delay_seconds:60}})}});
    const data = await resp.json();
    status.textContent = resp.ok ? ' queued. Refresh status in a few minutes.' : ' failed to queue.';
    document.getElementById('jobStatus').textContent = JSON.stringify(data, null, 2);
  }} catch (err) {{ status.textContent = ' unavailable.'; }}
}});
document.getElementById('tuneRun')?.addEventListener('click', async () => {{
  const status = document.getElementById('jobRunStatus');
  status.textContent = ' queuing weekly retune...';
  try {{
    const resp = await fetch('/jobs/tune', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{profiles:['swing','intraday','options_buying'], horizon_days:5, period:'2y', step:5, max_tickers:25}})}});
    const data = await resp.json();
    status.textContent = resp.ok ? ' retune queued. Refresh Status when it finishes.' : ' retune failed to queue.';
    document.getElementById('jobStatus').textContent = JSON.stringify(data, null, 2);
  }} catch (err) {{ status.textContent = ' retune unavailable.'; }}
}});
document.getElementById('snapshotStatusRefresh')?.addEventListener('click', async () => {{
  const out = document.getElementById('jobStatus');
  try {{
    const resp = await fetch('/snapshots/status');
    out.textContent = JSON.stringify(await resp.json(), null, 2);
  }} catch (err) {{ out.textContent = 'Snapshot status unavailable.'; }}
}});
document.getElementById('scorecardRefresh')?.addEventListener('click', async () => {{
  const out = document.getElementById('jobStatus');
  try {{
    const resp = await fetch('/reliability/scorecard');
    out.textContent = JSON.stringify(await resp.json(), null, 2);
  }} catch (err) {{ out.textContent = 'Reliability scorecard unavailable.'; }}
}});
document.getElementById('optionsScorecardRefresh')?.addEventListener('click', async () => {{
  const out = document.getElementById('jobStatus');
  try {{
    const resp = await fetch('/reliability/options-scorecard?target_days=3');
    out.textContent = JSON.stringify(await resp.json(), null, 2);
  }} catch (err) {{ out.textContent = 'Options scorecard unavailable.'; }}
}});
document.getElementById('calibrationRefresh')?.addEventListener('click', async () => {{
  const out = document.getElementById('jobStatus');
  try {{
    const resp = await fetch('/reliability/calibration');
    out.textContent = JSON.stringify(await resp.json(), null, 2);
  }} catch (err) {{ out.textContent = 'Calibration profile unavailable.'; }}
}});
document.getElementById('labelsRefresh')?.addEventListener('click', async () => {{
  const out = document.getElementById('jobStatus');
  try {{
    const resp = await fetch('/reliability/labels');
    out.textContent = JSON.stringify(await resp.json(), null, 2);
  }} catch (err) {{ out.textContent = 'Feature labels unavailable.'; }}
}});
refreshJobStatus();
// --- Parallel category refresh jobs (Jobs tab) ------------------------------
const REFRESH_CATS = ['market','news','social','xtwitter','government','trump','political','macro','global','official_economic','company_events','options_volatility','reference_dashboards','automation_apis','paid_platforms','source_registry'];
const CAT_LABEL = {{market:'Market data',news:'News',social:'Sentiment',xtwitter:'X / Twitter',government:'Government',trump:'Trump / Admin',political:'Political / Geopolitical',macro:'Macro',global:'Global markets',official_economic:'Official economic',company_events:'Company events',options_volatility:'Options / Volatility',reference_dashboards:'Dashboards / News refs',automation_apis:'Automation APIs',paid_platforms:'Paid platforms',source_registry:'Source registry'}};
function renderRefreshTable(cats) {{
  const body = document.getElementById('refreshTableBody');
  if (!body) return;
  const map = (cats && cats.categories) || {{}};
  body.innerHTML = REFRESH_CATS.map(c => {{
    const r = map[c] || {{}};
    const st = r.status || '—';
    const color = st === 'ok' ? '#16a34a' : st === 'failed' ? '#dc2626' : st === 'running' ? '#f59e0b' : '#6b7280';
    return '<tr id="refrow-' + c + '"><td><b>' + (CAT_LABEL[c]||c) + '</b></td>'
      + '<td style="color:' + color + ';font-weight:700">' + st + '</td>'
      + '<td>' + (r.finished_at || '—') + '</td>'
      + '<td>' + (r.elapsed_sec != null ? r.elapsed_sec + 's' : '—') + '</td>'
      + '<td><small>' + (r.summary || r.error || '—') + '</small></td>'
      + '<td><button class="tab catbtn" data-cat="' + c + '">run</button></td></tr>';
  }}).join('');
  bindCatButtons();
}}
async function loadRefreshStatus() {{
  try {{ const resp = await fetch('/jobs/refresh-status'); renderRefreshTable(await resp.json()); }}
  catch (e) {{}}
}}
function markRow(c, status) {{
  const row = document.getElementById('refrow-' + c);
  if (row && row.cells[1]) {{
    row.cells[1].textContent = status;
    row.cells[1].style.color = status === 'running' ? '#f59e0b' : status === 'ok' ? '#16a34a' : '#dc2626';
  }}
}}
async function runCategory(c) {{
  markRow(c, 'running');
  try {{
    const resp = await fetch('/jobs/refresh/' + c, {{method:'POST'}});
    const data = await resp.json();
    const r = (data.results || {{}})[c] || {{}};
    markRow(c, r.status || 'ok');
    await loadRefreshStatus();
  }} catch (e) {{ markRow(c, 'failed'); }}
}}
function bindCatButtons() {{
  document.querySelectorAll('.catbtn').forEach(b => {{
    b.onclick = () => runCategory(b.dataset.cat);
  }});
}}
bindCatButtons();
document.getElementById('refreshStatusBtn')?.addEventListener('click', loadRefreshStatus);
async function queueRefreshAll(analyze, buttonLabel) {{
  const status = document.getElementById('refreshAllStatus');
  REFRESH_CATS.forEach(c => markRow(c, 'running'));
  status.textContent = ' ' + buttonLabel + ': running all sources in parallel' + (analyze ? ' + analyzing/generating' : '') + '...';
  try {{
    const resp = await fetch('/jobs/refresh-all', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{analyze: !!analyze}})}});
    const data = await resp.json();
    if (data.status === 'queued') {{
      status.textContent = ' all sources refreshing in parallel + re-analyzing/generating. Polling...';
      const poll = setInterval(async () => {{
        await loadRefreshStatus();
        try {{
          const s = await fetch('/jobs/status'); const d = await s.json();
          const latest = d.latest || d;
          if (latest && latest.status === 'success') {{
            clearInterval(poll);
            status.textContent = ' done — reloading dashboard on this tab...';
            setTimeout(() => location.reload(), 800);
          }}
        }} catch (e) {{}}
      }}, 15000);
    }} else {{
      renderRefreshTable({{categories: data.results}});
      status.textContent = ' done in ' + (data.elapsed_sec ?? '?') + 's (parallel).';
    }}
  }} catch (err) {{ status.textContent = ' refresh unavailable (start the API server).'; }}
}}
document.getElementById('generateFreshDashboard')?.addEventListener('click', async () => {{
  const analyzeBox = document.getElementById('refreshAnalyze');
  if (analyzeBox) analyzeBox.checked = true;
  await queueRefreshAll(true, 'generate');
}});
document.getElementById('refreshAllJobs')?.addEventListener('click', async () => {{
  const analyze = document.getElementById('refreshAnalyze')?.checked;
  await queueRefreshAll(!!analyze, analyze ? 'refresh + analyze' : 'refresh');
}});
loadRefreshStatus();
let sourceAutoRefreshRunning = false;
async function refreshAllSourcesAuto() {{
  if (sourceAutoRefreshRunning) return;
  sourceAutoRefreshRunning = true;
  const status = document.getElementById('refreshAllStatus');
  if (status) status.textContent = ' auto-refreshing source groups in parallel...';
  try {{
    const resp = await fetch('/jobs/refresh-all', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{analyze:true}})}});
    const data = await resp.json();
    if (data.results) renderRefreshTable({{categories: data.results}});
    if (status) status.textContent = data.status === 'queued' ? ' auto refresh + analyze queued.' : ' auto source refresh done in ' + (data.elapsed_sec ?? '?') + 's.';
  }} catch (e) {{
    if (status) status.textContent = ' auto source refresh unavailable.';
  }} finally {{
    sourceAutoRefreshRunning = false;
  }}
}}
setInterval(refreshAllSourcesAuto, 2 * 60 * 60 * 1000);
// --- Global refresh controls (present on every tab via the sticky nav) ------
// Reload keeps the current tab because activateTab persists it to the URL hash
// + localStorage, and restoreTab() re-applies it on load.
document.getElementById('reloadKeep')?.addEventListener('click', () => location.reload());

// Live prices: pull the latest real prices without a full re-scan and patch the
// Overview + Current Prices cells in place. Stays on whatever tab you are on.
let livePriceRefreshRunning = false;
async function refreshLivePrices(auto=false) {{
  if (livePriceRefreshRunning) return;
  livePriceRefreshRunning = true;
  const status = document.getElementById('refreshStatus');
  if (status) status.textContent = auto ? ' auto-refreshing live prices...' : ' fetching live prices...';
  try {{
    const resp = await fetch('/prices/refresh');
    const data = await resp.json();
    const prices = data.prices || {{}};
    let n = 0;
    document.querySelectorAll('td.px').forEach(td => {{
      const q = prices[td.dataset.tk];
      if (q && q.current_price != null) {{ td.textContent = q.current_price; n++; }}
    }});
    document.querySelectorAll('td.daypx').forEach(td => {{
      const q = prices[td.dataset.tk];
      if (q && q.day_change_pct != null) {{
        const v = q.day_change_pct;
        td.textContent = (v >= 0 ? '+' : '') + v + '%';
        td.style.color = v > 0 ? '#16a34a' : v < 0 ? '#dc2626' : '#6b7280';
        td.classList.remove('up','down','neutral');
        td.classList.add(v > 0 ? 'up' : v < 0 ? 'down' : 'neutral');
      }}
    }});
    document.querySelectorAll('.signal-add-trade').forEach(btn => {{
      const q = prices[btn.dataset.tk];
      if (q && q.current_price != null) btn.dataset.price = q.current_price;
    }});
    updateStrategyRows(prices);
    const asof = document.getElementById('dataAsOf');
    if (asof) asof.textContent = 'Prices as of ' + (data.as_of || 'now') + ' (' + n + ' updated)';
    if (status) status.textContent = ' updated ' + n + ' prices.';
    await refreshManualTrades();
  }} catch (err) {{ if (status) status.textContent = ' price refresh unavailable (start the API server).'; }}
  finally {{ livePriceRefreshRunning = false; }}
}}
document.getElementById('refreshPrices')?.addEventListener('click', () => refreshLivePrices(false));
setInterval(() => refreshLivePrices(true), 10 * 60 * 1000);

// Re-scan: kick off a full live re-scan in the background, then auto-reload
// (staying on the current tab) once it finishes.
document.getElementById('rescanLive')?.addEventListener('click', async () => {{
  const status = document.getElementById('refreshStatus');
  status.textContent = ' starting full live re-scan (this takes a few minutes)...';
  try {{
    const resp = await fetch('/jobs/run', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{strategy:'swing', horizon:'5D', retries:2, retry_delay_seconds:60}})}});
    if (!resp.ok) {{ status.textContent = ' could not start re-scan.'; return; }}
    status.textContent = ' re-scan running... polling for completion.';
    const poll = setInterval(async () => {{
      try {{
        const s = await fetch('/jobs/status');
        const d = await s.json();
        const latest = (d.latest || d);
        if (latest && latest.status === 'success') {{
          clearInterval(poll);
          status.textContent = ' re-scan complete — reloading on this tab...';
          setTimeout(() => location.reload(), 800);
        }} else if (latest && (latest.status === 'failed')) {{
          clearInterval(poll);
          status.textContent = ' re-scan failed: ' + (latest.error || 'unknown');
        }}
      }} catch (e) {{}}
    }}, 15000);
  }} catch (err) {{ status.textContent = ' re-scan unavailable (start the API server).'; }}
}});

// --- US market open/close ticker (regular session, America/New_York) ---
// NYSE/Nasdaq full-day holidays for 2026–2028 (+ 2029-01-01 for the year boundary).
const MKT_HOLIDAYS = new Set([
  // 2026
  '2026-01-01','2026-01-19','2026-02-16','2026-04-03','2026-05-25','2026-06-19',
  '2026-07-03','2026-09-07','2026-11-26','2026-12-25',
  // 2027 (Juneteenth observed 06-18, July 4th observed 07-05, Christmas observed 12-24)
  '2027-01-01','2027-01-18','2027-02-15','2027-03-26','2027-05-31','2027-06-18',
  '2027-07-05','2027-09-06','2027-11-25','2027-12-24',
  // 2028
  '2028-01-17','2028-02-21','2028-04-14','2028-05-29','2028-06-19',
  '2028-07-04','2028-09-04','2028-11-23','2028-12-25',
  // year boundary
  '2029-01-01'
]);
// NYSE/Nasdaq half-days (regular session ends 13:00 ET) for 2026–2028.
const MKT_EARLY_CLOSE = new Set([
  '2026-11-27','2026-12-24',   // 2026
  '2027-11-26',                // 2027 (day after Thanksgiving; Dec 24 is a full holiday this year)
  '2028-07-03','2028-11-24'    // 2028
]);
function _etParts() {{
  const f = new Intl.DateTimeFormat('en-US', {{timeZone:'America/New_York', hourCycle:'h23',
    year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit'}});
  const o = {{}};
  for (const p of f.formatToParts(new Date())) o[p.type] = p.value;
  return {{y:+o.year, mo:+o.month, d:+o.day, h:+o.hour, mi:+o.minute, s:+o.second}};
}}
function _dow(y, mo, d) {{ return new Date(Date.UTC(y, mo - 1, d, 12)).getUTCDay(); }}      // 0=Sun..6=Sat
function _pad2(n) {{ return String(n).padStart(2, '0'); }}
function _key(y, mo, d) {{ return y + '-' + _pad2(mo) + '-' + _pad2(d); }}
function _hol(y, mo, d) {{ return MKT_HOLIDAYS.has(_key(y, mo, d)); }}
function _earlyClose(y, mo, d) {{ return MKT_EARLY_CLOSE.has(_key(y, mo, d)); }}
function _isTrading(y, mo, d) {{ const w = _dow(y, mo, d); return w !== 0 && w !== 6 && !_hol(y, mo, d); }}
function _addDays(y, mo, d, n) {{
  const dt = new Date(Date.UTC(y, mo - 1, d + n, 12));
  return {{y:dt.getUTCFullYear(), mo:dt.getUTCMonth() + 1, d:dt.getUTCDate()}};
}}
function _fmtDur(s) {{
  s = Math.max(0, Math.floor(s));
  const dd = Math.floor(s / 86400); s -= dd * 86400;
  const hh = Math.floor(s / 3600); s -= hh * 3600;
  const mm = Math.floor(s / 60); const ss = s - mm * 60;
  return (dd > 0 ? dd + 'd ' : '') + _pad2(hh) + ':' + _pad2(mm) + ':' + _pad2(ss);
}}
function updateMarketClock() {{
  const el = document.getElementById('marketClock');
  if (!el) return;
  const OPEN = 9 * 3600 + 30 * 60;                          // 09:30 ET
  const et = _etParts();
  const secs = et.h * 3600 + et.mi * 60 + et.s;
  const todayTrades = _isTrading(et.y, et.mo, et.d);
  const half = _earlyClose(et.y, et.mo, et.d);
  const CLOSE = half ? (13 * 3600) : (16 * 3600);          // 13:00 on half-days, else 16:00 ET
  if (todayTrades && secs >= OPEN && secs < CLOSE) {{
    el.innerHTML = '🟢 <b>Market OPEN' + (half ? ' (half day)' : '') + '</b> · closes in ' + _fmtDur(CLOSE - secs);
    el.style.background = '#064e3b'; el.style.color = '#d1fae5';
  }} else {{
    let toOpen;
    if (todayTrades && secs < OPEN) {{
      toOpen = OPEN - secs;
    }} else {{
      let ahead = 1, nd;
      while (ahead <= 14) {{ nd = _addDays(et.y, et.mo, et.d, ahead); if (_isTrading(nd.y, nd.mo, nd.d)) break; ahead++; }}
      toOpen = (86400 - secs) + (ahead - 1) * 86400 + OPEN;
    }}
    el.innerHTML = '🔴 <b>Market CLOSED</b> · opens in ' + _fmtDur(toOpen);
    el.style.background = '#7f1d1d'; el.style.color = '#fee2e2';
  }}
}}
updateMarketClock();
setInterval(updateMarketClock, 1000);
</script>
</body></html>"""


def write_reports(result: RunResult, base_dir: Path) -> dict[str, Path]:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = base_dir / day
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "report.md": render_markdown(result),
        "signals.json": render_json(result),
        "summary.csv": render_csv(result),
        "dashboard.html": render_html(result),
    }
    written: dict[str, Path] = {}
    for name, content in artifacts.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        written[name] = path

    result.evidence.dump_jsonl(out_dir / "audit_log.jsonl")
    written["audit_log.jsonl"] = out_dir / "audit_log.jsonl"
    return written
