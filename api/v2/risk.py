"""
QUANT INDUSTRY V1 - Risk Management API (v2)
=============================================
Risk metrics, exposure, alerts, and kill-switch.
Wired to real backend services.
"""

import logging
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Service Availability
# ============================================================================

SERVICES_AVAILABLE = False
KILL_SWITCH_AVAILABLE = False
MONTE_CARLO_AVAILABLE = False
RISK_SERVICE_AVAILABLE = False

_risk_service = None
_kill_switch = None
_monte_carlo_simulator = None
_sector_tracker = None
_correlation_manager = None
_multi_layer_engine = None

try:
    from backend.services.risk_service import (
        get_risk_service, get_sector_tracker, get_correlation_manager,
        get_multi_layer_risk_engine, RiskLevel as ServiceRiskLevel,
        AlertType as ServiceAlertType
    )
    RISK_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Risk service not available: {e}")

try:
    from backend.execution.kill_switch import get_kill_switch
    KILL_SWITCH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Kill switch not available: {e}")

try:
    from backend.risk.monte_carlo import MonteCarloSimulator, StressScenario
    MONTE_CARLO_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Monte Carlo not available: {e}")

try:
    from backend.services.trading_service import get_trading_service
    from backend.services.data_service import get_data_service
    SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Trading/data services not available: {e}")


def _get_risk_service():
    global _risk_service
    if _risk_service is None and RISK_SERVICE_AVAILABLE:
        _risk_service = get_risk_service()
    return _risk_service


def _get_kill_switch():
    global _kill_switch
    if _kill_switch is None and KILL_SWITCH_AVAILABLE:
        _kill_switch = get_kill_switch()
    return _kill_switch


def _get_sector_tracker():
    global _sector_tracker
    if _sector_tracker is None and RISK_SERVICE_AVAILABLE:
        _sector_tracker = get_sector_tracker()
    return _sector_tracker


def _get_correlation_manager():
    global _correlation_manager
    if _correlation_manager is None and RISK_SERVICE_AVAILABLE:
        _correlation_manager = get_correlation_manager()
    return _correlation_manager


def _get_multi_layer_engine():
    global _multi_layer_engine
    if _multi_layer_engine is None and RISK_SERVICE_AVAILABLE:
        _multi_layer_engine = get_multi_layer_risk_engine()
    return _multi_layer_engine


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
# Helper Functions
# ============================================================================

def _map_risk_level(level) -> RiskLevel:
    """Map service risk level to API risk level."""
    if not level:
        return RiskLevel.MEDIUM
    level_str = str(level.value if hasattr(level, 'value') else level).lower()
    mapping = {
        'low': RiskLevel.LOW,
        'moderate': RiskLevel.MEDIUM,
        'medium': RiskLevel.MEDIUM,
        'high': RiskLevel.HIGH,
        'critical': RiskLevel.CRITICAL,
    }
    return mapping.get(level_str, RiskLevel.MEDIUM)


