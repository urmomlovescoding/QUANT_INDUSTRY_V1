"""
ML Brain API Routes
===================
API endpoints for the ML Brain, trading bots, and signals.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import torch
import numpy as np

router = APIRouter(prefix="/brain", tags=["ML Brain"])

# Global state with thread-safe access
# SECURITY: Use asyncio.Lock to prevent race conditions in concurrent requests
_brain_instance = None
_bot_instances: Dict[str, Any] = {}
_pipeline_instance = None
_state_lock = asyncio.Lock()


async def _get_brain():
    """Thread-safe getter for brain instance."""
    async with _state_lock:
        return _brain_instance


async def _set_brain(instance):
    """Thread-safe setter for brain instance."""
    global _brain_instance
    async with _state_lock:
        _brain_instance = instance


async def _get_bot(bot_id: str):
    """Thread-safe getter for a bot instance."""
    async with _state_lock:
        return _bot_instances.get(bot_id)


async def _set_bot(bot_id: str, instance):
    """Thread-safe setter for a bot instance."""
    async with _state_lock:
        _bot_instances[bot_id] = instance


async def _remove_bot(bot_id: str):
    """Thread-safe removal of a bot instance."""
    async with _state_lock:
        return _bot_instances.pop(bot_id, None)


async def _get_all_bots():
    """Thread-safe getter for all bot instances."""
    async with _state_lock:
        return dict(_bot_instances)


class BrainStatus(BaseModel):
    """Brain status response."""
    initialized: bool
    multi_timeframe: bool
    signals_generated: int
    performance_received: int
    active_strategies: int
    registered_bots: List[str]
    learning_rate: float
    top_features: List[Dict[str, Any]]


class SignalResponse(BaseModel):
    """Trading signal response."""
    signal_id: str
    timestamp: str
    symbol: str
    horizon: Optional[str]
    direction: int
    action: str
    strength: float
    confidence: float
    suggested_size: float
    regime: str
    stop_loss: Optional[float]
    take_profit: Optional[float]


class MultiTimeframeSignals(BaseModel):
    """Multi-timeframe signals response."""
    symbol: str
    timestamp: str
    regime: str
    signals: Dict[str, SignalResponse]


class BotStatus(BaseModel):
    """Bot status response."""
    bot_id: str
    name: str
    status: str
    open_trades: int
    closed_trades: int
    open_pnl_pct: float
    closed_pnl_pct: float
    total_pnl_pct: float
    win_rate: float


class PerformanceMetrics(BaseModel):
    """Performance metrics."""
    total_signals: int
    total_trades: int
    win_rate: float
    total_pnl_pct: float
    sharpe_ratio: float
    max_drawdown: float
    by_horizon: Dict[str, Dict[str, float]]
    by_regime: Dict[str, Dict[str, float]]


# ============== Brain Endpoints ==============

@router.get("/status", response_model=BrainStatus)
async def get_brain_status():
    """Get ML Brain status and state."""
    brain = await _get_brain()

    if brain is None:
        return BrainStatus(
            initialized=False,
            multi_timeframe=False,
            signals_generated=0,
            performance_received=0,
            active_strategies=0,
            registered_bots=[],
            learning_rate=0.001,
            top_features=[]
        )

    state = brain.get_brain_state()

    return BrainStatus(
        initialized=True,
        multi_timeframe=getattr(brain, 'multi_timeframe', False),
        signals_generated=state['signals_generated'],
        performance_received=state['performance_received'],
        active_strategies=state['active_strategies'],
        registered_bots=state['registered_bots'],
        learning_rate=state['learning_rate'],
        top_features=[
            {'name': name, 'importance': score}
            for name, score in state['top_features']
        ]
    )


@router.post("/initialize")
async def initialize_brain(multi_timeframe: bool = True):
    """Initialize the ML Brain."""
    from brain.orchestrator import MLBrain

    brain = MLBrain()
    await brain.initialize(multi_timeframe=multi_timeframe)
    await _set_brain(brain)

    return {"status": "initialized", "multi_timeframe": multi_timeframe}


@router.post("/signal/generate")
async def generate_signal(
    symbol: str,
    timeframe: str = "1h"
) -> SignalResponse:
    """Generate a single trading signal."""
    brain = await _get_brain()

    if brain is None:
        raise HTTPException(status_code=400, detail="Brain not initialized")

    # Create dummy data (in production, fetch real data)
    market_data = torch.randn(1, 60, 32)
    current_price = 50000.0  # Would come from data feed

    signal = await brain.generate_signal(symbol, market_data, current_price)

    if signal is None:
        raise HTTPException(status_code=500, detail="Failed to generate signal")

    return SignalResponse(
        signal_id=signal.signal_id,
        timestamp=signal.timestamp.isoformat(),
        symbol=signal.symbol,
        horizon=None,
        direction=signal.direction,
        action='buy' if signal.direction > 0 else ('sell' if signal.direction < 0 else 'hold'),
        strength=signal.strength,
        confidence=signal.confidence,
        suggested_size=signal.suggested_size,
        regime=signal.regime,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit
    )


@router.post("/signal/multi-timeframe")
async def generate_multi_timeframe_signals(symbol: str) -> MultiTimeframeSignals:
    """Generate signals for all trading horizons."""
    brain = await _get_brain()

    if brain is None:
        raise HTTPException(status_code=400, detail="Brain not initialized")
    
    if not getattr(_brain_instance, 'multi_timeframe', False):
        raise HTTPException(status_code=400, detail="Brain not configured for multi-timeframe")
    
    # Create dummy multi-timeframe data
    timeframe_data = {
        '1m': torch.randn(1, 60, 32),
        '5m': torch.randn(1, 60, 32),
        '15m': torch.randn(1, 48, 32),
        '1h': torch.randn(1, 48, 32),
        '4h': torch.randn(1, 60, 32),
        '1d': torch.randn(1, 60, 32),
    }
    current_price = 50000.0
    
    signals = await _brain_instance.generate_multi_timeframe_signals(
        symbol, timeframe_data, current_price
    )
    
    # Get regime from any signal
    regime = next(iter(signals.values())).regime if signals else 'unknown'
    
    return MultiTimeframeSignals(
        symbol=symbol,
        timestamp=datetime.now().isoformat(),
        regime=regime,
        signals={
            horizon: SignalResponse(
                signal_id=sig.signal_id,
                timestamp=sig.timestamp.isoformat(),
                symbol=sig.symbol,
                horizon=horizon,
                direction=sig.direction,
                action='buy' if sig.direction > 0 else ('sell' if sig.direction < 0 else 'hold'),
                strength=sig.strength,
                confidence=sig.confidence,
                suggested_size=sig.suggested_size,
                regime=sig.regime,
                stop_loss=sig.stop_loss,
                take_profit=sig.take_profit
            )
            for horizon, sig in signals.items()
        }
    )


@router.get("/signals/history")
async def get_signal_history(limit: int = 100) -> List[SignalResponse]:
    """Get recent signal history."""
    # SECURITY: Validate limit to prevent DoS
    if limit < 1 or limit > 1000:
        limit = 100

    brain = await _get_brain()

    if brain is None:
        return []

    signals = brain.signal_history[-limit:]
    
    return [
        SignalResponse(
            signal_id=sig.signal_id,
            timestamp=sig.timestamp.isoformat(),
            symbol=sig.symbol,
            horizon=sig.metadata.get('horizon'),
            direction=sig.direction,
            action='buy' if sig.direction > 0 else ('sell' if sig.direction < 0 else 'hold'),
            strength=sig.strength,
            confidence=sig.confidence,
            suggested_size=sig.suggested_size,
            regime=sig.regime,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit
        )
        for sig in reversed(signals)
    ]


@router.get("/features/importance")
async def get_feature_importance() -> List[Dict[str, Any]]:
    """Get feature importance rankings."""
    brain = await _get_brain()

    if brain is None:
        return []

    return [
        {
            'name': name,
            'importance': fi.importance_score,
            'stability': fi.stability,
            'regime_dependency': fi.regime_dependency
        }
        for name, fi in sorted(
            brain.feature_importance.items(),
            key=lambda x: x[1].importance_score,
            reverse=True
        )
    ]


# ============== Bot Endpoints ==============

@router.get("/bots", response_model=List[BotStatus])
async def get_all_bots():
    """Get status of all trading bots."""
    bots = await _get_all_bots()
    
    return [
        BotStatus(
            bot_id=bot.config.bot_id,
            name=bot.config.name,
            status=bot.status.value,
            open_trades=len(bot.open_trades),
            closed_trades=len(bot.closed_trades),
            open_pnl_pct=sum(t.pnl_pct for t in bot.open_trades.values()),
            closed_pnl_pct=sum(t.pnl_pct for t in bot.closed_trades),
            total_pnl_pct=sum(t.pnl_pct for t in bot.open_trades.values()) +
                         sum(t.pnl_pct for t in bot.closed_trades),
            win_rate=bot._calculate_win_rate()
        )
        for bot in bots.values()
    ]


@router.get("/bots/{bot_id}", response_model=BotStatus)
async def get_bot_status(bot_id: str):
    """Get status of a specific bot."""
    bot = await _get_bot(bot_id)

    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    status = bot.get_status()

    return BotStatus(**status)


@router.get("/bots/{bot_id}/trades")
async def get_bot_trades(bot_id: str, status: str = "all"):
    """Get trades for a specific bot."""
    bot = await _get_bot(bot_id)

    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    
    trades = []
    
    if status in ["all", "open"]:
        for trade in bot.open_trades.values():
            trades.append({
                'trade_id': trade.trade_id,
                'symbol': trade.symbol,
                'direction': 'long' if trade.direction > 0 else 'short',
                'entry_price': trade.entry_price,
                'entry_time': trade.entry_time.isoformat(),
                'quantity': trade.quantity,
                'pnl_pct': trade.pnl_pct,
                'status': 'open',
                'stop_loss': trade.stop_loss,
                'take_profit': trade.take_profit,
            })
    
    if status in ["all", "closed"]:
        for trade in bot.closed_trades[-50:]:  # Last 50
            trades.append({
                'trade_id': trade.trade_id,
                'symbol': trade.symbol,
                'direction': 'long' if trade.direction > 0 else 'short',
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'entry_time': trade.entry_time.isoformat(),
                'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
                'quantity': trade.quantity,
                'pnl_pct': trade.pnl_pct,
                'status': 'closed',
                'exit_reason': trade.exit_reason,
            })
    
    return trades


# ============== Performance Endpoints ==============

@router.get("/performance", response_model=PerformanceMetrics)
async def get_performance_metrics():
    """Get overall performance metrics."""
    global _brain_instance, _bot_instances
    
    if _brain_instance is None:
        return PerformanceMetrics(
            total_signals=0,
            total_trades=0,
            win_rate=0,
            total_pnl_pct=0,
            sharpe_ratio=0,
            max_drawdown=0,
            by_horizon={},
            by_regime={}
        )
    
    # Aggregate from all bots
    all_trades = []
    for bot in _bot_instances.values():
        all_trades.extend(bot.closed_trades)
    
    total_trades = len(all_trades)
    wins = sum(1 for t in all_trades if t.pnl_pct > 0)
    win_rate = wins / total_trades if total_trades > 0 else 0
    total_pnl = sum(t.pnl_pct for t in all_trades)
    
    # Calculate by horizon and regime
    by_horizon = {}
    by_regime = {}
    
    for perf in _brain_instance.performance_history:
        # Would need to track horizon/regime per trade
        pass
    
    return PerformanceMetrics(
        total_signals=len(_brain_instance.signal_history),
        total_trades=total_trades,
        win_rate=win_rate,
        total_pnl_pct=total_pnl,
        sharpe_ratio=0,  # Would calculate properly
        max_drawdown=0,  # Would calculate properly
        by_horizon=by_horizon,
        by_regime=by_regime
    )


# ============== Pipeline Control ==============

@router.post("/pipeline/start")
async def start_pipeline(background_tasks: BackgroundTasks):
    """Start the full trading pipeline."""
    global _pipeline_instance
    
    from brain.pipeline import TradingPipeline, PipelineConfig
    
    config = PipelineConfig(
        active_bots=['tpt', 'momentum', 'swing'],
        symbols=['BTC/USD', 'ETH/USD'],
        signal_interval=60.0,
    )
    
    _pipeline_instance = TradingPipeline(config)
    await _pipeline_instance.initialize()
    
    # Store references
    global _brain_instance, _bot_instances
    _brain_instance = _pipeline_instance.brain
    _bot_instances = _pipeline_instance.bots
    
    # Run in background
    background_tasks.add_task(_pipeline_instance.run)
    
    return {"status": "started", "bots": list(_pipeline_instance.bots.keys())}


@router.post("/pipeline/stop")
async def stop_pipeline():
    """Stop the trading pipeline."""
    global _pipeline_instance
    
    if _pipeline_instance is None:
        raise HTTPException(status_code=400, detail="Pipeline not running")
    
    await _pipeline_instance.stop()
    
    return {"status": "stopped"}


@router.get("/pipeline/status")
async def get_pipeline_status():
    """Get pipeline status."""
    global _pipeline_instance
    
    if _pipeline_instance is None:
        return {"running": False}
    
    return _pipeline_instance.get_status()
