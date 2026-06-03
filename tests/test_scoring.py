from eaglesignal.analysis import scoring
from eaglesignal.schemas import Direction, SignalComponent


def _components():
    return [
        SignalComponent(name="technical_structure", score=80, weight=0),
        SignalComponent(name="price_volume_momentum", score=70, weight=0),
        SignalComponent(name="fundamentals", score=60, weight=0, available=False),  # missing
        SignalComponent(name="options_intelligence", score=75, weight=0),
        SignalComponent(name="macro_regime", score=55, weight=0),
        SignalComponent(name="sentiment", score=65, weight=0),
        SignalComponent(name="cross_market_correlation", score=72, weight=0),
    ]


def test_weights_normalize_and_skip_missing():
    weights = {
        "technical_structure": 0.2, "price_volume_momentum": 0.2, "fundamentals": 0.2,
        "options_intelligence": 0.15, "macro_regime": 0.1, "sentiment": 0.1,
        "cross_market_correlation": 0.05, "risk_penalty_adjustment": 0.05,
    }
    comps = scoring.apply_weights(_components(), weights)
    total = sum(c.weight for c in comps)
    assert abs(total - 1.0) < 1e-6  # weights of available components sum to 1
    missing = next(c for c in comps if c.name == "fundamentals")
    assert missing.weight == 0.0  # missing component gets no weight


def test_opportunity_and_direction_bullish():
    weights = {
        "technical_structure": 0.2, "price_volume_momentum": 0.2, "fundamentals": 0.2,
        "options_intelligence": 0.15, "macro_regime": 0.1, "sentiment": 0.1,
        "cross_market_correlation": 0.05, "risk_penalty_adjustment": 0.05,
    }
    comps = scoring.apply_weights(_components(), weights)
    opp = scoring.opportunity_score(comps)
    assert 60 <= opp <= 100
    assert scoring.to_direction(opp) in (Direction.bullish, Direction.neutral_to_bullish)


def test_confidence_higher_with_agreement():
    agree = [SignalComponent(name=f"c{i}", score=70, weight=0) for i in range(5)]
    disagree = [SignalComponent(name=f"c{i}", score=s, weight=0) for i, s in enumerate([10, 90, 20, 80, 50])]
    assert scoring.confidence_score(agree) > scoring.confidence_score(disagree)


def test_neutral_confidence_is_low_even_with_agreement():
    """A neutral setup (opportunity ~50) must NOT score high confidence, even
    when every engine agrees. High confidence is reserved for buy/sell calls."""
    agree_neutral = [SignalComponent(name=f"c{i}", score=50, weight=0) for i in range(6)]
    conf_neutral = scoring.confidence_score(agree_neutral, opportunity=50.0)
    conf_bullish = scoring.confidence_score(agree_neutral, opportunity=75.0)
    assert conf_neutral < 30, f"neutral confidence should be low, got {conf_neutral}"
    assert conf_bullish > conf_neutral
    assert conf_bullish >= 60, f"clear buy should be confident, got {conf_bullish}"


def test_conviction_zero_at_neutral_full_when_directional():
    assert scoring.conviction(50.0) == 0.0
    assert scoring.conviction(52.0) == 0.0  # inside the dead-zone
    assert scoring.conviction(75.0) == 1.0
    assert scoring.conviction(25.0) == 1.0
    assert 0.0 < scoring.conviction(62.0) < 1.0


def test_direction_buckets():
    assert scoring.to_direction(95) == Direction.bullish
    assert scoring.to_direction(50) == Direction.neutral
    assert scoring.to_direction(10) == Direction.bearish
