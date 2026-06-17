"""Strict expected-move / reward-risk candidate gate (SKILL-162).

Single source of truth that decides whether a ticker may be called a bullish or
bearish RESEARCH candidate. It enforces, identically for every tab/report:

    final_required_points = max(current_price * 0.05, 5 if price < 100 else 10)
    valid iff expected_points >= final_required_points
             AND expected_percent >= 5
             AND reward_risk_ratio >= 2.0
             AND score thresholds for the tier

If the honest, analysis-derived target does not clear the bar, the candidate is
DOWNGRADED (watchlist_only / no_trade / rejected_*). Targets are NEVER inflated to
pass — weak setups are rejected, not faked. Quality over quantity.

The gate is computed ONCE in ``prediction/engine.py`` and stored on
``PredictionResult`` so every view (Overview, Trade Summary, Trade Strategy,
Options Edge, Bull/Bear Verdicts, CSV, JSON, Markdown) reads the same numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Verdict label vocabulary (the only labels the system may emit).
STRONG_BULL = "strong_bullish_research_candidate"
BULL = "bullish_research_candidate"
STRONG_BEAR = "strong_bearish_research_candidate"
BEAR = "bearish_research_candidate"
WATCHLIST = "watchlist_only"
NO_TRADE = "no_trade"
REJECT_LOW_REWARD = "rejected_low_reward"
REJECT_HIGH_RISK = "rejected_high_risk"
REJECT_NO_CATALYST = "rejected_no_catalyst"
REJECT_INSUFFICIENT_MOVE = "rejected_insufficient_expected_move"

VALID_LABELS = {STRONG_BULL, BULL, STRONG_BEAR, BEAR}

# Validation-status buckets.
VS_VALID = "VALID_RESEARCH_CANDIDATE"
VS_REJECTED = "REJECTED"
VS_WATCHLIST = "WATCHLIST"
VS_NO_TRADE = "NO_TRADE"

MIN_REQUIRED_PERCENT = 5.0
MIN_REWARD_RISK = 2.0


@dataclass
class CandidateGate:
    current_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    direction: str = "neutral"
    expected_points: Optional[float] = None
    expected_percent: Optional[float] = None
    min_required_points: Optional[float] = None
    min_required_percent: float = MIN_REQUIRED_PERCENT
    final_required_points: Optional[float] = None
    risk_points: Optional[float] = None
    reward_risk_ratio: Optional[float] = None
    move_ok: bool = False
    rr_ok: bool = False
    validation_status: str = VS_NO_TRADE
    rejected_reason: Optional[str] = None
    final_label: str = NO_TRADE
    research_action: str = "wait_or_avoid"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_price": _round(self.current_price),
            "target_price": _round(self.target_price),
            "stop_price": _round(self.stop_price),
            "direction": self.direction,
            "expected_points": _round(self.expected_points),
            "expected_percent": _round(self.expected_percent),
            "min_required_points": _round(self.min_required_points),
            "min_required_percent": self.min_required_percent,
            "final_required_points": _round(self.final_required_points),
            "risk_points": _round(self.risk_points),
            "reward_risk_ratio": _round(self.reward_risk_ratio),
            "move_ok": self.move_ok,
            "rr_ok": self.rr_ok,
            "validation_status": self.validation_status,
            "rejected_reason": self.rejected_reason,
            "final_label": self.final_label,
            "research_action": self.research_action,
            "notes": self.notes,
        }


def _round(x: Optional[float], n: int = 2) -> Optional[float]:
    return round(float(x), n) if isinstance(x, (int, float)) else None


def required_points(current_price: float) -> tuple[float, float, float]:
    """(min_required_points, min_required_percent, final_required_points)."""
    min_pts = 5.0 if current_price < 100 else 10.0
    by_pct = current_price * (MIN_REQUIRED_PERCENT / 100.0)
    return (min_pts, MIN_REQUIRED_PERCENT, max(min_pts, by_pct))


def _research_action(label: str) -> str:
    if label in (STRONG_BULL, BULL):
        return "research_long_setup"
    if label in (STRONG_BEAR, BEAR):
        return "research_short_or_put_setup"
    if label == WATCHLIST:
        return "watch_only"
    return "wait_or_avoid"


def evaluate_candidate(
    *,
    direction: str,
    current_price: Optional[float],
    target_price: Optional[float],
    stop_price: Optional[float],
    opportunity_score: float,
    confidence_score: float,
    risk_score: float,
    has_catalyst: bool = False,
    blocked: bool = False,
) -> CandidateGate:
    """Apply the strict rule and return the gated verdict + every derived field."""
    g = CandidateGate(direction=direction, current_price=current_price,
                      target_price=target_price, stop_price=stop_price)

    if blocked:
        g.validation_status = VS_REJECTED
        g.final_label = REJECT_HIGH_RISK
        g.rejected_reason = "risk manager blocked the setup"
        g.research_action = "wait_or_avoid"
        return g

    if current_price is None or current_price <= 0 or target_price is None:
        g.validation_status = VS_NO_TRADE
        g.final_label = NO_TRADE
        g.rejected_reason = "no current price / target available"
        return g

    bullish = direction in ("bullish", "neutral_to_bullish")
    bearish = direction in ("bearish", "neutral_to_bearish")

    if bullish:
        g.expected_points = target_price - current_price
    elif bearish:
        g.expected_points = current_price - target_price
    else:
        g.expected_points = abs(target_price - current_price)
    g.expected_percent = g.expected_points / current_price * 100.0

    g.min_required_points, g.min_required_percent, g.final_required_points = required_points(current_price)

    if stop_price is not None:
        g.risk_points = abs(current_price - stop_price)
        if g.risk_points > 0:
            g.reward_risk_ratio = g.expected_points / g.risk_points

    g.move_ok = (g.expected_points >= g.final_required_points) and (g.expected_percent >= MIN_REQUIRED_PERCENT)
    g.rr_ok = g.reward_risk_ratio is not None and g.reward_risk_ratio >= MIN_REWARD_RISK

    # --- decision tree (percentage has priority, point floor still applies) ----
    if not (bullish or bearish):
        g.validation_status = VS_NO_TRADE
        g.final_label = NO_TRADE
        g.rejected_reason = "no clear directional edge (neutral)"
        g.research_action = "wait_or_avoid"
        return g

    if not g.move_ok:
        g.validation_status = VS_REJECTED
        g.final_label = REJECT_INSUFFICIENT_MOVE
        g.rejected_reason = (
            f"expected move {g.expected_points:+.2f}pts / {g.expected_percent:+.1f}% "
            f"is below the required {g.final_required_points:.2f}pts and {MIN_REQUIRED_PERCENT:.0f}%"
        )
        g.research_action = "watch_only"
        return g

    if not g.rr_ok:
        g.validation_status = VS_REJECTED
        g.final_label = REJECT_LOW_REWARD
        rr_txt = f"{g.reward_risk_ratio:.2f}" if g.reward_risk_ratio is not None else "n/a"
        g.rejected_reason = f"reward/risk {rr_txt} is below the required {MIN_REWARD_RISK:.1f}:1"
        g.research_action = "watch_only"
        return g

    if risk_score > 55:
        g.validation_status = VS_REJECTED
        g.final_label = REJECT_HIGH_RISK
        g.rejected_reason = f"risk score {risk_score:.0f} exceeds 55"
        g.research_action = "wait_or_avoid"
        return g

    # Move + reward/risk + risk all OK. Now the conviction tiers.
    if confidence_score < 55 or opportunity_score < 60:
        g.validation_status = VS_WATCHLIST
        g.final_label = WATCHLIST
        g.rejected_reason = (
            f"move qualifies but conviction is light "
            f"(confidence {confidence_score:.0f} / opportunity {opportunity_score:.0f})"
        )
        g.research_action = "watch_only"
        return g

    strong = opportunity_score >= 70 and confidence_score >= 65 and risk_score <= 45 and has_catalyst
    if bullish:
        g.final_label = STRONG_BULL if strong else BULL
    else:
        g.final_label = STRONG_BEAR if strong else BEAR
    g.validation_status = VS_VALID
    g.research_action = _research_action(g.final_label)
    g.notes.append(
        f"valid: {g.expected_points:+.2f}pts / {g.expected_percent:+.1f}% ≥ "
        f"{g.final_required_points:.2f}pts & 5%, R/R "
        f"{g.reward_risk_ratio:.2f}:1" if g.reward_risk_ratio is not None else "valid"
    )
    return g
