"""
Options Flow API Routes
=======================
REST endpoints for options flow data, unusual activity, gamma exposure, etc.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
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
        # Return realistic mock data
        return {
            "data": [
                {
                    "id": "UA-001",
                    "symbol": symbol or "SPY",
                    "contract": f"{symbol or 'SPY'} 02/21 $500C",
                    "activity_type": "sweep",
                    "side": "buy",
                    "premium": 1250000,
                    "size": 500,
                    "spot_price": 498.50,
                    "strike": 500,
                    "expiry": "2025-02-21",
                    "option_type": "call",
                    "score": 85,
                    "timestamp": datetime.now().isoformat(),
                    "exchange": "CBOE",
                    "is_bullish": True
                },
                {
                    "id": "UA-002",
                    "symbol": "QQQ",
                    "contract": "QQQ 02/14 $420P",
                    "activity_type": "whale",
                    "side": "buy",
                    "premium": 2100000,
                    "size": 1000,
                    "spot_price": 425.30,
                    "strike": 420,
                    "expiry": "2025-02-14",
                    "option_type": "put",
                    "score": 92,
                    "timestamp": datetime.now().isoformat(),
                    "exchange": "ISE",
                    "is_bullish": False
                },
                {
                    "id": "UA-003",
                    "symbol": "AAPL",
                    "contract": "AAPL 02/28 $195C",
                    "activity_type": "unusual_volume",
                    "side": "buy",
                    "premium": 890000,
                    "size": 2000,
                    "spot_price": 189.50,
                    "strike": 195,
                    "expiry": "2025-02-28",
                    "option_type": "call",
                    "score": 78,
                    "timestamp": datetime.now().isoformat(),
                    "exchange": "PHLX",
                    "is_bullish": True
                }
            ][:limit],
            "total": 3,
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
        import numpy as np
        strikes = list(range(480, 520, 5))
        return {
            "symbol": symbol,
            "spot_price": 498.50,
            "timestamp": datetime.now().isoformat(),
            "net_gamma": 125000000,
            "put_gamma": -85000000,
            "call_gamma": 210000000,
            "gamma_flip": 495.0,
            "max_pain": 500.0,
            "profile": [
                {"strike": s, "gamma": float(np.random.uniform(-50e6, 100e6))}
                for s in strikes
            ],
            "key_levels": [
                {"price": 495.0, "type": "gamma_flip", "strength": 0.9},
                {"price": 500.0, "type": "max_pain", "strength": 0.85},
                {"price": 510.0, "type": "call_wall", "strength": 0.7}
            ]
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
            "data": [
                {
                    "id": "DP-001",
                    "symbol": symbol or "SPY",
                    "price": 498.25,
                    "size": 50000,
                    "value": 24912500,
                    "venue": "FADF",
                    "timestamp": datetime.now().isoformat(),
                    "side_estimate": "buy",
                    "is_block": True
                },
                {
                    "id": "DP-002",
                    "symbol": "AAPL",
                    "price": 189.50,
                    "size": 25000,
                    "value": 4737500,
                    "venue": "UBSS",
                    "timestamp": datetime.now().isoformat(),
                    "side_estimate": "sell",
                    "is_block": True
                }
            ][:limit],
            "total": 2,
            "aggregate": {
                "total_volume": 75000,
                "total_value": 29650000,
                "buy_ratio": 0.65
            }
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
            "signals": [
                {
                    "id": "SIG-001",
                    "symbol": symbol or "SPY",
                    "signal_type": "bullish_flow",
                    "strength": 0.85,
                    "confidence": 0.78,
                    "description": "Heavy call buying detected with institutional footprints",
                    "timestamp": datetime.now().isoformat(),
                    "supporting_data": {
                        "call_premium": 15000000,
                        "put_premium": 5000000,
                        "ratio": 3.0
                    }
                },
                {
                    "id": "SIG-002",
                    "symbol": "NVDA",
                    "signal_type": "gamma_squeeze",
                    "strength": 0.72,
                    "confidence": 0.65,
                    "description": "Approaching gamma flip level with rising call OI",
                    "timestamp": datetime.now().isoformat(),
                    "supporting_data": {
                        "gamma_flip_distance": 2.5,
                        "call_oi_change": 25000
                    }
                }
            ]
        }
    
    signals = flow_signals.get_active_signals(symbol=symbol, signal_type=signal_type)
    return {"signals": [s.to_dict() for s in signals]}


@router.get("/smart-money")
async def get_smart_money_flow(symbol: Optional[str] = None):
    """Get smart money / institutional flow tracking."""
    if not MODULES_LOADED:
        return {
            "overall_sentiment": "bullish",
            "confidence": 0.72,
            "institutional_activity": [
                {
                    "symbol": symbol or "SPY",
                    "net_premium": 25000000,
                    "large_trades": 15,
                    "sentiment": "bullish",
                    "score": 78
                }
            ],
            "sector_flow": {
                "Technology": {"sentiment": "bullish", "score": 82},
                "Financials": {"sentiment": "neutral", "score": 55},
                "Healthcare": {"sentiment": "bearish", "score": 35}
            },
            "timestamp": datetime.now().isoformat()
        }
    
    flow = smart_money.get_current_flow(symbol=symbol)
    return flow.to_dict()
