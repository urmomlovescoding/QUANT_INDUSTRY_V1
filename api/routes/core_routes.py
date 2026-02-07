"""
Core API Routes
===============
Essential endpoints using REAL data from backend services.

Market data flows through MarketDataService (Alpaca/yfinance).
Trading data from TradingService, risk from RiskService.
AI/ML from PropFirm Brain V6 and FeedbackLoop.

When a service is unavailable, endpoints return honest zero/empty data
with data_source="none" -- never fake numbers.
"""

# IMPORTANT: Import config first to ensure env vars are loaded
from backend.config.env import config

import asyncio
import logging
import math
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)


def get_market_session() -> dict:
    """Detect real US equity market session based on current Eastern Time."""
    try:
        import pytz
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)
    except ImportError:
        # Fallback without pytz: assume UTC-5 (EST) as approximation
        from datetime import timezone
        et_offset = timezone(timedelta(hours=-5))
        now = datetime.now(et_offset)

    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    time_decimal = hour + minute / 60.0

    if weekday >= 5:  # Saturday/Sunday
        return {"session": "closed", "is_open": False, "is_pre_market": False, "is_after_hours": False}
    elif time_decimal < 4.0:
        return {"session": "closed", "is_open": False, "is_pre_market": False, "is_after_hours": False}
    elif time_decimal < 9.5:
        return {"session": "pre_market", "is_open": False, "is_pre_market": True, "is_after_hours": False}
    elif time_decimal < 16.0:
        return {"session": "regular", "is_open": True, "is_pre_market": False, "is_after_hours": False}
    elif time_decimal < 20.0:
        return {"session": "after_hours", "is_open": False, "is_pre_market": False, "is_after_hours": True}
    else:
        return {"session": "closed", "is_open": False, "is_pre_market": False, "is_after_hours": False}

router = APIRouter(prefix="/api", tags=["core"])

# Market data service - initialized per-request to handle event loop changes
_market_service = None
_service_loop_id = None


async def get_service():
    """Dependency to get market data service."""
    global _market_service, _service_loop_id
    import asyncio
    
    # Get current event loop id
    try:
        current_loop = asyncio.get_running_loop()
        current_loop_id = id(current_loop)
    except RuntimeError:
        current_loop_id = None
    
    # Reinitialize if loop changed or service doesn't exist
    if _market_service is None or _service_loop_id != current_loop_id:
        try:
            from backend.services.market_data_service import MarketDataService
            _market_service = await MarketDataService.create()
            _service_loop_id = current_loop_id
            logger.info(f"Market data service initialized (mode: {_market_service.data_mode})")
        except Exception as e:
            logger.error(f"Failed to initialize market data service: {e}")
            from backend.services.market_data_service import MarketDataService
            _market_service = MarketDataService()
            _service_loop_id = current_loop_id
    
    return _market_service


# ============== HEALTH & STATUS ==============

