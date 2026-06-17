import pandas as pd

from eaglesignal.analysis.options import analyze_expiries
from eaglesignal.ingestion.options_chain import ExpiryChain, OptionsChain, _select_expiries


def _chain(
    *,
    ticker="NVDA",
    contract_root="NVDA",
    spot=221.0,
    strike=220.0,
    call_price=10.0,
    put_price=9.5,
    bid=9.8,
    ask=10.2,
    oi=5000,
    volume=1500,
    iv=0.42,
    dte=18,
    expiry="2026-06-19",
    pcr_bullish=True,
):
    calls = pd.DataFrame(
        [
            {
                "contractSymbol": f"{contract_root}260619C{int(strike * 1000):08d}",
                "strike": strike,
                "lastPrice": call_price,
                "bid": bid,
                "ask": ask,
                "volume": volume,
                "openInterest": oi,
                "impliedVolatility": iv,
            }
        ]
    )
    puts = pd.DataFrame(
        [
            {
                "contractSymbol": f"{contract_root}260619P{int(strike * 1000):08d}",
                "strike": strike,
                "lastPrice": put_price,
                "bid": 9.3,
                "ask": 9.7,
                "volume": 500 if pcr_bullish else volume * 2,
                "openInterest": oi,
                "impliedVolatility": iv,
            }
        ]
    )
    expiry_chain = ExpiryChain(expiry, dte, calls, puts)
    return OptionsChain(
        ticker=ticker,
        expiration=expiry_chain.expiration,
        expirations=[expiry_chain.expiration],
        spot=spot,
        calls=calls,
        puts=puts,
        chains=[expiry_chain],
        source="test",
        available=True,
    )


def test_deep_options_confidence_can_exceed_75_when_sources_agree():
    ideas = analyze_expiries(
        _chain(spot=1000.0, strike=1000.0, call_price=40.0, bid=39.8, ask=40.2, iv=0.30, dte=30),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 35,
        },
    )

    top = ideas[0]
    assert top["action"] == "BUY CALL"
    assert top["confidence"] >= 75
    assert top["confidence_color"] == "green"
    assert top["readiness"] == "high"
    assert top["risk_gate"] == "high"
    assert top["option_quality_score"] >= 80
    assert top["bid_ask_spread_pct"] <= 8
    assert top["delta"] is not None
    assert top["theta_per_day"] is not None


def test_options_confidence_caps_wide_illiquid_contracts():
    ideas = analyze_expiries(
        _chain(bid=1.0, ask=2.0, oi=25, volume=5),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 35,
        },
    )

    top = ideas[0]
    assert top["confidence"] <= 55
    assert top["readiness"] == "paper only"
    assert top["risk_gate"] == "paper only"
    assert top["bid_ask_spread_pct"] > 25


def test_sub_7_dte_high_iv_call_is_paper_only():
    ideas = analyze_expiries(
        _chain(
            ticker="MU",
            contract_root="MU",
            spot=1035.5,
            strike=1035.0,
            call_price=46.05,
            bid=44.35,
            ask=45.2,
            oi=1000,
            volume=2662,
            iv=1.80,
            dte=6,
            expiry="2026-06-07",
        ),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 80,
        },
    )

    top = ideas[0]
    assert top["risk_gate"] == "paper only"
    assert top["confidence"] <= 60
    assert any("sub-7-DTE" in reason for reason in top["reasons"])
    assert top["theta_per_day"] is not None


def test_under_5_dte_expiries_are_not_considered():
    ideas = analyze_expiries(
        _chain(
            ticker="MU",
            contract_root="MU",
            spot=1035.5,
            strike=1035.0,
            call_price=46.05,
            bid=44.35,
            ask=45.2,
            oi=1000,
            volume=2662,
            iv=1.80,
            dte=4,
            expiry="2026-06-05",
        ),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 80,
            "min_days_to_expiry": 5,
        },
    )

    assert ideas == []


def test_options_chain_selector_never_falls_back_below_min_dte(monkeypatch):
    from datetime import date, timedelta

    today = date.today()
    expirations = [
        (today + timedelta(days=1)).isoformat(),
        (today + timedelta(days=4)).isoformat(),
    ]

    assert _select_expiries(expirations, max_n=3, min_days=5) == []


def test_expensive_high_iv_call_is_not_directly_tradeable():
    ideas = analyze_expiries(
        _chain(
            ticker="SNDK",
            contract_root="SNDK",
            spot=1761.43,
            strike=1760.0,
            call_price=154.8,
            bid=149.0,
            ask=160.0,
            oi=500,
            volume=250,
            iv=1.85,
            dte=17,
            expiry="2026-06-18",
        ),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 100,
        },
    )

    top = ideas[0]
    assert top["risk_gate"] in {"spread only", "paper only"}
    assert top["confidence"] <= 65
    assert top["premium_pct_spot"] > 8
    assert top["iv_realized_ratio"] > 1