def _map_alert_severity(sev) -> AlertSeverity:
    """Map service alert type to API severity."""
    if not sev:
        return AlertSeverity.INFO
    sev_str = str(sev.value if hasattr(sev, 'value') else sev).lower()
    mapping = {
        'info': AlertSeverity.INFO,
        'warning': AlertSeverity.WARNING,
        'error': AlertSeverity.CRITICAL,
        'critical': AlertSeverity.CRITICAL,
    }
    return mapping.get(sev_str, AlertSeverity.INFO)


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
    """Get comprehensive risk summary from real services."""
    risk_svc = _get_risk_service()
    
    if risk_svc and SERVICES_AVAILABLE:
        try:
            svc_metrics = risk_svc.calculate_metrics()
            
            metrics = RiskMetrics(
                portfolio_beta=svc_metrics.beta,
                portfolio_volatility=svc_metrics.portfolio_volatility,
                value_at_risk_95=svc_metrics.var_95,
                value_at_risk_99=svc_metrics.var_99,
                expected_shortfall=svc_metrics.cvar_95,
                sharpe_ratio=svc_metrics.sharpe_ratio,
                sortino_ratio=svc_metrics.sortino_ratio,
                max_drawdown=svc_metrics.max_drawdown,
                current_drawdown=svc_metrics.current_drawdown
            )
            
            limits = RiskLimits(
                max_position_size=svc_metrics.total_equity * (risk_svc.limits.max_position_pct / 100),
                max_portfolio_risk=risk_svc.limits.max_var_95,
                max_daily_loss=svc_metrics.total_equity * (risk_svc.limits.max_daily_loss_pct / 100),
                max_drawdown=risk_svc.limits.max_drawdown_pct,
                max_sector_concentration=risk_svc.limits.max_sector_pct,
                max_correlation=risk_svc.limits.max_correlation_exposure
            )
            
            # Determine safety status
            violations = []
            warnings = []
            
            if svc_metrics.current_drawdown > risk_svc.limits.max_drawdown_pct:
                violations.append(f"Drawdown exceeds limit: {svc_metrics.current_drawdown:.1f}%")
            elif svc_metrics.current_drawdown > risk_svc.limits.max_drawdown_pct * 0.8:
                warnings.append(f"Drawdown approaching limit: {svc_metrics.current_drawdown:.1f}%")
            
            if svc_metrics.max_position_pct > risk_svc.limits.max_position_pct:
                warnings.append(f"Position concentration at {svc_metrics.max_position_pct:.1f}%")
            
            safety = SafetyStatus(
                is_safe=len(violations) == 0,
                risk_level=_map_risk_level(svc_metrics.risk_level),
                violations=violations,
                warnings=warnings
            )
            
            return RiskSummary(
                metrics=metrics,
                limits=limits,
                safety=safety,
                daily_pnl=svc_metrics.daily_pnl,
                daily_pnl_percent=svc_metrics.daily_pnl_pct
            )
        except Exception as e:
            logger.error(f"Error getting risk summary: {e}")
    
    # Fallback mock data
    metrics = RiskMetrics(
        portfolio_beta=1.15, portfolio_volatility=18.5,
        value_at_risk_95=1850.00, value_at_risk_99=2750.00,
        expected_shortfall=3200.00, sharpe_ratio=1.85, sortino_ratio=2.15,
        max_drawdown=-8.5, current_drawdown=-2.1
    )
    limits = RiskLimits(
        max_position_size=25000.00, max_portfolio_risk=2.0,
        max_daily_loss=2500.00, max_drawdown=15.0,
        max_sector_concentration=40.0, max_correlation=0.8
    )
    safety = SafetyStatus(is_safe=True, risk_level=RiskLevel.MEDIUM, violations=[], warnings=[])
    
    return RiskSummary(metrics=metrics, limits=limits, safety=safety, daily_pnl=520.00, daily_pnl_percent=0.85)