@router.get("/health")
async def health():
    """Health check with data source info."""
    service = await get_service()

    # Detect real market session
    market = get_market_session()

    # Check brain availability
    brain_available = False
    try:
        from backend.brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()
        brain_available = brain is not None
    except Exception:
        pass

    return {
        "status": "healthy",
        "data_mode": service.data_mode if service else "mock",
        "alpaca_configured": config.alpaca_configured,
        "polygon_configured": config.polygon_configured,
        "market": market,
        "services": {
            "database": True,
            "redis": config.redis_configured,
            "brain": brain_available,
            "data_provider": config.alpaca_configured or config.polygon_configured
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/system/status")
async def system_status():
    """System status using real system metrics."""
    service = await get_service()

    # Real system metrics via psutil
    cpu_percent = 0.0
    memory_percent = 0.0
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
    except ImportError:
        logger.warning("psutil not installed -- system metrics unavailable")
    except Exception as e:
        logger.warning(f"Failed to read system metrics: {e}")

    # GPU detection
    gpu_available = False
    gpu_percent = 0.0
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_percent = torch.cuda.memory_allocated() / torch.cuda.get_device_properties(0).total_mem * 100
    except Exception:
        pass

    return {
        "cpu_percent": round(cpu_percent, 1),
        "memory_percent": round(memory_percent, 1),
        "gpu_available": gpu_available,
        "gpu_percent": round(gpu_percent, 1),
        "data_mode": service.data_mode if service else "mock",
        "alpaca_connected": service._alpaca is not None if service else False,
        "timestamp": datetime.now().isoformat()
    }


# ============== MARKET DATA ==============

@router.get("/market/status")
async def market_status():
    """Get market status."""
    service = await get_service()
    return await service.get_market_status()


@router.get("/market/tickers")
async def get_tickers(symbols: str = "SPY,QQQ,DIA,IWM"):
    """Get market tickers - REAL quotes when available."""
    service = await get_service()
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    
    quotes = await service.get_quotes(symbol_list)

    # Fetch previous close for change calculation
    prev_closes = {}
    try:
        for sym in symbol_list:
            bars = await service.get_bars(sym, timeframe="1Day", days=5)
            if bars and len(bars) >= 2:
                prev_closes[sym] = bars[-2].close
            elif bars and len(bars) >= 1:
                prev_closes[sym] = bars[-1].close
    except Exception as e:
        logger.warning(f"Could not fetch previous closes for change calc: {e}")

    results = []
    for symbol in symbol_list:
        q = quotes.get(symbol)
        if q:
            price = q.last or q.mid
            prev = prev_closes.get(symbol, 0)
            change = (price - prev) if prev else 0
            change_pct = ((price - prev) / prev * 100) if prev else 0

            results.append({
                "symbol": symbol,
                "price": price,
                "bid": q.bid,
                "ask": q.ask,
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": q.volume,
                "source": q.source
            })

    return results


@router.get("/market/quote/{symbol}")
async def get_quote(symbol: str):
    """Get single quote - REAL data when available."""
    service = await get_service()
    quote = await service.get_quote(symbol.upper())
    
    price = quote.last or quote.mid

    # Fetch bars for previous close, open, high, low
    prev_close = 0.0
    open_price = price
    high_price = price
    low_price = price
    try:
        bars = await service.get_bars(symbol.upper(), timeframe="1Day", days=5)
        if bars and len(bars) >= 2:
            prev_close = bars[-2].close
            today_bar = bars[-1]
            open_price = today_bar.open
            high_price = today_bar.high
            low_price = today_bar.low
        elif bars and len(bars) >= 1:
            today_bar = bars[-1]
            prev_close = today_bar.open  # Fallback
            open_price = today_bar.open
            high_price = today_bar.high
            low_price = today_bar.low
    except Exception as e:
        logger.warning(f"Could not fetch bars for {symbol}: {e}")

    change = (price - prev_close) if prev_close else 0
    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

    return {
        "symbol": quote.symbol,
        "price": price,
        "bid": quote.bid,
        "ask": quote.ask,
        "bid_size": quote.bid_size,
        "ask_size": quote.ask_size,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "volume": quote.volume,
        "high": high_price,
        "low": low_price,
        "open": open_price,
        "prev_close": prev_close,
        "source": quote.source,
        "timestamp": quote.timestamp.isoformat() if quote.timestamp else datetime.now().isoformat()
    }


@router.get("/market/bars/{symbol}")
async def get_bars(
    symbol: str,
    timeframe: str = "1Day",
    days: int = 30
):
    """Get historical bars."""
    service = await get_service()
    bars = await service.get_bars(
        symbol=symbol.upper(),
        timeframe=timeframe,
        days=days
    )
    
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "count": len(bars),
        "source": bars[0].source if bars else "none",
        "bars": [b.to_dict() for b in bars]
    }


@router.get("/market/snapshot/{symbol}")
async def get_snapshot(symbol: str):
    """Get complete market snapshot."""
    service = await get_service()
    return await service.get_snapshot(symbol.upper())


# ============== BRAIN & AI ==============

@router.get("/brain-v6/status")
async def brain_status():
    """Trading brain status from real PropFirm Brain V6."""
    try:
        from backend.brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()
        status = brain.get_status()
        status["available"] = True
        status["data_source"] = "propfirm_brain_v6"
        return status
    except Exception as e:
        logger.warning(f"PropFirm Brain V6 not available: {e}")
        return {
            "available": False,
            "device": "cpu",
            "is_trained": False,
            "current_regime": "unknown",
            "auto_train_enabled": False,
            "training_step": 0,
            "total_trades": 0,
            "metrics": {
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0
            },
            "strategies": [],
            "data_source": "none",
            "message": f"Brain not initialized: {str(e)}"
        }


@router.get("/feedback/status")
async def feedback_status():
    """Feedback loop status from real feedback loop."""
    try:
        from backend.brain.feedback_loop import get_feedback_loop
        loop = get_feedback_loop()
        status = loop.get_status()
        status["data_source"] = "feedback_loop"
        return status
    except Exception as e:
        logger.warning(f"Feedback loop not available: {e}")
        return {
            "phase": "not_initialized",
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "convergence_progress": {},
            "is_converged": False,
            "data_source": "none",
            "message": f"Feedback loop not initialized: {str(e)}"
        }


# ============== SIGNALS & POSITIONS ==============

@router.get("/signals")
@router.get("/signals/active")
async def get_signals():
    """Get active trading signals from the brain's signal history."""
    try:
        from backend.brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()

        # The brain stores its last signal; collect any available signals
        signals = []
        if brain.last_signal:
            sig = brain.last_signal
            signals.append({
                "id": f"sig-latest",
                "symbol": sig.get("symbol", "N/A"),
                "direction": sig.get("direction", "NEUTRAL"),
                "confidence": round(sig.get("confidence", 0), 3),
                "strategy": sig.get("strategy", ""),
                "entry_price": sig.get("entry_price", 0),
                "stop_loss": sig.get("stop_loss", 0),
                "take_profit": sig.get("take_profit", 0),
                "risk_reward": round(sig.get("risk_reward", 0), 2),
                "timeframe": sig.get("timeframe", "1D"),
                "regime": brain.current_regime.value,
                "timestamp": sig.get("timestamp", datetime.now().isoformat()),
                "status": "active",
                "data_source": "propfirm_brain_v6"
            })
        return signals
    except Exception as e:
        logger.warning(f"Could not fetch signals from brain: {e}")
        return []


@router.get("/positions")
async def get_positions():
    """Get current positions from the trading service."""
    try:
        from backend.services.trading_service import get_trading_service
        trading = get_trading_service()
        positions = trading.get_all_positions()
        return [p.to_dict() for p in positions]
    except Exception as e:
        logger.warning(f"Could not fetch positions from trading service: {e}")
        return []


@router.get("/portfolio")
async def get_portfolio_summary():
    """Get portfolio summary from the trading service."""
    try:
        from backend.services.trading_service import get_trading_service
        trading = get_trading_service()
        account = trading.get_account_info()
        positions = trading.get_all_positions()
        return {
            "equity": round(account.equity, 2),
            "cash": round(account.cash, 2),
            "buying_power": round(account.buying_power, 2),
            "day_pnl": round(account.day_pnl, 2),
            "day_pnl_pct": round(account.day_pnl_pct, 2),
            "total_pnl": round(account.total_pnl, 2),
            "total_pnl_pct": round(account.total_pnl_pct, 2),
            "positions_count": len(positions),
            "data_source": "trading_service"
        }
    except Exception as e:
        logger.warning(f"Could not fetch portfolio from trading service: {e}")
        return {
            "equity": 0.0,
            "cash": 0.0,
            "buying_power": 0.0,
            "day_pnl": 0.0,
            "day_pnl_pct": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
            "positions_count": 0,
            "data_source": "none",
            "message": f"Trading service not available: {str(e)}"
        }


@router.get("/portfolio/performance")
async def get_performance():
    """Get portfolio performance computed from real trade history."""
    try:
        from backend.services.trading_service import get_trading_service
        trading = get_trading_service()
        account = trading.get_account_info()
        trades = trading.get_trades(limit=10000)

        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_return": round(account.total_pnl, 2),
                "total_return_pct": round(account.total_pnl_pct, 2),
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "data_source": "trading_service"
            }

        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        win_count = len(winning_trades)
        loss_count = len(losing_trades)

        win_rate = win_count / total_trades if total_trades > 0 else 0
        avg_win = sum(t.pnl for t in winning_trades) / win_count if win_count > 0 else 0
        avg_loss = sum(t.pnl for t in losing_trades) / loss_count if loss_count > 0 else 0
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Compute Sharpe and Sortino from trade PnLs
        pnls = [t.pnl for t in trades]
        mean_pnl = sum(pnls) / len(pnls)
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls) if len(pnls) > 1 else 0
        std_pnl = math.sqrt(variance)
        sharpe_ratio = (mean_pnl / std_pnl) * math.sqrt(252) if std_pnl > 0 else 0

        downside_pnls = [p for p in pnls if p < 0]
        downside_var = sum(p ** 2 for p in downside_pnls) / len(downside_pnls) if downside_pnls else 0
        downside_std = math.sqrt(downside_var)
        sortino_ratio = (mean_pnl / downside_std) * math.sqrt(252) if downside_std > 0 else 0

        # Max drawdown from cumulative PnL
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in sorted(trades, key=lambda x: x.exit_time):
            cumulative += t.pnl
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "total_return": round(account.total_pnl, 2),
            "total_return_pct": round(account.total_pnl_pct, 2),
            "win_rate": round(win_rate, 3),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "max_drawdown": round(max_dd, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "data_source": "trading_service"
        }
    except Exception as e:
        logger.warning(f"Could not compute performance: {e}")
        return {
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "data_source": "none",
            "message": f"Performance computation unavailable: {str(e)}"
        }


