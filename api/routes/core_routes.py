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