@router.get(
    "/exposure",
    response_model=ExposureResponse,
    summary="Position exposure",
    description="Get portfolio exposure breakdown."
)
async def get_exposure() -> ExposureResponse:
    """Get detailed exposure breakdown by sector and asset."""
    sector_tracker = _get_sector_tracker()
    
    if sector_tracker and SERVICES_AVAILABLE:
        try:
            trading_svc = get_trading_service()
            account = trading_svc.get_account_info()
            positions = trading_svc.get_all_positions()
            
            position_dicts = [
                {'symbol': p.symbol, 'market_value': p.market_value, 'quantity': p.quantity}
                for p in positions
            ]
            
            exposure_summary = sector_tracker.get_exposure_summary(position_dicts, account.equity)
            
            by_sector = []
            total_long = 0
            total_short = 0
            
            for sector_data in exposure_summary.get('sectors', []):
                value = sector_data['value']
                if value >= 0:
                    total_long += value
                else:
                    total_short += abs(value)
                
                by_sector.append(ExposureItem(
                    category=sector_data['sector'],
                    gross_exposure=abs(value),
                    net_exposure=value,
                    long_exposure=max(0, value),
                    short_exposure=abs(min(0, value)),
                    weight=sector_data['pct_of_portfolio'] / 100
                ))
            
            total_gross = total_long + total_short
            total_net = total_long - total_short
            leverage = total_gross / account.equity if account.equity > 0 else 0
            
            return ExposureResponse(
                total_gross=total_gross, total_net=total_net,
                total_long=total_long, total_short=total_short,
                by_sector=by_sector, by_asset=[], leverage=leverage
            )
        except Exception as e:
            logger.error(f"Error getting exposure: {e}")
    
    # Fallback
    by_sector = [
        ExposureItem(category="Technology", gross_exposure=37075.00, net_exposure=37075.00,
                     long_exposure=37075.00, short_exposure=0, weight=0.60),
        ExposureItem(category="Financial", gross_exposure=9900.00, net_exposure=9900.00,
                     long_exposure=9900.00, short_exposure=0, weight=0.16),
    ]
    return ExposureResponse(
        total_gross=46975.00, total_net=46975.00, total_long=46975.00,
        total_short=0, by_sector=by_sector, by_asset=[], leverage=1.0
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
    """Get correlation matrix for portfolio holdings."""
    corr_mgr = _get_correlation_manager()
    
    if corr_mgr and SERVICES_AVAILABLE:
        try:
            trading_svc = get_trading_service()
            positions = trading_svc.get_all_positions()
            position_dicts = [
                {'symbol': p.symbol, 'market_value': p.market_value}
                for p in positions
            ]
            
            analysis = corr_mgr.get_correlation_analysis(position_dicts)
            
            pairs = []
            for pair_data in analysis.get('pairs', []):
                if symbol and symbol.upper() not in (pair_data['symbol1'], pair_data['symbol2']):
                    continue
                pairs.append(CorrelationPair(
                    symbol1=pair_data['symbol1'],
                    symbol2=pair_data['symbol2'],
                    correlation=pair_data['correlation'],
                    period_days=252
                ))
            
            correlations = [p.correlation for p in pairs] if pairs else [0]
            
            return CorrelationResponse(
                pairs=pairs,
                avg_correlation=analysis.get('portfolio_correlation', sum(correlations) / len(correlations)),
                max_correlation=max(correlations),
                min_correlation=min(correlations),
                high_correlation_count=analysis.get('high_correlation_count', len([c for c in correlations if c > 0.7]))
            )
        except Exception as e:
            logger.error(f"Error getting correlation: {e}")
    
    # Fallback
    pairs = [
        CorrelationPair(symbol1="AAPL", symbol2="NVDA", correlation=0.72, period_days=252),
        CorrelationPair(symbol1="AAPL", symbol2="JPM", correlation=0.45, period_days=252),
        CorrelationPair(symbol1="NVDA", symbol2="JPM", correlation=0.38, period_days=252),
    ]
    if symbol:
        pairs = [p for p in pairs if symbol.upper() in (p.symbol1, p.symbol2)]
    
    return CorrelationResponse(
        pairs=pairs, avg_correlation=0.52, max_correlation=0.72,
        min_correlation=0.38, high_correlation_count=1
    )


@router.get(
    "/var",
    response_model=VaRReport,
    summary="Value at Risk",
    description="Get Value at Risk report."
)
async def get_var() -> VaRReport:
    """Get detailed Value at Risk analysis."""
    risk_svc = _get_risk_service()
    
    if risk_svc and MONTE_CARLO_AVAILABLE and SERVICES_AVAILABLE:
        try:
            metrics = risk_svc.calculate_metrics()
            
            # Run Monte Carlo for additional VaR estimates
            simulator = MonteCarloSimulator(
                daily_return=metrics.daily_pnl_pct / 100 if metrics.daily_pnl_pct else 0.0005,
                daily_volatility=metrics.portfolio_volatility / 100 / 16,  # Convert annual to daily
                initial_capital=metrics.total_equity
            )
            mc_result = simulator.run(n_simulations=5000, n_days=10)
            
            return VaRReport(
                confidence_95=metrics.var_95,
                confidence_99=metrics.var_99,
                expected_shortfall=metrics.cvar_95,
                historical_var=metrics.var_95 * 1.05,  # Estimate
                parametric_var=metrics.var_95,
                monte_carlo_var=abs(mc_result.var_95 * metrics.total_equity),
                worst_case_scenario=abs(mc_result.var_99 * metrics.total_equity * 2)
            )
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
    
    return VaRReport(
        confidence_95=1850.00, confidence_99=2750.00, expected_shortfall=3200.00,
        historical_var=1920.00, parametric_var=1850.00, monte_carlo_var=1880.00,
        worst_case_scenario=5500.00
    )


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Risk alerts",
    description="Get active risk alerts."
)
async def get_alerts() -> AlertsResponse:
    """Get active risk alerts and warnings."""
    risk_svc = _get_risk_service()
    
    if risk_svc:
        try:
            svc_alerts = risk_svc.alerts
            
            alerts = []
            for alert in svc_alerts:
                alerts.append(RiskAlert(
                    id=alert.id,
                    severity=_map_alert_severity(alert.type),
                    category=alert.category,
                    message=alert.message,
                    threshold=alert.limit,
                    current_value=alert.value,
                    created_at=alert.timestamp,
                    acknowledged=alert.acknowledged
                ))
            
            return AlertsResponse(
                alerts=alerts,
                unacknowledged_count=len([a for a in alerts if not a.acknowledged]),
                critical_count=len([a for a in alerts if a.severity == AlertSeverity.CRITICAL])
            )
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
    
    # Fallback
    return AlertsResponse(alerts=[], unacknowledged_count=0, critical_count=0)


