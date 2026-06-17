"""Data contracts shared across every module.

Every engine exchanges these explicit pydantic models instead of loose dicts
(see ARCHITECTURE.md section 4). Keeping the contracts in one place makes each
module replaceable without breaking the pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetType(str, Enum):
    equity = "equity"
    etf = "etf"
    index = "index"
    option = "option"


class Direction(str, Enum):
    bullish = "bullish"
    neutral_to_bullish = "neutral_to_bullish"
    neutral = "neutral"
    neutral_to_bearish = "neutral_to_bearish"
    bearish = "bearish"
    avoid = "avoid"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    extreme = "extreme"


class Severity(str, Enum):
    """Alert severity, per WORKFLOW.md section 11."""

    P0 = "P0"  # market-moving event, send urgent
    P1 = "P1"  # strong fresh signal, send normal alert
    P2 = "P2"  # watchlist update only, include in report
    P3 = "P3"  # weak / stale / conflicting, store no alert


class AssetEntity(BaseModel):
    ticker: str
    asset_type: AssetType = AssetType.equity
    company_name: Optional[str] = None
    cik: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    strategy_tags: list[str] = Field(default_factory=list)
    related_etfs: list[str] = Field(default_factory=list)
    resolved: bool = False


class Evidence(BaseModel):
    """One stored claim. No final prediction is produced without evidence."""

    evidence_id: str
    entity: str
    source_name: str
    source_type: str = "unknown"  # official | exchange | news | aggregator | social | search
    url: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_at: Optional[datetime] = None
    claim: str = ""
    raw_excerpt: str = ""
    polarity: float = 0.0  # -1 bearish .. +1 bullish
    reliability_score: int = 50  # 0..100, see DATA_SOURCES.md ranking
    freshness_score: int = 100  # 0..100


class SignalComponent(BaseModel):
    """One scored engine output (technical, fundamental, options, ...)."""

    name: str
    score: float  # 0..100, 50 == neutral
    weight: float  # 0..1
    rationale: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    available: bool = True  # False when the underlying data was missing


class ExpectedMove(BaseModel):
    low_pct: Optional[float] = None
    high_pct: Optional[float] = None
    basis: str = ""  # e.g. "ATR(14)" or "options straddle"


class RiskDecision(BaseModel):
    risk_level: RiskLevel = RiskLevel.medium
    risk_score: float = 50.0  # 0 safe .. 100 dangerous
    penalties: list[str] = Field(default_factory=list)
    block_trade: bool = False
    warnings: list[str] = Field(default_factory=list)


class Forecast(BaseModel):
    """Probabilistic forward view (research only, simulated from REAL history).

    Implements the direction/magnitude/uncertainty separation borrowed from the
    JordiCorbilla LSTM repo and the Monte-Carlo bands from huseinzol05. These are
    forward *simulations* from observed returns, never fabricated market prices.
    """

    horizon_days: int = 5
    prob_up: Optional[float] = None  # P(price higher at horizon), 0..1
    expected_return_pct: Optional[float] = None  # median simulated return
    p05_return_pct: Optional[float] = None  # 5th percentile (downside band)
    p95_return_pct: Optional[float] = None  # 95th percentile (upside band)
    method: str = ""  # e.g. "monte_carlo_gbm(real_returns)"
    n_paths: int = 0
    agent_votes: dict[str, str] = Field(default_factory=dict)  # turtle/ma/momentum -> long/short/flat
    rationale: list[str] = Field(default_factory=list)
    available: bool = False


class PredictionResult(BaseModel):
    """Canonical output schema (ARCHITECTURE.md section 6)."""

    prediction_id: str
    created_at: datetime = Field(default_factory=utcnow)
    ticker: str
    asset_type: AssetType
    horizon: str = "5D"
    strategy: str = "swing"
    direction: Direction = Direction.neutral

    opportunity_score: float = 50.0  # how attractive the setup is
    confidence_score: float = 50.0  # how reliable the evidence/model is
    risk_score: float = 50.0  # how dangerous the setup is

    component_scores: dict[str, float] = Field(default_factory=dict)
    component_weights: dict[str, float] = Field(default_factory=dict)
    expected_move: ExpectedMove = Field(default_factory=ExpectedMove)
    forecast: Forecast = Field(default_factory=Forecast)
    short_horizon_forecasts: dict[str, Forecast] = Field(default_factory=dict)
    market_snapshot: dict[str, Any] = Field(default_factory=dict)
    paper_trade: dict[str, Any] = Field(default_factory=dict)
    manual_trade: dict[str, Any] = Field(default_factory=dict)
    options_trade_idea: dict[str, Any] = Field(default_factory=dict)
    trend_impact: dict[str, Any] = Field(default_factory=dict)
    event_radar: dict[str, Any] = Field(default_factory=dict)
    economic_event_impact: dict[str, Any] = Field(default_factory=dict)
    final_verdict: dict[str, Any] = Field(default_factory=dict)
    confidence_trace: dict[str, Any] = Field(default_factory=dict)
    market_regime: dict[str, Any] = Field(default_factory=dict)  # shared risk-on/off tape
    stock_market_engine: dict[str, Any] = Field(default_factory=dict)  # macro/geo/calendar market read
    factor_coverage: dict[str, Any] = Field(default_factory=dict)  # 23-group checklist audit

    # --- strict expected-move / reward-risk candidate gate (single source of truth) ---
    candidate_gate: dict[str, Any] = Field(default_factory=dict)
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    expected_points: Optional[float] = None
    expected_percent: Optional[float] = None
    final_required_points: Optional[float] = None
    reward_risk_ratio: Optional[float] = None
    validation_status: str = "NO_TRADE"
    rejected_reason: Optional[str] = None
    global_correlations: dict[str, float] = Field(default_factory=dict)  # index -> rolling corr

    key_bullish_evidence: list[str] = Field(default_factory=list)
    key_bearish_evidence: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    policy_impacts: list[str] = Field(default_factory=list)  # SKILL-056 gov->ticker links
    invalidation_conditions: list[str] = Field(default_factory=list)

    risk: RiskDecision = Field(default_factory=RiskDecision)
    severity: Severity = Severity.P3
    data_freshness: dict[str, Any] = Field(default_factory=dict)
    missing_data: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)

    model_version: str = "v0.1.0"
    disclaimer: str = "Research only, not financial advice."
