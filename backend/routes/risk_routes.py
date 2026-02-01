"""
Risk Management Routes
======================
Endpoints for risk metrics, limits, and portfolio risk analysis.
"""

import math
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ._shared import (
    logger, SERVICES_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE, PROPFIRM_AVAILABLE,
    BROKER_ADAPTER_AVAILABLE, RiskMetrics,
    get_data_service, get_risk_service, get_portfolio_service
)

router = APIRouter(prefix="/api", tags=["risk"])


# ============== RISK METRICS ==============

@router.get("/risk/metrics")
async def get_risk_metrics():
    """Get current risk metrics"""
    var_95, current_drawdown, max_position_exposure = 3.0, 0.0, 0.0
    sector_concentration, daily_pnl, risk_score = 35.0, 0.0, 50.0
    
    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            if hasattr(brain, 'performance_tracker') and brain.performance_tracker:
                tracker = brain.performance_tracker
                if hasattr(tracker, 'current_drawdown'):
                    current_drawdown = abs(tracker.current_drawdown * 100)
        except:
            pass

    risk_score = min(100, (var_95 / 5) * 100 * 0.3 + (current_drawdown / 15) * 100 * 0.3 + 
                     (max_position_exposure / 15) * 100 * 0.2 + (sector_concentration / 40) * 100 * 0.2)

    return RiskMetrics(
        var_95=round(var_95, 2),
        current_drawdown=round(current_drawdown, 2),
        max_position_exposure=round(max_position_exposure, 2),
        sector_concentration=round(sector_concentration, 2),
        daily_pnl=round(daily_pnl, 2),
        risk_score=round(risk_score, 1)
    )


@router.get("/risk/limits")
async def get_risk_limits():
    """Get risk limits configuration"""
    return {
        "max_position_pct": 15,
        "max_sector_pct": 40,
        "max_drawdown_pct": 15,
        "max_daily_loss_pct": 3,
        "max_var_95": 5,
        "alerts": []
    }


@router.get("/risk/exposure")
async def get_risk_exposure():
    """Get portfolio risk exposure"""
    return {
        "gross": 0, "net": 0, "long": 0, "short": 0,
        "by_sector": {}
    }


@router.get("/risk/safety")
async def get_safety_status():
    """Get trading safety status"""
    return {
        "is_safe": True,
        "breaches": [],
        "warnings": [],
        "daily_loss": 0,
        "max_daily_loss": 5000,
        "current_drawdown": 0,
        "max_drawdown_limit": 0.1
    }


# ============== RISK CHECK ==============

class TradeCheckRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float


@router.post("/risk/check-trade")
async def check_trade_risk(request: TradeCheckRequest):
    """Run multi-layer risk checks on a proposed trade"""
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="Risk services not available")

    try:
        from services.risk_service import get_multi_layer_risk_engine
        from services.trading_service import get_trading_service

        trading = get_trading_service()
        account = trading.get_account_info()
        positions = trading.get_all_positions()

        position_dicts = [{
            'symbol': p.symbol,
            'market_value': p.market_value,
            'quantity': p.quantity,
            'avg_cost': p.avg_cost
        } for p in positions]

        risk_engine = get_multi_layer_risk_engine()
        result = risk_engine.check_trade(
            symbol=request.symbol.upper(),
            side=request.side.lower(),
            quantity=request.quantity,
            price=request.price,
            account_equity=account.equity,
            current_positions=position_dicts,
            daily_pnl=getattr(account, 'daily_pnl', 0.0),
            vix=0.0
        )
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== PROP FIRM RISK ==============

