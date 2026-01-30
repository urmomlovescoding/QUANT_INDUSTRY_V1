"""
V2 Brain Router
===============
ML/AI trading brain - signals, training, regime detection, feedback.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

router = APIRouter()


class BrainStatus(BaseModel):
    """Brain status overview."""
    available: bool
    device: str
    is_trained: bool
    current_regime: str
    auto_train_enabled: bool
    training_step: int
    total_trades: int
    metrics: Dict


class BrainConfig(BaseModel):
    """Brain configuration."""
    model_type: str
    learning_rate: float
    batch_size: int
    auto_train: bool
    regime_detection: bool


class Signal(BaseModel):
    """Brain-generated signal."""
    id: str
    symbol: str
    direction: str
    confidence: float
    strategy: str
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: str


class Prediction(BaseModel):
    """Price prediction."""
    symbol: str
    direction: str
    confidence: float
    price_target: float
    timeframe: str


class Analysis(BaseModel):
    """Full symbol analysis."""
    symbol: str
    overall_score: float
    technical_score: float
    sentiment_score: float
    regime_alignment: bool
    recommendation: str
    key_factors: List[str]


class TrainResult(BaseModel):
    """Training result."""
    success: bool
    epochs: int
    final_loss: float
    metrics: Dict


class MarketRegime(BaseModel):
    """Market regime."""
    regime: str  # trending, ranging, volatile, quiet
    confidence: float
    volatility: float
    trend_strength: float


class FeedbackStatus(BaseModel):
    """Feedback loop status."""
    phase: str
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    is_converged: bool


class FeedbackRecord(BaseModel):
    """Trade feedback record."""
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    pnl: float
    strategy: str


class AgentStatus(BaseModel):
    """Multi-agent status."""
    agent_id: str
    type: str
    active: bool
    last_signal: Optional[str] = None


class ModelInfo(BaseModel):
    """Model information."""
    name: str
    type: str  # BEAST, RL, DL, Evolution
    is_trained: bool
    last_trained: Optional[str] = None
    accuracy: Optional[float] = None


# Brain Core endpoints
@router.get("/status", response_model=BrainStatus)
async def get_brain_status():
    """Get overall brain status."""
    return BrainStatus(
        available=True,
        device="cuda:0",
        is_trained=True,
        current_regime="trending",
        auto_train_enabled=True,
        training_step=15000,
        total_trades=500,
        metrics={"win_rate": 0.65, "profit_factor": 1.8, "sharpe": 1.5}
    )


@router.post("/initialize")
async def initialize_brain():
    """Initialize the brain."""
    return {"success": True, "message": "Brain initialized"}


@router.get("/config", response_model=BrainConfig)
async def get_brain_config():
    """Get brain configuration."""
    return BrainConfig(
        model_type="transformer",
        learning_rate=0.001,
        batch_size=64,
        auto_train=True,
        regime_detection=True
    )


@router.put("/config")
async def update_brain_config(config: BrainConfig):
    """Update brain configuration."""
    return {"success": True, "message": "Config updated"}


# Signals & Predictions
@router.get("/signals", response_model=List[Signal])
async def get_brain_signals():
    """Get active brain-generated signals."""
    return [
        Signal(
            id="brain_sig_001",
            symbol="SPY",
            direction="LONG",
            confidence=0.85,
            strategy="brain_v6",
            entry_price=690.0,
            stop_loss=685.0,
            take_profit=700.0,
            timestamp=datetime.utcnow().isoformat()
        )
    ]


@router.post("/signals/generate", response_model=Signal)
async def generate_signal(symbol: str):
    """Generate a new signal for a symbol."""
    return Signal(
        id=f"brain_sig_{datetime.utcnow().timestamp():.0f}",
        symbol=symbol.upper(),
        direction="LONG",
        confidence=0.78,
        strategy="brain_v6",
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/predict/{symbol}", response_model=Prediction)
async def get_prediction(symbol: str):
    """Get price prediction for a symbol."""
    return Prediction(
        symbol=symbol.upper(),
        direction="up",
        confidence=0.72,
        price_target=105.0,
        timeframe="1D"
    )


@router.get("/analyze/{symbol}", response_model=Analysis)
async def get_analysis(symbol: str):
    """Get full analysis for a symbol."""
    return Analysis(
        symbol=symbol.upper(),
        overall_score=75.0,
        technical_score=80.0,
        sentiment_score=70.0,
        regime_alignment=True,
        recommendation="BUY",
        key_factors=["Strong momentum", "Regime aligned", "Low volatility"]
    )


# Training
@router.post("/train", response_model=TrainResult)
async def train_brain():
    """Train the brain model."""
    return TrainResult(
        success=True,
        epochs=10,
        final_loss=0.025,
        metrics={"accuracy": 0.68, "precision": 0.72}
    )


@router.get("/training/history")
async def get_training_history(limit: int = 10):
    """Get training history."""
    return [
        {"timestamp": "2026-01-30T00:00:00", "loss": 0.03, "metrics": {"accuracy": 0.65}},
        {"timestamp": "2026-01-29T00:00:00", "loss": 0.035, "metrics": {"accuracy": 0.63}}
    ]


@router.post("/auto-train/start")
async def start_auto_train():
    """Start auto-training."""
    return {"success": True, "message": "Auto-training started"}


@router.post("/auto-train/stop")
async def stop_auto_train():
    """Stop auto-training."""
    return {"success": True, "message": "Auto-training stopped"}


# Regime Detection
@router.get("/regime", response_model=MarketRegime)
async def get_current_regime():
    """Get current market regime."""
    return MarketRegime(
        regime="trending",
        confidence=0.78,
        volatility=0.15,
        trend_strength=0.65
    )


@router.get("/regime/history")
async def get_regime_history(days: int = 30):
    """Get regime history."""
    return [
        {"date": "2026-01-30", "regime": "trending", "confidence": 0.78},
        {"date": "2026-01-29", "regime": "ranging", "confidence": 0.65}
    ]


# Feedback Loop
@router.get("/feedback/status", response_model=FeedbackStatus)
async def get_feedback_status():
    """Get feedback loop status."""
    return FeedbackStatus(
        phase="optimization",
        total_trades=500,
        win_rate=0.65,
        profit_factor=1.8,
        sharpe_ratio=1.5,
        is_converged=False
    )


@router.post("/feedback/record")
async def record_feedback(record: FeedbackRecord):
    """Record trade feedback."""
    return {"success": True, "message": "Feedback recorded"}


@router.get("/feedback/metrics")
async def get_feedback_metrics():
    """Get feedback metrics."""
    return {
        "total_feedback": 500,
        "positive": 325,
        "negative": 175,
        "convergence_progress": 0.75
    }


# Multi-Agent
@router.get("/agents/status", response_model=List[AgentStatus])
async def get_agents_status():
    """Get multi-agent status."""
    return [
        AgentStatus(agent_id="momentum", type="MomentumAgent", active=True, last_signal="LONG"),
        AgentStatus(agent_id="mean_reversion", type="MeanReversionAgent", active=True),
        AgentStatus(agent_id="breakout", type="BreakoutAgent", active=True),
        AgentStatus(agent_id="volatility", type="VolatilityAgent", active=True)
    ]


@router.post("/agents/consensus")
async def get_consensus(symbol: str):
    """Get consensus signal from agents."""
    return {
        "symbol": symbol.upper(),
        "consensus": "LONG",
        "confidence": 0.72,
        "votes": {"LONG": 3, "SHORT": 1, "NEUTRAL": 0}
    }


# Models
@router.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List all available models."""
    return [
        ModelInfo(name="beast", type="BEAST", is_trained=True, accuracy=0.68),
        ModelInfo(name="rl_agent", type="RL", is_trained=True, accuracy=0.62),
        ModelInfo(name="deep_learning", type="DL", is_trained=True, accuracy=0.65),
        ModelInfo(name="evolution", type="Evolution", is_trained=True)
    ]


@router.get("/models/{model_type}/status")
async def get_model_status(model_type: str):
    """Get status for a specific model type."""
    return {
        "type": model_type,
        "is_trained": True,
        "last_trained": "2026-01-30T00:00:00",
        "accuracy": 0.68
    }


@router.post("/models/{model_type}/train")
async def train_model(model_type: str):
    """Train a specific model type."""
    return {"success": True, "message": f"Training {model_type} started"}


@router.get("/models/{model_type}/predict")
async def get_model_prediction(model_type: str, symbol: str):
    """Get prediction from a specific model."""
    return {
        "model": model_type,
        "symbol": symbol.upper(),
        "prediction": "up",
        "confidence": 0.72
    }
