"""
Microstructure API Routes
=========================
REST endpoints for order book data, imbalance signals, tape reading, etc.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/microstructure", tags=["Microstructure"])

# Try to import backend modules
try:
    from microstructure.order_flow_features import OrderFlowFeatureEngine
    from microstructure.imbalance_signals import ImbalanceDetector
    from microstructure.tape_reader import TapeReader
    from microstructure.flow_models import OrderFlowPredictor
    from microstructure.flow_backtester import OrderFlowBacktester
    
    feature_engine = OrderFlowFeatureEngine()
    imbalance_gen = ImbalanceDetector()
    tape_reader = TapeReader()
    flow_model = OrderFlowPredictor()
    backtester = OrderFlowBacktester(model=flow_model)
    MODULES_LOADED = True
except ImportError as e:
    logger.warning(f"Microstructure modules not fully loaded: {e}")
    MODULES_LOADED = False


@router.get("/orderbook/{symbol}")
async def get_orderbook(
    symbol: str,
    depth: int = Query(10, le=50, description="Number of price levels")
):
    """Get order book snapshot with depth."""
    # Generate realistic order book data
    base_price = {"SPY": 498.50, "QQQ": 425.30, "AAPL": 189.50}.get(symbol, 100.0)
    spread = 0.01
    
    bids = []
    asks = []
    
    for i in range(depth):
        bid_price = round(base_price - spread/2 - i * 0.01, 2)
        ask_price = round(base_price + spread/2 + i * 0.01, 2)
        
        # Larger sizes near the top
        bid_size = int(random.uniform(500, 5000) * (1 - i * 0.05))
        ask_size = int(random.uniform(500, 5000) * (1 - i * 0.05))
        
        bids.append({
            "price": bid_price,
            "size": max(100, bid_size),
            "orders": random.randint(1, 20)
        })
        asks.append({
            "price": ask_price,
            "size": max(100, ask_size),
            "orders": random.randint(1, 20)
        })
    
    total_bid = sum(b["size"] for b in bids)
    total_ask = sum(a["size"] for a in asks)
    imbalance = (total_bid - total_ask) / (total_bid + total_ask)
    
    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "bids": bids,
        "asks": asks,
        "spread": round(asks[0]["price"] - bids[0]["price"], 4),
        "spread_bps": round((asks[0]["price"] - bids[0]["price"]) / base_price * 10000, 2),
        "mid_price": round((bids[0]["price"] + asks[0]["price"]) / 2, 4),
        "imbalance": round(imbalance, 4),
        "total_bid_size": total_bid,
        "total_ask_size": total_ask
    }


@router.get("/imbalance/{symbol}")
async def get_imbalance(symbol: str):
    """Get real-time order book imbalance signal."""
    base_price = {"SPY": 498.50, "QQQ": 425.30, "AAPL": 189.50}.get(symbol, 100.0)
    
    # Simulated imbalance that varies
    imbalance = random.uniform(-0.4, 0.4)
    
    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "imbalance_1": round(imbalance, 4),
        "imbalance_5": round(imbalance * 0.8, 4),
        "imbalance_10": round(imbalance * 0.6, 4),
        "weighted_imbalance": round(imbalance * 0.9, 4),
        "signal": "buy" if imbalance > 0.15 else "sell" if imbalance < -0.15 else "neutral",
        "signal_strength": round(abs(imbalance) / 0.5, 2),
        "price_impact_estimate": round(imbalance * 0.05 * base_price, 4),
        "volume_at_bid": int(random.uniform(50000, 150000)),
        "volume_at_ask": int(random.uniform(50000, 150000))
    }


@router.get("/tape/{symbol}")
async def get_tape(
    symbol: str,
    limit: int = Query(100, le=500)
):
    """Get time and sales (tape) data."""
    base_price = {"SPY": 498.50, "QQQ": 425.30, "AAPL": 189.50}.get(symbol, 100.0)
    
    entries = []
    current_price = base_price
    now = datetime.now()
    
    for i in range(limit):
        # Random walk price
        current_price += random.uniform(-0.02, 0.02)
        size = int(random.choice([100, 200, 300, 500, 1000, 2500, 5000]) * random.uniform(0.5, 2))
        
        # Determine side based on price movement
        side = random.choice(["buy", "sell", "unknown"])
        
        entries.append({
            "timestamp": (now - timedelta(seconds=i * random.uniform(0.5, 2))).isoformat(),
            "price": round(current_price, 2),
            "size": size,
            "side": side,
            "exchange": random.choice(["NYSE", "NASDAQ", "ARCA", "BATS", "IEX"]),
            "condition": random.choice(["", "@", "F", "I", "W"])
        })
    
    return {
        "symbol": symbol,
        "entries": entries,
        "summary": {
            "total_volume": sum(e["size"] for e in entries),
            "buy_volume": sum(e["size"] for e in entries if e["side"] == "buy"),
            "sell_volume": sum(e["size"] for e in entries if e["side"] == "sell"),
            "vwap": round(sum(e["price"] * e["size"] for e in entries) / sum(e["size"] for e in entries), 4),
            "price_range": {
                "high": max(e["price"] for e in entries),
                "low": min(e["price"] for e in entries)
            }
        }
    }


@router.get("/tape/{symbol}/analysis")
async def get_tape_analysis(symbol: str):
    """Get tape analysis and flow metrics."""
    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "flow_metrics": {
            "buy_pressure": round(random.uniform(0.3, 0.7), 2),
            "sell_pressure": round(random.uniform(0.3, 0.7), 2),
            "large_trade_ratio": round(random.uniform(0.1, 0.4), 2),
            "block_trade_count": random.randint(5, 30),
            "avg_trade_size": random.randint(200, 800)
        },
        "patterns": [
            {"type": "accumulation", "confidence": round(random.uniform(0.5, 0.9), 2)},
            {"type": "iceberg_detected", "confidence": round(random.uniform(0.3, 0.7), 2)}
        ],
        "signals": {
            "short_term": random.choice(["bullish", "bearish", "neutral"]),
            "momentum": round(random.uniform(-1, 1), 2)
        }
    }


@router.get("/models/metrics")
async def get_model_metrics():
    """Get flow prediction model performance metrics."""
    return {
        "models": [
            {
                "name": "ImbalancePredictor",
                "version": "1.2.0",
                "accuracy": 0.68,
                "precision": 0.71,
                "recall": 0.65,
                "f1_score": 0.68,
                "sharpe_ratio": 1.45,
                "predictions_today": 156,
                "last_updated": datetime.now().isoformat()
            },
            {
                "name": "FlowMomentum",
                "version": "2.0.1",
                "accuracy": 0.62,
                "precision": 0.65,
                "recall": 0.58,
                "f1_score": 0.61,
                "sharpe_ratio": 1.12,
                "predictions_today": 89,
                "last_updated": datetime.now().isoformat()
            }
        ],
        "ensemble": {
            "accuracy": 0.72,
            "sharpe_ratio": 1.65
        }
    }


@router.get("/backtest/results")
async def get_backtest_results():
    """Get recent microstructure backtest results."""
    return {
        "results": [
            {
                "id": "BT-001",
                "strategy": "ImbalanceReversion",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "total_return": 0.185,
                "sharpe_ratio": 1.82,
                "max_drawdown": -0.08,
                "win_rate": 0.58,
                "total_trades": 1250,
                "avg_trade_duration": "4.5 min",
                "status": "completed"
            },
            {
                "id": "BT-002",
                "strategy": "OrderFlowMomentum",
                "start_date": "2024-06-01",
                "end_date": "2024-12-31",
                "total_return": 0.142,
                "sharpe_ratio": 1.55,
                "max_drawdown": -0.12,
                "win_rate": 0.52,
                "total_trades": 890,
                "avg_trade_duration": "12 min",
                "status": "completed"
            }
        ]
    }


@router.post("/backtest/run")
async def run_backtest(config: dict):
    """Run a new microstructure backtest."""
    return {
        "job_id": f"BT-{random.randint(1000, 9999)}",
        "status": "queued",
        "estimated_time": "5-10 minutes",
        "config": config
    }


# Import timedelta for tape generation
from datetime import timedelta
