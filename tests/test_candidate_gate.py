from eaglesignal.analysis.candidate_gate import (
    BULL,
    REJECT_HIGH_RISK,
    REJECT_INSUFFICIENT_MOVE,
    REJECT_LOW_REWARD,
    STRONG_BULL,
    VS_REJECTED,
    VS_VALID,
    evaluate_candidate,
    required_points,
)


def test_required_points_price_bands():
    # <100 -> floor 5, but 5% may dominate
    assert required_points(54)[2] == 5.0          # 5% of 54 = 2.7 < 5 -> 5
    assert required_points(80)[2] == 5.0          # 5% of 80 = 4 < 5 -> 5
    assert required_points(120)[2] == 10.0        # 5% of 120 = 6 < 10 -> 10
    assert round(required_points(340)[2], 2) == 17.0   # 5% of 340 = 17 > 10
    assert round(required_points(1032)[2], 2) == 51.6  # 5% of 1032 = 51.6 > 10


def test_weak_move_is_rejected_not_bullish():
    # current 54.11, target 54.77 -> ~0.66 pts / 1.2% -> below 5pts & 5%
    g = evaluate_candidate(
        direction="bullish", current_price=54.11, target_price=54.77, stop_price=51.0,
        opportunity_score=70, confidence_score=70, risk_score=40, has_catalyst=True,
    )
    assert g.validation_status == VS_REJECTED
    assert g.final_label == REJECT_INSUFFICIENT_MOVE
    assert "below" in (g.rejected_reason or "")


def test_expensive_stock_needs_5pct_not_just_10pts():
    # 1032 -> needs 51.6 pts. A 20-pt move (>10) must STILL reject.
    g = evaluate_candidate(
        direction="bullish", current_price=1032.0, target_price=1052.0, stop_price=1020.0,
        opportunity_score=80, confidence_score=70, risk_score=40, has_catalyst=True,
    )
    assert g.validation_status == VS_REJECTED
    assert g.final_label == REJECT_INSUFFICIENT_MOVE


def test_valid_strong_bullish():
    # 100 -> needs 5 pts & 5%. Target 112 = +12 pts / +12%, stop 96 -> R/R 12/4=3
    g = evaluate_candidate(
        direction="bullish", current_price=100.0, target_price=112.0, stop_price=96.0,
        opportunity_score=75, confidence_score=70, risk_score=40, has_catalyst=True,
    )
    assert g.validation_status == VS_VALID
    assert g.final_label == STRONG_BULL
    assert g.reward_risk_ratio == 3.0


def test_good_move_but_thin_reward_risk_rejected():
    # price 90 -> required 5 pts. Target 99 = +9 pts/+10% clears move, but stop 82
    # -> risk 8, reward 9 -> R/R 1.13 < 2 -> low reward.
    g = evaluate_candidate(
        direction="bullish", current_price=90.0, target_price=99.0, stop_price=82.0,
        opportunity_score=75, confidence_score=70, risk_score=40, has_catalyst=True,
    )
    assert g.validation_status == VS_REJECTED
    assert g.final_label == REJECT_LOW_REWARD


def test_qualifying_move_light_conviction_is_watchlist():
    g = evaluate_candidate(
        direction="bullish", current_price=100.0, target_price=112.0, stop_price=96.0,
        opportunity_score=58, confidence_score=52, risk_score=50, has_catalyst=False,
    )
    assert g.validation_status == "WATCHLIST"
    assert g.final_label == "watchlist_only"


def test_high_risk_rejected():
    g = evaluate_candidate(
        direction="bullish", current_price=100.0, target_price=112.0, stop_price=96.0,
        opportunity_score=75, confidence_score=70, risk_score=70, has_catalyst=True,
    )
    assert g.validation_status == VS_REJECTED
    assert g.final_label == REJECT_HIGH_RISK


def test_blocked_is_rejected():
    g = evaluate_candidate(
        direction="bullish", current_price=100.0, target_price=112.0, stop_price=96.0,
        opportunity_score=75, confidence_score=70, risk_score=40, has_catalyst=True, blocked=True,
    )
    assert g.validation_status == VS_REJECTED


def test_valid_moderate_bullish_without_catalyst():
    # passes thresholds but no catalyst -> not strong, plain bullish candidate
    g = evaluate_candidate(
        direction="bullish", current_price=100.0, target_price=112.0, stop_price=96.0,
        opportunity_score=65, confidence_score=60, risk_score=50, has_catalyst=False,
    )
    assert g.validation_status == VS_VALID
    assert g.final_label == BULL
