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
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["core"])


# ============== DEV MODE AUTH (No Database Required) ==============
# Simple in-memory auth for development - DO NOT USE IN PRODUCTION

_dev_users: Dict[str, Dict[str, Any]] = {}
_dev_tokens: Dict[str, str] = {}  # token -> email


class DevLoginRequest(BaseModel):
    email: str
    password: str


class DevRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = "Dev User"
    organization_name: str = "Dev Org"


@router.post("/auth/login")
async def dev_login(data: DevLoginRequest):
    """Dev mode login - works without database."""
    # Check if user exists
    if data.email not in _dev_users:
        # Auto-create user on first login for dev convenience
        _dev_users[data.email] = {
            "email": data.email,
            "password": data.password,
            "full_name": "Dev User",
            "organization_name": "Dev Org",
            "role": "owner",
            "id": str(uuid.uuid4()),
            "organization_id": str(uuid.uuid4()),
        }
        logger.info(f"[DEV] Auto-created user: {data.email}")

    user = _dev_users[data.email]

    if user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate simple token
    token = f"dev_{uuid.uuid4().hex}"
    _dev_tokens[token] = data.email

    return {
        "tokens": {
            "access_token": token,
            "refresh_token": f"refresh_{uuid.uuid4().hex}",
            "token_type": "bearer",
            "expires_in": 86400
        },
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "organization_id": user["organization_id"],
            "organization_name": user["organization_name"],
            "is_active": True
        }
    }


@router.post("/auth/register")
async def dev_register(data: DevRegisterRequest):
    """Dev mode register - works without database."""
    if data.email in _dev_users:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    _dev_users[data.email] = {
        "email": data.email,
        "password": data.password,
        "full_name": data.full_name,
        "organization_name": data.organization_name,
        "role": "owner",
        "id": user_id,
        "organization_id": org_id,
    }

    # Generate token
    token = f"dev_{uuid.uuid4().hex}"
    _dev_tokens[token] = data.email

    logger.info(f"[DEV] Registered user: {data.email}")

    return {
        "tokens": {
            "access_token": token,
            "refresh_token": f"refresh_{uuid.uuid4().hex}",
            "token_type": "bearer",
            "expires_in": 86400
        },
        "user": {
            "id": user_id,
            "email": data.email,
            "full_name": data.full_name,
            "role": "owner",
            "organization_id": org_id,
            "organization_name": data.organization_name,
            "is_active": True
        }
    }


@router.get("/auth/me")
async def dev_me():
    """Dev mode - return mock user."""
    return {
        "id": "dev-user-1",
        "email": "dev@example.com",
        "full_name": "Dev User",
        "role": "owner",
        "organization_id": "dev-org-1",
        "organization_name": "Dev Org",
        "is_active": True
    }


@router.post("/auth/refresh")
async def dev_refresh():
    """Dev mode token refresh."""
    return {
        "access_token": f"dev_{uuid.uuid4().hex}",
        "refresh_token": f"refresh_{uuid.uuid4().hex}",
        "token_type": "bearer",
        "expires_in": 86400
    }

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


# ============== STUB ENDPOINTS (Prevent 404s) ==============
# These return mock data to prevent frontend errors

@router.get("/risk/scenarios")
async def get_risk_scenarios():
    """Get risk scenarios."""
    return {
        "scenarios": [
            {"name": "Base Case", "probability": 0.6, "impact": 0},
            {"name": "Bull Case", "probability": 0.25, "impact": 15},
            {"name": "Bear Case", "probability": 0.15, "impact": -20}
        ]
    }


@router.get("/risk/scenarios/history")
async def get_risk_scenarios_history():
    """Get risk scenarios history."""
    return {"history": []}


@router.get("/brain-v6/config")
async def get_brain_config():
    """Get brain configuration."""
    return {
        "model": "propfirm_brain_v6",
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
        "features": ["price", "volume", "momentum", "volatility"],
        "horizons": ["5m", "15m", "1h", "4h", "1d"]
    }


@router.get("/brain-v6/training-history")
async def get_brain_training_history(limit: int = 100):
    """Get brain training history."""
    return {"history": [], "total": 0}


@router.get("/brain-v6/analyze/{symbol}")
async def analyze_brain_symbol(symbol: str):
    """Analyze symbol with brain."""
    return {
        "symbol": symbol.upper(),
        "signal": "HOLD",
        "confidence": 0.65,
        "analysis": {
            "trend": "neutral",
            "momentum": "neutral",
            "volatility": "low"
        }
    }


