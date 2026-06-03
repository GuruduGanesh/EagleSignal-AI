from eaglesignal.config import Settings, load_watchlist


def test_load_watchlist_keeps_company_metadata(tmp_path):
    watchlist = tmp_path / "watchlist.yml"
    watchlist.write_text(
        """
assets:
  - ticker: aapl
    asset_type: equity
    company_name: Apple Inc.
    exchange: NASDAQ
    sector: Technology
    strategy_tags: [mega_cap, options]
strategies: {}
""",
        encoding="utf-8",
    )

    assets, _ = load_watchlist(watchlist)

    assert len(assets) == 1
    assert assets[0].ticker == "AAPL"
    assert assets[0].company_name == "Apple Inc."
    assert assets[0].exchange == "NASDAQ"
    assert assets[0].sector == "Technology"


def test_strict_watchlist_defaults_to_true():
    assert Settings().strict_watchlist_only is True


def test_options_minimum_expiry_defaults_to_five_days():
    assert Settings().min_option_days_to_expiry == 5


def test_default_watchlist_is_focused_on_requested_niche_names():
    assets, _ = load_watchlist()
    tickers = {a.ticker for a in assets}

    # Core niche/AI watchlist.
    assert {"MU", "AMD", "AVGO", "NVDA", "INTC", "META", "GOOGL", "AMZN", "TSM", "ASML", "LRCX",
            "SMCI", "DELL", "HPE", "WDC", "AMAT", "OKLO", "PLTR", "ISRG", "RKLB", "SNDK"} <= tickers
    # Trump/Administration policy basket is now actively scored too.
    assert {"DJT", "LMT", "RTX", "NOC", "GD", "GE", "BAH", "SMR", "CEG", "VST",
            "TSLA", "LUNR", "ASTS", "ORCL", "MSFT"} <= tickers
    # Recently requested public AI/options names are active; private Groq stays context-only.
    assert {"AAPL", "MRVL", "QBTS"} <= tickers
    assert "GROQ" not in tickers
