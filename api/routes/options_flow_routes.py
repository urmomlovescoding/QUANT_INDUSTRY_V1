"""
Options Flow API Routes
=======================
REST endpoints for options flow data, unusual activity, gamma exposure, etc.
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/options-flow", tags=["Options Flow"])

# Try to import backend modules
try:
    from options_flow.unusual_activity import UnusualActivityDetector, DetectorConfig
    from options_flow.gamma_exposure import GammaExposureCalculator
    from options_flow.dark_pool import DarkPoolMonitor
    from options_flow.flow_signals import OptionsFlowSignals
    from options_flow.smart_money import SmartMoneyTracker
    
    detector = UnusualActivityDetector()
    gamma_calc = GammaExposureCalculator()
    dark_pool = DarkPoolMonitor()
    flow_signals = OptionsFlowSignals()
    smart_money = SmartMoneyTracker()
    MODULES_LOADED = True
except ImportError as e:
    logger.warning(f"Options flow modules not fully loaded: {e}")
    MODULES_LOADED = False


@router.get("/unusual")
async def get_unusual_activity(
    symbol: Optional[str] = None,
    min_premium: float = Query(25000, description="Minimum premium filter"),
    limit: int = Query(50, le=200)
):
    """Get unusual options activity."""
    if not MODULES_LOADED:
        return {
            "status": "unavailable",
            "message": "Options flow modules not loaded. Unusual activity detection requires the options_flow package.",
            "data": [],
            "total": 0,
            "filters": {"symbol": symbol, "min_premium": min_premium}
        }

    # Real implementation
    activities = detector.get_recent_activities(symbol=symbol, limit=limit)
    return {
        "data": [a.to_dict() for a in activities],
        "total": len(activities)
    }


@router.get("/gamma-exposure/{symbol}")
async def get_gamma_exposure(symbol: str):
    """Get gamma exposure profile for a symbol."""
    if not MODULES_LOADED:
        return {
            "status": "unavailable",
            "message": "Options flow modules not loaded. Gamma exposure calculation requires the options_flow package.",
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "profile": [],
            "key_levels": []
        }

    profile = gamma_calc.calculate(symbol)
    return profile.to_dict()


@router.get("/dark-pool")
async def get_dark_pool_prints(
    symbol: Optional[str] = None,
    min_value: float = Query(1000000, description="Minimum trade value"),
    limit: int = Query(50, le=200)
):
    """Get dark pool and block trade prints."""
    if not MODULES_LOADED:
        return {
            "status": "unavailable",
            "message": "Options flow modules not loaded. Dark pool monitoring requires the options_flow package.",
            "data": [],
            "total": 0,
            "aggregate": {}
        }

    prints = dark_pool.get_recent_prints(symbol=symbol, min_value=min_value, limit=limit)
    return {"data": [p.to_dict() for p in prints], "total": len(prints)}


@router.get("/signals")
async def get_flow_signals(
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None
):
    """Get options flow trading signals."""
    if not MODULES_LOADED:
        return {
            "status": "unavailable",
            "message": "Options flow modules not loaded. Flow signal generation requires the options_flow package.",
            "signals": []
        }

    signals = flow_signals.get_active_signals(symbol=symbol, signal_type=signal_type)
    return {"signals": [s.to_dict() for s in signals]}


@router.get("/smart-money")
async def get_smart_money_flow(symbol: Optional[str] = None):
    """Get smart money / institutional flow tracking."""
    if not MODULES_LOADED:
        return {
            "status": "unavailable",
            "message": "Options flow modules not loaded. Smart money tracking requires the options_flow package.",
            "institutional_activity": [],
            "sector_flow": {},
            "timestamp": datetime.now().isoformat()
        }

    flow = smart_money.get_current_flow(symbol=symbol)
    return flow.to_dict()
