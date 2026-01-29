"""
Database Models
===============
SQLAlchemy models for the quant trading platform.

Design Principles:
- All timestamps in UTC
- Decimal for financial values (avoid float precision issues)
- JSON fields for flexible metadata
- Proper indexing for query performance
- Soft deletes where appropriate
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, 
    ForeignKey, Text, Index, Numeric, JSON, Enum as SQLEnum,
    UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


# ============== ENUMS ==============

class Side(str, enum.Enum):
    LONG = "long"
    SHORT = "short"
    
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class SignalStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ============== CORE TRADING MODELS ==============

class Trade(Base):
    """
    Trade journal entry - complete audit trail of every trade.
    """
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Trade details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(SQLEnum(Side), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    
    # Pricing
    entry_price = Column(Numeric(18, 8))
    exit_price = Column(Numeric(18, 8))
    avg_fill_price = Column(Numeric(18, 8))
    
    # P&L
    realized_pnl = Column(Numeric(18, 2), default=0)
    realized_pnl_pct = Column(Float, default=0)
    commission = Column(Numeric(18, 2), default=0)
    slippage = Column(Numeric(18, 2), default=0)
    
    # Timing
    entry_time = Column(DateTime(timezone=True))
    exit_time = Column(DateTime(timezone=True))
    holding_period_seconds = Column(Integer)
    
    # Strategy attribution
    strategy = Column(String(100), index=True)
    signal_id = Column(String(64), ForeignKey("signals.signal_id"))
    regime = Column(String(50))
    
    # Status
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, index=True)
    
    # Metadata
    notes = Column(Text)
    metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    signal = relationship("Signal", back_populates="trades")
    decisions = relationship("TradeDecision", back_populates="trade")
    
    __table_args__ = (
        Index('ix_trades_symbol_time', 'symbol', 'entry_time'),
        Index('ix_trades_strategy_time', 'strategy', 'entry_time'),
    )


class TradeDecision(Base):
    """
    Decision log for trades - ML explainability and audit.
    """
    __tablename__ = "trade_decisions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(64), ForeignKey("trades.trade_id"), nullable=False)
    
    decision_type = Column(String(50))  # entry, exit, scale, stop_adjustment
    reason = Column(Text)
    confidence = Column(Float)
    
    # Features at decision time
    features = Column(JSON)
    model_version = Column(String(50))
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    trade = relationship("Trade", back_populates="decisions")


class Position(Base):
    """
    Current portfolio positions.
    """
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    side = Column(SQLEnum(Side), nullable=False)
    quantity = Column(Numeric(18, 8), nullable=False)
    
    # Cost basis
    avg_cost = Column(Numeric(18, 8), nullable=False)
    total_cost = Column(Numeric(18, 2))
    
    # Current valuation
    current_price = Column(Numeric(18, 8))
    market_value = Column(Numeric(18, 2))
    
    # P&L
    unrealized_pnl = Column(Numeric(18, 2), default=0)
    unrealized_pnl_pct = Column(Float, default=0)
    
    # Timing
    opened_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Signal(Base):
    """
    Trading signals from strategies/models.
    """
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Signal details
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(SQLEnum(Side), nullable=False)
    signal_type = Column(String(50))  # entry, exit, scale
    
    # Confidence & strength
    strength = Column(Float)  # 0-1
    confidence = Column(Float)  # 0-1
    
    # Execution levels
    entry_price = Column(Numeric(18, 8))
    stop_loss = Column(Numeric(18, 8))
    take_profit = Column(Numeric(18, 8))
    
    # Attribution
    strategy = Column(String(100), index=True)
    timeframe = Column(String(20))
    regime = Column(String(50))
    
    # Features that generated this signal
    features = Column(JSON)
    
    # Status tracking
    status = Column(SQLEnum(SignalStatus), default=SignalStatus.PENDING, index=True)
    
    # Outcome (filled after execution)
    executed_at = Column(DateTime(timezone=True))
    actual_entry = Column(Numeric(18, 8))
    outcome_pnl = Column(Numeric(18, 2))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    trades = relationship("Trade", back_populates="signal")
    
    __table_args__ = (
        Index('ix_signals_symbol_created', 'symbol', 'created_at'),
        Index('ix_signals_strategy_status', 'strategy', 'status'),
    )


# ============== MARKET DATA ==============

class MarketBar(Base):
    """
    OHLCV market data bars.
    Designed for efficient time-series queries.
    """
    __tablename__ = "market_bars"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 1h, 1d
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    open = Column(Numeric(18, 8), nullable=False)
    high = Column(Numeric(18, 8), nullable=False)
    low = Column(Numeric(18, 8), nullable=False)
    close = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(18, 2), nullable=False)
    
    vwap = Column(Numeric(18, 8))
    trade_count = Column(Integer)
    
    # Data source
    source = Column(String(50))  # alpaca, polygon, yahoo
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timeframe', 'timestamp', name='uix_bar_identity'),
        Index('ix_bars_symbol_tf_ts', 'symbol', 'timeframe', 'timestamp'),
    )


# ============== PORTFOLIO & PERFORMANCE ==============

class PortfolioSnapshot(Base):
    """
    Portfolio state snapshots for equity curve and analytics.
    """
    __tablename__ = "portfolio_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Values
    equity = Column(Numeric(18, 2), nullable=False)
    cash = Column(Numeric(18, 2))
    buying_power = Column(Numeric(18, 2))
    margin_used = Column(Numeric(18, 2))
    
    # Daily P&L
    day_pnl = Column(Numeric(18, 2))
    day_pnl_pct = Column(Float)
    
    # Cumulative
    total_pnl = Column(Numeric(18, 2))
    total_pnl_pct = Column(Float)
    
    # Drawdown
    peak_equity = Column(Numeric(18, 2))
    drawdown = Column(Float)
    drawdown_pct = Column(Float)
    
    # Position summary
    positions_count = Column(Integer)
    long_exposure = Column(Numeric(18, 2))
    short_exposure = Column(Numeric(18, 2))
    net_exposure = Column(Float)


class RiskMetric(Base):
    """
    Risk metrics time series.
    """
    __tablename__ = "risk_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # VaR
    var_95 = Column(Float)
    var_99 = Column(Float)
    cvar_95 = Column(Float)
    
    # Drawdown
    max_drawdown = Column(Float)
    current_drawdown = Column(Float)
    
    # Ratios
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    calmar_ratio = Column(Float)
    
    # Greeks/Factor exposure
    beta = Column(Float)
    correlation_spy = Column(Float)
    
    # Concentration
    position_concentration = Column(Float)
    sector_exposure = Column(JSON)
    
    # Rolling window
    window_days = Column(Integer, default=20)


# ============== BACKTESTING ==============

class BacktestRun(Base):
    """
    Backtest run results.
    """
    __tablename__ = "backtest_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Config
    strategy_name = Column(String(100), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    symbols = Column(JSON)  # List of symbols
    parameters = Column(JSON)  # Strategy parameters
    
    # Capital
    initial_capital = Column(Numeric(18, 2), nullable=False)
    final_capital = Column(Numeric(18, 2))
    
    # Performance
    total_return = Column(Float)
    total_return_pct = Column(Float)
    cagr = Column(Float)
    
    # Risk metrics
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_duration_days = Column(Integer)
    
    # Trade stats
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    duration_seconds = Column(Float)
    status = Column(String(20), default='completed')


# ============== FEATURE STORE ==============

class Feature(Base):
    """
    ML Feature store - pre-computed features for fast inference.
    """
    __tablename__ = "features"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    symbol = Column(String(20), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    feature_set = Column(String(50), nullable=False)  # 'technical', 'fundamental', 'sentiment'
    
    # Features stored as JSON for flexibility
    values = Column(JSON, nullable=False)
    
    # Metadata
    version = Column(String(20))
    source = Column(String(50))
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timestamp', 'feature_set', name='uix_feature_identity'),
        Index('ix_features_symbol_ts', 'symbol', 'timestamp'),
    )


# ============== COMPLIANCE ==============

class ComplianceRule(Base):
    """
    Compliance rules and limits.
    """
    __tablename__ = "compliance_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(64), unique=True, nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # position, risk, exposure
    
    # Rule definition
    metric = Column(String(100))  # e.g., 'position_size_pct'
    operator = Column(String(10))  # <=, >=, ==, <, >
    threshold = Column(Float)
    
    # Status
    is_active = Column(Boolean, default=True)
    severity = Column(String(20), default='warning')  # warning, critical, block
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ComplianceViolation(Base):
    """
    Compliance violation records.
    """
    __tablename__ = "compliance_violations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    violation_id = Column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    rule_id = Column(String(64), ForeignKey("compliance_rules.rule_id"), nullable=False)
    
    severity = Column(String(20))
    message = Column(Text)
    metric_value = Column(Float)
    threshold = Column(Float)
    
    # Context
    context = Column(JSON)  # Additional context about the violation
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(String(100))
    resolution_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    rule = relationship("ComplianceRule")