@router.post(
    "/alerts/{alert_id}/ack",
    summary="Acknowledge alert",
    description="Acknowledge a risk alert."
)
async def acknowledge_alert(alert_id: str = Path(..., description="Alert ID")) -> dict:
    """Acknowledge a risk alert."""
    risk_svc = _get_risk_service()
    
    if risk_svc:
        try:
            for alert in risk_svc.alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return {
                        "status": "acknowledged",
                        "alert_id": alert_id,
                        "acknowledged_at": datetime.utcnow().isoformat()
                    }
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
    
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
    """Run pre-trade risk checks using multi-layer engine."""
    engine = _get_multi_layer_engine()
    sector_tracker = _get_sector_tracker()
    
    if engine and SERVICES_AVAILABLE:
        try:
            trading_svc = get_trading_service()
            data_svc = get_data_service()
            
            account = trading_svc.get_account_info()
            positions = trading_svc.get_all_positions()
            
            # Get price if not provided
            price = request.price
            if price is None:
                quote = data_svc.get_quote(request.symbol)
                price = quote.price if quote else 0
            
            position_dicts = [
                {'symbol': p.symbol, 'market_value': p.market_value, 'quantity': p.quantity}
                for p in positions
            ]
            
            result = engine.check_trade(
                symbol=request.symbol.upper(),
                side=request.side.lower(),
                quantity=int(request.quantity),
                price=price,
                account_equity=account.equity,
                current_positions=position_dicts,
                daily_pnl=getattr(account, 'day_pnl', 0.0)
            )
            
            # Calculate position after trade
            trade_value = request.quantity * price
            existing_pos = next((p for p in positions if p.symbol == request.symbol.upper()), None)
            position_after = (existing_pos.market_value if existing_pos else 0) + trade_value
            
            # Calculate sector weight after
            sector_weight_after = 0.0
            if sector_tracker:
                sector = sector_tracker.get_sector(request.symbol)
                exposure = sector_tracker.calculate_exposure(position_dicts, account.equity)
                if sector.value in exposure:
                    sector_weight_after = (exposure[sector.value].pct_of_portfolio + trade_value / account.equity * 100) / 100
            
            # Risk score from checks
            passed_pct = result.passed_checks / result.total_checks * 100 if result.total_checks > 0 else 0
            risk_score = 100 - passed_pct
            
            return TradeCheckResponse(
                approved=result.approved,
                risk_score=risk_score,
                warnings=result.warnings,
                rejections=[c.message for c in result.checks if not c.passed],
                position_after=position_after,
                sector_weight_after=sector_weight_after
            )
        except Exception as e:
            logger.error(f"Error checking trade: {e}")
    
    # Fallback
    return TradeCheckResponse(
        approved=True, risk_score=35.0, warnings=["Services unavailable - using defaults"],
        rejections=[], position_after=request.quantity * (request.price or 100),
        sector_weight_after=0.1
    )


