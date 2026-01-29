"""
Tests for Prop Firm Risk Manager.
"""

import pytest
from decimal import Decimal

from prop_firm.risk_manager import (
    PropFirmRiskManager, RiskLevel, RiskAction
)
from prop_firm.models import TraderAccount


class TestRiskLevels:
    """Tests for risk level calculations."""
    
    def test_risk_level_normal(self, db_session, funded_account):
        """Test normal risk level."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # No drawdown
        funded_account.initial_balance = Decimal("100000")
        funded_account.current_balance = Decimal("100000")
        db_session.commit()
        
        level = risk_mgr._get_risk_level(funded_account)
        assert level == RiskLevel.NORMAL
    
    def test_risk_level_elevated(self, db_session, funded_account):
        """Test elevated risk level (50%+ of max drawdown)."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # 5.5% drawdown (55% of 10% max)
        funded_account.initial_balance = Decimal("100000")
        funded_account.current_balance = Decimal("94500")
        funded_account.max_total_drawdown = Decimal("10000")
        db_session.commit()
        
        level = risk_mgr._get_risk_level(funded_account)
        assert level == RiskLevel.ELEVATED
    
    def test_risk_level_high(self, db_session, funded_account):
        """Test high risk level (70%+ of max drawdown)."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # 7.5% drawdown (75% of 10% max)
        funded_account.initial_balance = Decimal("100000")
        funded_account.current_balance = Decimal("92500")
        funded_account.max_total_drawdown = Decimal("10000")
        db_session.commit()
        
        level = risk_mgr._get_risk_level(funded_account)
        assert level == RiskLevel.HIGH
    
    def test_risk_level_critical(self, db_session, funded_account):
        """Test critical risk level (85%+ of max drawdown)."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # 9% drawdown (90% of 10% max)
        funded_account.initial_balance = Decimal("100000")
        funded_account.current_balance = Decimal("91000")
        funded_account.max_total_drawdown = Decimal("10000")
        db_session.commit()
        
        level = risk_mgr._get_risk_level(funded_account)
        assert level == RiskLevel.CRITICAL


