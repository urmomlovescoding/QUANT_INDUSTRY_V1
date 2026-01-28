"""
Core API Routes
===============
Essential endpoints for frontend functionality.
"""

from fastapi import APIRouter
from datetime import datetime, timedelta
import random

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "market": {
            "session": "regular",
            "is_open": True,
            "is_pre_market": False,
            "is_after_hours": False
        },
        "services": {
            "database": True,
            "redis": True,
            "brain": True
        },
        "uptime": 3600
    }


@router.get("/system/status")
async def system_status():
    """System status"""
    return {
        "cpu_percent": random.uniform(10, 40),
        "memory_percent": random.uniform(30, 60),
        "gpu_available": True,
        "gpu_percent": random.uniform(5, 30),
        "active_connections": random.randint(1, 10),
        "uptime_hours": 24.5
    }


@router.get("/market/status")
async def market_status():
    """Market status"""
    now = datetime.now()
    hour = now.hour
    
    if 9 <= hour < 16:
        session = "regular"
        is_open = True
    elif 4 <= hour < 9:
        session = "pre_market"
        is_open = True
    elif 16 <= hour < 20:
        session = "after_hours"
        is_open = True
    else:
        session = "closed"
        is_open = False
    
    return {
        "session": session,
        "is_open": is_open,
        "is_pre_market": session == "pre_market",
        "is_after_hours": session == "after_hours",
        "next_open": (now + timedelta(hours=8)).isoformat() if not is_open else None,
        "next_close": (now.replace(hour=16, minute=0)).isoformat() if is_open else None
    }


@router.get("/market/tickers")
async def get_tickers(symbols: str = "SPY,QQQ,DIA,IWM"):
    """Get market tickers"""
    symbol_list = symbols.split(",")
    base_prices = {"SPY": 585.42, "QQQ": 512.88, "DIA": 428.15, "IWM": 225.33, 
                   "AAPL": 242.50, "MSFT": 445.80, "NVDA": 142.30, "TSLA": 425.60}
    
    return [
        {
            "symbol": s,
            "price": base_prices.get(s, 100) * (1 + random.uniform(-0.02, 0.02)),
            "change": random.uniform(-5, 5),
            "change_pct": random.uniform(-1.5, 1.5),
            "volume": random.randint(1000000, 50000000),
            "bid": base_prices.get(s, 100) * 0.999,
            "ask": base_prices.get(s, 100) * 1.001
        }
        for s in symbol_list
    ]


@router.get("/market/quote/{symbol}")
async def get_quote(symbol: str):
    """Get quote for symbol"""
    base = {"SPY": 585, "QQQ": 512, "AAPL": 242, "MSFT": 445, "NVDA": 142}.get(symbol, 100)
    price = base * (1 + random.uniform(-0.01, 0.01))
    change = random.uniform(-3, 3)
    
    return {
        "symbol": symbol,
        "price": price,
        "bid": price * 0.999,
        "ask": price * 1.001,
        "change": change,
        "change_pct": change / price * 100,
        "volume": random.randint(1000000, 50000000),
        "high": price * 1.02,
        "low": price * 0.98,
        "open": price * (1 + random.uniform(-0.005, 0.005)),
        "prev_close": price - change,
        "source": "mock",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/brain-v6/status")
async def brain_status():
    """Trading brain status"""
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
    """Feedback loop status"""
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


@router.get("/signals")
@router.get("/signals/active")
async def get_signals():
    """Get active signals"""
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
    """Get current positions"""
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
    """Get portfolio summary"""
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
    """Get portfolio performance"""
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


@router.get("/risk/metrics")
async def get_risk_metrics():
    """Get risk metrics"""
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
    """Get safety status"""
    return {
        "is_safe": True,
        "breaches": [],
        "warnings": ["Approaching daily loss limit (85%)"],
        "daily_loss": 850.00,
        "max_daily_loss": 1000.00,
        "current_drawdown": 0.05,
        "max_drawdown_limit": 0.20
    }


@router.get("/ml/regime")
async def get_regime():
    """Get market regime"""
    return {
        "regime": random.choice(["trending", "ranging", "volatile", "quiet"]),
        "confidence": random.uniform(0.7, 0.95),
        "volatility": random.uniform(0.1, 0.3),
        "trend_strength": random.uniform(0.3, 0.8)
    }


@router.get("/news")
async def get_news(symbol: str = None):
    """Get market news"""
    news_items = [
        {"title": "Fed Signals Rate Cuts Ahead", "source": "Bloomberg", "sentiment": "positive"},
        {"title": "Tech Earnings Beat Expectations", "source": "Reuters", "sentiment": "positive"},
        {"title": "Oil Prices Surge on Supply Concerns", "source": "CNBC", "sentiment": "neutral"},
        {"title": "China Trade Data Shows Weakness", "source": "FT", "sentiment": "negative"},
        {"title": "AI Stocks Rally on Strong Demand", "source": "WSJ", "sentiment": "positive"},
    ]
    
    return [
        {
            "id": f"news-{i}",
            "title": item["title"],
            "summary": f"Breaking: {item['title']}. Market analysts weigh in on implications...",
            "source": item["source"],
            "url": f"https://example.com/news/{i}",
            "symbols": [symbol] if symbol else ["SPY", "QQQ"],
            "sentiment": item["sentiment"],
            "published_at": (datetime.now() - timedelta(hours=i)).isoformat()
        }
        for i, item in enumerate(news_items)
    ]


@router.get("/settings")
async def get_settings():
    """Get user settings"""
    return {
        "theme": "dark",
        "notifications_enabled": True,
        "auto_refresh_interval": 15,
        "default_order_type": "limit",
        "risk_params": {
            "max_position_size": 0.1,
            "max_daily_loss": 1000,
            "max_drawdown": 0.2
        }
    }


@router.get("/settings/api-keys")
async def get_api_keys():
    """Get API key status"""
    return {
        "alpaca": True,
        "tradier": False,
        "polygon": True
    }