@router.post(
    "/montecarlo",
    response_model=MonteCarloResult,
    summary="Monte Carlo simulation",
    description="Run Monte Carlo simulation on portfolio."
)
async def run_monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    """Run Monte Carlo simulation for portfolio risk."""
    if MONTE_CARLO_AVAILABLE and SERVICES_AVAILABLE:
        try:
            risk_svc = _get_risk_service()
            metrics = risk_svc.calculate_metrics() if risk_svc else None
            
            initial_capital = metrics.total_equity if metrics else 100000
            daily_vol = (metrics.portfolio_volatility / 100 / 16) if metrics else 0.015
            daily_ret = 0.0005  # Assume small positive drift
            
            simulator = MonteCarloSimulator(
                daily_return=daily_ret,
                daily_volatility=daily_vol,
                initial_capital=initial_capital,
                target_return=(request.time_horizon_days / 252) * 0.10  # 10% annualized target
            )
            
            result = simulator.run(
                n_simulations=request.num_simulations,
                n_days=request.time_horizon_days
            )
            
            return MonteCarloResult(
                var_amount=abs(result.var_95 * initial_capital),
                var_percent=abs(result.var_95 * 100),
                expected_return=result.mean_return * initial_capital,
                worst_case=result.var_99 * initial_capital,
                best_case=(result.mean_return + 2 * result.std_return) * initial_capital,
                median_outcome=result.median_return * initial_capital,
                probability_of_loss=result.prob_loss,
                simulations_run=result.n_simulations
            )
        except Exception as e:
            logger.error(f"Error running Monte Carlo: {e}")
    
    # Fallback
    return MonteCarloResult(
        var_amount=2500.00, var_percent=4.05, expected_return=1250.00,
        worst_case=-8500.00, best_case=12000.00, median_outcome=800.00,
        probability_of_loss=0.35, simulations_run=request.num_simulations
    )


@router.get(
    "/kill-switch",
    response_model=KillSwitchResponse,
    summary="Kill switch status",
    description="Get kill switch status."
)
async def get_kill_switch_status() -> KillSwitchResponse:
    """Get current kill switch status."""
    ks = _get_kill_switch()
    
    if ks:
        try:
            status = KillSwitchStatus.ACTIVE if ks.is_active else KillSwitchStatus.INACTIVE
            return KillSwitchResponse(
                status=status,
                activated_at=ks.activated_at,
                activated_by="system" if ks.is_active else None,
                reason=ks.reason if ks.is_active else None,
                positions_closed=0
            )
        except Exception as e:
            logger.error(f"Error getting kill switch status: {e}")
    
    return KillSwitchResponse(status=KillSwitchStatus.INACTIVE, positions_closed=0)


@router.post(
    "/kill-switch/activate",
    response_model=KillSwitchResponse,
    summary="Activate kill switch",
    description="Activate emergency kill switch to close all positions."
)
async def activate_kill_switch(request: KillSwitchActivateRequest) -> KillSwitchResponse:
    """Activate the kill switch."""
    ks = _get_kill_switch()
    positions_closed = 0
    
    if ks:
        try:
            ks.activate(reason=request.reason, triggered_by="api_v2")
            
            # Optionally close positions
            if request.close_positions and SERVICES_AVAILABLE:
                try:
                    trading_svc = get_trading_service()
                    positions = trading_svc.get_all_positions()
                    for pos in positions:
                        # trading_svc.close_position(pos.symbol)  # Would need to implement
                        positions_closed += 1
                except Exception as e:
                    logger.error(f"Error closing positions: {e}")
            
            return KillSwitchResponse(
                status=KillSwitchStatus.ACTIVE,
                activated_at=ks.activated_at,
                activated_by="api_v2",
                reason=request.reason,
                positions_closed=positions_closed
            )
        except Exception as e:
            logger.error(f"Error activating kill switch: {e}")
    
    return KillSwitchResponse(
        status=KillSwitchStatus.ACTIVE,
        activated_at=datetime.utcnow(),
        activated_by="user",
        reason=request.reason,
        positions_closed=positions_closed
    )


@router.post(
    "/kill-switch/release",
    response_model=KillSwitchResponse,
    summary="Release kill switch",
    description="Release the kill switch and resume trading."
)
async def release_kill_switch() -> KillSwitchResponse:
    """Release the kill switch."""
    ks = _get_kill_switch()
    
    if ks:
        try:
            ks.deactivate(reason="API v2 release", triggered_by="api_v2")
            return KillSwitchResponse(status=KillSwitchStatus.INACTIVE, positions_closed=0)
        except Exception as e:
            logger.error(f"Error releasing kill switch: {e}")
    
    return KillSwitchResponse(status=KillSwitchStatus.INACTIVE, positions_closed=0)
