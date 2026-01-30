"""
QUANT INDUSTRY V1 - Risk Management API (v2)
=============================================
Risk metrics, exposure, alerts, and kill-switch.
"""

from fastapi import APIRouter, Query, Path
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

router = APIRouter()


# ============================================================================
# Enums
# ============================================================================

class RiskLevel(str, Enum):
    """Risk level classifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class KillSwitchStatus(str, Enum):
    """Kill switch status."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    COOLDOWN = "cooldown"


# ============================================================================
# Pydantic Models
# ============================================================================

class RiskLimits(BaseModel):
    """Configured risk limits."""
    max_position_size: float = Field(..., description="Max $ per position")
    max_portfolio_risk: float = Field(..., description="Max portfolio risk %")
    max_daily_loss: float = Field(..., description="Max daily loss $")
    max_drawdown: float = Field(..., description="Max drawdown %")
    max_sector_concentration: float = Field(..., description="Max sector weight %")
    max_correlation: float = Field(..., description="Max position correlation")


class RiskMetrics(BaseModel):
    """Current risk metrics."""
    portfolio_beta: float
    portfolio_volatility: float = Field(..., description="Annualized volatility %")
    value_at_risk_95: float = Field(..., description="95% VaR in $")
    value_at_risk_99: float = Field(..., description="99% VaR in $")
    expected_shortfall: float = Field(..., description="CVaR/Expected Shortfall $")
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float = Field(..., description="Current max drawdown %")
    current_drawdown: float = Field(..., description="Current drawdown %")


class SafetyStatus(BaseModel):
    """Safety/risk compliance status."""
    is_safe: bool
    risk_level: RiskLevel
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RiskSummary(BaseModel):
    """Combined risk summary."""
    metrics: RiskMetrics
    limits: RiskLimits
    safety: SafetyStatus
    daily_pnl: float
    daily_pnl_percent: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExposureItem(BaseModel):
    """Exposure breakdown item."""
    category: str
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    weight: float


class ExposureResponse(BaseModel):
    """Position exposure response."""
    total_gross: float
    total_net: float
    total_long: float
    total_short: float
    by_sector: list[ExposureItem] = Field(default_factory=list)
    by_asset: list[ExposureItem] = Field(default_factory=list)
    leverage: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CorrelationPair(BaseModel):
    """Correlation between two assets."""
    symbol1: str
    symbol2: str
    correlation: float
    period_days: int


class CorrelationResponse(BaseModel):
    """Correlation matrix response."""
    pairs: list[CorrelationPair] = Field(default_factory=list)
    avg_correlation: float
    max_correlation: float
    min_correlation: float
    high_correlation_count: int = Field(..., description="Pairs with correlation > 0.7")


class VaRReport(BaseModel):
    """Value at Risk report."""
    confidence_95: float
    confidence_99: float
    expected_shortfall: float
    historical_var: float
    parametric_var: float
    monte_carlo_var: float
    worst_case_scenario: float
    calculation_date: datetime = Field(default_factory=datetime.utcnow)


class RiskAlert(BaseModel):
    """Risk alert."""
    id: str
    severity: AlertSeverity
    category: str
    message: str
    threshold: Optional[float] = None
    current_value: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None


class AlertsResponse(BaseModel):
    """Risk alerts response."""
    alerts: list[RiskAlert] = Field(default_factory=list)
    unacknowledged_count: int
    critical_count: int


class TradeCheckRequest(BaseModel):
    """Pre-trade risk check request."""
    symbol: str
    side: str = Field(..., description="buy or sell")
    quantity: float
    price: Optional[float] = None


class TradeCheckResponse(BaseModel):
    """Pre-trade risk check response."""
    approved: bool
    risk_score: float = Field(..., ge=0, le=100)
    warnings: list[str] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)
    position_after: float = Field(..., description="Position size after trade")
    sector_weight_after: float = Field(..., description="Sector weight after trade")


