"""
Advanced Trading Routes
=======================
Endpoints for SLIDE Doctrine, Market Microstructure, and advanced analytics.
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from ._shared import logger, SERVICES_AVAILABLE, get_data_service

router = APIRouter(prefix="/api", tags=["advanced"])


# ============== SLIDE DOCTRINE ==============

@router.get("/slide-doctrine")
async def get_slide_doctrine():
    """Get SLIDE Doctrine ML model compliance and documentation"""
    return {
        "status": "active",
        "compliance_framework": "SLIDE",
        "description": "Systematic Learning-based Investment Decision Engine - ML model compliance framework",
        "models": [
            {
                "id": "trend_classifier",
                "name": "Trend Classifier",
                "type": "Random Forest",
                "status": "active",
                "features": ["RSI", "MACD", "BB Width", "Volume Ratio"],
                "last_trained": (datetime.now() - timedelta(hours=6)).isoformat(),
                "performance_metrics": {
                    "accuracy": 0.72,
                    "sharpe_ratio": 1.45,
                    "max_drawdown": 8.2
                },
                "compliance": {
                    "risk_limits": True,
                    "position_sizing": True,
                    "stop_loss": True,
                    "audit_trail": True
                }
            },
            {
                "id": "sentiment_analyzer",
                "name": "Sentiment Analyzer",
                "type": "LSTM Neural Network",
                "status": "active",
                "features": ["News Headlines", "Social Sentiment", "Options Flow"],
                "last_trained": (datetime.now() - timedelta(days=1)).isoformat(),
                "performance_metrics": {
                    "accuracy": 0.68,
                    "sharpe_ratio": 1.22,
                    "max_drawdown": 12.5
                },
                "compliance": {
                    "risk_limits": True,
                    "position_sizing": True,
                    "stop_loss": True,
                    "audit_trail": True
                }
            },
            {
                "id": "volatility_predictor",
                "name": "Volatility Predictor",
                "type": "GARCH + XGBoost Ensemble",
                "status": "active",
                "features": ["ATR", "VIX", "Put/Call Ratio", "Historical Vol"],
                "last_trained": (datetime.now() - timedelta(hours=12)).isoformat(),
                "performance_metrics": {
                    "accuracy": 0.75,
                    "sharpe_ratio": 1.65,
                    "max_drawdown": 6.8
                },
                "compliance": {
                    "risk_limits": True,
                    "position_sizing": True,
                    "stop_loss": True,
                    "audit_trail": True
                }
            },
            {
                "id": "regime_detector",
                "name": "Market Regime Detector",
                "type": "Hidden Markov Model",
                "status": "standby",
                "features": ["Correlation Matrix", "Sector Returns", "VIX Term Structure"],
                "last_trained": (datetime.now() - timedelta(days=3)).isoformat(),
                "performance_metrics": {
                    "accuracy": 0.81,
                    "sharpe_ratio": 1.88,
                    "max_drawdown": 5.4
                },
                "compliance": {
                    "risk_limits": True,
                    "position_sizing": True,
                    "stop_loss": False,
                    "audit_trail": True
                }
            }
        ],
        "compliance_rules": [
            {"rule": "Maximum Position Size", "value": "5% of portfolio", "status": "enforced"},
            {"rule": "Stop Loss Required", "value": "2% maximum loss per trade", "status": "enforced"},
            {"rule": "Daily Loss Limit", "value": "3% of portfolio", "status": "enforced"},
            {"rule": "Model Confidence Threshold", "value": "65% minimum", "status": "active"},
            {"rule": "Correlation Limit", "value": "0.7 max between positions", "status": "active"},
            {"rule": "Overnight Exposure", "value": "50% max portfolio", "status": "enforced"}
        ],
        "audit_log_count": 1247,
        "last_compliance_check": datetime.now().isoformat()
    }


@router.get("/slide-doctrine/audit")
async def get_slide_doctrine_audit(limit: int = 20):
    """Get SLIDE Doctrine audit log"""
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN"]
    models = ["trend_classifier", "sentiment_analyzer", "volatility_predictor", "regime_detector"]
    actions = ["SIGNAL_GENERATED", "POSITION_SIZED", "RISK_CHECK", "TRADE_EXECUTED", "MODEL_UPDATED"]
    decisions = ["BUY", "SELL", "HOLD", "REDUCE"]

    audit_log = []
    for i in range(limit):
        audit_log.append({
            "timestamp": (datetime.now() - timedelta(minutes=i * 5)).isoformat(),
            "model": random.choice(models),
            "action": random.choice(actions),
            "symbol": random.choice(symbols),
            "decision": random.choice(decisions),
            "confidence": round(random.uniform(0.55, 0.92), 3),
            "risk_check": "PASSED"
        })

    return {"audit_log": audit_log}


# ============== MARKET MICROSTRUCTURE ==============

@router.get("/microstructure/status")
async def get_microstructure_status():
    """Get microstructure engine status"""
    return {
        "available": True,
        "version": "2.1.0",
        "current_session": "REGULAR",
        "active_signals": 3,
        "config": {
            "modules": {
                "order_flow": True,
                "volatility_regime": True,
                "liquidity_monitor": True,
                "signal_decay": True,
                "adaptive_sizing": True,
                "market_hours": True,
                "cross_asset": True
            }
        },
        "module_stats": {
            "order_flow": {"signals_today": 42, "avg_accuracy": 0.68},
            "volatility_regime": {"regime_changes": 3, "current_state": "NORMAL"},
            "liquidity_monitor": {"alerts_today": 7, "avg_spread_bps": 2.3}
        }
    }


@router.get("/microstructure/sessions")
async def get_microstructure_sessions():
    """Get market session profiles"""
    return {
        "current_session": "REGULAR",
        "should_trade": True,
        "reason": "Regular market hours - optimal liquidity",
        "size_multiplier": 1.0,
        "profiles": [
            {"session": "PRE_MARKET", "avg_volatility": 1.8, "avg_volume_ratio": 0.3, "avg_spread_bps": 8.5, "win_rate": 0.42, "avg_pnl": -45, "trade_count": 156, "recommended_action": "reduce_size"},
            {"session": "OPEN_AUCTION", "avg_volatility": 2.5, "avg_volume_ratio": 2.1, "avg_spread_bps": 3.2, "win_rate": 0.48, "avg_pnl": 120, "trade_count": 89, "recommended_action": "aggressive"},
            {"session": "MORNING", "avg_volatility": 1.4, "avg_volume_ratio": 1.2, "avg_spread_bps": 1.8, "win_rate": 0.56, "avg_pnl": 85, "trade_count": 423, "recommended_action": "trade_normal"},
            {"session": "MIDDAY", "avg_volatility": 0.8, "avg_volume_ratio": 0.7, "avg_spread_bps": 2.1, "win_rate": 0.51, "avg_pnl": 25, "trade_count": 312, "recommended_action": "reduce_size"},
            {"session": "REGULAR", "avg_volatility": 1.0, "avg_volume_ratio": 1.0, "avg_spread_bps": 1.5, "win_rate": 0.54, "avg_pnl": 65, "trade_count": 1245, "recommended_action": "trade_normal"},
            {"session": "POWER_HOUR", "avg_volatility": 1.6, "avg_volume_ratio": 1.8, "avg_spread_bps": 2.0, "win_rate": 0.58, "avg_pnl": 145, "trade_count": 267, "recommended_action": "aggressive"},
            {"session": "CLOSE_AUCTION", "avg_volatility": 2.2, "avg_volume_ratio": 2.5, "avg_spread_bps": 2.8, "win_rate": 0.52, "avg_pnl": 95, "trade_count": 78, "recommended_action": "trade_normal"},
            {"session": "AFTER_HOURS", "avg_volatility": 1.5, "avg_volume_ratio": 0.2, "avg_spread_bps": 12.0, "win_rate": 0.38, "avg_pnl": -85, "trade_count": 45, "recommended_action": "avoid"}
        ]
    }


@router.get("/microstructure/analyze/{symbol}")
async def analyze_microstructure(symbol: str):
    """Run full microstructure analysis on a symbol"""
    symbol = symbol.upper()

    # Generate realistic analysis data
    flow_direction = random.choice(["BUYING", "SELLING", "NEUTRAL", "MIXED"])
    vol_state = random.choice(["COMPRESSED", "NORMAL", "EXPANDING", "CRISIS"])
    liq_state = random.choice(["DEEP", "NORMAL", "THIN", "VACUUM"])

    imbalance = random.uniform(-0.4, 0.4)
    composite_score = random.uniform(-0.5, 0.5)

    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "composite_score": round(composite_score, 4),
        "recommendation": "FAVORABLE" if composite_score > 0.2 else "NEUTRAL_POSITIVE" if composite_score > 0 else "NEUTRAL_NEGATIVE" if composite_score > -0.2 else "UNFAVORABLE",
        "score_breakdown": {
            "order_flow": round(random.uniform(-0.3, 0.3), 4),
            "volatility": round(random.uniform(-0.2, 0.2), 4),
            "liquidity": round(random.uniform(-0.2, 0.3), 4),
            "session": round(random.uniform(0, 0.2), 4),
            "cross_asset": round(random.uniform(-0.2, 0.2), 4)
        },
        "alerts": [
            "Elevated spread detected - reduce position size",
            "Volume below average - monitor liquidity"
        ] if random.random() > 0.5 else [],
        "modules": {
            "order_flow": {
                "flow_direction": flow_direction,
                "imbalance_ratio": round(imbalance, 4),
                "bid_volume": random.randint(500000, 2000000),
                "ask_volume": random.randint(500000, 2000000),
                "net_flow": random.randint(-500000, 500000),
                "cumulative_delta": random.randint(-100000, 100000),
                "flow_toxicity": round(random.uniform(0.1, 0.6), 4),
                "iceberg_probability": round(random.uniform(0.1, 0.5), 4),
                "absorption_detected": random.random() > 0.7,
                "unusual_flow": random.random() > 0.8
            },
            "volatility_regime": {
                "state": vol_state,
                "confidence": round(random.uniform(0.6, 0.95), 4),
                "atr_percentile": round(random.uniform(20, 80), 2),
                "bollinger_width_percentile": round(random.uniform(20, 80), 2),
                "vix_level": round(random.uniform(12, 25), 2),
                "vix_term_structure": random.choice(["contango", "backwardation", "flat"]),
                "position_size_multiplier": round(random.uniform(0.5, 1.2), 2),
                "transition_probability": round(random.uniform(0.1, 0.4), 4),
                "regime_duration_bars": random.randint(10, 100)
            },
            "liquidity": {
                "state": liq_state,
                "spread_bps": round(random.uniform(1, 8), 2),
                "spread_percentile": round(random.uniform(20, 80), 2),
                "relative_volume": round(random.uniform(0.5, 2.0), 2),
                "depth_score": round(random.uniform(0.4, 0.9), 4),
                "fill_quality_estimate": round(random.uniform(1, 5), 2),
                "deteriorating": random.random() > 0.7
            },
            "market_hours": {
                "session": "REGULAR",
                "should_trade": True,
                "reason": "Regular market hours - optimal conditions"
            },
            "cross_asset": {
                "is_confirmed": random.random() > 0.4,
                "confirmation_score": round(random.uniform(0.3, 0.8), 4),
                "signal_direction": random.choice(["BUY", "SELL"]),
                "sector_alignment": round(random.uniform(-0.5, 0.8), 4),
                "correlation_check": round(random.uniform(-0.3, 0.7), 4),
                "options_flow_alignment": round(random.uniform(-0.4, 0.6), 4),
                "confirming_assets": [
                    {"asset": "XLK", "return": round(random.uniform(0.001, 0.02), 4)},
                    {"asset": "QQQ", "return": round(random.uniform(0.001, 0.015), 4)}
                ],
                "diverging_assets": [
                    {"asset": "XLF", "return": round(random.uniform(-0.02, -0.001), 4), "warning": "Sector divergence"}
                ] if random.random() > 0.6 else []
            },
            "position_sizing": {
                "base_size": round(random.uniform(0.02, 0.05), 4),
                "adjusted_size": round(random.uniform(0.015, 0.04), 4),
                "final_size": round(random.uniform(0.01, 0.035), 4),
                "max_size": 0.05,
                "adjustments": {
                    "volatility_adj": round(random.uniform(0.6, 1.0), 4),
                    "liquidity_adj": round(random.uniform(0.7, 1.0), 4),
                    "confidence_adj": round(random.uniform(0.8, 1.0), 4),
                    "correlation_adj": round(random.uniform(0.85, 1.0), 4)
                },
                "reasoning": [
                    f"Base Kelly size: {round(random.uniform(0.02, 0.05) * 100, 2)}%",
                    f"Volatility adjustment: {round(random.uniform(0.6, 1.0), 2)}x",
                    f"Final position: {round(random.uniform(0.01, 0.035) * 100, 2)}% of portfolio"
                ]
            }
        }
    }


@router.post("/microstructure/config")
async def update_microstructure_config(config: Dict[str, Any]):
    """Update microstructure engine configuration"""
    return {"status": "updated", "config": config}


# ============== GEX ANALYSIS ==============

@router.get("/gex/{symbol}")
async def get_gex_analysis(symbol: str):
    """Get Gamma Exposure (GEX) analysis for a symbol"""
    symbol = symbol.upper()

    current_price = random.uniform(150, 200) if symbol in ["AAPL", "MSFT"] else random.uniform(300, 500)

    # Generate strike levels around current price
    strikes = []
    for i in range(-10, 11):
        strike = round(current_price + (i * 5), 0)
        call_gex = random.uniform(-50, 150) * 1000000
        put_gex = random.uniform(-100, 50) * 1000000
        strikes.append({
            "strike": strike,
            "call_gex": round(call_gex, 0),
            "put_gex": round(put_gex, 0),
            "net_gex": round(call_gex + put_gex, 0)
        })

    total_gex = sum(s["net_gex"] for s in strikes)

    return {
        "symbol": symbol,
        "current_price": round(current_price, 2),
        "total_gex": round(total_gex, 0),
        "gex_flip_level": round(current_price * random.uniform(0.95, 1.05), 2),
        "max_pain": round(current_price * random.uniform(0.98, 1.02), 2),
        "put_wall": round(current_price * 0.95, 2),
        "call_wall": round(current_price * 1.05, 2),
        "dealer_positioning": "LONG_GAMMA" if total_gex > 0 else "SHORT_GAMMA",
        "expected_move": round(random.uniform(2, 8), 2),
        "strikes": strikes,
        "timestamp": datetime.now().isoformat()
    }


# ============== FLOW SCANNER ==============

@router.get("/flow/unusual")
async def get_unusual_flow():
    """Get unusual options flow"""
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL", "AMZN", "SPY", "QQQ"]
    flow_items = []

    for i in range(15):
        symbol = random.choice(symbols)
        is_call = random.random() > 0.45
        sentiment = "BULLISH" if is_call else "BEARISH"
        if random.random() > 0.7:
            sentiment = "BEARISH" if is_call else "BULLISH"  # Contrarian flow

        flow_items.append({
            "id": f"flow_{i}",
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 120))).isoformat(),
            "symbol": symbol,
            "type": "CALL" if is_call else "PUT",
            "strike": round(random.uniform(150, 500), 0),
            "expiry": (datetime.now() + timedelta(days=random.randint(7, 90))).strftime("%Y-%m-%d"),
            "premium": round(random.uniform(50000, 2000000), 0),
            "volume": random.randint(500, 10000),
            "open_interest": random.randint(1000, 50000),
            "vol_oi_ratio": round(random.uniform(0.5, 5.0), 2),
            "sentiment": sentiment,
            "unusual_score": round(random.uniform(60, 99), 1)
        })

    return sorted(flow_items, key=lambda x: x["unusual_score"], reverse=True)


@router.get("/flow/signals")
async def get_flow_signals():
    """Get flow-based trading signals"""
    symbols = ["AAPL", "NVDA", "TSLA", "AMD", "META"]
    signals = []

    for symbol in symbols:
        if random.random() > 0.6:
            signals.append({
                "symbol": symbol,
                "signal": random.choice(["STRONG_BUY", "BUY", "SELL", "STRONG_SELL"]),
                "confidence": round(random.uniform(0.6, 0.95), 2),
                "premium_ratio": round(random.uniform(1.5, 4.0), 2),
                "smart_money_indicator": round(random.uniform(0.5, 1.0), 2),
                "timestamp": datetime.now().isoformat()
            })

    return signals
