"""
Tests for Profit Split Calculator.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from prop_firm.profit_split import ProfitSplitCalculator
from prop_firm.models import Payout


class TestProfitSplitCalculation:
    """Tests for profit split calculations."""
    
    def test_basic_split_calculation(self, db_session, funded_trader, funded_account):
        """Test basic 80/20 profit split."""
        calculator = ProfitSplitCalculator(db_session)
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("10000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert result["gross_profit"] == 10000.0
        assert result["trader_split_pct"] >= 80.0
        assert result["trader_amount"] >= 8000.0  # At least 80%
        assert result["firm_amount"] <= 2000.0
    
    def test_zero_profit_split(self, db_session, funded_trader, funded_account):
        """Test split with zero profit."""
        calculator = ProfitSplitCalculator(db_session)
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("0"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert result["trader_amount"] == 0
        assert result["firm_amount"] == 0
    
    def test_negative_profit_split(self, db_session, funded_trader, funded_account):
        """Test split with negative profit (loss)."""
        calculator = ProfitSplitCalculator(db_session)
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("-5000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert result["trader_amount"] == 0
        assert result["firm_amount"] == 0


class TestBonusCalculations:
    """Tests for profit split bonuses."""
    
    def test_consistency_bonus(self, db_session, funded_trader, funded_account, performance_metrics):
        """Test consistency bonus (+2%)."""
        calculator = ProfitSplitCalculator(db_session)
        
        # High consistency score
        performance_metrics.consistency_score = 75.0
        db_session.commit()
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("10000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert "consistency" in result["bonuses"]
        assert result["bonuses"]["consistency"] == 2.0
    
    def test_scaling_bonus(self, db_session, funded_trader, funded_account):
        """Test scaling bonus (+1% per level)."""
        calculator = ProfitSplitCalculator(db_session)
        
        # Scale level 3
        funded_account.scale_level = 3
        db_session.commit()
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("10000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert "scaling" in result["bonuses"]
        assert result["bonuses"]["scaling"] == 2.0  # 2 levels above 1
    
    def test_top_performer_bonus(self, db_session, funded_trader, funded_account, performance_metrics):
        """Test top performer bonus (+3%)."""
        calculator = ProfitSplitCalculator(db_session)
        
        # Top 10 monthly rank
        performance_metrics.monthly_rank = 5
        db_session.commit()
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("10000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert "top_performer" in result["bonuses"]
        assert result["bonuses"]["top_performer"] == 3.0
    
    def test_max_split_capped(self, db_session, funded_trader, funded_account, performance_metrics):
        """Test that max split is capped at 95%."""
        calculator = ProfitSplitCalculator(db_session)
        
        # Maximize all bonuses
        performance_metrics.consistency_score = 80.0
        performance_metrics.monthly_rank = 1
        funded_account.scale_level = 10  # Would give +9%, but capped at +5%
        funded_account.created_at = datetime.utcnow() - timedelta(days=400)  # Longevity
        funded_trader.profit_split_percentage = 90.0
        db_session.commit()
        
        result = calculator.calculate_split(
            trader_id=funded_trader.id,
            gross_profit=Decimal("10000"),
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        assert result["trader_split_pct"] <= 95.0


class TestPayoutRequests:
    """Tests for payout request handling."""
    
    def test_create_payout_request(self, db_session, funded_trader, funded_account):
        """Test creating a payout request."""
        calculator = ProfitSplitCalculator(db_session)
        
        # Ensure pending payout exists
        funded_account.pending_payout = Decimal("5000")
        db_session.commit()
        
        payout = calculator.create_payout_request(
            trader_id=funded_trader.id,
            account_id=funded_account.id,
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow(),
            payment_method="bank_transfer"
        )
        
        assert payout.id is not None
        assert payout.status == "pending"
        assert payout.trader_amount > 0
        
        # Verify pending payout cleared
        db_session.refresh(funded_account)
        assert funded_account.pending_payout == Decimal("0")
    
    def test_create_payout_no_profit(self, db_session, funded_trader, funded_account):
        """Test payout request fails with no profit."""
        calculator = ProfitSplitCalculator(db_session)
        
        funded_account.pending_payout = Decimal("0")
        db_session.commit()
        
        with pytest.raises(ValueError, match="No profit"):
            calculator.create_payout_request(
                trader_id=funded_trader.id,
                account_id=funded_account.id,
                period_start=datetime.utcnow() - timedelta(days=14),
                period_end=datetime.utcnow()
            )
    
    def test_process_payout(self, db_session, funded_trader, funded_account):
        """Test processing a payout."""
        calculator = ProfitSplitCalculator(db_session)
        
        # Create payout first
        funded_account.pending_payout = Decimal("5000")
        db_session.commit()
        
        payout = calculator.create_payout_request(
            trader_id=funded_trader.id,
            account_id=funded_account.id,
            period_start=datetime.utcnow() - timedelta(days=14),
            period_end=datetime.utcnow()
        )
        
        # Process it
        processed = calculator.process_payout(
            payout_id=payout.id,
            payment_reference="PAY-12345"
        )
        
        assert processed.status == "completed"
        assert processed.payment_reference == "PAY-12345"
        assert processed.completed_at is not None


class TestPayoutHistory:
    """Tests for payout history."""
    
    def test_get_payout_history(self, db_session, funded_trader, funded_account):
        """Test retrieving payout history."""
        calculator = ProfitSplitCalculator(db_session)
        
        # Create multiple payouts
        for i in range(3):
            payout = Payout(
                trader_id=funded_trader.id,
                account_id=funded_account.id,
                gross_profit=Decimal("5000"),
                trader_share_pct=80.0,
                trader_amount=Decimal("4000"),
                firm_amount=Decimal("1000"),
                period_start=datetime.utcnow() - timedelta(days=14*(i+1)),
                period_end=datetime.utcnow() - timedelta(days=14*i),
                status="completed"
            )
            db_session.add(payout)
        db_session.commit()
        
        history = calculator.get_payout_history(funded_trader.id, limit=10)
        
        assert len(history) == 3
        assert all("trader_amount" in p for p in history)
    
    def test_estimate_next_payout(self, db_session, funded_account):
        """Test estimating next payout."""
        calculator = ProfitSplitCalculator(db_session)
        
        funded_account.pending_payout = Decimal("6000")
        db_session.commit()
        
        estimate = calculator.estimate_next_payout(funded_account.id)
        
        assert estimate["pending_profit"] == 6000.0
        assert estimate["estimated_payout"] > 0
        assert "next_payout_date" in estimate
