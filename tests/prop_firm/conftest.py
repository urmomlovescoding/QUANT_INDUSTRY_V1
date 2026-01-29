"""
Pytest fixtures for Prop Firm tests.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from prop_firm.models import (
    Base, Trader, Challenge, Evaluation, TraderAccount,
    PropTrade, PerformanceMetrics, Payout, Badge,
    AccountStatus, ChallengePhase, ChallengeResult
)


@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_trader(db_session):
    """Create a sample trader for testing."""
    trader = Trader(
        email="test@example.com",
        username="testtrader",
        full_name="Test Trader",
        password_hash="salt:hash",
        country="US",
        timezone="America/New_York",
        status=AccountStatus.PENDING,
        referral_code="TEST1234",
        xp_points=0,
        rank="Rookie",
        badges=[]
    )
    db_session.add(trader)
    db_session.commit()
    return trader


@pytest.fixture
def funded_trader(db_session):
    """Create a funded trader with KYC verified."""
    trader = Trader(
        email="funded@example.com",
        username="fundedtrader",
        full_name="Funded Trader",
        password_hash="salt:hash",
        country="US",
        timezone="America/New_York",
        status=AccountStatus.FUNDED,
        kyc_verified=True,
        referral_code="FUND1234",
        profit_split_percentage=80.0,
        xp_points=1000,
        rank="Trader",
        badges=["First Trade", "Century Club"]
    )
    db_session.add(trader)
    db_session.commit()
    return trader


@pytest.fixture
def sample_challenge(db_session, sample_trader):
    """Create a sample challenge."""
    challenge = Challenge(
        trader_id=sample_trader.id,
        name="Elite $100K Challenge",
        phase=ChallengePhase.PHASE_1,
        starting_balance=Decimal("100000"),
        current_balance=Decimal("100000"),
        peak_balance=Decimal("100000"),
        profit_target_pct=10.0,
        profit_target_amount=Decimal("10000"),
        max_daily_drawdown_pct=5.0,
        max_total_drawdown_pct=10.0,
        max_daily_drawdown_amount=Decimal("5000"),
        max_total_drawdown_amount=Decimal("10000"),
        min_trading_days=5,
        max_trading_days=30,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        result=ChallengeResult.PENDING
    )
    db_session.add(challenge)
    db_session.commit()
    return challenge


@pytest.fixture
def funded_account(db_session, funded_trader):
    """Create a funded trading account."""
    account = TraderAccount(
        trader_id=funded_trader.id,
        account_number="QI-TEST1234",
        account_type="funded",
        initial_balance=Decimal("100000"),
        current_balance=Decimal("105000"),
        buying_power=Decimal("105000"),
        max_daily_loss=Decimal("5000"),
        max_total_drawdown=Decimal("10000"),
        scale_level=1,
        is_active=True,
        daily_pnl=Decimal("500"),
        total_pnl=Decimal("5000"),
        total_payouts=Decimal("0"),
        pending_payout=Decimal("4000")
    )
    db_session.add(account)
    db_session.commit()
    return account


@pytest.fixture
def performance_metrics(db_session, funded_trader):
    """Create performance metrics for a trader."""
    metrics = PerformanceMetrics(
        trader_id=funded_trader.id,
        total_trades=150,
        winning_trades=90,
        losing_trades=60,
        win_rate=60.0,
        total_pnl=Decimal("15000"),
        avg_daily_pnl=Decimal("500"),
        best_day=Decimal("3000"),
        worst_day=Decimal("-1500"),
        sharpe_ratio=1.8,
        sortino_ratio=2.1,
        profit_factor=1.75,
        max_drawdown=6.5,
        avg_risk_reward=1.5,
        profitable_days=25,
        total_trading_days=35,
        consistency_score=75.0,
        current_win_streak=3,
        max_win_streak=8,
        global_rank=15,
        monthly_rank=8
    )
    db_session.add(metrics)
    db_session.commit()
    return metrics


@pytest.fixture
def sample_trades(db_session, funded_trader, funded_account):
    """Create sample trades for testing."""
    trades = []
    base_time = datetime.utcnow() - timedelta(days=7)
    
    # Mix of winning and losing trades
    trade_data = [
        ("AAPL", "BUY", 100, 150.00, 155.00, 500),
        ("MSFT", "BUY", 50, 300.00, 295.00, -250),
        ("GOOGL", "SELL", 20, 140.00, 135.00, 100),
        ("TSLA", "BUY", 30, 250.00, 260.00, 300),
        ("NVDA", "BUY", 40, 450.00, 440.00, -400),
        ("META", "SELL", 25, 350.00, 340.00, 250),
    ]
    
    for i, (symbol, side, qty, entry, exit, pnl) in enumerate(trade_data):
        trade = PropTrade(
            trader_id=funded_trader.id,
            account_id=funded_account.id,
            symbol=symbol,
            side=side,
            quantity=qty,
            entry_price=Decimal(str(entry)),
            exit_price=Decimal(str(exit)),
            realized_pnl=Decimal(str(pnl)),
            entry_time=base_time + timedelta(hours=i*4),
            exit_time=base_time + timedelta(hours=i*4 + 2),
            is_open=False,
            stop_loss=Decimal(str(entry * 0.98)) if side == "BUY" else Decimal(str(entry * 1.02))
        )
        trades.append(trade)
        db_session.add(trade)
    
    db_session.commit()
    return trades
