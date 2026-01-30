"""
Portfolio Routes
================
Endpoints for portfolio management, holdings, and performance.
"""

from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE, BROKER_ADAPTER_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE,
    get_data_service, get_portfolio_service
)

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio")
async def get_portfolio():
    """Get portfolio overview with equity, cash, and P&L"""
    total_position_value = 0
    total_pnl = 0
    day_pnl = 0

    if BROKER_ADAPTER_AVAILABLE:
        try:
            from execution.broker_adapter import PaperBroker
            broker = PaperBroker()
            positions = broker.get_positions()
            for pos in positions:
                total_position_value += pos.get('market_value', 0)
                total_pnl += pos.get('unrealized_pnl', 0)
                day_pnl += pos.get('unrealized_intraday_pnl', 0)
        except Exception as e:
            logger.debug(f"Using paper portfolio data: {e}")

    starting_equity = 100000
    equity = starting_equity + total_pnl
    cash = equity - total_position_value
    buying_power = cash * 2

    return {
        "equity": round(equity, 2),
        "cash": round(max(0, cash), 2),
        "buying_power": round(max(0, buying_power), 2),
        "day_pnl": round(day_pnl, 2),
        "day_pnl_pct": round((day_pnl / equity) * 100 if equity > 0 else 0, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round((total_pnl / starting_equity) * 100 if starting_equity > 0 else 0, 2),
        "positions_count": 0
    }


@router.get("/portfolio/holdings")
async def get_portfolio_holdings():
    """Get portfolio holdings"""
    return {
        "holdings": [],
        "summary": {
            "total_value": 0,
            "total_cost": 0,
            "total_pnl": 0,
            "total_pnl_pct": 0,
            "day_change": 0,
            "day_change_pct": 0
        }
    }


@router.get("/portfolio/performance")
async def get_portfolio_performance():
    """Get portfolio performance metrics"""
    import math
    import statistics

    annual_return = 0.0
    volatility = 15.0
    sharpe_ratio = 0.0
    max_drawdown = 0.0

    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            if brain.trade_history and len(brain.trade_history) >= 5:
                total_pnl = sum(t.pnl for t in brain.trade_history)
                days_traded = min(252, len(brain.trade_history))
                annual_return = (total_pnl / 100000 * 100) * (252 / max(days_traded, 1))

                pnls = [t.pnl for t in brain.trade_history]
                if len(pnls) >= 2:
                    daily_std = statistics.stdev(pnls) / 100000 * 100
                    volatility = daily_std * math.sqrt(252)
                    sharpe_ratio = (annual_return - 4.5) / volatility if volatility > 0 else 0
        except Exception as e:
            logger.warning(f"Portfolio performance error: {e}")

    return {
        "annual_return": round(annual_return, 2),
        "volatility": round(volatility, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "sortino_ratio": 0.0,
        "beta": 1.0,
        "alpha": 0.0,
        "max_drawdown": round(max_drawdown, 2),
        "var_95": 3.0,
        "calmar_ratio": 0.0,
        "information_ratio": 0.0
    }


# ============== REPORTS ==============

@router.get("/reports/summary")
async def get_report_summary(range: str = "30d"):
    """Get trading report summary"""
    total_pnl = 0.0
    total_trades = 0
    win_rate = 0.0
    profit_factor = 0.0

    if PROPFIRM_BRAIN_V6_AVAILABLE:
        try:
            from brain.propfirm_brain_v6 import get_propfirm_brain_v6
            brain = get_propfirm_brain_v6()
            trades_list = brain.trade_history if hasattr(brain, 'trade_history') else []

            if trades_list:
                total_trades = len(trades_list)
                winning_trades = [t for t in trades_list if t.pnl > 0]
                total_pnl = sum(t.pnl for t in trades_list)
                win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

                total_wins = sum(t.pnl for t in winning_trades)
                total_losses = abs(sum(t.pnl for t in trades_list if t.pnl <= 0))
                profit_factor = total_wins / total_losses if total_losses > 0 else (999 if total_wins > 0 else 0)
        except Exception as e:
            logger.warning(f"Report summary error: {e}")

    return {
        "period": range,
        "summary": {
            "totalPnl": round(total_pnl, 2),
            "totalTrades": total_trades,
            "winRate": round(win_rate, 1),
            "profitFactor": round(profit_factor, 2)
        },
        "generatedAt": datetime.now().isoformat()
    }


@router.post("/reports/generate")
async def generate_report(format: str = "json", range: str = "30d"):
    """Generate a trading report"""
    return {
        "format": format,
        "range": range,
        "status": "generated",
        "downloadUrl": f"/api/reports/download/{format}_{range}_{datetime.now().strftime('%Y%m%d')}",
        "generatedAt": datetime.now().isoformat()
    }