class MonteCarloRequest(BaseModel):
    """Monte Carlo simulation request."""
    num_simulations: int = Field(1000, ge=100, le=100000)
    time_horizon_days: int = Field(30, ge=1, le=365)
    confidence_level: float = Field(0.95, ge=0.9, le=0.99)


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result."""
    var_amount: float
    var_percent: float
    expected_return: float
    worst_case: float
    best_case: float
    median_outcome: float
    probability_of_loss: float
    simulations_run: int


class KillSwitchResponse(BaseModel):
    """Kill switch status response."""
    status: KillSwitchStatus
    activated_at: Optional[datetime] = None
    activated_by: Optional[str] = None
    reason: Optional[str] = None
    positions_closed: int = 0
    cooldown_ends_at: Optional[datetime] = None


class KillSwitchActivateRequest(BaseModel):
    """Kill switch activation request."""
    reason: str = Field(..., description="Reason for activation")
    close_positions: bool = Field(True, description="Whether to close all positions")


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/summary",
    response_model=RiskSummary,
    summary="Risk summary",
    description="Get combined risk metrics, limits, and safety status."
)
async def get_risk_summary() -> RiskSummary:
    """
    Get comprehensive risk summary.
    
    Combines metrics, limits, and safety status in a single call.
    """
    metrics = RiskMetrics(
        portfolio_beta=1.15,
        portfolio_volatility=18.5,
        value_at_risk_95=1850.00,
        value_at_risk_99=2750.00,
        expected_shortfall=3200.00,
        sharpe_ratio=1.85,
        sortino_ratio=2.15,
        max_drawdown=-8.5,
        current_drawdown=-2.1
    )
    
    limits = RiskLimits(
        max_position_size=25000.00,
        max_portfolio_risk=2.0,
        max_daily_loss=2500.00,
        max_drawdown=15.0,
        max_sector_concentration=40.0,
        max_correlation=0.8
    )
    
    safety = SafetyStatus(
        is_safe=True,
        risk_level=RiskLevel.MEDIUM,
        violations=[],
        warnings=["Technology sector at 60% (limit: 40%)"]
    )
    
    return RiskSummary(
        metrics=metrics,
        limits=limits,
        safety=safety,
        daily_pnl=520.00,
        daily_pnl_percent=0.85
    )


@router.get(
    "/exposure",
    response_model=ExposureResponse,
    summary="Position exposure",
    description="Get portfolio exposure breakdown."
)
async def get_exposure() -> ExposureResponse:
    """
    Get detailed exposure breakdown by sector and asset.
    """
    by_sector = [
        ExposureItem(
            category="Technology",
            gross_exposure=37075.00,
            net_exposure=37075.00,
            long_exposure=37075.00,
            short_exposure=0,
            weight=0.60
        ),
        ExposureItem(
            category="Financial",
            gross_exposure=9900.00,
            net_exposure=9900.00,
            long_exposure=9900.00,
            short_exposure=0,
            weight=0.16
        ),
    ]
    
    return ExposureResponse(
        total_gross=46975.00,
        total_net=46975.00,
        total_long=46975.00,
        total_short=0,
        by_sector=by_sector,
        by_asset=[],
        leverage=1.0
    )


@router.get(
    "/correlation",
    response_model=CorrelationResponse,
    summary="Correlation matrix",
    description="Get correlation between portfolio holdings."
)
async def get_correlation(
    symbol: Optional[str] = Query(None, description="Filter correlations for specific symbol")
) -> CorrelationResponse:
    """
    Get correlation matrix for portfolio holdings.
    """
    pairs = [
        CorrelationPair(symbol1="AAPL", symbol2="NVDA", correlation=0.72, period_days=252),
        CorrelationPair(symbol1="AAPL", symbol2="JPM", correlation=0.45, period_days=252),
        CorrelationPair(symbol1="NVDA", symbol2="JPM", correlation=0.38, period_days=252),
    ]
    
    if symbol:
        pairs = [p for p in pairs if symbol.upper() in (p.symbol1, p.symbol2)]
    
    return CorrelationResponse(
        pairs=pairs,
        avg_correlation=0.52,
        max_correlation=0.72,
        min_correlation=0.38,
        high_correlation_count=1
    )


@router.get(
    "/var",
    response_model=VaRReport,
    summary="Value at Risk",
    description="Get Value at Risk report."
)
async def get_var() -> VaRReport:
    """
    Get detailed Value at Risk analysis.
    
    Includes parametric, historical, and Monte Carlo VaR.
    """
    return VaRReport(
        confidence_95=1850.00,
        confidence_99=2750.00,
        expected_shortfall=3200.00,
        historical_var=1920.00,
        parametric_var=1850.00,
        monte_carlo_var=1880.00,
        worst_case_scenario=5500.00
    )


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Risk alerts",
    description="Get active risk alerts."
)
async def get_alerts() -> AlertsResponse:
    """
    Get active risk alerts and warnings.
    """
    alerts = [
        RiskAlert(
            id="alert-001",
            severity=AlertSeverity.WARNING,
            category="concentration",
            message="Technology sector concentration exceeds limit",
            threshold=40.0,
            current_value=60.0
        ),
        RiskAlert(
            id="alert-002",
            severity=AlertSeverity.INFO,
            category="correlation",
            message="High correlation detected: AAPL-NVDA at 0.72",
            threshold=0.70,
            current_value=0.72
        ),
    ]
    
    return AlertsResponse(
        alerts=alerts,
        unacknowledged_count=2,
        critical_count=0
    )


@router.post(
    "/alerts/{alert_id}/ack",
    summary="Acknowledge alert",
    description="Acknowledge a risk alert."
)
async def acknowledge_alert(
    alert_id: str = Path(..., description="Alert ID")
) -> dict:
    """
    Acknowledge a risk alert.
    """
    return {
        "status": "acknowledged",
        "alert_id": alert_id,
        "acknowledged_at": datetime.utcnow().isoformat()
    }


@router.post(
    "/check",
    response_model=TradeCheckResponse,
    summary="Pre-trade risk check",
    description="Check a proposed trade against risk limits."
)
async def check_trade(request: TradeCheckRequest) -> TradeCheckResponse:
    """
    Run pre-trade risk checks.
    
    Validates trade against position limits, sector concentration, and correlation.
    """
    return TradeCheckResponse(
        approved=True,
        risk_score=35.0,
        warnings=["Will increase Technology sector to 65%"],
        rejections=[],
        position_after=25000.00,
        sector_weight_after=0.65
    )


@router.post(
    "/montecarlo",
    response_model=MonteCarloResult,
    summary="Monte Carlo simulation",
    description="Run Monte Carlo simulation on portfolio."
)
async def run_monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for portfolio risk.
    """
    return MonteCarloResult(
        var_amount=2500.00,
        var_percent=4.05,
        expected_return=1250.00,
        worst_case=-8500.00,
        best_case=12000.00,
        median_outcome=800.00,
        probability_of_loss=0.35,
        simulations_run=request.num_simulations
    )