# ============== RISK ==============

@router.get("/risk/metrics")
async def get_risk_metrics():
    """Get risk metrics from the risk service."""
    try:
        from backend.services.risk_service import get_risk_service
        risk = get_risk_service()
        metrics = risk.calculate_metrics()
        return metrics.to_dict()
    except Exception as e:
        logger.warning(f"Could not compute risk metrics: {e}")
        return {
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "current_drawdown": 0.0,
            "max_drawdown": 0.0,
            "max_position_pct": 0.0,
            "sector_concentration": 0.0,
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0,
            "risk_score": 0,
            "risk_level": "unknown",
            "data_source": "none",
            "message": f"Risk service not available: {str(e)}"
        }


@router.get("/risk/safety")
async def get_safety_status():
    """Get safety status from real risk monitoring."""
    try:
        from backend.services.risk_service import get_risk_service
        risk_svc = get_risk_service()
        metrics = risk_svc.calculate_metrics()
        alerts = risk_svc.get_alerts(unacknowledged_only=True)

        breaches = [a.to_dict() for a in alerts if a.type.value == "CRITICAL"]
        warnings = [a.to_dict() for a in alerts if a.type.value == "WARNING"]

        # Determine safety based on risk level
        is_safe = metrics.risk_level.value in ("LOW", "MODERATE")

        return {
            "is_safe": is_safe,
            "risk_level": metrics.risk_level.value,
            "risk_score": round(metrics.risk_score, 1),
            "breaches": breaches,
            "warnings": warnings,
            "daily_pnl": round(metrics.daily_pnl, 2),
            "daily_pnl_pct": round(metrics.daily_pnl_pct, 2),
            "current_drawdown": round(metrics.current_drawdown, 4),
            "max_drawdown_limit": risk_svc.limits.max_drawdown_pct,
            "max_daily_loss_limit": risk_svc.limits.max_daily_loss_pct,
            "data_source": "risk_service"
        }
    except Exception as e:
        logger.warning(f"Could not compute safety status: {e}")
        return {
            "is_safe": True,
            "risk_level": "unknown",
            "risk_score": 0,
            "breaches": [],
            "warnings": [],
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0,
            "current_drawdown": 0.0,
            "max_drawdown_limit": 0.0,
            "max_daily_loss_limit": 0.0,
            "data_source": "none",
            "message": f"Risk service not available: {str(e)}"
        }


# ============== ML/REGIME ==============

@router.get("/ml/regime")
async def get_regime():
    """Get market regime from the real PropFirm Brain V6 regime detector."""
    try:
        from backend.brain.propfirm_brain_v6 import get_propfirm_brain_v6
        brain = get_propfirm_brain_v6()

        regime = brain.current_regime.value
        probs = brain.regime_probs if brain.regime_probs else {}

        # Confidence is the probability of the detected regime
        confidence = probs.get(regime, 0.5)

        return {
            "regime": regime,
            "confidence": round(confidence, 3),
            "regime_probabilities": {k: round(v, 3) for k, v in probs.items()} if probs else {},
            "data_source": "propfirm_brain_v6"
        }
    except Exception as e:
        logger.warning(f"Regime detector not available: {e}")
        return {
            "regime": "unknown",
            "confidence": 0.0,
            "regime_probabilities": {},
            "data_source": "none",
            "message": f"Regime detector not available: {str(e)}"
        }


