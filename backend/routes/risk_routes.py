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