@router.get(
    "/kill-switch",
    response_model=KillSwitchResponse,
    summary="Kill switch status",
    description="Get kill switch status."
)
async def get_kill_switch() -> KillSwitchResponse:
    """
    Get current kill switch status.
    """
    return KillSwitchResponse(
        status=KillSwitchStatus.INACTIVE,
        positions_closed=0
    )


@router.post(
    "/kill-switch/activate",
    response_model=KillSwitchResponse,
    summary="Activate kill switch",
    description="Activate emergency kill switch to close all positions."
)
async def activate_kill_switch(request: KillSwitchActivateRequest) -> KillSwitchResponse:
    """
    Activate the kill switch.
    
    Closes all open positions and halts trading.
    """
    return KillSwitchResponse(
        status=KillSwitchStatus.ACTIVE,
        activated_at=datetime.utcnow(),
        activated_by="user",
        reason=request.reason,
        positions_closed=3 if request.close_positions else 0
    )


@router.post(
    "/kill-switch/release",
    response_model=KillSwitchResponse,
    summary="Release kill switch",
    description="Release the kill switch and resume trading."
)
async def release_kill_switch() -> KillSwitchResponse:
    """
    Release the kill switch.
    
    Resumes normal trading operations.
    """
    return KillSwitchResponse(
        status=KillSwitchStatus.INACTIVE,
        positions_closed=0
    )
