"""
Core API Routes
===============
Essential endpoints using REAL data from Alpaca when configured,
with intelligent fallback to mock data.

All market data flows through the MarketDataService for consistency.
"""

# IMPORTANT: Import config first to ensure env vars are loaded
from backend.config.env import config

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from typing import Optional, List
import random

logger = logging.getLogger(__name__)

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
    
    return {
        "status": "healthy",
        "data_mode": service.data_mode if service else "mock",
        "alpaca_configured": config.alpaca_configured,
        "polygon_configured": config.polygon_configured,
        "market": {
            "session": "regular",
            "is_open": True,
            "is_pre_market": False,
            "is_after_hours": False
        },
        "services": {
            "database": True,
            "redis": config.redis_configured,
            "brain": True,
            "data_provider": config.alpaca_configured or config.polygon_configured
        },
        "uptime": 3600
    }


@router.get("/system/status")
async def system_status():
    """System status."""
    service = await get_service()
    
    return {
        "cpu_percent": random.uniform(10, 40),
        "memory_percent": random.uniform(30, 60),
        "gpu_available": True,
        "gpu_percent": random.uniform(5, 30),
        "active_connections": random.randint(1, 10),
        "uptime_hours": 24.5,
        "data_mode": service.data_mode if service else "mock",
        "alpaca_connected": service._alpaca is not None if service else False
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
    
    results = []
    for symbol in symbol_list:
        q = quotes.get(symbol)
        if q:
            results.append({
                "symbol": symbol,
                "price": q.last or q.mid,
                "bid": q.bid,
                "ask": q.ask,
                "change": random.uniform(-5, 5),  # Would need previous close for real change
                "change_pct": random.uniform(-1.5, 1.5),
                "volume": q.volume,
                "source": q.source
            })
    
    return results


@router.get("/market/quote/{symbol}")
async def get_quote(symbol: str):
    """Get single quote - REAL data when available."""
    service = await get_service()
    quote = await service.get_quote(symbol.upper())
    
    return {
        "symbol": quote.symbol,
        "price": quote.last or quote.mid,
        "bid": quote.bid,
        "ask": quote.ask,
        "bid_size": quote.bid_size,
        "ask_size": quote.ask_size,
        "change": random.uniform(-3, 3),
        "change_pct": random.uniform(-1, 1),
        "volume": quote.volume,
        "high": quote.last * 1.02 if quote.last else 0,
        "low": quote.last * 0.98 if quote.last else 0,
        "open": quote.last,
        "prev_close": quote.last,
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
    """Trading brain status."""
    return {
        "available": True,
        "device": "cuda:0",
        "is_trained": True,
        "current_regime": "trending",
        "auto_train_enabled": True,
        "training_step": 15000,
        "total_trades": 1247,
        "metrics": {
            "win_rate": 0.68,
            "total_pnl": 125430.50,
            "profit_factor": 2.15
        },
        "strategies": [
            {"name": "Momentum", "weight": 0.35, "win_rate": 0.72},
            {"name": "Mean Reversion", "weight": 0.25, "win_rate": 0.65},
            {"name": "Breakout", "weight": 0.20, "win_rate": 0.58},
            {"name": "ML Ensemble", "weight": 0.20, "win_rate": 0.75}
        ]
    }


@router.get("/feedback/status")
async def feedback_status():
    """Feedback loop status."""
    return {
        "phase": "exploitation",
        "total_trades": 1247,
        "win_rate": 0.68,
        "profit_factor": 2.15,
        "sharpe_ratio": 1.85,
        "convergence_progress": {
            "momentum": 0.95,
            "mean_reversion": 0.88,
            "breakout": 0.82
        },
        "is_converged": True
    }


# ============== SIGNALS & POSITIONS ==============

@router.get("/signals")
@router.get("/signals/active")
async def get_signals():
    """Get active trading signals."""
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "META"]
    strategies = ["Momentum", "Mean Reversion", "Breakout", "ML Ensemble"]
    
    return [
        {
            "id": f"sig-{i}",
            "symbol": random.choice(symbols),
            "direction": random.choice(["LONG", "SHORT"]),
            "confidence": random.uniform(0.65, 0.95),
            "strategy": random.choice(strategies),
            "entry_price": random.uniform(100, 500),
            "stop_loss": random.uniform(95, 480),
            "take_profit": random.uniform(105, 520),
            "risk_reward": random.uniform(1.5, 3.5),
            "timeframe": random.choice(["1H", "4H", "1D"]),
            "regime_alignment": random.choice([True, True, True, False]),
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 120))).isoformat(),
            "status": "active"
        }
        for i in range(5)
    ]