def test_high_iv_rank_caps_long_premium_to_spread_only():
    ideas = analyze_expiries(
        _chain(spot=100.0, strike=100.0, call_price=4.0, bid=3.95, ask=4.05, iv=0.55, dte=21),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 50,
            "iv_history": {
                "by_expiration": {
                    "2026-06-19": {
                        "available": True,
                        "sample_count": 25,
                        "scope": "exact_expiration",
                        "iv_rank": 92.0,
                        "iv_percentile": 96.0,
                    }
                }
            },
        },
    )

    top = ideas[0]
    assert top["iv_rank"] == 92.0
    assert top["iv_percentile"] == 96.0
    assert top["risk_gate"] == "spread only"
    assert top["confidence"] <= 62


def test_earnings_in_window_caps_long_call_to_spread_only():
    ideas = analyze_expiries(
        _chain(spot=100.0, strike=100.0, call_price=4.0, bid=3.95, ask=4.05, iv=0.40, dte=21),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 40,
            "days_to_earnings": 7,
            "next_earnings_date": "2026-06-12",
        },
    )

    top = ideas[0]
    assert top["earnings_in_window"] is True
    assert top["days_to_earnings"] == 7
    assert top["risk_gate"] == "spread only"
    assert top["confidence"] <= 66
    assert any("earnings" in reason.lower() for reason in top["reasons"])


def test_high_iv_rank_suggests_premium_selling_alternative():
    ideas = analyze_expiries(
        _chain(spot=100.0, strike=100.0, call_price=4.0, bid=3.95, ask=4.05, iv=0.55, dte=21),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 50,
            "iv_history": {
                "by_expiration": {
                    "2026-06-19": {
                        "available": True,
                        "sample_count": 25,
                        "scope": "exact_expiration",
                        "iv_rank": 92.0,
                        "iv_percentile": 96.0,
                    }
                }
            },
        },
    )

    top = ideas[0]
    assert top["alt_structure"] is not None
    assert top["alt_structure"]["type"] == "bull_put_credit_spread"
    assert top["alt_structure"]["est_max_gain"] is not None
    # Defined-risk primary vertical now carries max gain/loss/breakeven (§1.7).
    assert top["spread"]["est_max_loss"] is not None
    assert top["spread"]["breakeven"] is not None
    assert "credit" in (top["strategy_label"] or "").lower()


def test_options_skew_term_unusual_activity_and_oi_change_are_reported():
    near = _chain(
        ticker="NVDA",
        contract_root="NVDA",
        spot=100.0,
        strike=100.0,
        call_price=4.0,
        put_price=5.0,
        bid=3.95,
        ask=4.05,
        oi=100,
        volume=300,
        iv=0.40,
        dte=14,
        expiry="2026-06-19",
    )
    near.chains[0].puts.loc[0, "impliedVolatility"] = 0.50
    later = _chain(
        ticker="NVDA",
        contract_root="NVDA",
        spot=100.0,
        strike=100.0,
        call_price=5.0,
        put_price=5.0,
        bid=4.9,
        ask=5.1,
        oi=100,
        volume=80,
        iv=0.60,
        dte=28,
        expiry="2026-07-03",
    ).chains[0]
    near.chains.append(later)
    near.expirations.append(later.expiration)

    ideas = analyze_expiries(
        near,
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 40,
            "option_history": {
                "NVDA260619C00100000": {
                    "exact_contract_oi": 80,
                }
            },
        },
    )

    first = next(i for i in ideas if i["expiration"] == "2026-06-19")
    assert first["atm_iv_skew_pct"] == 10.0
    assert first["skew_label"] == "puts_richer_bearish_hedging"
    assert first["term_structure_slope_pct"] > 0
    assert first["term_structure_label"] == "contango_longer_expiry_richer"
    assert first["volume_oi_ratio"] == 3.0
    assert first["unusual_activity_score"] >= 50
    assert first["oi_change"] == 20
    assert any("chain-derived unusual activity" in reason for reason in first["reasons"])


def test_index_options_require_50_point_expected_move():
    ideas = analyze_expiries(
        _chain(ticker="SPX", contract_root="SPX", spot=6000.0, strike=6000.0, call_price=35.0, bid=34.8, ask=35.2),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 18,
            "is_index_option": True,
            "expected_points": 42.0,
            "min_index_option_move_points": 50.0,
        },
    )

    top = ideas[0]
    assert top["action"] == "NO TRADE"
    assert top["direction"] == "up"
    assert top["reference_contract"]
    assert top["reference_option_price"] == 35.0
    assert any("50-point minimum" in reason for reason in top["reasons"])


def test_index_options_allow_50_plus_point_expected_move():
    ideas = analyze_expiries(
        _chain(ticker="SPX", contract_root="SPX", spot=6000.0, strike=6000.0, call_price=35.0, bid=34.8, ask=35.2),
        {
            "direction": "up",
            "conviction": 1.0,
            "data_quality": 95,
            "algo_confluence": 5,
            "risk_score": 35,
            "realized_vol_20d": 18,
            "is_index_option": True,
            "expected_points": 55.0,
            "min_index_option_move_points": 50.0,
        },
    )

    assert ideas[0]["action"] == "BUY CALL"