# ============== NEWS ==============

@router.get("/news")
async def get_news(symbol: Optional[str] = None, limit: int = 10):
    """Get market news."""
    service = await get_service()
    symbols = [symbol] if symbol else None
    return await service.get_news(symbols=symbols, limit=limit)


# ============== SETTINGS ==============

@router.get("/settings")
async def get_settings():
    """Get user settings."""
    return {
        "theme": "dark",
        "notifications_enabled": True,
        "auto_refresh_interval": 15,
        "default_order_type": "limit",
        "risk_params": {
            "max_position_size": 0.1,
            "max_daily_loss": 1000,
            "max_drawdown": 0.2
        },
        "data_provider": config.get_data_mode(),
        "api_keys_configured": {
            "alpaca": config.alpaca_configured,
            "polygon": config.polygon_configured
        }
    }


@router.get("/settings/api-keys")
async def get_api_keys():
    """Get API key status (not the actual keys)."""
    return {
        "alpaca": config.alpaca_configured,
        "polygon": config.polygon_configured,
        "tradier": False
    }


# ============== STRATEGIES ==============

@router.get("/strategies")
async def list_strategies():
    """List available trading strategies."""
    try:
        from strategies import list_strategies, STRATEGY_REGISTRY
        return {
            "strategies": list_strategies(),
            "count": len(STRATEGY_REGISTRY)
        }
    except ImportError:
        return {
            "strategies": [
                {"id": "momentum", "name": "Momentum", "description": "Time-series momentum strategy"},
                {"id": "mean_reversion", "name": "Mean Reversion", "description": "Z-score based reversion"},
                {"id": "dual_momentum", "name": "Dual Momentum", "description": "Absolute + relative momentum"},
            ],
            "count": 3
        }


@router.get("/strategies/{strategy_id}")
async def get_strategy_info(strategy_id: str):
    """Get strategy details."""
    try:
        from strategies import STRATEGY_REGISTRY, StrategyConfig
        
        if strategy_id not in STRATEGY_REGISTRY:
            raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")
        
        strategy_class = STRATEGY_REGISTRY[strategy_id]
        temp_config = StrategyConfig(symbols=['TEST'])
        
        try:
            instance = strategy_class(temp_config)
            return {
                "id": strategy_id,
                "name": instance.name,
                "description": instance.description,
                "required_history": instance.get_required_history(),
                "parameters": getattr(instance, 'default_params', {})
            }
        except Exception as e:
            return {
                "id": strategy_id,
                "name": strategy_id,
                "description": "Strategy requires specific parameters",
                "error": str(e)
            }
    except ImportError:
        raise HTTPException(status_code=500, detail="Strategy module not available")


# ============== PORTFOLIO MANAGEMENT ==============

# In-memory portfolio for demo (would use database in production)
_portfolio_instance = None


def get_portfolio_manager():
    """Get or create portfolio instance."""
    global _portfolio_instance
    if _portfolio_instance is None:
        try:
            from portfolio import PortfolioManager
            _portfolio_instance = PortfolioManager(initial_capital=100000)
        except ImportError:
            return None
    return _portfolio_instance


@router.get("/portfolio/live")
async def get_live_portfolio():
    """Get live portfolio state."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        return {
            "error": "Portfolio module not available",
            "equity": 0.0,
            "cash": 0.0,
            "positions": [],
            "total_pnl": 0.0,
            "data_source": "none"
        }

    return portfolio.to_dict()


@router.get("/portfolio/positions")
async def get_positions():
    """Get all positions."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        return {"positions": [], "count": 0}
    
    return {
        "positions": [p.to_dict() for p in portfolio.get_positions()],
        "count": len(portfolio.positions)
    }


@router.get("/portfolio/position/{symbol}")
async def get_position(symbol: str):
    """Get single position."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        raise HTTPException(status_code=503, detail="Portfolio not available")
    
    position = portfolio.get_position(symbol.upper())
    if not position:
        raise HTTPException(status_code=404, detail=f"No position in {symbol}")
    
    return position.to_dict()


@router.post("/portfolio/trade")
async def execute_trade(
    symbol: str,
    quantity: float,
    side: str,  # 'buy' or 'sell'
    price: Optional[float] = None
):
    """Execute a trade."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        raise HTTPException(status_code=503, detail="Portfolio not available")
    
    if side not in ['buy', 'sell']:
        raise HTTPException(status_code=400, detail="Side must be 'buy' or 'sell'")
    
    # Get current price if not provided
    if price is None:
        service = await get_service()
        quote = await service.get_quote(symbol.upper())
        price = quote.last or quote.mid
        if not price:
            raise HTTPException(status_code=400, detail=f"Could not get price for {symbol}")
    
    trade = portfolio.execute_trade(
        symbol=symbol.upper(),
        quantity=quantity,
        side=side,
        price=price
    )
    
    if not trade:
        raise HTTPException(status_code=400, detail="Trade failed")
    
    return trade.to_dict()


@router.delete("/portfolio/position/{symbol}")
async def close_position(symbol: str):
    """Close a position."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        raise HTTPException(status_code=503, detail="Portfolio not available")
    
    # Get current price
    service = await get_service()
    quote = await service.get_quote(symbol.upper())
    price = quote.last or quote.mid
    
    trade = portfolio.close_position(symbol.upper(), price=price)
    if not trade:
        raise HTTPException(status_code=404, detail=f"No position to close in {symbol}")
    
    return trade.to_dict()


@router.get("/portfolio/risk")
async def get_portfolio_risk():
    """Get portfolio risk metrics."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        return {
            "var_95": 0.0,
            "max_drawdown": 0.0,
            "current_drawdown": 0.0,
            "leverage": 0.0,
            "gross_exposure": 0.0,
            "net_exposure": 0.0,
            "data_source": "none"
        }

    metrics = portfolio.calculate_risk_metrics()
    return metrics.to_dict()


