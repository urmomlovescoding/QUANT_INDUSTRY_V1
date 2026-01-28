"""
QUANT INDUSTRY - Risk API Routes
================================
REST API endpoints for risk monitoring and analysis.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import risk modules
import sys
sys.path.insert(0, '..')

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskSummaryResponse(BaseModel):
    """Risk summary response model"""
    status: str
    timestamp: str
    portfolio: dict
    risk_metrics: dict
    alerts: dict
    thresholds: dict


class AlertResponse(BaseModel):
    """Alert response model"""
    timestamp: str
    type: str
    severity: str
    message: str
    metric: str
    current: float
    threshold: float
    symbol: str
    acknowledged: bool


class MonteCarloRequest(BaseModel):
    """Monte Carlo simulation request"""
    daily_return: float = 0.0005
    daily_volatility: float = 0.015
    initial_capital: float = 100000
    n_simulations: int = 1000
    n_days: int = 252
    scenario: str = "normal"


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation response"""
    mean_return: float
    median_return: float
    var_95: float
    var_99: float
    cvar_95: float
    max_drawdown_mean: float
    max_drawdown_95th: float
    prob_loss: float
    prob_ruin: float


@router.get("/summary", response_model=RiskSummaryResponse)
async def get_risk_summary():
    """Get current risk monitoring summary"""
    try:
        from risk import get_risk_monitor
        monitor = get_risk_monitor()
        summary = monitor.get_risk_summary()
        return RiskSummaryResponse(
            status=summary.get("status", "unknown"),
            timestamp=datetime.now().isoformat(),
            portfolio=summary.get("portfolio", {}),
            risk_metrics=summary.get("risk_metrics", {}),
            alerts=summary.get("alerts", {}),
            thresholds=summary.get("thresholds", {})
        )
    except Exception as e:
        # Return default values if monitor not available
        return RiskSummaryResponse(
            status="offline",
            timestamp=datetime.now().isoformat(),
            portfolio={"equity": 0, "drawdown_pct": 0, "daily_pnl": 0, "daily_loss_pct": 0},
            risk_metrics={"var_95_pct": 0, "position_count": 0},
            alerts={"active_count": 0, "total_generated": 0, "critical_count": 0},
            thresholds={"drawdown_limit": 10, "daily_loss_limit": 3, "var_limit": 5}
        )


@router.get("/alerts", response_model=List[AlertResponse])
async def get_active_alerts():
    """Get all active risk alerts"""
    try:
        from risk import get_risk_monitor
        monitor = get_risk_monitor()
        alerts = monitor.get_active_alerts()
        return [AlertResponse(**alert) for alert in alerts]
    except Exception as e:
        return []


@router.post("/alerts/{alert_key}/acknowledge")
async def acknowledge_alert(alert_key: str):
    """Acknowledge a risk alert"""
    try:
        from risk import get_risk_monitor
        monitor = get_risk_monitor()
        monitor.acknowledge_alert(alert_key)
        return {"status": "acknowledged", "alert_key": alert_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/montecarlo/simulate", response_model=MonteCarloResponse)
async def run_monte_carlo(request: MonteCarloRequest):
    """Run Monte Carlo stress test simulation"""
    try:
        from risk import MonteCarloSimulator, StressScenario
        
        # Map scenario string to enum
        scenario_map = {
            "normal": StressScenario.NORMAL,
            "high_vol": StressScenario.HIGH_VOL,
            "crisis_2008": StressScenario.CRISIS_2008,
            "covid_crash": StressScenario.COVID_CRASH,
            "flash_crash": StressScenario.FLASH_CRASH,
            "black_swan": StressScenario.BLACK_SWAN,
        }
        
        scenario = scenario_map.get(request.scenario.lower(), StressScenario.NORMAL)
        
        sim = MonteCarloSimulator(
            daily_return=request.daily_return,
            daily_volatility=request.daily_volatility,
            initial_capital=request.initial_capital
        )
        
        result = sim.run(
            n_simulations=min(request.n_simulations, 10000),  # Cap at 10k
            n_days=min(request.n_days, 504),  # Cap at 2 years
            scenario=scenario
        )
        
        return MonteCarloResponse(
            mean_return=result.mean_return,
            median_return=result.median_return,
            var_95=result.var_95,
            var_99=result.var_99,
            cvar_95=result.cvar_95,
            max_drawdown_mean=result.max_drawdown_mean,
            max_drawdown_95th=result.max_drawdown_95th,
            prob_loss=result.prob_loss,
            prob_ruin=result.prob_ruin
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/var")
async def calculate_var(
    position_value: float = Query(100000, description="Position value"),
    daily_vol: float = Query(0.02, description="Daily volatility"),
    confidence: float = Query(0.95, description="Confidence level"),
    holding_days: int = Query(1, description="Holding period")
):
    """Calculate Value at Risk for a position"""
    try:
        from risk import quick_var
        
        var = quick_var(
            position_value=position_value,
            daily_vol=daily_vol,
            confidence=confidence,
            holding_days=holding_days
        )
        
        return {
            "var": var,
            "var_pct": var / position_value * 100,
            "position_value": position_value,
            "confidence": confidence,
            "holding_days": holding_days
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
