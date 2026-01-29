"""
Tests for Challenge Engine.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from prop_firm.challenge_engine import (
    ChallengeEngine, ChallengeType, CHALLENGE_CONFIGS
)
from prop_firm.models import Challenge, ChallengePhase, ChallengeResult, AccountStatus


class TestChallengeConfigs:
    """Tests for challenge configuration."""
    
    def test_all_challenge_types_have_configs(self):
        """Test all challenge types are configured."""
        for challenge_type in ChallengeType:
            assert challenge_type in CHALLENGE_CONFIGS
    
    def test_config_structure(self):
        """Test configuration structure."""
        for challenge_type, config in CHALLENGE_CONFIGS.items():
            assert "name" in config
            assert "starting_balance" in config
            assert "fee" in config
            assert "phase_1" in config
            assert "phase_2" in config
            assert "profit_split" in config
    
    def test_phase_configs(self):
        """Test phase configuration structure."""
        for config in CHALLENGE_CONFIGS.values():
            for phase in ["phase_1", "phase_2"]:
                phase_config = config[phase]
                assert "profit_target_pct" in phase_config
                assert "max_daily_drawdown_pct" in phase_config
                assert "max_total_drawdown_pct" in phase_config
                assert "min_trading_days" in phase_config
                assert "max_trading_days" in phase_config


class TestChallengeEngine:
    """Tests for ChallengeEngine class."""
    
    def test_create_challenge(self, db_session, sample_trader):
        """Test challenge creation."""
        engine = ChallengeEngine(db_session)
        challenge = engine.create_challenge(
            trader_id=sample_trader.id,
            challenge_type=ChallengeType.ELITE_100K
        )
        
        assert challenge.id is not None
        assert challenge.trader_id == sample_trader.id
        assert challenge.starting_balance == Decimal("100000")
        assert challenge.phase == ChallengePhase.PHASE_1
        assert challenge.result == ChallengeResult.PENDING
    
    def test_create_challenge_starter(self, db_session, sample_trader):
        """Test starter challenge creation."""
        engine = ChallengeEngine(db_session)
        challenge = engine.create_challenge(
            trader_id=sample_trader.id,
            challenge_type=ChallengeType.STARTER_10K
        )
        
        assert challenge.starting_balance == Decimal("10000")
        assert challenge.profit_target_pct == 8.0
    
    def test_create_challenge_master(self, db_session, sample_trader):
        """Test master challenge creation."""
        engine = ChallengeEngine(db_session)
        challenge = engine.create_challenge(
            trader_id=sample_trader.id,
            challenge_type=ChallengeType.MASTER_200K
        )
        
        assert challenge.starting_balance == Decimal("200000")
        assert challenge.profit_target_pct == 10.0
    
    def test_update_challenge_metrics_profit(self, db_session, sample_challenge):
        """Test updating challenge with profit."""
        engine = ChallengeEngine(db_session)
        
        challenge, status = engine.update_challenge_metrics(
            challenge_id=sample_challenge.id,
            current_balance=Decimal("105000"),
            daily_pnl=Decimal("2000")
        )
        
        assert challenge.current_balance == Decimal("105000")
        assert challenge.current_pnl == Decimal("5000")
        assert challenge.current_pnl_pct == 5.0
        assert status["failed"] == False
    
    def test_update_challenge_metrics_loss(self, db_session, sample_challenge):
        """Test updating challenge with loss."""
        engine = ChallengeEngine(db_session)
        
        challenge, status = engine.update_challenge_metrics(
            challenge_id=sample_challenge.id,
            current_balance=Decimal("97000"),
            daily_pnl=Decimal("-3000")
        )
        
        assert challenge.current_balance == Decimal("97000")
        assert challenge.current_pnl == Decimal("-3000")
        assert challenge.current_drawdown == Decimal("3000")
    
    def test_challenge_fails_on_drawdown(self, db_session, sample_challenge):
        """Test challenge fails when drawdown exceeded."""
        engine = ChallengeEngine(db_session)
        
        # First update to set peak
        engine.update_challenge_metrics(
            challenge_id=sample_challenge.id,
            current_balance=Decimal("102000"),
            daily_pnl=Decimal("2000")
        )
        
        # Then big loss
        challenge, status = engine.update_challenge_metrics(
            challenge_id=sample_challenge.id,
            current_balance=Decimal("88000"),  # 14% drawdown from peak
            daily_pnl=Decimal("-14000")
        )
        
        assert challenge.result == ChallengeResult.FAILED
        assert status["failed"] == True
        assert "drawdown" in challenge.failed_reason.lower()
    
    def test_challenge_passes_on_target(self, db_session, sample_challenge):
        """Test challenge passes when profit target reached."""
        engine = ChallengeEngine(db_session)
        
        # Set enough trading days
        sample_challenge.trading_days_completed = 5
        db_session.commit()
        
        challenge, status = engine.update_challenge_metrics(
            challenge_id=sample_challenge.id,
            current_balance=Decimal("111000"),  # 11% profit
            daily_pnl=Decimal("1000")
        )
        
        assert challenge.result == ChallengeResult.PASSED
        assert status["passed"] == True
    
    def test_challenge_needs_min_trading_days(self, db_session, sample_challenge):
        """Test challenge requires minimum trading days to pass."""
        engine = ChallengeEngine(db_session)
        
        # Profit target reached but not enough days
        sample_challenge.trading_days_completed = 2  # Less than 5 required
        db_session.commit()
        
        challenge, status = engine.update_challenge_metrics(
            challenge_id=sample_challenge.id,
            current_balance=Decimal("111000"),
            daily_pnl=Decimal("1000")
        )
        
        # Should still be pending
        assert challenge.result == ChallengeResult.PENDING
        assert status["passed"] == False
    
    def test_get_challenge_summary(self, db_session, sample_challenge):
        """Test challenge summary generation."""
        engine = ChallengeEngine(db_session)
        
        summary = engine.get_challenge_summary(sample_challenge.id)
        
        assert summary["id"] == sample_challenge.id
        assert "balance" in summary
        assert "pnl" in summary
        assert "targets" in summary
        assert "drawdown" in summary
        assert "trading_days" in summary
    
    def test_record_trading_day(self, db_session, sample_challenge):
        """Test recording a trading day evaluation."""
        engine = ChallengeEngine(db_session)
        
        evaluation = engine.record_trading_day(
            challenge_id=sample_challenge.id,
            evaluation={
                "date": datetime.utcnow(),
                "start_balance": Decimal("100000"),
                "end_balance": Decimal("101500"),
                "daily_pnl": Decimal("1500"),
                "daily_pnl_pct": 1.5,
                "trades_count": 5,
                "winning_trades": 3,
                "losing_trades": 2,
                "win_rate": 60.0,
                "is_trading_day": True
            }
        )
        
        assert evaluation.id is not None
        assert evaluation.daily_pnl == Decimal("1500")
        assert sample_challenge.trading_days_completed == 1


class TestChallengeProgression:
    """Tests for challenge phase progression."""
    
    def test_advance_to_phase_2(self, db_session, sample_trader):
        """Test advancing from Phase 1 to Phase 2."""
        engine = ChallengeEngine(db_session)
        
        # Create and pass Phase 1
        challenge = engine.create_challenge(
            trader_id=sample_trader.id,
            challenge_type=ChallengeType.ELITE_100K
        )
        challenge.result = ChallengeResult.PASSED
        challenge.trading_days_completed = 5
        db_session.commit()
        
        # Advance to Phase 2
        phase_2 = engine.advance_to_phase_2(challenge.id)
        
        assert phase_2.phase == ChallengePhase.PHASE_2
        assert phase_2.profit_target_pct == 5.0  # Phase 2 target
        assert phase_2.starting_balance == Decimal("100000")
    
    def test_cannot_advance_failed_challenge(self, db_session, sample_challenge):
        """Test cannot advance a failed challenge."""
        engine = ChallengeEngine(db_session)
        
        sample_challenge.result = ChallengeResult.FAILED
        db_session.commit()
        
        with pytest.raises(ValueError, match="must be passed"):
            engine.advance_to_phase_2(sample_challenge.id)
    
    def test_provision_funded_account(self, db_session, sample_trader):
        """Test provisioning a funded account after Phase 2."""
        engine = ChallengeEngine(db_session)
        
        # Create Phase 2 challenge that passed
        challenge = Challenge(
            trader_id=sample_trader.id,
            name="Test Challenge - Phase 2",
            phase=ChallengePhase.PHASE_2,
            starting_balance=Decimal("100000"),
            current_balance=Decimal("105000"),
            peak_balance=Decimal("105000"),
            profit_target_pct=5.0,
            profit_target_amount=Decimal("5000"),
            max_daily_drawdown_pct=5.0,
            max_total_drawdown_pct=10.0,
            max_daily_drawdown_amount=Decimal("5000"),
            max_total_drawdown_amount=Decimal("10000"),
            min_trading_days=5,
            max_trading_days=60,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=30),
            result=ChallengeResult.PASSED
        )
        db_session.add(challenge)
        db_session.commit()
        
        # Provision funded account
        account = engine.provision_funded_account(challenge.id)
        
        assert account.id is not None
        assert account.account_number.startswith("QI-")
        assert account.initial_balance == Decimal("100000")
        assert account.is_active == True
        
        # Check trader status updated
        db_session.refresh(sample_trader)
        assert sample_trader.status == AccountStatus.FUNDED