@router.get("/portfolio/trades")
async def get_trades(limit: int = 100):
    """Get trade history."""
    portfolio = get_portfolio_manager()
    if not portfolio:
        return {"trades": [], "count": 0}
    
    trades = portfolio.trades[-limit:]
    return {
        "trades": [t.to_dict() for t in trades],
        "count": len(portfolio.trades),
        "showing": len(trades)
    }


# ==============================================================================
# TRADING BRAIN INTEGRATION - Phase 1-3 Math Features
# ==============================================================================

# Singleton TradingBrain instance
_trading_brain = None

def get_trading_brain():
    """Get or create TradingBrain singleton."""
    global _trading_brain
    if _trading_brain is None:
        try:
            from backend.brain.trading_brain import TradingBrain
            _trading_brain = TradingBrain(account_equity=100000)
            logger.info("TradingBrain initialized with math integration")
        except Exception as e:
            logger.error(f"Failed to initialize TradingBrain: {e}")
            return None
    return _trading_brain


@router.get("/regime/detect")
async def detect_market_regime(symbol: str = "SPY"):
    """
    Detect current market regime using HMM-based detection.
    
    Returns regime state with:
    - Current regime (BULL_STRONG, BULL_WEAK, NEUTRAL, BEAR_WEAK, BEAR_STRONG, CRISIS, EUPHORIA)
    - Confidence level
    - Volatility regime
    - Risk adjustments (position scalar, stop multiplier)
    """
    brain = get_trading_brain()
    if brain is None:
        raise HTTPException(status_code=503, detail="TradingBrain not available")
    
    # Fetch market data
    try:
        service = await get_service()
        bars = await service.get_bars(symbol, timeframe="1d", limit=252)
        
        if not bars:
            raise HTTPException(status_code=400, detail=f"No data available for {symbol}")
        
        # Prepare market data for brain
        import numpy as np
        ohlcv = [
            {
                'timestamp': bar.timestamp.isoformat() if hasattr(bar, 'timestamp') else str(bar.get('timestamp', '')),
                'open': bar.open if hasattr(bar, 'open') else bar.get('open', 0),
                'high': bar.high if hasattr(bar, 'high') else bar.get('high', 0),
                'low': bar.low if hasattr(bar, 'low') else bar.get('low', 0),
                'close': bar.close if hasattr(bar, 'close') else bar.get('close', 0),
                'volume': bar.volume if hasattr(bar, 'volume') else bar.get('volume', 0),
            }
            for bar in bars
        ]
        
        market_data = {'ohlcv': ohlcv, 'spy_ohlcv': ohlcv}
        
        # Get regime alignment and state
        alignment, regime_state = brain._get_regime_alignment(market_data)
        
        if regime_state is None:
            return {
                "regime": "NEUTRAL",
                "confidence": 0.5,
                "alignment": 0.0,
                "volatility_regime": "normal",
                "position_scalar": 0.75,
                "stop_multiplier": 1.0,
                "fitted": brain.regime_fitted,
                "message": "Regime detection not fitted (insufficient data)"
            }
        
        return {
            "regime": regime_state.regime.value,
            "confidence": regime_state.confidence,
            "alignment": alignment,
            "volatility_regime": regime_state.volatility_regime,
            "trend_strength": regime_state.trend_strength,
            "expected_return": regime_state.expected_return,
            "expected_volatility": regime_state.expected_volatility,
            "regime_duration": regime_state.regime_duration,
            "position_scalar": regime_state.position_scalar,
            "stop_multiplier": regime_state.stop_multiplier,
            "profit_multiplier": regime_state.profit_multiplier,
            "probabilities": regime_state.probabilities,
            "fitted": brain.regime_fitted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regime detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/report")
async def get_risk_report(symbol: str = "SPY"):
    """
    Get comprehensive risk report.
    
    Includes:
    - Circuit breaker status
    - Drawdown metrics
    - CVaR/VaR tail risk
    - Regime shift detection
    - Position limits
    """
    brain = get_trading_brain()
    if brain is None:
        raise HTTPException(status_code=503, detail="TradingBrain not available")
    
    try:
        # Fetch market data for regime shift detection
        market_data = None
        try:
            service = await get_service()
            bars = await service.get_bars(symbol, timeframe="1d", limit=252)
            if bars:
                ohlcv = [
                    {
                        'timestamp': bar.timestamp.isoformat() if hasattr(bar, 'timestamp') else str(bar.get('timestamp', '')),
                        'close': bar.close if hasattr(bar, 'close') else bar.get('close', 0),
                    }
                    for bar in bars
                ]
                market_data = {'ohlcv': ohlcv}
        except Exception as e:
            logger.warning(f"Could not fetch market data for risk report: {e}")
        
        # Get full risk report
        report = brain.get_full_risk_report(market_data)
        
        return report
        
    except Exception as e:
        logger.error(f"Risk report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/brain/analyze")
async def analyze_symbol(symbol: str = "AAPL"):
    """
    Run full TradingBrain analysis on a symbol.
    
    Returns decision with:
    - Direction (LONG/SHORT/NEUTRAL)
    - Confidence level
    - Position size (Kelly-adjusted)
    - Entry/stop/target prices
    - Factors and warnings
    """
    brain = get_trading_brain()
    if brain is None:
        raise HTTPException(status_code=503, detail="TradingBrain not available")
    
    try:
        service = await get_service()
        
        # Fetch OHLCV data
        bars = await service.get_bars(symbol, timeframe="1d", limit=100)
        if not bars:
            raise HTTPException(status_code=400, detail=f"No data for {symbol}")
        
        # Get current quote
        quote = await service.get_quote(symbol)
        
        # Fetch SPY for regime detection
        spy_bars = await service.get_bars("SPY", timeframe="1d", limit=100)
        
        # Prepare market data
        ohlcv = [
            {
                'timestamp': bar.timestamp.isoformat() if hasattr(bar, 'timestamp') else str(bar.get('timestamp', '')),
                'open': bar.open if hasattr(bar, 'open') else bar.get('open', 0),
                'high': bar.high if hasattr(bar, 'high') else bar.get('high', 0),
                'low': bar.low if hasattr(bar, 'low') else bar.get('low', 0),
                'close': bar.close if hasattr(bar, 'close') else bar.get('close', 0),
                'volume': bar.volume if hasattr(bar, 'volume') else bar.get('volume', 0),
            }
            for bar in bars
        ]
        
        spy_ohlcv = [
            {
                'timestamp': bar.timestamp.isoformat() if hasattr(bar, 'timestamp') else str(bar.get('timestamp', '')),
                'open': bar.open if hasattr(bar, 'open') else bar.get('open', 0),
                'high': bar.high if hasattr(bar, 'high') else bar.get('high', 0),
                'low': bar.low if hasattr(bar, 'low') else bar.get('low', 0),
                'close': bar.close if hasattr(bar, 'close') else bar.get('close', 0),
                'volume': bar.volume if hasattr(bar, 'volume') else bar.get('volume', 0),
            }
            for bar in spy_bars
        ] if spy_bars else ohlcv
        
        market_data = {
            'ohlcv': ohlcv,
            'spy_ohlcv': spy_ohlcv,
            'quote': {
                'price': quote.last or quote.mid,
                'bid': quote.bid,
                'ask': quote.ask,
            },
            'avg_volume': sum(bar.volume if hasattr(bar, 'volume') else bar.get('volume', 0) for bar in bars[-20:]) / 20
        }
        
        # Run brain analysis
        decision = brain.think(symbol, market_data)
        
        return decision.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Brain analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/brain/status")
async def get_brain_status():
    """Get TradingBrain status including math integration."""
    brain = get_trading_brain()
    if brain is None:
        return {
            "initialized": False,
            "math_available": False,
            "message": "TradingBrain not initialized"
        }
    
    return {
        "initialized": True,
        "math_available": brain.risk_monitor is not None,
        "regime_detector": brain.get_regime_status(),
        "risk_status": brain.get_risk_status(),
        "account_equity": brain.account_equity
    }


# ==============================================================================
# BACKTESTING ENDPOINT
# ==============================================================================

@router.post("/backtest/run")
async def run_backtest(
    ticker: str = "SPY",
    strategy: str = "sma_cross",
    period: str = "1Y",
    capital: float = 100000
):
    """
    Run a simple backtest using available strategies.
    
    Strategies:
    - sma_cross: SMA crossover (20/50)
    - rsi_oversold: RSI < 30 buy, RSI > 70 sell
    - macd_cross: MACD crossover
    - momentum: Price momentum
    """
    try:
        import numpy as np
        
        # Fetch historical data
        service = await get_service()
        
        # Period mapping
        period_map = {
            "6M": 126,
            "1Y": 252,
            "2Y": 504,
            "5Y": 1260,
            "MAX": 2520
        }
        limit = period_map.get(period, 252)
        
        bars = await service.get_bars(ticker, timeframe="1d", limit=limit)
        
        if not bars or len(bars) < 50:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {ticker}")
        
        # Extract prices
        closes = np.array([
            bar.close if hasattr(bar, 'close') else bar.get('close', 0)
            for bar in bars
        ])
        
        # Simple SMA crossover backtest
        if strategy == "sma_cross":
            short_window = 20
            long_window = 50
            
            short_ma = np.convolve(closes, np.ones(short_window)/short_window, mode='valid')
            long_ma = np.convolve(closes, np.ones(long_window)/long_window, mode='valid')
            
            # Align arrays
            offset = short_window - 1
            long_ma_aligned = long_ma[offset - (long_window - short_window):]
            short_ma_aligned = short_ma[:len(long_ma_aligned)]
            closes_aligned = closes[long_window-1:long_window-1+len(long_ma_aligned)]
            
            # Generate signals
            signals = np.where(short_ma_aligned > long_ma_aligned, 1, -1)
            
        elif strategy == "rsi_oversold":
            # Simple RSI calculation
            delta = np.diff(closes)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            
            avg_gain = np.convolve(gain, np.ones(14)/14, mode='valid')
            avg_loss = np.convolve(loss, np.ones(14)/14, mode='valid')
            
            rs = avg_gain / (avg_loss + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            
            signals = np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0))
            closes_aligned = closes[14:14+len(signals)]
            
        else:
            # Default momentum
            returns = np.diff(closes) / closes[:-1]
            momentum = np.convolve(returns, np.ones(20)/20, mode='valid')
            signals = np.where(momentum > 0, 1, -1)
            closes_aligned = closes[20:20+len(signals)]
        
        # Calculate returns
        price_returns = np.diff(closes_aligned) / closes_aligned[:-1]
        strategy_returns = signals[:-1] * price_returns
        
        # Metrics
        cumulative = np.cumprod(1 + strategy_returns)
        total_return = (cumulative[-1] - 1) * 100
        
        # Annualize
        n_years = len(strategy_returns) / 252
        annual_return = ((cumulative[-1]) ** (1/max(n_years, 0.1)) - 1) * 100
        
        # Sharpe
        daily_std = np.std(strategy_returns)
        sharpe = (np.mean(strategy_returns) / daily_std) * np.sqrt(252) if daily_std > 0 else 0
        
        # Max drawdown
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak
        max_dd = np.max(drawdown) * 100
        
        # Win rate
        wins = np.sum(strategy_returns > 0)
        total_trades = np.sum(strategy_returns != 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Final equity
        final_equity = capital * cumulative[-1]
        
        return {
            "status": "completed",
            "ticker": ticker,
            "strategy": strategy,
            "period": period,
            "metrics": {
                "total_return": round(total_return, 2),
                "annual_return": round(annual_return, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
                "win_rate": round(win_rate, 1),
                "total_trades": int(total_trades),
                "final_equity": round(final_equity, 2),
                "initial_capital": capital
            },
            "equity_curve": (cumulative * capital).tolist()[-100:],  # Last 100 points
            "benchmark_return": round((closes[-1] / closes[0] - 1) * 100, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# MONTE CARLO SIMULATION ENDPOINT
# ==============================================================================

@router.post("/monte-carlo/simulate")
async def run_monte_carlo(
    ticker: str = "SPY",
    period: str = "1Y",
    simulations: int = 500,
    days_forward: int = 252,
    method: str = "bootstrap"  # bootstrap, shuffle, parametric
):
    """
    Run Monte Carlo simulation for future returns distribution.
    
    Returns:
        - Distribution of possible outcomes
        - VaR and CVaR metrics
        - Probability of loss
    """
    try:
        import numpy as np
        
        service = await get_service()
        
        # Period mapping
        period_map = {"6M": 126, "1Y": 252, "2Y": 504, "5Y": 1260}
        limit = period_map.get(period, 252)
        
        bars = await service.get_bars(ticker, timeframe="1d", limit=limit)
        
        if not bars or len(bars) < 50:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {ticker}")
        
        # Extract returns
        closes = np.array([bar.close if hasattr(bar, 'close') else bar.get('close', 0) for bar in bars])
        daily_returns = np.diff(closes) / closes[:-1]
        
        # Run simulations
        initial_capital = 100000
        n_sims = min(simulations, 1000)  # Cap at 1000
        days = min(days_forward, 504)  # Cap at 2 years
        
        equity_curves = np.zeros((n_sims, days + 1))
        equity_curves[:, 0] = initial_capital
        
        mu = np.mean(daily_returns)
        sigma = np.std(daily_returns)
        
        for sim in range(n_sims):
            if method == "bootstrap":
                sampled = np.random.choice(daily_returns, size=days, replace=True)
            elif method == "shuffle":
                sampled = np.random.permutation(daily_returns)
                if len(sampled) < days:
                    sampled = np.tile(sampled, days // len(sampled) + 1)[:days]
            else:  # parametric
                sampled = np.random.normal(mu, sigma, days)
            
            equity_curves[sim, 1:] = initial_capital * np.cumprod(1 + sampled)
        
        # Calculate metrics
        final_equity = equity_curves[:, -1]
        total_returns = (final_equity - initial_capital) / initial_capital
        
        # Max drawdowns
        max_drawdowns = []
        for sim in range(n_sims):
            curve = equity_curves[sim]
            peak = np.maximum.accumulate(curve)
            dd = (peak - curve) / peak
            max_drawdowns.append(np.max(dd))
        max_drawdowns = np.array(max_drawdowns)
        
        # Percentile curves for visualization (10th, 50th, 90th)
        percentile_10 = np.percentile(equity_curves, 10, axis=0)
        percentile_50 = np.percentile(equity_curves, 50, axis=0)
        percentile_90 = np.percentile(equity_curves, 90, axis=0)
        
        return {
            "ticker": ticker,
            "simulations": n_sims,
            "days_forward": days,
            "method": method,
            "historical": {
                "mean_daily_return": round(mu * 100, 4),
                "daily_volatility": round(sigma * 100, 4),
                "data_points": len(daily_returns)
            },
            "results": {
                "mean_return": round(np.mean(total_returns) * 100, 2),
                "median_return": round(np.median(total_returns) * 100, 2),
                "std_return": round(np.std(total_returns) * 100, 2),
                "percentile_5": round(np.percentile(total_returns, 5) * 100, 2),
                "percentile_25": round(np.percentile(total_returns, 25) * 100, 2),
                "percentile_75": round(np.percentile(total_returns, 75) * 100, 2),
                "percentile_95": round(np.percentile(total_returns, 95) * 100, 2),
                "probability_of_loss": round(np.mean(total_returns < 0) * 100, 1),
                "var_95": round(np.percentile(total_returns, 5) * 100, 2),
                "cvar_95": round(np.mean(total_returns[total_returns <= np.percentile(total_returns, 5)]) * 100, 2),
                "max_dd_mean": round(np.mean(max_drawdowns) * 100, 2),
                "max_dd_95": round(np.percentile(max_drawdowns, 95) * 100, 2)
            },
            "curves": {
                "percentile_10": percentile_10[::max(1, days//50)].tolist(),  # Subsample for frontend
                "percentile_50": percentile_50[::max(1, days//50)].tolist(),
                "percentile_90": percentile_90[::max(1, days//50)].tolist()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Monte Carlo error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# MULTI-AGENT SYSTEM ENDPOINT (PHASE 5)
# ==============================================================================

# Global agent manager instance
_agent_manager = None

def get_agent_manager():
    """Get or create the global agent manager."""
    global _agent_manager
    if _agent_manager is None:
        from brain.math.multi_agent import create_default_agent_team
        _agent_manager = create_default_agent_team()
        _agent_manager.start_all()
        logger.info("Multi-agent system initialized with default team")
    return _agent_manager


@router.get("/agents/status")
async def get_agents_status():
    """Get status of all trading agents."""
    try:
        manager = get_agent_manager()
        return manager.get_status()
    except Exception as e:
        logger.error(f"Agent status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/consensus")
async def get_agent_consensus(
    ticker: str = "SPY",
    period: str = "1M"
):
    """
    Get consensus decision from all agents for a symbol.
    
    Returns aggregated signal from multiple trading strategies.
    """
    try:
        import numpy as np
        
        service = await get_service()
        manager = get_agent_manager()
        
        # Period mapping
        period_map = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}
        limit = period_map.get(period, 63) + 50  # Extra for lookback
        
        bars = await service.get_bars(ticker, timeframe="1d", limit=limit)
        
        if not bars or len(bars) < 30:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {ticker}")
        
        # Extract market data
        closes = [bar.close if hasattr(bar, 'close') else bar.get('close', 0) for bar in bars]
        highs = [bar.high if hasattr(bar, 'high') else bar.get('high', 0) for bar in bars]
        lows = [bar.low if hasattr(bar, 'low') else bar.get('low', 0) for bar in bars]
        
        market_data = {
            'closes': closes,
            'highs': highs,
            'lows': lows
        }
        
        # Get consensus
        decision = manager.get_consensus_decision(ticker, market_data)
        
        if not decision:
            return {
                "ticker": ticker,
                "signal": "NO_SIGNAL",
                "message": "Insufficient agent signals"
            }
        
        # Get individual agent signals for detail
        signals = manager.get_agent_signals(ticker, market_data)
        agent_details = []
        for sig in signals:
            agent = manager.agents.get(sig.agent_id)
            agent_details.append({
                "agent": agent.name if agent else sig.agent_id,
                "signal": sig.signal_type.name,
                "confidence": round(sig.confidence, 2),
                "position_pct": round(sig.target_position_pct * 100, 1),
                "reasoning": sig.reasoning
            })
        
        return {
            "ticker": ticker,
            "consensus": {
                "signal": decision.consensus_signal.name,
                "confidence": round(decision.consensus_confidence, 2),
                "position_pct": round(decision.target_position_pct * 100, 1),
                "agreement": f"{decision.agreement_ratio:.0%}",
                "weighted_signal": round(decision.weighted_signal, 2)
            },
            "agents": agent_details,
            "recommendation": _get_recommendation(decision)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent consensus error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_recommendation(decision) -> str:
    """Generate human-readable recommendation."""
    signal = decision.consensus_signal.name
    confidence = decision.consensus_confidence
    agreement = decision.agreement_ratio
    
    if signal == "STRONG_BUY":
        action = "Strong Buy"
    elif signal == "BUY":
        action = "Buy"
    elif signal == "STRONG_SELL":
        action = "Strong Sell"
    elif signal == "SELL":
        action = "Sell"
    else:
        return "Hold - No clear directional signal from agents"
    
    if agreement >= 0.75:
        consensus = "Strong consensus"
    elif agreement >= 0.5:
        consensus = "Moderate consensus"
    else:
        consensus = "Weak consensus"
    
    if confidence >= 0.7:
        conf_str = "high confidence"
    elif confidence >= 0.4:
        conf_str = "moderate confidence"
    else:
        conf_str = "low confidence"
    
    return f"{action} - {consensus} ({agreement:.0%}) with {conf_str}"


@router.post("/agents/portfolio")
async def get_portfolio_allocation(
    tickers: str = "SPY,QQQ,AAPL,MSFT",
    period: str = "1M"
):
    """
    Get recommended portfolio allocation across multiple symbols.
    """
    try:
        import numpy as np
        
        service = await get_service()
        manager = get_agent_manager()
        
        symbols = [t.strip() for t in tickers.split(",")]
        period_map = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}
        limit = period_map.get(period, 63) + 50
        
        all_market_data = {}
        
        for symbol in symbols:
            try:
                bars = await service.get_bars(symbol, timeframe="1d", limit=limit)
                if bars and len(bars) >= 30:
                    all_market_data[symbol] = {
                        'closes': [bar.close if hasattr(bar, 'close') else bar.get('close', 0) for bar in bars],
                        'highs': [bar.high if hasattr(bar, 'high') else bar.get('high', 0) for bar in bars],
                        'lows': [bar.low if hasattr(bar, 'low') else bar.get('low', 0) for bar in bars]
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
        
        if not all_market_data:
            raise HTTPException(status_code=400, detail="No valid data for any symbols")
        
        # Get allocations
        allocations = manager.get_portfolio_allocation(
            list(all_market_data.keys()),
            all_market_data
        )
        
        # Format response
        portfolio = []
        total_long = 0
        total_short = 0
        
        for symbol, alloc in allocations.items():
            pct = alloc * 100
            if pct > 0:
                total_long += pct
            else:
                total_short += abs(pct)
            
            portfolio.append({
                "symbol": symbol,
                "allocation_pct": round(pct, 1),
                "direction": "LONG" if pct > 0 else "SHORT" if pct < 0 else "FLAT"
            })
        
        # Add symbols with no position
        for symbol in all_market_data.keys():
            if symbol not in allocations:
                portfolio.append({
                    "symbol": symbol,
                    "allocation_pct": 0,
                    "direction": "FLAT"
                })
        
        return {
            "portfolio": sorted(portfolio, key=lambda x: abs(x["allocation_pct"]), reverse=True),
            "summary": {
                "total_long_pct": round(total_long, 1),
                "total_short_pct": round(total_short, 1),
                "net_exposure_pct": round(total_long - total_short, 1),
                "gross_exposure_pct": round(total_long + total_short, 1),
                "cash_pct": round(100 - total_long - total_short, 1)
            },
            "agent_count": len(manager.agents)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portfolio allocation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
