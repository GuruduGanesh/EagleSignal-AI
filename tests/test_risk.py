from eaglesignal.analysis.options import OptionsAnalytics
from eaglesignal.config import Settings
from eaglesignal.ingestion.market_data import MarketData, _synthetic_bars
from eaglesignal.risk.manager import assess_risk
from eaglesignal.schemas import RiskLevel, SignalComponent


def _settings():
    return Settings()


def test_synthetic_data_blocks_trade():
    market = MarketData(ticker="TEST", bars=_synthetic_bars("TEST"), is_synthetic=True)
    comps = [SignalComponent(name="technical_structure", score=80, weight=1.0)]
    decision, penalty = assess_risk(_settings(), market, comps, None, confidence=80)
    assert decision.block_trade is True
    assert penalty > 0


def test_conflicting_signals_raise_risk():
    market = MarketData(ticker="TEST", bars=_synthetic_bars("TEST"), is_synthetic=False)
    comps = [
        SignalComponent(name="a", score=90, weight=0.5),
        SignalComponent(name="b", score=20, weight=0.5),
    ]
    decision, _ = assess_risk(_settings(), market, comps, None, confidence=80)
    assert any("Conflicting" in w for w in decision.warnings)


def test_illiquid_options_penalty():
    market = MarketData(ticker="TEST", bars=_synthetic_bars("TEST"), is_synthetic=False)
    comps = [SignalComponent(name="a", score=70, weight=1.0)]
    opts = OptionsAnalytics(total_oi=10, illiquid=True)
    decision, _ = assess_risk(_settings(), market, comps, opts, confidence=80, is_option_setup=True)
    assert any("open interest" in p.lower() for p in decision.penalties)
    assert decision.risk_level in (RiskLevel.medium, RiskLevel.high, RiskLevel.extreme)