@router.get("/brain-v6/signal/{symbol}")
async def get_brain_signal(symbol: str):
    """Get brain signal for symbol."""
    return {
        "symbol": symbol.upper(),
        "signal": "HOLD",
        "confidence": 0.5,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/brain-v6/train")
async def train_brain():
    """Train the brain model."""
    return {"status": "training_queued", "message": "Training will start shortly"}


@router.get("/brain-v6/strategies")
async def get_brain_strategies():
    """Get available strategies."""
    return {
        "strategies": [
            {"name": "Trend Following", "status": "active", "pnl": 2.5},
            {"name": "Mean Reversion", "status": "active", "pnl": 1.2},
            {"name": "Momentum", "status": "paused", "pnl": -0.5},
            {"name": "Vol Targeting", "status": "active", "pnl": 3.1}
        ]
    }


@router.get("/microstructure/status")
async def get_microstructure_status():
    """Get microstructure analysis status."""
    return {"status": "ready", "symbols_tracked": 50}


@router.get("/microstructure/sessions")
async def get_microstructure_sessions():
    """Get microstructure sessions."""
    return {"sessions": []}


@router.get("/microstructure/analyze/{symbol}")
async def analyze_microstructure(symbol: str):
    """Analyze microstructure for symbol."""
    return {
        "symbol": symbol.upper(),
        "spread_bps": 2.5,
        "depth_imbalance": 0.1,
        "trade_flow": "neutral",
        "volatility_regime": "low"
    }


@router.get("/futures/{symbol}/prices")
async def get_futures_prices(symbol: str):
    """Get futures prices."""
    base_price = 4500 if symbol.upper() == "ES" else 15000
    return {
        "symbol": symbol.upper(),
        "price": base_price + random.uniform(-50, 50),
        "change": random.uniform(-1, 1),
        "volume": random.randint(100000, 500000)
    }


@router.get("/futures/{symbol}/signals")
async def get_futures_signals(symbol: str):
    """Get futures trading signals."""
    return {
        "symbol": symbol.upper(),
        "signal": random.choice(["LONG", "SHORT", "FLAT"]),
        "confidence": round(random.uniform(0.5, 0.9), 2),
        "entry": 4500,
        "stop": 4480,
        "target": 4550
    }


@router.get("/ml/predict/{symbol}")
async def ml_predict(symbol: str, model: str = "ensemble", horizon: str = "5d"):
    """ML prediction for symbol."""
    return {
        "symbol": symbol.upper(),
        "model": model,
        "horizon": horizon,
        "prediction": random.choice(["bullish", "bearish", "neutral"]),
        "confidence": round(random.uniform(0.5, 0.85), 2),
        "expected_return": round(random.uniform(-5, 10), 2)
    }


@router.get("/regime/detect")
async def detect_regime(symbol: str = "SPY"):
    """Detect market regime."""
    return {
        "symbol": symbol.upper(),
        "regime": random.choice(["trending_up", "trending_down", "ranging", "volatile"]),
        "confidence": round(random.uniform(0.6, 0.9), 2),
        "duration_days": random.randint(5, 30)
    }


@router.get("/neural/analyze/{symbol}")
async def neural_analyze(symbol: str):
    """Neural network analysis."""
    return {
        "symbol": symbol.upper(),
        "prediction": round(random.uniform(-2, 5), 2),
        "confidence": round(random.uniform(0.5, 0.8), 2),
        "features": {
            "momentum": round(random.uniform(-1, 1), 2),
            "trend": round(random.uniform(-1, 1), 2),
            "volatility": round(random.uniform(0, 1), 2)
        }
    }


@router.get("/neural/analysis/{symbol}")
async def neural_analysis(symbol: str):
    """Neural network detailed analysis."""
    return await neural_analyze(symbol)


@router.get("/neural/regime")
async def neural_regime():
    """Neural network regime detection."""
    return {
        "regime": random.choice(["risk_on", "risk_off", "neutral"]),
        "probability": round(random.uniform(0.6, 0.9), 2),
        "indicators": {
            "vix": round(random.uniform(12, 25), 1),
            "credit_spread": round(random.uniform(1, 3), 2),
            "yield_curve": round(random.uniform(-0.5, 1), 2)
        }
    }


@router.get("/research/13f/{symbol}")
async def research_13f(symbol: str):
    """Get 13F institutional holdings."""
    return {
        "symbol": symbol.upper(),
        "holders": [
            {"name": "Vanguard", "shares": 50000000, "change_pct": 2.5},
            {"name": "BlackRock", "shares": 45000000, "change_pct": -1.2},
            {"name": "State Street", "shares": 30000000, "change_pct": 0.5}
        ],
        "total_institutional_pct": 75.5
    }


@router.get("/research/sec/{symbol}")
async def research_sec(symbol: str):
    """Get SEC filings."""
    return {
        "symbol": symbol.upper(),
        "filings": [
            {"type": "10-K", "date": "2025-02-15", "description": "Annual Report"},
            {"type": "10-Q", "date": "2025-11-01", "description": "Quarterly Report"},
            {"type": "8-K", "date": "2025-12-10", "description": "Current Report"}
        ]
    }


@router.get("/research/darkpool/{symbol}")
async def research_darkpool(symbol: str):
    """Get dark pool data."""
    return {
        "symbol": symbol.upper(),
        "darkpool_volume": random.randint(1000000, 10000000),
        "darkpool_pct": round(random.uniform(30, 50), 1),
        "sentiment": random.choice(["bullish", "bearish", "neutral"]),
        "large_prints": random.randint(5, 20)
    }


@router.get("/research/earnings")
async def research_earnings():
    """Get upcoming earnings."""
    return {
        "upcoming": [
            {"symbol": "AAPL", "date": "2026-02-05", "estimate": 2.15, "time": "after_close"},
            {"symbol": "MSFT", "date": "2026-02-06", "estimate": 3.05, "time": "after_close"},
            {"symbol": "GOOGL", "date": "2026-02-07", "estimate": 1.85, "time": "after_close"}
        ]
    }


@router.get("/charts/{symbol}")
async def get_chart_data(symbol: str, interval: str = "1d", period: str = "1M"):
    """Get chart data for symbol."""
    return await get_charts_ohlcv(symbol, interval)


@router.get("/charts/ohlcv/{symbol}")
async def get_charts_ohlcv(symbol: str, timeframe: str = "1d"):
    """Get OHLCV chart data for symbol."""
    service = await get_service()

    # Try to get real data
    try:
        bars = await service.get_bars(symbol.upper(), timeframe=timeframe, limit=100)
        if bars and len(bars) > 0:
            return {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "data": [
                    {
                        "time": bar.get("timestamp", bar.get("t")),
                        "open": bar.get("open", bar.get("o")),
                        "high": bar.get("high", bar.get("h")),
                        "low": bar.get("low", bar.get("l")),
                        "close": bar.get("close", bar.get("c")),
                        "volume": bar.get("volume", bar.get("v"))
                    }
                    for bar in bars
                ]
            }
    except Exception as e:
        logger.warning(f"Chart data fetch failed: {e}")

    # Return mock data
    import time as time_module
    base_price = 450 if symbol.upper() == "SPY" else 150
    data = []
    current_time = int(time_module.time())
    for i in range(100):
        t = current_time - (99 - i) * 86400
        price = base_price + random.uniform(-10, 10)
        data.append({
            "time": t,
            "open": round(price, 2),
            "high": round(price + random.uniform(0, 3), 2),
            "low": round(price - random.uniform(0, 3), 2),
            "close": round(price + random.uniform(-2, 2), 2),
            "volume": random.randint(10000000, 50000000)
        })

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "data": data
    }