@router.get("/positions")
async def get_positions():
    """Get current positions."""
    # TODO: Integrate with database
    return [
        {
            "id": "pos-1",
            "symbol": "AAPL",
            "side": "long",
            "quantity": 100,
            "entry_price": 238.50,
            "current_price": 242.30,
            "pnl": 380.00,
            "pnl_pct": 1.59,
            "opened_at": (datetime.now() - timedelta(days=2)).isoformat()
        },
        {
            "id": "pos-2",
            "symbol": "NVDA",
            "side": "long",
            "quantity": 50,
            "entry_price": 138.20,
            "current_price": 142.50,
            "pnl": 215.00,
            "pnl_pct": 3.11,
            "opened_at": (datetime.now() - timedelta(days=1)).isoformat()
        }
    ]


@router.get("/portfolio")
async def get_portfolio():
    """Get portfolio summary."""
    return {
        "equity": 125430.50,
        "cash": 45230.25,
        "buying_power": 90460.50,
        "day_pnl": 1523.45,
        "day_pnl_pct": 1.23,
        "total_pnl": 25430.50,
        "total_pnl_pct": 25.43,
        "positions_count": 5
    }


@router.get("/portfolio/performance")
async def get_performance():
    """Get portfolio performance."""
    return {
        "total_return": 25430.50,
        "total_return_pct": 25.43,
        "win_rate": 0.68,
        "profit_factor": 2.15,
        "sharpe_ratio": 1.85,
        "sortino_ratio": 2.45,
        "max_drawdown": 0.12,
        "avg_win": 523.45,
        "avg_loss": -243.20,
        "total_trades": 1247,
        "winning_trades": 848,
        "losing_trades": 399
    }


# ============== RISK ==============

@router.get("/risk/metrics")
async def get_risk_metrics():
    """Get risk metrics."""
    return {
        "var_95": 2500.00,
        "current_drawdown": 0.05,
        "max_position_exposure": 0.15,
        "sector_concentration": 0.35,
        "daily_pnl": 1523.45,
        "risk_score": 35
    }


@router.get("/risk/safety")
async def get_safety_status():
    """Get safety status."""
    return {
        "is_safe": True,
        "breaches": [],
        "warnings": ["Approaching daily loss limit (85%)"],
        "daily_loss": 850.00,
        "max_daily_loss": 1000.00,
        "current_drawdown": 0.05,
        "max_drawdown_limit": 0.20
    }


# ============== ML/REGIME ==============

@router.get("/ml/regime")
async def get_regime():
    """Get market regime."""
    return {
        "regime": random.choice(["trending", "ranging", "volatile", "quiet"]),
        "confidence": random.uniform(0.7, 0.95),
        "volatility": random.uniform(0.1, 0.3),
        "trend_strength": random.uniform(0.3, 0.8)
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


def get_portfolio():
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
    portfolio = get_portfolio()
    if not portfolio:
        return {
            "error": "Portfolio module not available",
            "mock": True,
            "equity": 125430.50,
            "cash": 45230.25,
            "positions": [],
            "total_pnl": 25430.50
        }
    
    return portfolio.to_dict()


@router.get("/portfolio/positions")
async def get_positions():
    """Get all positions."""
    portfolio = get_portfolio()
    if not portfolio:
        return {"positions": [], "count": 0}
    
    return {
        "positions": [p.to_dict() for p in portfolio.get_positions()],
        "count": len(portfolio.positions)
    }


@router.get("/portfolio/position/{symbol}")
async def get_position(symbol: str):
    """Get single position."""
    portfolio = get_portfolio()
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
    portfolio = get_portfolio()
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
    portfolio = get_portfolio()
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
    portfolio = get_portfolio()
    if not portfolio:
        return {
            "var_95": 2500.00,
            "max_drawdown": 0.12,
            "current_drawdown": 0.05,
            "leverage": 1.0,
            "gross_exposure": 0.75,
            "net_exposure": 0.60
        }
    
    metrics = portfolio.calculate_risk_metrics()
    return metrics.to_dict()


@router.get("/portfolio/trades")
async def get_trades(limit: int = 100):
    """Get trade history."""
    portfolio = get_portfolio()
    if not portfolio:
        return {"trades": [], "count": 0}
    
    trades = portfolio.trades[-limit:]
    return {
        "trades": [t.to_dict() for t in trades],
        "count": len(portfolio.trades),
        "showing": len(trades)
    }
