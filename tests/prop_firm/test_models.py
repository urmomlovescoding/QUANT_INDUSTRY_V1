"""
Tests for Prop Firm database models.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from prop_firm.models import (
    Trader, Challenge, Evaluation, TraderAccount, PropTrade,
    PerformanceMetrics, Payout, Badge,
    AccountStatus, ChallengePhase, ChallengeResult
)


class TestTraderModel:
    """Tests for Trader model."""
    
    def test_create_trader(self, db_session):
        """Test trader creation."""
        trader = Trader(
            email="new@example.com",
            username="newtrader",
            full_name="New Trader",
            password_hash="salt:hash",
            country="US",
            status=AccountStatus.PENDING
        )
        db_session.add(trader)
        db_session.commit()
        
        assert trader.id is not None
        assert trader.email == "new@example.com"
        assert trader.status == AccountStatus.PENDING
    
    def test_trader_default_values(self, sample_trader):
        """Test trader default values."""
        assert sample_trader.profit_split_percentage is None or sample_trader.profit_split_percentage == 80.0
        assert sample_trader.two_factor_enabled == False
        assert sample_trader.kyc_verified == False
    
    def test_trader_repr(self, sample_trader):
        """Test trader string representation."""
        repr_str = repr(sample_trader)
        assert "testtrader" in repr_str
        assert "pending" in repr_str


class TestChallengeModel:
    """Tests for Challenge model."""
    
    def test_create_challenge(self, sample_challenge):
        """Test challenge creation."""
        assert sample_challenge.id is not None
        assert sample_challenge.starting_balance == Decimal("100000")
        assert sample_challenge.phase == ChallengePhase.PHASE_1
        assert sample_challenge.result == ChallengeResult.PENDING
    
    def test_days_remaining(self, sample_challenge):
        """Test days remaining calculation."""
        assert sample_challenge.days_remaining >= 0
        assert sample_challenge.days_remaining <= 30
    
    def test_profit_target_reached_false(self, sample_challenge):
        """Test profit target not reached."""
        sample_challenge.current_pnl_pct = 5.0
        assert sample_challenge.profit_target_reached == False
    
    def test_profit_target_reached_true(self, db_session, sample_challenge):
        """Test profit target reached."""
        sample_challenge.current_pnl_pct = 10.0
        db_session.commit()
        assert sample_challenge.profit_target_reached == True
    
    def test_is_breached_false(self, sample_challenge):
        """Test challenge not breached."""
        sample_challenge.current_drawdown_pct = 5.0
        assert sample_challenge.is_breached == False
    
    def test_is_breached_true(self, db_session, sample_challenge):
        """Test challenge breached."""
        sample_challenge.current_drawdown_pct = 12.0  # Exceeds 10% max
        db_session.commit()
        assert sample_challenge.is_breached == True


class TestTraderAccountModel:
    """Tests for TraderAccount model."""
    
    def test_create_account(self, funded_account):
        """Test account creation."""
        assert funded_account.id is not None
        assert funded_account.account_number == "QI-TEST1234"
        assert funded_account.is_active == True
    
    def test_account_balances(self, funded_account):
        """Test account balance tracking."""
        assert funded_account.initial_balance == Decimal("100000")
        assert funded_account.current_balance == Decimal("105000")
        assert funded_account.total_pnl == Decimal("5000")


class TestPropTradeModel:
    """Tests for PropTrade model."""
    
    def test_create_trade(self, db_session, funded_trader, funded_account):
        """Test trade creation."""
        trade = PropTrade(
            trader_id=funded_trader.id,
            account_id=funded_account.id,
            symbol="AAPL",
            side="BUY",
            quantity=100,
            entry_price=Decimal("150.00"),
            entry_time=datetime.utcnow(),
            is_open=True
        )
        db_session.add(trade)
        db_session.commit()
        
        assert trade.id is not None
        assert trade.symbol == "AAPL"
        assert trade.is_open == True
    
    def test_trade_with_pnl(self, sample_trades):
        """Test trades with realized P&L."""
        winning_trades = [t for t in sample_trades if t.realized_pnl > 0]
        losing_trades = [t for t in sample_trades if t.realized_pnl < 0]
        
        assert len(winning_trades) > 0
        assert len(losing_trades) > 0


class TestPerformanceMetricsModel:
    """Tests for PerformanceMetrics model."""
    
    def test_create_metrics(self, performance_metrics):
        """Test metrics creation."""
        assert performance_metrics.id is not None
        assert performance_metrics.total_trades == 150
        assert performance_metrics.win_rate == 60.0
    
    def test_risk_metrics(self, performance_metrics):
        """Test risk metrics."""
        assert performance_metrics.sharpe_ratio == 1.8
        assert performance_metrics.profit_factor == 1.75
        assert performance_metrics.max_drawdown == 6.5


class TestPayoutModel:
    """Tests for Payout model."""
    
    def test_create_payout(self, db_session, funded_trader, funded_account):
        """Test payout creation."""
        payout = Payout(
            trader_id=funded_trader.id,
            account_id=funded_account.id,
            gross_profit=Decimal("5000"),
            trader_share_pct=80.0,
            trader_amount=Decimal("4000"),
            firm_amount=Decimal("1000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow(),
            status="pending",
            payment_method="bank_transfer"
        )
        db_session.add(payout)
        db_session.commit()
        
        assert payout.id is not None
        assert payout.trader_amount == Decimal("4000")
        assert payout.status == "pending"


class TestEnumValues:
    """Tests for enum values."""
    
    def test_account_status_values(self):
        """Test AccountStatus enum."""
        assert AccountStatus.PENDING.value == "pending"
        assert AccountStatus.FUNDED.value == "funded"
        assert AccountStatus.SUSPENDED.value == "suspended"
    
    def test_challenge_phase_values(self):
        """Test ChallengePhase enum."""
        assert ChallengePhase.PHASE_1.value == "phase_1"
        assert ChallengePhase.PHASE_2.value == "phase_2"
        assert ChallengePhase.FUNDED.value == "funded"
    
    def test_challenge_result_values(self):
        """Test ChallengeResult enum."""
        assert ChallengeResult.PENDING.value == "pending"
        assert ChallengeResult.PASSED.value == "passed"
        assert ChallengeResult.FAILED.value == "failed"
