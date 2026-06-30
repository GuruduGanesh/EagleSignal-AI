from datetime import datetime, timedelta, timezone

from eaglesignal.config import Settings
from eaglesignal.ingestion import news


def test_fetch_news_filters_stale_items_to_last_24_hours(monkeypatch):
    now = datetime.now(timezone.utc)
    fresh = news.NewsItem(
        title="Fresh market clue",
        source="Unit Test",
        url="https://example.com/fresh",
        published_at=now - timedelta(hours=3),
        source_type="news",
    )
    stale = news.NewsItem(
        title="Stale market clue",
        source="Unit Test",
        url="https://example.com/stale",
        published_at=now - timedelta(hours=30),
        source_type="news",
    )

    monkeypatch.setattr(news, "get_settings", lambda: Settings(
        news_max_age_hours=24,
        enable_social_sentiment=False,
    ))
    monkeypatch.setattr(news, "_from_google_news", lambda ticker, company_name=None: [fresh, stale])
    monkeypatch.setattr(news, "_from_yahoo_rss", lambda ticker: [])
    monkeypatch.setattr(news, "_from_seeking_alpha_latest_articles", lambda *args, **kwargs: [])
    monkeypatch.setattr(news, "_from_gdelt", lambda ticker, company_name=None: [])
    monkeypatch.setattr(news, "_from_yfinance", lambda ticker: [])
    monkeypatch.setattr(news, "_from_bluesky", lambda ticker, company_name=None: [])
    monkeypatch.setattr(news, "_from_hacker_news_market", lambda days=2: [])
    monkeypatch.setattr(news, "_from_seeking_alpha_market_news", lambda days=2: [])
    monkeypatch.setattr(news, "_news_cache", {})

    res = news._fetch_news_uncached("SPX", "S&P 500 Index")

    titles = [item.title for item in res.items]
    assert "Fresh market clue" in titles
    assert "Stale market clue" not in titles


def test_entity_relevant_matches_ticker_or_company_name():
    items = [
        news.NewsItem(title="AMD expands AI chip shipments", source="X", url="https://example.com/1"),
        news.NewsItem(title="Completely unrelated headline", source="X", url="https://example.com/2"),
        news.NewsItem(title="Advanced Micro Devices sees strong demand", source="X", url="https://example.com/3"),
    ]

    filtered = news._entity_relevant(items, "AMD", "Advanced Micro Devices")

    assert [item.title for item in filtered] == [
        "AMD expands AI chip shipments",
        "Advanced Micro Devices sees strong demand",
    ]