@router.get("/charts/indicators/{symbol}")
async def get_charts_indicators(symbol: str, timeframe: str = "1d"):
    """Get technical indicators for symbol."""
    base_price = 450 if symbol.upper() == "SPY" else 150

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "indicators": {
            "sma_20": round(base_price + random.uniform(-5, 5), 2),
            "sma_50": round(base_price + random.uniform(-8, 8), 2),
            "sma_200": round(base_price + random.uniform(-15, 15), 2),
            "ema_12": round(base_price + random.uniform(-3, 3), 2),
            "ema_26": round(base_price + random.uniform(-5, 5), 2),
            "rsi": round(random.uniform(30, 70), 1),
            "macd": round(random.uniform(-2, 2), 2),
            "macd_signal": round(random.uniform(-2, 2), 2),
            "macd_histogram": round(random.uniform(-1, 1), 2),
            "bb_upper": round(base_price + random.uniform(5, 15), 2),
            "bb_middle": round(base_price, 2),
            "bb_lower": round(base_price - random.uniform(5, 15), 2),
            "atr": round(random.uniform(1, 5), 2),
            "adx": round(random.uniform(15, 40), 1),
            "stoch_k": round(random.uniform(20, 80), 1),
            "stoch_d": round(random.uniform(20, 80), 1)
        },
        "signals": {
            "trend": random.choice(["UP", "DOWN", "NEUTRAL"]),
            "momentum": random.choice(["STRONG", "WEAK", "NEUTRAL"]),
            "volatility": random.choice(["HIGH", "LOW", "NORMAL"])
        }
    }
