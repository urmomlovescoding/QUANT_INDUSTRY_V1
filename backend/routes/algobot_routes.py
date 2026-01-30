"""
AlgoBot Routes
==============
Endpoints for algorithmic trading bot management and auto-run features.
"""

from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE, BROKER_ADAPTER_AVAILABLE,
    get_data_service, get_algo_bot
)

router = APIRouter(prefix="/api", tags=["algobot"])


# Bot state
_algobot_state = {
    "status": "STOPPED",
    "mode": "PAPER",
    "started_at": None
}

# Auto-run bot states
_auto_run_bots = {
    "brain_v6": False,
    "beast_ml": False,
    "neural": False,
    "rl": False,
    "algo_bot": False
}


# ============== ALGOBOT STATUS ==============

@router.get("/algobot/status")
async def get_algobot_status():
    """Get algo bot status"""
    capital = 100000.0
    open_positions = 0
    pnl_today = 0.0
    pnl_total = 0.0
    trades_today = 0
    win_rate = 0.0

    if BROKER_ADAPTER_AVAILABLE:
        try:
            from execution.broker_adapter import PaperBroker
            broker = PaperBroker()
            account = broker.get_account()
            if account:
                capital = account.equity if hasattr(account, 'equity') else account.buying_power
            positions = broker.get_positions()
            if positions:
                open_positions = len(positions)
                pnl_today = sum(p.unrealized_pnl for p in positions if hasattr(p, 'unrealized_pnl'))
        except Exception as e:
            logger.warning(f"AlgoBot status broker error: {e}")

    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            trades_list = brain.trade_history if hasattr(brain, 'trade_history') else []
            if trades_list:
                total_trades = len(trades_list)
                winners = len([t for t in trades_list if t.pnl > 0])
                win_rate = (winners / total_trades * 100) if total_trades > 0 else 0.0
                pnl_total = sum(t.pnl for t in trades_list)
                trades_today = total_trades
        except Exception as e:
            logger.warning(f"AlgoBot status brain error: {e}")

    return {
        "status": _algobot_state["status"],
        "capital": round(capital, 2),
        "open_positions": open_positions,
        "mode": _algobot_state["mode"],
        "pnl_today": round(pnl_today, 2),
        "pnl_total": round(pnl_total, 2),
        "trades_today": trades_today,
        "win_rate": round(win_rate, 1)
    }


@router.post("/algobot/start")
async def start_algobot():
    """Start the algo bot"""
    _algobot_state["status"] = "RUNNING"
    _algobot_state["started_at"] = datetime.now().isoformat()
    return {"status": "started", "message": "AlgoBot is now running"}


@router.post("/algobot/stop")
async def stop_algobot():
    """Stop the algo bot"""
    _algobot_state["status"] = "STOPPED"
    _algobot_state["started_at"] = None
    return {"status": "stopped", "message": "AlgoBot has been stopped"}


@router.post("/algobot/pause")
async def pause_algobot():
    """Pause the algo bot"""
    _algobot_state["status"] = "PAUSED"
    return {"status": "paused", "message": "AlgoBot is paused"}


@router.get("/algobot/trades")
async def get_algobot_trades():
    """Get recent algo bot trades"""
    trades = []
    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            if brain.trade_history:
                for i, trade in enumerate(brain.trade_history[-10:]):
                    trades.append({
                        "id": f"T{i+1000}",
                        "timestamp": trade.exit_time.isoformat() if trade.exit_time else trade.entry_time.isoformat(),
                        "symbol": trade.symbol,
                        "side": trade.direction.upper(),
                        "quantity": trade.quantity,
                        "price": round(trade.entry_price, 2),
                        "exit_price": round(trade.exit_price, 2) if trade.exit_price else None,
                        "pnl": round(trade.pnl, 2)
                    })
        except Exception as e:
            logger.warning(f"AlgoBot trades error: {e}")
    return trades


# ============== AUTO-RUN MANAGEMENT ==============

@router.get("/bots/auto-run")
async def get_auto_run_status():
    """Get auto-run status for all bots"""
    return {"bots": _auto_run_bots, "any_active": any(_auto_run_bots.values())}


@router.post("/bots/auto-run/{bot_name}/start")
async def start_bot_auto_run(bot_name: str, interval: int = 300):
    """Start auto-run for a specific bot"""
    if bot_name not in _auto_run_bots:
        raise HTTPException(status_code=404, detail=f"Bot {bot_name} not found")

    _auto_run_bots[bot_name] = True

    try:
        if bot_name == "brain_v6" and PROPFIRM_BRAIN_V6_AVAILABLE:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            brain.start_auto_training(interval)
        elif bot_name == "algo_bot" and SERVICES_AVAILABLE:
            algo_bot = get_algo_bot()
            algo_bot.start_auto_trade(interval)
    except Exception as e:
        logger.warning(f"Error starting auto-run for {bot_name}: {e}")

    return {"status": "started", "bot": bot_name, "interval": interval}


@router.post("/bots/auto-run/{bot_name}/stop")
async def stop_bot_auto_run(bot_name: str):
    """Stop auto-run for a specific bot"""
    if bot_name not in _auto_run_bots:
        raise HTTPException(status_code=404, detail=f"Bot {bot_name} not found")

    _auto_run_bots[bot_name] = False

    try:
        if bot_name == "brain_v6" and PROPFIRM_BRAIN_V6_AVAILABLE:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            brain.stop_auto_training()
        elif bot_name == "algo_bot" and SERVICES_AVAILABLE:
            algo_bot = get_algo_bot()
            algo_bot.stop_auto_trade()
    except Exception as e:
        logger.warning(f"Error stopping auto-run for {bot_name}: {e}")

    return {"status": "stopped", "bot": bot_name}


@router.post("/bots/auto-run/all/start")
async def start_all_bots_auto_run(interval: int = 300):
    """Start auto-run for all available bots"""
    started = []
    for bot_name in _auto_run_bots:
        try:
            _auto_run_bots[bot_name] = True
            started.append(bot_name)
        except Exception as e:
            logger.warning(f"Error starting {bot_name}: {e}")
    return {"status": "started", "started_bots": started, "interval": interval}


@router.post("/bots/auto-run/all/stop")
async def stop_all_bots_auto_run():
    """Stop auto-run for all bots"""
    stopped = []
    for bot_name in _auto_run_bots:
        try:
            _auto_run_bots[bot_name] = False
            stopped.append(bot_name)
        except Exception as e:
            logger.warning(f"Error stopping {bot_name}: {e}")
    return {"status": "stopped", "stopped_bots": stopped}
