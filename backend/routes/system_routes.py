"""
System Routes
=============
Endpoints for health checks, system status, settings, and configuration.
"""

import os
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE, MARKET_HOURS_AVAILABLE,
    PROPFIRM_BRAIN_V6_AVAILABLE, BEAST_AVAILABLE, RL_AVAILABLE, DL_AVAILABLE,
    DATA_INTEGRITY_AVAILABLE, BROKER_ADAPTER_AVAILABLE,
    MARKET_DATA, get_data_service, get_health_service
)

router = APIRouter(prefix="/api", tags=["system"])


# ============== HEALTH CHECKS ==============

@router.get("/health")
async def health_check():
    """Health check with market status, data source info, and system state"""
    market_info = {}
    if MARKET_HOURS_AVAILABLE:
        try:
            from services.market_hours import get_market_status
            market_info = get_market_status()
        except Exception as e:
            logger.warning(f"Market status failed: {e}")
            market_info = {"session": "unknown", "error": str(e)}

    # Data source status
    data_status = {
        "is_live": False,
        "primary_source": "none",
        "active_sources": [],
        "last_update": None,
        "quality_score": 0.0
    }

    if SERVICES_AVAILABLE:
        try:
            ds = get_data_service()
            active_sources = []
            for source in ds.sources:
                source_name = getattr(source, 'name', '').lower()
                if source_name and source_name != 'fallback':
                    active_sources.append(source_name)

            data_status["active_sources"] = active_sources
            data_status["is_live"] = len(active_sources) > 0
            data_status["primary_source"] = active_sources[0] if active_sources else "fallback"
        except Exception as e:
            logger.debug(f"Data status check: {e}")

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "market": market_info,
        "data": data_status,
        "services": {
            "data_service": SERVICES_AVAILABLE,
            "brain_v6": PROPFIRM_BRAIN_V6_AVAILABLE,
            "broker_adapter": BROKER_ADAPTER_AVAILABLE,
            "market_hours": MARKET_HOURS_AVAILABLE
        }
    }


@router.get("/system/health")
async def get_system_health():
    """Get detailed system health"""
    if SERVICES_AVAILABLE:
        try:
            hs = get_health_service()
            return hs.get_detailed_status()
        except Exception as e:
            logger.error(f"Error getting system health: {e}")

    return {
        "status": "OK",
        "services_available": SERVICES_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/system/status")
async def get_system_status():
    """Get comprehensive system status including data source mode"""
    try:
        ds = get_data_service()
        active_sources = []
        data_mode = "OFFLINE"

        if ds:
            for source in ds.sources:
                source_info = {"name": source.name, "available": True}
                if source.name in ["alpaca", "tradier", "finnhub"]:
                    if hasattr(source, 'api_key') and source.api_key:
                        source_info["has_key"] = True
                        active_sources.append(source_info)
                        data_mode = "LIVE"
                elif source.name == "yahoo":
                    active_sources.append(source_info)
                    if data_mode != "LIVE":
                        data_mode = "DELAYED"

        env_keys = {
            "ALPACA_API_KEY": bool(os.getenv("ALPACA_API_KEY")),
            "TRADIER_API_KEY": bool(os.getenv("TRADIER_API_KEY")),
            "FINNHUB_API_KEY": bool(os.getenv("FINNHUB_API_KEY"))
        }

        return {
            "status": "online",
            "version": "10.0",
            "data_mode": data_mode,
            "is_live_data": data_mode == "LIVE",
            "timestamp": datetime.now().isoformat(),
            "data_sources": active_sources,
            "api_keys": env_keys,
            "services": {
                "brain_v6": PROPFIRM_BRAIN_V6_AVAILABLE,
                "beast_ml": BEAST_AVAILABLE,
                "rl_engine": RL_AVAILABLE,
                "dl_engine": DL_AVAILABLE,
                "market_hours": MARKET_HOURS_AVAILABLE,
                "services_loaded": SERVICES_AVAILABLE
            }
        }
    except Exception as e:
        logger.error(f"System status error: {e}")
        return {"status": "error", "data_mode": "OFFLINE", "error": str(e)}


@router.get("/system/memory")
async def get_system_memory():
    """Get detailed memory usage status with trend analysis."""
    try:
        from services.health_service import get_memory_monitor
        monitor = get_memory_monitor()
        status = monitor.get_current_status()
        trend = monitor.get_memory_trend()
        return {**status, 'trend': trend}
    except Exception as e:
        logger.error(f"Memory monitor error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/resources")
async def get_system_resources():
    """Get real-time system resource usage (CPU, Memory, GPU)"""
    if SERVICES_AVAILABLE:
        try:
            hs = get_health_service()
            metrics = hs.get_system_metrics()
            return metrics.to_dict()
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")

    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "gpu_available": False,
        "gpu_percent": 0,
    }


@router.get("/system/ml-capabilities")
async def get_ml_capabilities():
    """Get ML/DL/RL capabilities and GPU status"""
    if SERVICES_AVAILABLE:
        try:
            from services.health_service import (
                DEVICE, GPU_MEMORY_TOTAL, GPU_NAME, HAS_CUDA,
                get_gpu_utilization, get_ml_capabilities as fetch_ml_caps
            )
            caps = fetch_ml_caps()
            gpu = get_gpu_utilization()

            return {
                "capabilities": caps,
                "gpu": {
                    "available": HAS_CUDA,
                    "name": GPU_NAME,
                    "memory_total_gb": GPU_MEMORY_TOTAL,
                    "memory_used_gb": gpu['gpu_memory_used'],
                    "utilization_percent": gpu['gpu_percent'],
                },
                "device": DEVICE,
            }
        except Exception as e:
            logger.error(f"Error getting ML capabilities: {e}")

    return {"capabilities": {}, "gpu": {"available": False}, "device": "cpu"}


