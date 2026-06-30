from eaglesignal.pipeline import RunResult
from eaglesignal.reports.generator import render_html
from eaglesignal.schemas import AssetType, Direction, PredictionResult


def test_dashboard_renders_only_requested_tabs():
    result = RunResult(
        predictions=[
            PredictionResult(
                prediction_id="p1",
                ticker="SPX",
                asset_type=AssetType.index,
                direction=Direction.bullish,
                opportunity_score=62,
                confidence_score=58,
                risk_score=34,
                trend_impact={"summary": "fresh news + bullish tape", "news_count": 2, "news_providers": ["seeking_alpha_latest_articles_24h"]},
                final_verdict={"label": "bullish_research_candidate", "research_action": "research_long_setup", "reasons": ["fresh catalysts"]},
                market_snapshot={"current_price": 6000.0, "day_change_pct": 0.8, "previous_close": 5952.4, "volume": 1, "source": "test"},
                stock_market_engine={"direction": "constructive", "summary": "broad tape constructive"},
                options_trade_idea={"min_index_option_move_points": 50.0},
            )
        ],
        strategy="index_trend",
        horizon="5D",
    )

    html = render_html(result)

    assert 'data-tab="index_strategies">Index Options<' in html
    assert 'data-tab="trends">Trends & Impact<' in html
    assert 'data-tab="news">News & Evidence<' in html
    assert 'data-tab="why">Why Suggested<' in html
    assert 'data-tab="markets">Global Market<' in html
    assert 'data-tab="jobs">Jobs<' in html
    assert 'data-tab="validation">MD Validation<' in html

    assert 'data-tab="overview"' not in html
    assert 'data-tab="prices"' not in html
    assert 'data-tab="confidence"' not in html
    assert 'data-tab="trade_summary"' not in html
    assert 'data-tab="strategy"' not in html
    assert 'data-tab="themes"' not in html
