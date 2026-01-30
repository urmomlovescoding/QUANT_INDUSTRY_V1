"""
QUANT INDUSTRY - Data Integrity Router
=======================================
Handles data integrity and mode management endpoints:
- Data mode (LIVE, PAPER, BACKTEST, SIMULATION)
- Data integrity status and provenance
- Data staleness monitoring

Extracted from main.py to improve maintainability.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Data Integrity"])

# ============== SERVICE AVAILABILITY ==============

_DATA_INTEGRITY_AVAILABLE = False
_data_integrity_module = None

try:
    from core.data_integrity import (
        DataMode,
        get_data_mode,
        get_price_truth,
        get_quality_stats,
        set_data_mode,
    )
    _DATA_INTEGRITY_AVAILABLE = True
except ImportError:
    pass


# ============== MODELS ==============


class DataModeRequest(BaseModel):
    mode: str = Field(
        ...,
        description="Data mode: live, paper, backtest, or simulation",
        pattern="^(live|paper|backtest|simulation)$",
    )
    reason: str = Field(
        default="API request",
        description="Reason for mode change",
        max_length=200,
    )


# ============== ROUTES ==============


@router.get("/data-integrity/mode")
async def get_current_data_mode():
    """
    Get current data mode and integrity status.

    Returns the active data mode along with descriptions of all available modes
    and current quality statistics.
    """
    if not _DATA_INTEGRITY_AVAILABLE:
        return {
            "mode": "unknown",
            "available": False,
            "_note": "Data integrity layer not loaded",
        }

    mode = get_data_mode()
    quality_stats = get_quality_stats()

    mode_descriptions = {
        "live": "Real broker connection, real money at risk",
        "paper": "Paper trading with real market prices",
        "backtest": "Historical simulation",
        "simulation": "Demo mode with synthetic data",
    }

    return {
        "mode": mode.value,
        "available": True,
        "modes": {k.upper(): v for k, v in mode_descriptions.items()},
        "current_description": mode_descriptions.get(mode.value, "Unknown mode"),
        "quality_stats": quality_stats,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/data-integrity/mode")
async def set_current_data_mode(request: DataModeRequest):
    """
    Set data mode (live, paper, backtest, simulation).

    WARNING: Setting to 'live' enables real trading with real money.
    Mode changes are logged for audit purposes.
    """
    if not _DATA_INTEGRITY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Data integrity layer not available",
        )

    try:
        new_mode = DataMode(request.mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {request.mode}. Must be one of: live, paper, backtest, simulation",
        )

    if new_mode == DataMode.LIVE:
        logger.warning(f"LIVE MODE REQUESTED - Reason: {request.reason}")

    success = set_data_mode(new_mode, request.reason)

    if not success:
        raise HTTPException(
            status_code=403,
            detail="Cannot change to this mode - mode is locked",
        )

    return {
        "mode": new_mode.value,
        "changed": True,
        "reason": request.reason,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/data-integrity/status/v2")
async def get_data_integrity_status():
    """
    Get comprehensive data integrity status.

    Returns current mode, sample price data with provenance information,
    and overall quality statistics.
    """
    if not _DATA_INTEGRITY_AVAILABLE:
        return {"available": False}

    sample_symbols = ["SPY", "QQQ", "AAPL"]
    prices = {}

    for symbol in sample_symbols:
        try:
            truth = get_price_truth(symbol)
            prices[symbol] = truth.to_dict()
        except Exception as e:
            logger.debug(f"Price truth failed for {symbol}: {e}")
            prices[symbol] = {"error": str(e)}

    return {
        "available": True,
        "mode": get_data_mode().value,
        "sample_prices": prices,
        "quality_stats": get_quality_stats(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/data-integrity/price/{symbol}")
async def get_price_with_provenance(symbol: str):
    """
    Get price with full provenance information.

    Returns the current price along with source, quality, and staleness
    metadata via the data integrity layer.
    """
    if not _DATA_INTEGRITY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Data integrity layer not available",
        )

    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 10:
        raise HTTPException(
            status_code=400,
            detail="Invalid symbol format",
        )

    try:
        truth = get_price_truth(symbol)
        return truth.to_dict()
    except Exception as e:
        logger.error(f"Price provenance failed for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get price provenance for {symbol}",
        )


@router.get("/data-integrity/staleness")
async def get_data_staleness():
    """
    Get data staleness status and alerts.

    Monitors data freshness for quotes, historical data, and options.
    Returns per-category staleness levels and any active alerts.
    """
    try:
        from services.data_service import get_staleness_tracker
        tracker = get_staleness_tracker()
        return tracker.get_staleness_summary()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Staleness tracker not available",
        )
    except Exception as e:
        logger.error(f"Staleness check error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to check data staleness",
        )


@router.get("/data-integrity/staleness/{symbol}")
async def check_symbol_staleness(
    symbol: str,
    data_type: str = Query(
        default="quote",
        description="Data type to check staleness for",
        pattern="^(quote|historical|options)$",
    ),
):
    """
    Check staleness for a specific symbol and data type.

    Returns the staleness level (fresh, stale, very_stale) and any
    associated alert information.
    """
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid symbol format")

    try:
        from services.data_service import StalenessLevel, get_staleness_tracker
        tracker = get_staleness_tracker()
        level, alert = tracker.check_staleness(
            symbol=symbol,
            data_type=data_type,
        )
        return {
            "symbol": symbol,
            "data_type": data_type,
            "staleness_level": level.value,
            "is_fresh": level == StalenessLevel.FRESH,
            "is_usable": level in (StalenessLevel.FRESH, StalenessLevel.STALE),
            "alert": {
                "message": alert.message,
                "age_seconds": alert.age_seconds,
                "threshold_seconds": alert.threshold_seconds,
            }
            if alert
            else None,
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Staleness tracker not available",
        )
    except Exception as e:
        logger.error(f"Staleness check error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check staleness for {symbol}",
        )
