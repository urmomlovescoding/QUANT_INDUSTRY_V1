"""
Brain Routes
============
Endpoints for Brain V6, BEAST ML, RL, DL, Evolution, and Neural Analysis.
"""

import math
from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE,
    BEAST_AVAILABLE, RL_AVAILABLE, DL_AVAILABLE, EVOLUTION_AVAILABLE,
    get_data_service, get_neural_engine, get_regime_detector
)

router = APIRouter(prefix="/api", tags=["brain"])


# ============== BRAIN V6 ==============
# NOTE: /brain-v6/status is defined in api/routes/core_routes.py (authoritative).

@router.get("/brain-v6/signal/{symbol}")
async def get_brain_v6_signal(symbol: str, lookback_days: int = 60):
    """Generate trading signal from Brain V6"""
    if not PROPFIRM_BRAIN_V6_AVAILABLE or not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="Brain V6 not available")
    try:
        import pandas as pd
        from brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()
        ds = get_data_service()
        data = ds.get_historical(symbol.upper(), f"{lookback_days}d", "1d")
        df = pd.DataFrame([{
            'timestamp': d.timestamp, 'open': d.open, 'high': d.high,
            'low': d.low, 'close': d.close, 'volume': d.volume
        } for d in data])
        df.set_index('timestamp', inplace=True)
        return brain.generate_signal(df, symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/brain-v6/train")
async def train_brain_v6(config: Dict[str, Any] = None):
    """Trigger training step for Brain V6"""
    if not PROPFIRM_BRAIN_V6_AVAILABLE:
        raise HTTPException(status_code=503, detail="Brain V6 not available")
    try:
        from brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()
        if config:
            for k, v in config.items():
                if hasattr(brain.config, k):
                    setattr(brain.config, k, v)
        result = brain.train_step()
        return {"trained": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brain-v6/strategies")
async def get_brain_v6_strategies():
    """Get strategy ensemble performance"""
    if not PROPFIRM_BRAIN_V6_AVAILABLE:
        raise HTTPException(status_code=503, detail="Brain V6 not available")
    try:
        from brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()
        return {
            "strategies": [{
                "name": s.name,
                "weight": s.weight,
                "win_rate": s.win_rate,
                "pnl": s.total_pnl,
                "trades": s.total_trades
            } for s in brain.strategy_ensemble.strategies]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== NEURAL ANALYSIS ==============

@router.get("/neural/analysis/{symbol}")
async def get_neural_analysis(symbol: str, lookback: str = "6M"):
    """Get neural pattern analysis"""
    symbol = symbol.upper()
    try:
        ds = get_data_service()
        period_map = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
        historical = ds.get_historical(symbol, period=period_map.get(lookback, "6mo"), interval="1d")

        if not historical or len(historical) < 20:
            raise HTTPException(status_code=404, detail=f"Insufficient data for {symbol}")

        ohlcv_data = [{
            "open": bar.open, "high": bar.high, "low": bar.low,
            "close": bar.close, "volume": bar.volume,
            "timestamp": bar.timestamp.isoformat() if hasattr(bar.timestamp, 'isoformat') else str(bar.timestamp)
        } for bar in historical]

        neural_engine = get_neural_engine()
        analysis = neural_engine.analyze(symbol, ohlcv_data)

        return {
            "symbol": symbol,
            "current_price": round(analysis.current_price, 2),
            "trend": {"direction": analysis.trend, "strength": round(analysis.trend_strength, 2)},
            "patterns_detected": [p.pattern.value for p in analysis.patterns[:5]],
            "support_levels": [round(s, 2) for s in analysis.support_levels],
            "resistance_levels": [round(r, 2) for r in analysis.resistance_levels],
            "recommendation": {
                "signal": analysis.recommendation,
                "neural_score": round(analysis.neural_score, 2)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/neural/analyze/{symbol}")
async def get_neural_analyze(symbol: str):
    """Alias for neural analysis"""
    return await get_neural_analysis(symbol)


@router.get("/neural/regime")
async def get_regime_detection():
    """Get market regime detection"""
    try:
        ds = get_data_service()
        regime_detector = get_regime_detector()

        indices = ["SPY", "QQQ", "IWM", "DIA"]
        market_data = {}
        for symbol in indices:
            historical = ds.get_historical(symbol, period="6mo", interval="1d")
            if historical:
                market_data[symbol] = [{
                    "open": bar.open, "high": bar.high, "low": bar.low,
                    "close": bar.close, "volume": bar.volume
                } for bar in historical]

        analysis = regime_detector.detect_regime(market_data, None)
        return {
            "current_regime": analysis.current_state.regime.value,
            "confidence": analysis.current_state.confidence,
            "regime_change_probability": analysis.regime_change_probability,
            "recommended_strategies": analysis.current_state.recommended_strategies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== BEAST ML ==============

@router.get("/beast/status")
async def get_beast_status():
    """Get BEAST ML engine status"""
    if not BEAST_AVAILABLE:
        return {"available": False}
    try:
        from brain.beast_ml import get_beast_engine
        import torch
        engine = get_beast_engine()
        return {
            "available": True,
            "trained": engine.is_trained,
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


# ============== RL ENGINE ==============

@router.get("/rl/status")
async def get_rl_status():
    """Get RL engine status"""
    if not RL_AVAILABLE:
        return {"available": False}
    try:
        from brain.reinforcement_loop import get_rl_engine
        engine = get_rl_engine()
        return {"available": True, "trained": engine.model is not None, "algorithm": "PPO"}
    except Exception as e:
        return {"available": True, "error": str(e)}


# ============== DL ENGINE ==============

@router.get("/dl/status")
async def get_dl_status():
    """Get Deep Learning engine status"""
    if not DL_AVAILABLE:
        return {"available": False}
    try:
        from brain.deep_learning import get_deep_learning_engine
        engine = get_deep_learning_engine()
        return {
            "available": True,
            "models": {
                "lstm": engine.lstm_model is not None,
                "transformer": engine.transformer_model is not None,
                "hybrid": engine.hybrid_model is not None
            }
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


# ============== EVOLUTION ==============

@router.get("/evolution/status")
async def get_evolution_status():
    """Get Evolution engine status using real engine data"""
    if not EVOLUTION_AVAILABLE:
        return {"available": False}
    try:
        from brain.evolution_engine import get_evolution_engine
        engine = get_evolution_engine()
        status = engine.get_status()
        best_fitness = engine.best_fitness_history[-1] if engine.best_fitness_history else None

        return {
            "available": True,
            "population_size": status.get("population_size", engine.config.population_size),
            "generations": engine.config.generations,
            "mutation_rate": engine.config.mutation_rate,
            "crossover_rate": engine.config.crossover_rate,
            "elite_size": engine.config.elite_size,
            "current_generation": status.get("generation", engine.generation),
            "best_fitness": status.get("best_fitness", best_fitness),
            "best_sharpe": status.get("best_sharpe", 0),
            "generations_history": status.get("generations_history", len(engine.best_fitness_history)),
            "has_population": status.get("population_size", 0) > 0,
            "top_strategies": engine.get_top_strategies(3) if engine.population else []
        }
    except Exception as e:
        return {"available": True, "error": str(e)}


# ============== BRAIN MODULES ==============

@router.get("/brain/modules")
async def get_brain_modules():
    """Get status of all brain modules"""
    modules = {
        "beast_ml": {"available": BEAST_AVAILABLE, "description": "XGBoost/LightGBM/Neural ensemble"},
        "reinforcement_learning": {"available": RL_AVAILABLE, "description": "PPO/A2C reinforcement learning"},
        "deep_learning": {"available": DL_AVAILABLE, "description": "LSTM, Transformer, Hybrid models"},
        "evolution": {"available": EVOLUTION_AVAILABLE, "description": "Genetic algorithm optimization"},
        "propfirm_brain_v6": {"available": PROPFIRM_BRAIN_V6_AVAILABLE, "description": "Advanced ML/RL/DL trading brain"},
        "neural_engine": {"available": SERVICES_AVAILABLE, "description": "Pattern recognition"},
        "regime_detector": {"available": SERVICES_AVAILABLE, "description": "Market regime detection"}
    }
    return {
        "modules": modules,
        "total_available": sum(1 for m in modules.values() if m["available"]),
        "total_modules": len(modules)
    }


@router.get("/neural/modules")
async def get_neural_modules():
    """Get status of all neural/AI modules (alias for /api/brain/modules)"""
    return await get_brain_modules()


@router.get("/brain/gpu")
async def get_gpu_status():
    """Get GPU status for ML acceleration"""
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "gpu_available": True,
                "device_name": torch.cuda.get_device_name(0),
                "device_count": torch.cuda.device_count(),
                "memory_allocated": f"{torch.cuda.memory_allocated(0) / 1e9:.2f} GB"
            }
        return {"gpu_available": False, "device": "CPU"}
    except ImportError:
        return {"gpu_available": False, "error": "PyTorch not installed"}