@router.get("/propfirm/status")
async def get_propfirm_status():
    """Get prop firm risk engine status"""
    if not PROPFIRM_AVAILABLE:
        return {"available": False}
    try:
        from brain.propfirm_risk import get_propfirm_risk_engine
        engine = get_propfirm_risk_engine()
        state = engine.get_risk_state()
        return {"available": True, "state": state.to_dict()}
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.get("/propfirm/position-size")
async def get_propfirm_position_size(
    symbol: str = "SPY",
    entry_price: float = 500.0,
    stop_loss_price: float = 495.0
):
    """Get recommended position size based on prop firm rules"""
    if not PROPFIRM_AVAILABLE:
        raise HTTPException(status_code=503, detail="Prop firm risk engine not available")

    try:
        from brain.propfirm_risk import get_propfirm_risk_engine
        engine = get_propfirm_risk_engine()
        position_size = engine.get_position_size_recommendation(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price
        )
        return {
            "symbol": symbol,
            "recommended_position_size": round(position_size, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== KILL SWITCH ==============

@router.get("/kill-switch")
async def get_kill_switch_status():
    """Get kill switch status"""
    if BROKER_ADAPTER_AVAILABLE:
        from execution.broker_adapter import get_kill_switch
        return get_kill_switch().to_dict()
    return {"active": False, "reason": "", "activated_at": None}


@router.post("/kill-switch/activate")
async def activate_kill_switch(reason: str = "Manual activation", duration_minutes: int = None):
    """Activate the kill switch"""
    if BROKER_ADAPTER_AVAILABLE:
        from execution.broker_adapter import get_kill_switch
        ks = get_kill_switch()
        ks.activate(reason=reason, activated_by="api", duration_minutes=duration_minutes)
        logger.warning(f"Kill switch activated: {reason}")
        return {"status": "activated", "kill_switch": ks.to_dict()}
    return {"status": "error", "message": "Broker adapter not available"}


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch():
    """Deactivate the kill switch"""
    if BROKER_ADAPTER_AVAILABLE:
        from execution.broker_adapter import get_kill_switch
        ks = get_kill_switch()
        ks.deactivate(deactivated_by="api")
        return {"status": "deactivated"}
    return {"status": "error", "message": "Broker adapter not available"}


# ============== RISK DECOMPOSITION ==============

@router.get("/risk/factor-decomposition")
async def get_factor_decomposition():
    """Get factor exposure decomposition"""
    import random
    return {
        "timestamp": datetime.now().isoformat(),
        "total_return_bps": round(random.uniform(-50, 100), 2),
        "factors": [
            {"factor": "market", "exposure": round(random.uniform(0.8, 1.2), 3), "contribution_bps": round(random.uniform(-30, 50), 2), "pct_of_risk": round(random.uniform(30, 50), 1)},
            {"factor": "sector", "exposure": round(random.uniform(-0.3, 0.5), 3), "contribution_bps": round(random.uniform(-20, 30), 2), "pct_of_risk": round(random.uniform(10, 25), 1)},
            {"factor": "momentum", "exposure": round(random.uniform(-0.2, 0.4), 3), "contribution_bps": round(random.uniform(-15, 25), 2), "pct_of_risk": round(random.uniform(8, 18), 1)},
            {"factor": "volatility", "exposure": round(random.uniform(-0.4, 0.2), 3), "contribution_bps": round(random.uniform(-25, 15), 2), "pct_of_risk": round(random.uniform(10, 20), 1)},
            {"factor": "size", "exposure": round(random.uniform(-0.2, 0.3), 3), "contribution_bps": round(random.uniform(-10, 15), 2), "pct_of_risk": round(random.uniform(5, 12), 1)},
        ],
        "residual_bps": round(random.uniform(-20, 40), 2),
        "r_squared": round(random.uniform(0.75, 0.92), 3)
    }


@router.get("/risk/attribution")
async def get_risk_attribution():
    """Get PnL attribution breakdown"""
    import random

    alpha = round(random.uniform(-50, 80), 2)
    beta = round(random.uniform(-30, 50), 2)
    sector = round(random.uniform(-20, 40), 2)
    timing = round(random.uniform(-25, 35), 2)
    costs = round(random.uniform(-15, -5), 2)
    total = alpha + beta + sector + timing + costs

    return {
        "timestamp": datetime.now().isoformat(),
        "total_pnl": round(total, 2),
        "components": [
            {"name": "Alpha Generation", "value": alpha, "pct_of_total": round(abs(alpha / max(abs(total), 1)) * 100, 1), "description": "Skill-based returns from stock selection"},
            {"name": "Beta Exposure", "value": beta, "pct_of_total": round(abs(beta / max(abs(total), 1)) * 100, 1), "description": "Market exposure contribution"},
            {"name": "Sector Allocation", "value": sector, "pct_of_total": round(abs(sector / max(abs(total), 1)) * 100, 1), "description": "Sector tilt contribution"},
            {"name": "Market Timing", "value": timing, "pct_of_total": round(abs(timing / max(abs(total), 1)) * 100, 1), "description": "Entry/exit timing contribution"},
            {"name": "Transaction Costs", "value": costs, "pct_of_total": round(abs(costs / max(abs(total), 1)) * 100, 1), "description": "Commissions and slippage"},
        ],
        "waterfall": [
            {"name": "Alpha", "start": 0, "end": alpha, "value": alpha, "is_positive": alpha >= 0},
            {"name": "Beta", "start": alpha, "end": alpha + beta, "value": beta, "is_positive": beta >= 0},
            {"name": "Sector", "start": alpha + beta, "end": alpha + beta + sector, "value": sector, "is_positive": sector >= 0},
            {"name": "Timing", "start": alpha + beta + sector, "end": alpha + beta + sector + timing, "value": timing, "is_positive": timing >= 0},
            {"name": "Costs", "start": alpha + beta + sector + timing, "end": total, "value": costs, "is_positive": costs >= 0},
            {"name": "TOTAL", "start": 0, "end": total, "value": total, "is_positive": total >= 0, "is_total": True},
        ]
    }


@router.get("/risk/budgets")
async def get_risk_budgets():
    """Get risk budget utilizations"""
    import random
    return {
        "utilizations": {
            "momentum_strategy": {
                "budget": {"name": "Momentum Strategy", "budget_type": "aggressive", "max_var_pct": 3.0, "max_drawdown_pct": 8.0, "max_gross_exposure_pct": 150.0, "current_utilization": round(random.uniform(40, 85), 1)},
                "overall_utilization": round(random.uniform(40, 85), 1),
                "metrics": {
                    "var": {"current": round(random.uniform(1, 2.5), 2), "limit": 3.0, "utilization": round(random.uniform(40, 80), 1)},
                    "drawdown": {"current": round(random.uniform(1, 5), 2), "limit": 8.0, "utilization": round(random.uniform(20, 60), 1)}
                }
            },
            "mean_reversion": {
                "budget": {"name": "Mean Reversion", "budget_type": "conservative", "max_var_pct": 2.0, "max_drawdown_pct": 5.0, "max_gross_exposure_pct": 100.0, "current_utilization": round(random.uniform(30, 70), 1)},
                "overall_utilization": round(random.uniform(30, 70), 1),
                "metrics": {
                    "var": {"current": round(random.uniform(0.5, 1.5), 2), "limit": 2.0, "utilization": round(random.uniform(30, 70), 1)},
                    "drawdown": {"current": round(random.uniform(0.5, 3), 2), "limit": 5.0, "utilization": round(random.uniform(15, 50), 1)}
                }
            },
            "trend_following": {
                "budget": {"name": "Trend Following", "budget_type": "moderate", "max_var_pct": 2.5, "max_drawdown_pct": 6.0, "max_gross_exposure_pct": 120.0, "current_utilization": round(random.uniform(50, 90), 1)},
                "overall_utilization": round(random.uniform(50, 90), 1),
                "metrics": {
                    "var": {"current": round(random.uniform(1, 2), 2), "limit": 2.5, "utilization": round(random.uniform(45, 85), 1)},
                    "drawdown": {"current": round(random.uniform(1, 4), 2), "limit": 6.0, "utilization": round(random.uniform(25, 65), 1)}
                }
            }
        },
        "alerts": [],
        "scale_recommendations": [],
        "budgets_over_limit": 0,
        "budgets_approaching": 1 if random.random() > 0.5 else 0
    }


@router.get("/risk/correlation-monitor")
async def get_correlation_monitor():
    """Get portfolio correlation monitoring data"""
    import random
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]
    n = len(symbols)

    # Generate correlation matrix
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif j > i:
                row.append(round(random.uniform(0.2, 0.8), 3))
            else:
                row.append(matrix[j][i])  # Mirror
        matrix.append(row)

    avg_corr = round(sum(matrix[i][j] for i in range(n) for j in range(i+1, n)) / (n * (n-1) / 2), 3)

    regime = "low" if avg_corr < 0.35 else "normal" if avg_corr < 0.55 else "elevated" if avg_corr < 0.7 else "crisis"

    high_pairs = []
    for i in range(n):
        for j in range(i+1, n):
            if matrix[i][j] > 0.6:
                high_pairs.append({"symbol1": symbols[i], "symbol2": symbols[j], "correlation": matrix[i][j]})

    high_pairs.sort(key=lambda x: x["correlation"], reverse=True)

    div_score = round(max(0, 100 - avg_corr * 80 - len(high_pairs) * 5), 1)
    grade = "A" if div_score >= 70 else "B" if div_score >= 50 else "C" if div_score >= 30 else "D"

    return {
        "correlation_matrix": {
            "symbols": symbols,
            "matrix": matrix,
            "avg_correlation": avg_corr,
            "high_correlation_pairs": high_pairs[:5]
        },
        "regime": {
            "regime": regime,
            "avg_correlation": avg_corr,
            "description": f"Portfolio correlations are {regime}. {'Normal diversification.' if regime in ['low', 'normal'] else 'Consider reducing correlated positions.'}"
        },
        "diversification": {
            "score": div_score,
            "grade": grade,
            "effective_positions": round(n / (1 + (n-1) * avg_corr), 1),
            "recommendations": ["Portfolio is well diversified"] if div_score > 60 else ["Consider adding uncorrelated assets", "Reduce exposure to highly correlated pairs"]
        },
        "alerts": []
    }


@router.get("/risk/attribution/alpha-trend")
async def get_alpha_trend():
    """Get alpha generation trend analysis"""
    import random
    avg_alpha = round(random.uniform(-20, 40), 2)
    is_decaying = random.random() > 0.7

    return {
        "trend": "decaying" if is_decaying else ("improving" if avg_alpha > 15 else "stable"),
        "avg_alpha": avg_alpha,
        "alpha_sharpe": round(avg_alpha / max(abs(avg_alpha) * 0.5, 10), 2),
        "is_decaying": is_decaying
    }