class TestPreTradeRiskCheck:
    """Tests for pre-trade risk validation."""
    
    def test_pre_trade_check_approved(self, db_session, funded_account):
        """Test pre-trade check passes for valid trade."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # Reset to normal state
        funded_account.is_active = True
        funded_account.is_paused = False
        funded_account.current_balance = Decimal("100000")
        funded_account.daily_pnl = Decimal("0")
        funded_account.max_position_size = Decimal("10000")
        db_session.commit()
        
        approved, details = risk_mgr.check_pre_trade_risk(
            account_id=funded_account.id,
            symbol="AAPL",
            side="BUY",
            quantity=50,
            price=150.0  # $7500 position
        )
        
        assert approved == True
        assert details["approved"] == True
    
    def test_pre_trade_check_position_size_exceeded(self, db_session, funded_account):
        """Test pre-trade check fails for oversized position."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        funded_account.max_position_size = Decimal("5000")
        funded_account.is_active = True
        funded_account.is_paused = False
        db_session.commit()
        
        approved, details = risk_mgr.check_pre_trade_risk(
            account_id=funded_account.id,
            symbol="AAPL",
            side="BUY",
            quantity=100,
            price=150.0  # $15000 position > $5000 limit
        )
        
        assert approved == False
        assert any("position_size" in str(c) for c in details.get("failed_checks", []))
    
    def test_pre_trade_check_daily_loss_exceeded(self, db_session, funded_account):
        """Test pre-trade check fails when daily loss limit hit."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        funded_account.is_active = True
        funded_account.is_paused = False
        funded_account.daily_pnl = Decimal("-5000")  # At limit
        funded_account.max_daily_loss = Decimal("5000")
        db_session.commit()
        
        approved, details = risk_mgr.check_pre_trade_risk(
            account_id=funded_account.id,
            symbol="AAPL",
            side="BUY",
            quantity=10,
            price=150.0
        )
        
        assert approved == False
        assert any("daily_loss" in str(c) for c in details.get("failed_checks", []))
    
    def test_pre_trade_check_inactive_account(self, db_session, funded_account):
        """Test pre-trade check fails for inactive account."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        funded_account.is_active = False
        db_session.commit()
        
        approved, details = risk_mgr.check_pre_trade_risk(
            account_id=funded_account.id,
            symbol="AAPL",
            side="BUY",
            quantity=10,
            price=150.0
        )
        
        assert approved == False
        assert "not active" in details.get("error", "")
    
    def test_pre_trade_check_paused_account(self, db_session, funded_account):
        """Test pre-trade check fails for paused account."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        funded_account.is_active = True
        funded_account.is_paused = True
        funded_account.pause_reason = "Risk limit reached"
        db_session.commit()
        
        approved, details = risk_mgr.check_pre_trade_risk(
            account_id=funded_account.id,
            symbol="AAPL",
            side="BUY",
            quantity=10,
            price=150.0
        )
        
        assert approved == False
        assert "paused" in details.get("error", "")


class TestDynamicLimits:
    """Tests for dynamic position limits."""
    
    def test_dynamic_limits_normal(self, db_session, funded_account, performance_metrics):
        """Test dynamic limits under normal conditions."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # Normal state
        funded_account.current_balance = Decimal("100000")
        funded_account.initial_balance = Decimal("100000")
        funded_account.max_total_drawdown = Decimal("10000")
        db_session.commit()
        
        limits = risk_mgr.get_dynamic_position_limits(funded_account.id)
        
        assert "max_position_size" in limits
        assert "max_positions" in limits
        assert limits["risk_level"] == "normal"
    
    def test_dynamic_limits_high_risk(self, db_session, funded_account, performance_metrics):
        """Test dynamic limits are reduced in high risk state."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # High risk state (75% drawdown used)
        funded_account.initial_balance = Decimal("100000")
        funded_account.current_balance = Decimal("92500")
        funded_account.max_total_drawdown = Decimal("10000")
        db_session.commit()
        
        limits = risk_mgr.get_dynamic_position_limits(funded_account.id)
        
        assert limits["risk_level"] == "high"
        assert limits["multipliers"]["risk"] < 1.0  # Reduced
    
    def test_dynamic_limits_performance_bonus(self, db_session, funded_account, performance_metrics):
        """Test dynamic limits increase with good performance."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        # Good metrics
        performance_metrics.win_rate = 65.0
        performance_metrics.profit_factor = 2.0
        performance_metrics.sharpe_ratio = 1.5
        performance_metrics.consistency_score = 80.0
        db_session.commit()
        
        # Normal risk
        funded_account.initial_balance = Decimal("100000")
        funded_account.current_balance = Decimal("100000")
        funded_account.max_total_drawdown = Decimal("10000")
        db_session.commit()
        
        limits = risk_mgr.get_dynamic_position_limits(funded_account.id)
        
        assert limits["multipliers"]["performance"] > 1.0


class TestEmergencyFlatten:
    """Tests for emergency position flattening."""
    
    def test_emergency_flatten(self, db_session, funded_account):
        """Test emergency flatten functionality."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        funded_account.is_active = True
        funded_account.is_paused = False
        db_session.commit()
        
        result = risk_mgr.emergency_flatten(
            account_id=funded_account.id,
            reason="Manual trigger for testing"
        )
        
        assert result["success"] == True
        assert result["account_paused"] == True
        
        # Verify account is paused
        db_session.refresh(funded_account)
        assert funded_account.is_paused == True
        assert "emergency" in funded_account.pause_reason.lower()


class TestRiskAlerts:
    """Tests for risk alert generation."""
    
    def test_daily_loss_alert(self, db_session, funded_account):
        """Test daily loss alert generation."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        alerts = risk_mgr._check_risk_alerts(
            account=funded_account,
            equity=Decimal("96000"),
            daily_pnl=Decimal("-4000")  # 80% of $5000 limit
        )
        
        daily_alerts = [a for a in alerts if a["type"] == "daily_loss"]
        assert len(daily_alerts) > 0
    
    def test_no_alerts_when_healthy(self, db_session, funded_account):
        """Test no alerts when account is healthy."""
        risk_mgr = PropFirmRiskManager(db_session)
        
        funded_account.initial_balance = Decimal("100000")
        db_session.commit()
        
        alerts = risk_mgr._check_risk_alerts(
            account=funded_account,
            equity=Decimal("101000"),
            daily_pnl=Decimal("1000")  # Profitable day
        )
        
        assert len(alerts) == 0