# ============== DATA INTEGRITY ==============

@router.get("/data-mode")
async def get_current_data_mode():
    """Get current data mode and integrity status"""
    if not DATA_INTEGRITY_AVAILABLE:
        return {"mode": "unknown", "available": False}

    from core.data_integrity import get_data_mode, get_quality_stats
    mode = get_data_mode()
    quality_stats = get_quality_stats()

    return {
        "mode": mode.value,
        "available": True,
        "quality_stats": quality_stats,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/data-mode")
async def set_current_data_mode(mode: str, reason: str = "API request"):
    """Set data mode (LIVE, PAPER, BACKTEST, SIMULATION)."""
    if not DATA_INTEGRITY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Data integrity layer not available")

    from core.data_integrity import DataMode, set_data_mode

    try:
        new_mode = DataMode(mode.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    if new_mode.value == "live":
        logger.warning(f"LIVE MODE REQUESTED - Reason: {reason}")

    success = set_data_mode(new_mode, reason)
    if not success:
        raise HTTPException(status_code=403, detail="Cannot change to this mode - mode is locked")

    return {"mode": new_mode.value, "changed": True, "reason": reason}


# ============== SETTINGS ==============

@router.get("/settings")
async def get_settings():
    """Get current settings"""
    if SERVICES_AVAILABLE:
        from config.settings import get_settings
        settings = get_settings()
        return settings.to_dict()
    return {"error": "Settings service not available"}


@router.post("/settings")
async def update_settings(updates: Dict[str, Any]):
    """Update settings"""
    if SERVICES_AVAILABLE:
        from config.settings import update_settings
        settings = update_settings(updates)
        return settings.to_dict()
    raise HTTPException(status_code=500, detail="Settings service not available")


@router.put("/settings")
async def update_settings_put(settings_data: Dict[str, Any]):
    """PUT endpoint for settings update"""
    return await update_settings(settings_data)


@router.get("/settings/presets")
async def get_ui_presets():
    """Get available UI presets"""
    if SERVICES_AVAILABLE:
        from config.settings import get_available_presets, UI_PRESETS
        return {"presets": get_available_presets(), "details": UI_PRESETS}
    return {"presets": [], "details": {}}


@router.post("/settings/preset/{preset_name}")
async def apply_preset(preset_name: str):
    """Apply a UI preset"""
    if SERVICES_AVAILABLE:
        from config.settings import apply_ui_preset
        settings = apply_ui_preset(preset_name)
        return settings.to_dict()
    raise HTTPException(status_code=500, detail="Settings service not available")


# ============== API KEYS ==============

@router.get("/settings/api-keys")
async def get_api_keys():
    """Get API keys status (masked)"""
    if SERVICES_AVAILABLE:
        from config.api_keys import get_api_keys
        keys = get_api_keys()
        return keys.to_safe_dict()
    return {"error": "API keys service not available"}


@router.post("/settings/api-keys/{provider}")
async def update_api_key(provider: str, key_data: Dict[str, str]):
    """Update API key for a provider"""
    if SERVICES_AVAILABLE:
        from config.api_keys import update_api_key
        keys = update_api_key(provider, key_data)
        return keys.to_safe_dict()
    raise HTTPException(status_code=500, detail="API keys service not available")


@router.post("/settings/api-keys")
async def save_api_keys(data: Dict[str, Any]):
    """Save API keys for a provider"""
    provider = data.get("provider")
    key_data = data.get("keys", {})
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required")

    if SERVICES_AVAILABLE:
        from config.api_keys import update_api_key
        keys = update_api_key(provider, key_data)
        return {"success": True, "keys": keys.to_safe_dict()}
    return {"success": True, "provider": provider}


@router.get("/settings/api-keys/{provider}/test")
async def test_api_connection(provider: str):
    """Test API connection for a provider"""
    if SERVICES_AVAILABLE:
        from config.api_keys import test_api_connection
        return test_api_connection(provider)
    return {"provider": provider, "success": False, "message": "Service not available"}


# ============== MODULES STATUS ==============

@router.get("/modules/status")
async def get_all_modules_status():
    """Get status of all parity modules"""
    from ._shared import (
        ICT_AVAILABLE, MARKET_MEMORY_AVAILABLE, REGIME_DISCOVERY_AVAILABLE,
        TPT_AGGRESSIVE_AVAILABLE, TRADE_JOURNAL_AVAILABLE, LEARNING_CENTER_AVAILABLE
    )
    return {
        "ict_strategies": ICT_AVAILABLE,
        "market_memory": MARKET_MEMORY_AVAILABLE,
        "regime_discovery": REGIME_DISCOVERY_AVAILABLE,
        "tpt_aggressive": TPT_AGGRESSIVE_AVAILABLE,
        "trade_journal": TRADE_JOURNAL_AVAILABLE,
        "broker_adapter": BROKER_ADAPTER_AVAILABLE,
        "learning_center": LEARNING_CENTER_AVAILABLE,
        "brain_v6": PROPFIRM_BRAIN_V6_AVAILABLE,
        "beast_ml": BEAST_AVAILABLE,
        "rl_engine": RL_AVAILABLE,
        "dl_engine": DL_AVAILABLE
    }


# ============== CACHE MANAGEMENT ==============

@router.post("/system/clear-cache")
async def clear_system_cache():
    """Clear all cached data"""
    try:
        ds = get_data_service()
        if ds and hasattr(ds, 'cache_lock'):
            with ds.cache_lock:
                ds.cache.clear()
        return {"status": "cleared", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
