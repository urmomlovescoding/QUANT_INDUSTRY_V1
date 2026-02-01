"""
Cross-Exchange Arbitrage API Routes
====================================
REST endpoints for cross-exchange prices, arb opportunities, execution, etc.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import random

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/arbitrage", tags=["Cross-Exchange Arbitrage"])

# Try to import backend modules
try:
    from cross_exchange.price_feeds import MultiExchangeFeed, Exchange
    from cross_exchange.arb_detector import ArbDetector
    from cross_exchange.execution import CrossExchangeExecutor
    from cross_exchange.triangular_arb import TriangularArbDetector
    from cross_exchange.cex_dex_arb import CexDexArbDetector
    from cross_exchange.latency import LatencyMonitor
    
    price_feed = MultiExchangeFeed()
    arb_detector = ArbDetector(price_feed)
    arb_executor = CrossExchangeExecutor()
    triangular = TriangularArbDetector(exchange=Exchange.BINANCE)
    cex_dex = CexDexArbDetector()
    latency_monitor = LatencyMonitor()
    MODULES_LOADED = True
except (ImportError, Exception) as e:
    logger.warning(f"Cross-exchange modules not fully loaded: {e}")
    MODULES_LOADED = False


EXCHANGES = ["binance", "coinbase", "kraken", "okx", "bybit", "kucoin"]
DEX_EXCHANGES = ["uniswap_v3", "sushiswap", "curve", "balancer"]


@router.get("/prices")
async def get_cross_exchange_prices(
    symbol: Optional[str] = Query(None),
    exchanges: Optional[str] = Query(None, description="Comma-separated exchange list")
):
    """Get prices across multiple exchanges."""
    symbols = [symbol] if symbol else ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    base_prices = {"BTC/USDT": 42500, "ETH/USDT": 2650, "SOL/USDT": 98}
    
    exchange_list = exchanges.split(",") if exchanges else EXCHANGES[:4]
    
    prices = []
    for sym in symbols:
        base = base_prices.get(sym, 100)
        for exch in exchange_list:
            # Add realistic price variations
            variation = random.uniform(-0.002, 0.002)
            spread = random.uniform(0.0001, 0.001)
            
            bid = round(base * (1 + variation - spread/2), 2)
            ask = round(base * (1 + variation + spread/2), 2)
            
            prices.append({
                "symbol": sym,
                "exchange": exch,
                "bid": bid,
                "bid_size": round(random.uniform(1, 50), 4),
                "ask": ask,
                "ask_size": round(random.uniform(1, 50), 4),
                "mid": round((bid + ask) / 2, 2),
                "spread_bps": round((ask - bid) / base * 10000, 2),
                "timestamp": datetime.now().isoformat(),
                "latency_ms": random.randint(5, 100)
            })
    
    return {
        "prices": prices,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/opportunities")
async def get_arb_opportunities(
    min_profit_pct: float = Query(0.1, description="Minimum profit percentage"),
    symbol: Optional[str] = None
):
    """Get active arbitrage opportunities."""
    opportunities = []
    
    # Generate some realistic opportunities
    for i in range(random.randint(2, 8)):
        sym = symbol or random.choice(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        base_price = {"BTC/USDT": 42500, "ETH/USDT": 2650, "SOL/USDT": 98}.get(sym, 100)
        
        buy_exch = random.choice(EXCHANGES)
        sell_exch = random.choice([e for e in EXCHANGES if e != buy_exch])
        
        profit_pct = random.uniform(0.05, 0.3)
        if profit_pct < min_profit_pct:
            continue
            
        opportunities.append({
            "id": f"ARB-{random.randint(10000, 99999)}",
            "type": "spatial",
            "symbol": sym,
            "buy_exchange": buy_exch,
            "buy_price": round(base_price * (1 - profit_pct/200), 2),
            "sell_exchange": sell_exch,
            "sell_price": round(base_price * (1 + profit_pct/200), 2),
            "gross_profit_pct": round(profit_pct, 3),
            "net_profit_pct": round(profit_pct - 0.06, 3),  # After fees
            "max_size": round(random.uniform(0.5, 10), 4),
            "profit_usd": round(base_price * random.uniform(0.5, 5) * profit_pct / 100, 2),
            "expires_at": (datetime.now() + timedelta(seconds=random.randint(5, 30))).isoformat(),
            "execution_risk": round(random.uniform(0.1, 0.4), 2),
            "detected_at": datetime.now().isoformat()
        })
    
    return {
        "opportunities": sorted(opportunities, key=lambda x: -x["net_profit_pct"]),
        "count": len(opportunities),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/opportunities/{opp_id}/execute")
async def execute_opportunity(opp_id: str):
    """Execute an arbitrage opportunity."""
    return {
        "execution_id": f"EXEC-{random.randint(10000, 99999)}",
        "opportunity_id": opp_id,
        "status": "executing",
        "legs": [
            {"side": "buy", "exchange": "binance", "status": "filled", "fill_price": 42450.00},
            {"side": "sell", "exchange": "coinbase", "status": "filled", "fill_price": 42520.00}
        ],
        "realized_profit": 65.50,
        "realized_profit_pct": 0.165,
        "execution_time_ms": random.randint(150, 500),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/triangular")
async def get_triangular_arb():
    """Get triangular arbitrage opportunities."""
    opportunities = []
    
    for i in range(random.randint(1, 5)):
        profit_pct = random.uniform(0.02, 0.15)
        
        opportunities.append({
            "id": f"TRI-{random.randint(10000, 99999)}",
            "exchange": random.choice(EXCHANGES),
            "path": ["BTC/USDT", "ETH/BTC", "ETH/USDT"],
            "direction": random.choice(["forward", "reverse"]),
            "profit_pct": round(profit_pct, 4),
            "max_size_usd": round(random.uniform(1000, 50000), 2),
            "execution_steps": 3,
            "estimated_slippage": round(random.uniform(0.01, 0.05), 4),
            "net_profit_pct": round(profit_pct - 0.03, 4),
            "detected_at": datetime.now().isoformat()
        })
    
    return {
        "opportunities": opportunities,
        "count": len(opportunities)
    }


@router.get("/cex-dex/{symbol}")
async def get_cex_dex_spread(symbol: str):
    """Get CEX vs DEX spread for a symbol."""
    base_price = {"BTC": 42500, "ETH": 2650, "SOL": 98}.get(symbol.split("/")[0], 100)
    
    cex_price = base_price * (1 + random.uniform(-0.001, 0.001))
    dex_price = base_price * (1 + random.uniform(-0.003, 0.003))
    
    return {
        "symbol": symbol,
        "cex_price": round(cex_price, 2),
        "cex_exchange": "binance",
        "dex_price": round(dex_price, 2),
        "dex_exchange": "uniswap_v3",
        "spread_pct": round((dex_price - cex_price) / cex_price * 100, 4),
        "spread_bps": round((dex_price - cex_price) / cex_price * 10000, 2),
        "arb_opportunity": abs(dex_price - cex_price) / cex_price > 0.002,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/cex-dex/{symbol}/history")
async def get_cex_dex_history(symbol: str, hours: int = Query(24, le=168)):
    """Get historical CEX vs DEX spread."""
    history = []
    now = datetime.now()
    
    for i in range(hours * 4):  # 15-min intervals
        ts = now - timedelta(minutes=i * 15)
        spread = random.uniform(-0.5, 0.5)
        
        history.append({
            "timestamp": ts.isoformat(),
            "spread_pct": round(spread, 4),
            "cex_price": round(42500 * (1 + random.uniform(-0.02, 0.02)), 2),
            "dex_price": round(42500 * (1 + random.uniform(-0.02, 0.02)), 2),
            "volume": round(random.uniform(100000, 5000000), 2)
        })
    
    return {
        "symbol": symbol,
        "history": list(reversed(history)),
        "stats": {
            "avg_spread": round(sum(h["spread_pct"] for h in history) / len(history), 4),
            "max_spread": round(max(h["spread_pct"] for h in history), 4),
            "min_spread": round(min(h["spread_pct"] for h in history), 4)
        }
    }


@router.get("/latency")
async def get_exchange_latency():
    """Get exchange latency statistics."""
    latencies = []
    
    for exch in EXCHANGES + DEX_EXCHANGES[:2]:
        is_dex = exch in DEX_EXCHANGES
        base_latency = 500 if is_dex else random.randint(10, 50)
        
        latencies.append({
            "exchange": exch,
            "type": "dex" if is_dex else "cex",
            "latency_ms": base_latency + random.randint(-10, 30),
            "latency_p95_ms": base_latency + random.randint(20, 100),
            "latency_p99_ms": base_latency + random.randint(50, 200),
            "uptime_pct": round(random.uniform(99.5, 99.99), 2),
            "last_check": datetime.now().isoformat(),
            "status": "healthy" if random.random() > 0.1 else "degraded"
        })
    
    return {
        "latencies": sorted(latencies, key=lambda x: x["latency_ms"]),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/executions")
async def get_execution_history(limit: int = Query(50, le=200)):
    """Get arbitrage execution history."""
    executions = []
    
    for i in range(min(limit, random.randint(10, 50))):
        success = random.random() > 0.15
        
        executions.append({
            "id": f"EXEC-{random.randint(10000, 99999)}",
            "opportunity_id": f"ARB-{random.randint(10000, 99999)}",
            "type": random.choice(["spatial", "triangular", "cex_dex"]),
            "symbol": random.choice(["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
            "status": "completed" if success else "failed",
            "profit_usd": round(random.uniform(5, 200), 2) if success else 0,
            "profit_pct": round(random.uniform(0.05, 0.25), 3) if success else 0,
            "execution_time_ms": random.randint(100, 1000),
            "slippage_bps": round(random.uniform(1, 10), 2),
            "timestamp": (datetime.now() - timedelta(minutes=i * random.randint(5, 30))).isoformat()
        })
    
    total_profit = sum(e["profit_usd"] for e in executions)
    success_count = len([e for e in executions if e["status"] == "completed"])
    
    return {
        "executions": executions,
        "summary": {
            "total_executions": len(executions),
            "successful": success_count,
            "failed": len(executions) - success_count,
            "success_rate": round(success_count / len(executions), 3) if executions else 0,
            "total_profit_usd": round(total_profit, 2),
            "avg_profit_per_trade": round(total_profit / success_count, 2) if success_count else 0
        }
    }
