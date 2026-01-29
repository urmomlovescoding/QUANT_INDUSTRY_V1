"""
Prop Firm Database Models
SQLAlchemy models for trader management, challenges, and evaluations.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, 
    DateTime, ForeignKey, Enum as SQLEnum, Text, JSON, Numeric
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class AccountStatus(str, Enum):
    PENDING = "pending"
    EVALUATION = "evaluation"
    FUNDED = "funded"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class ChallengePhase(str, Enum):
    PHASE_1 = "phase_1"  # Initial evaluation
    PHASE_2 = "phase_2"  # Verification
    FUNDED = "funded"    # Live trading


class ChallengeResult(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


class Trader(Base):
    """Trader profile and account information."""
    __tablename__ = "prop_traders"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Identity
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50))
    country = Column(String(100))
    timezone = Column(String(50), default="UTC")
    
    # Authentication (hashed)
    password_hash = Column(String(256), nullable=False)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(100))
    
    # Account status
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.PENDING)
    kyc_verified = Column(Boolean, default=False)
    kyc_documents = Column(JSON)  # Document references
    
    # Profit sharing
    profit_split_percentage = Column(Float, default=80.0)  # Trader gets 80%
    
    # Gamification
    badges = Column(JSON, default=list)  # List of earned badges
    xp_points = Column(Integer, default=0)
    rank = Column(String(50), default="Rookie")
    
    # Referral
    referral_code = Column(String(20), unique=True)
    referred_by = Column(BigInteger, ForeignKey("prop_traders.id"))
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)
    
    # Relationships
    challenges = relationship("Challenge", back_populates="trader")
    accounts = relationship("TraderAccount", back_populates="trader")
    trades = relationship("PropTrade", back_populates="trader")
    
    def __repr__(self):
        return f"<Trader {self.username} ({self.status.value})>"


class Challenge(Base):
    """Trading challenge/evaluation configuration."""
    __tablename__ = "prop_challenges"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trader_id = Column(BigInteger, ForeignKey("prop_traders.id"), nullable=False)
    
    # Challenge type
    name = Column(String(100), nullable=False)  # e.g., "100K Challenge"
    phase = Column(SQLEnum(ChallengePhase), default=ChallengePhase.PHASE_1)
    
    # Capital
    starting_balance = Column(Numeric(15, 2), nullable=False)
    current_balance = Column(Numeric(15, 2), nullable=False)
    
    # Targets
    profit_target_pct = Column(Float, nullable=False)  # e.g., 10% for phase 1
    profit_target_amount = Column(Numeric(15, 2))
    
    # Risk limits
    max_daily_drawdown_pct = Column(Float, default=5.0)
    max_total_drawdown_pct = Column(Float, default=10.0)
    max_daily_drawdown_amount = Column(Numeric(15, 2))
    max_total_drawdown_amount = Column(Numeric(15, 2))
    
    # Current metrics
    current_pnl = Column(Numeric(15, 2), default=0)
    current_pnl_pct = Column(Float, default=0)
    peak_balance = Column(Numeric(15, 2))
    current_drawdown = Column(Numeric(15, 2), default=0)
    current_drawdown_pct = Column(Float, default=0)
    daily_pnl = Column(Numeric(15, 2), default=0)
    daily_drawdown = Column(Numeric(15, 2), default=0)
    
    # Trading rules
    min_trading_days = Column(Integer, default=5)
    max_trading_days = Column(Integer, default=30)
    trading_days_completed = Column(Integer, default=0)
    
    # Position limits
    max_position_size_pct = Column(Float, default=10.0)  # % of balance
    max_lots = Column(Float)
    allowed_instruments = Column(JSON)  # List of tradeable symbols
    
    # Time constraints
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Result
    result = Column(SQLEnum(ChallengeResult), default=ChallengeResult.PENDING)
    failed_reason = Column(Text)
    completed_at = Column(DateTime)
    
    # Fees
    fee_paid = Column(Numeric(10, 2), default=0)
    fee_refunded = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    trader = relationship("Trader", back_populates="challenges")
    evaluations = relationship("Evaluation", back_populates="challenge")
    
    def __repr__(self):
        return f"<Challenge {self.name} - {self.phase.value} ({self.result.value})>"
    
    @property
    def days_remaining(self) -> int:
        if self.end_date:
            remaining = (self.end_date - datetime.utcnow()).days
            return max(0, remaining)
        return 0
    
    @property
    def profit_target_reached(self) -> bool:
        return self.current_pnl_pct >= self.profit_target_pct
    
    @property
    def is_breached(self) -> bool:
        return (
            self.current_drawdown_pct >= self.max_total_drawdown_pct or
            self.daily_drawdown >= (self.max_daily_drawdown_amount or float('inf'))
        )


class Evaluation(Base):
    """Daily evaluation snapshots for tracking progress."""
    __tablename__ = "prop_evaluations"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    challenge_id = Column(BigInteger, ForeignKey("prop_challenges.id"), nullable=False)
    trader_id = Column(BigInteger, ForeignKey("prop_traders.id"), nullable=False)
    
    # Date
    evaluation_date = Column(DateTime, nullable=False)
    
    # Balances
    start_balance = Column(Numeric(15, 2), nullable=False)
    end_balance = Column(Numeric(15, 2), nullable=False)
    
    # P&L
    daily_pnl = Column(Numeric(15, 2), default=0)
    daily_pnl_pct = Column(Float, default=0)
    cumulative_pnl = Column(Numeric(15, 2), default=0)
    cumulative_pnl_pct = Column(Float, default=0)
    
    # Drawdown
    daily_drawdown = Column(Numeric(15, 2), default=0)
    daily_drawdown_pct = Column(Float, default=0)
    max_drawdown = Column(Numeric(15, 2), default=0)
    max_drawdown_pct = Column(Float, default=0)
    
    # Trading activity
    trades_count = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0)
    
    # Risk metrics
    sharpe_ratio = Column(Float)
    profit_factor = Column(Float)
    avg_win = Column(Numeric(15, 2))
    avg_loss = Column(Numeric(15, 2))
    largest_win = Column(Numeric(15, 2))
    largest_loss = Column(Numeric(15, 2))
    
    # Compliance
    rules_violated = Column(JSON)  # List of violated rules
    is_trading_day = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    challenge = relationship("Challenge", back_populates="evaluations")
    
    def __repr__(self):
        return f"<Evaluation {self.evaluation_date} - P&L: {self.daily_pnl}>"


class TraderAccount(Base):
    """Funded trading account after passing challenge."""
    __tablename__ = "prop_accounts"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trader_id = Column(BigInteger, ForeignKey("prop_traders.id"), nullable=False)
    challenge_id = Column(BigInteger, ForeignKey("prop_challenges.id"))
    
    # Account details
    account_number = Column(String(50), unique=True, nullable=False)
    account_type = Column(String(50), default="funded")  # funded, scaled
    
    # Capital
    initial_balance = Column(Numeric(15, 2), nullable=False)
    current_balance = Column(Numeric(15, 2), nullable=False)
    buying_power = Column(Numeric(15, 2))
    
    # Scaling
    scale_level = Column(Integer, default=1)
    next_scale_target = Column(Numeric(15, 2))
    
    # Risk limits (can be dynamic based on performance)
    max_daily_loss = Column(Numeric(15, 2), nullable=False)
    max_total_drawdown = Column(Numeric(15, 2), nullable=False)
    max_position_size = Column(Numeric(15, 2))
    
    # Current state
    daily_pnl = Column(Numeric(15, 2), default=0)
    total_pnl = Column(Numeric(15, 2), default=0)
    total_payouts = Column(Numeric(15, 2), default=0)
    pending_payout = Column(Numeric(15, 2), default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_paused = Column(Boolean, default=False)
    pause_reason = Column(Text)
    
    # Broker connection
    broker = Column(String(50))  # IBKR, Alpaca, etc.
    broker_account_id = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_trade_at = Column(DateTime)
    
    # Relationships
    trader = relationship("Trader", back_populates="accounts")
    
    def __repr__(self):
        return f"<TraderAccount {self.account_number} - ${self.current_balance}>"


class PropTrade(Base):
    """Individual trade records for prop trading."""
    __tablename__ = "prop_trades"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trader_id = Column(BigInteger, ForeignKey("prop_traders.id"), nullable=False)
    challenge_id = Column(BigInteger, ForeignKey("prop_challenges.id"))
    account_id = Column(BigInteger, ForeignKey("prop_accounts.id"))
    
    # Trade details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Float, nullable=False)
    
    # Prices
    entry_price = Column(Numeric(15, 6), nullable=False)
    exit_price = Column(Numeric(15, 6))
    stop_loss = Column(Numeric(15, 6))
    take_profit = Column(Numeric(15, 6))
    
    # P&L
    realized_pnl = Column(Numeric(15, 2))
    unrealized_pnl = Column(Numeric(15, 2))
    commission = Column(Numeric(10, 4), default=0)
    
    # Timing
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Status
    is_open = Column(Boolean, default=True)
    close_reason = Column(String(50))  # manual, stop_loss, take_profit, margin_call
    
    # Risk
    risk_amount = Column(Numeric(15, 2))  # Initial risk on trade
    risk_reward_ratio = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    trader = relationship("Trader", back_populates="trades")
    
    def __repr__(self):
        return f"<PropTrade {self.symbol} {self.side} @ {self.entry_price}>"


class PerformanceMetrics(Base):
    """Aggregated performance metrics for leaderboards and analytics."""
    __tablename__ = "prop_performance_metrics"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trader_id = Column(BigInteger, ForeignKey("prop_traders.id"), nullable=False, unique=True)
    
    # Overall stats
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0)
    
    # P&L
    total_pnl = Column(Numeric(15, 2), default=0)
    avg_daily_pnl = Column(Numeric(15, 2), default=0)
    best_day = Column(Numeric(15, 2))
    worst_day = Column(Numeric(15, 2))
    
    # Risk metrics
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    profit_factor = Column(Float)
    max_drawdown = Column(Float)
    avg_risk_reward = Column(Float)
    
    # Consistency
    profitable_days = Column(Integer, default=0)
    total_trading_days = Column(Integer, default=0)
    consistency_score = Column(Float)  # Custom metric
    
    # Streaks
    current_win_streak = Column(Integer, default=0)
    max_win_streak = Column(Integer, default=0)
    current_loss_streak = Column(Integer, default=0)
    max_loss_streak = Column(Integer, default=0)
    
    # Rankings
    global_rank = Column(Integer)
    monthly_rank = Column(Integer)
    
    # Timestamps
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PerformanceMetrics trader={self.trader_id} win_rate={self.win_rate}%>"


class Payout(Base):
    """Profit payout records."""
    __tablename__ = "prop_payouts"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trader_id = Column(BigInteger, ForeignKey("prop_traders.id"), nullable=False)
    account_id = Column(BigInteger, ForeignKey("prop_accounts.id"), nullable=False)
    
    # Amounts
    gross_profit = Column(Numeric(15, 2), nullable=False)
    trader_share_pct = Column(Float, nullable=False)
    trader_amount = Column(Numeric(15, 2), nullable=False)
    firm_amount = Column(Numeric(15, 2), nullable=False)
    
    # Period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    payment_method = Column(String(50))  # bank_transfer, crypto, paypal
    payment_reference = Column(String(100))
    
    # Timestamps
    requested_at = Column(DateTime, default=func.now())
    processed_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    def __repr__(self):
        return f"<Payout ${self.trader_amount} ({self.status})>"


class Badge(Base):
    """Gamification badges."""
    __tablename__ = "prop_badges"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    icon = Column(String(100))  # Icon filename or URL
    xp_reward = Column(Integer, default=0)
    
    # Unlock criteria (JSON for flexibility)
    criteria = Column(JSON)  # e.g., {"win_rate": {"gte": 60}, "trades": {"gte": 100}}
    
    # Rarity
    rarity = Column(String(20), default="common")  # common, rare, epic, legendary
    
    def __repr__(self):
        return f"<Badge {self.name} ({self.rarity})>"
