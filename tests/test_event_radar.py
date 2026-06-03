import pandas as pd

from eaglesignal.analysis.event_radar import detect_event_radar


def test_event_radar_flags_breakout_with_volume():
    closes = [100 + i for i in range(80)]
    closes[-20:] = [160 + i * 4 for i in range(20)]
    volumes = [1_000_000] * 79 + [3_000_000]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": volumes,
        }
    )

    radar = detect_event_radar(df, news_items=4, policy_links=1)

    assert radar["available"] is True
    assert radar["breakout_score"] > radar["exhaustion_score"]
    assert radar["verdict"] in {"bullish_event_watch", "early_event_watch"}
    assert radar["bullish_clues"]


def test_event_radar_flags_exhaustion_after_stretched_drop():
    closes = [100 + i * 3 for i in range(80)]
    closes[-5:] = [420, 400, 365, 325, 285]
    volumes = [1_000_000] * 80
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": volumes,
        }
    )

    radar = detect_event_radar(df)

    assert radar["available"] is True
    assert radar["exhaustion_score"] >= 20
    assert radar["bearish_clues"]
