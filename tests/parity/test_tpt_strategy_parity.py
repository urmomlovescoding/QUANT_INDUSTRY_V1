"""
TPT Aggressive Strategy Parity Tests
=====================================
Verifies TPT strategy matches quant-platform behavior.
"""
import pytest
from datetime import time, datetime


class TestTPTRulesParity:
    """Test TPT rules match platform."""

    def test_initial_balance(self):
        """Verify initial balance is $50K."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.initial_balance == 50000.0

    def test_profit_target(self):
        """Verify profit target is $3K."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.profit_target == 3000.0

    def test_balance_floor(self):
        """Verify balance floor is $48K."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.balance_floor == 48000.0

    def test_max_contracts(self):
        """Verify max contracts is 6."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.max_contracts == 6

    def test_min_trading_days(self):
        """Verify min trading days is 5."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.min_trading_days == 5

    def test_consistency_rule(self):
        """Verify 50% consistency rule."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.max_single_day_pct == 0.50

    def test_permitted_products_count(self):
        """Verify permitted products list."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert len(rules.permitted_products) >= 20

    def test_contract_multipliers(self):
        """Verify contract multipliers."""
        from backend.strategies import TPTRules

        rules = TPTRules()
        assert rules.contract_multipliers["ES"] == 50.0
        assert rules.contract_multipliers["MES"] == 5.0
        assert rules.contract_multipliers["NQ"] == 20.0


class TestTPTStatusParity:
    """Test TPT status enum."""

    def test_status_values(self):
        """Verify all status values exist."""
        from backend.strategies import TPTStatus

        assert TPTStatus.ACTIVE.value == "active"
        assert TPTStatus.PASSED.value == "passed"
        assert TPTStatus.FAILED.value == "failed"
        assert TPTStatus.PAUSED.value == "paused"


class TestTPTStateParity:
    """Test TPT state tracking."""

    def test_initial_state(self):
        """Verify initial state values."""
        from backend.strategies import TPTState, TPTStatus

        state = TPTState()
        assert state.status == TPTStatus.ACTIVE
        assert state.current_balance == 50000.0
        assert state.total_pnl == 0.0
        assert state.trading_days == 0

    def test_balance_update(self):
        """Verify balance updates correctly."""
        from backend.strategies import TPTState

        state = TPTState()
        state.update_balance(500.0)

        assert state.current_balance == 50500.0
        assert state.total_pnl == 500.0
        assert state.daily_pnl == 500.0
        assert state.high_water_mark == 50500.0

    def test_failure_detection(self):
        """Verify failure state triggers."""
        from backend.strategies import TPTState, TPTRules, TPTStatus

        state = TPTState()
        rules = TPTRules()

        # Simulate loss below floor
        state.update_balance(-2500.0)
        status = state.check_status(rules)

        assert status == TPTStatus.FAILED

    def test_pass_detection(self):
        """Verify pass state triggers."""
        from backend.strategies import TPTState, TPTRules, TPTStatus

        state = TPTState()
        rules = TPTRules()

        # Simulate profit target met over 5 trading days
        for day in range(5):
            state.update_balance(700.0)
            state.daily_trades = 1  # Mark as a trading day
            state.end_day()

        status = state.check_status(rules)
        assert status == TPTStatus.PASSED


class TestTPTAggressiveStrategyParity:
    """Test TPT Aggressive Strategy."""

    def test_strategy_initialization(self):
        """Verify strategy initializes correctly."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()

        assert strategy.daily_target == 300.0
        assert strategy.daily_max == 600.0
        assert strategy.daily_min == -400.0
        assert strategy.min_rr_ratio == 1.5

    def test_should_trade_active(self):
        """Verify trading allowed when active."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        should_trade, reason = strategy.should_trade_now(time(9, 30))

        assert should_trade is True
        assert reason == "OK"

    def test_should_trade_after_hours(self):
        """Verify trading blocked after hours."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        should_trade, reason = strategy.should_trade_now(time(18, 0))

        assert should_trade is False
        assert "After trading hours" in reason

    def test_should_trade_at_max(self):
        """Verify trading blocked at daily max."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        strategy.state.daily_pnl = 700.0  # Above daily_max

        should_trade, reason = strategy.should_trade_now(time(9, 30))

        assert should_trade is False
        assert "Daily max" in reason

    def test_evaluate_signal_accepted(self):
        """Verify good signal is accepted."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        take, setup = strategy.evaluate_signal(
            symbol="ES",
            direction="LONG",
            confidence=0.70,
            entry_price=5000.0,
            stop_loss=4996.0,
            take_profit=5012.0,
        )

        assert take is True
        assert setup.risk_reward == 3.0  # (12 / 4)
        assert setup.contracts >= 1

    def test_evaluate_signal_rejected_low_confidence(self):
        """Verify low confidence rejected."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        take, setup = strategy.evaluate_signal(
            symbol="ES",
            direction="LONG",
            confidence=0.40,  # Below threshold
            entry_price=5000.0,
            stop_loss=4996.0,
            take_profit=5012.0,
        )

        assert take is False

    def test_evaluate_signal_rejected_low_rr(self):
        """Verify low R:R rejected."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        take, setup = strategy.evaluate_signal(
            symbol="ES",
            direction="LONG",
            confidence=0.70,
            entry_price=5000.0,
            stop_loss=4996.0,
            take_profit=5004.0,  # Only 1:1 R:R
        )

        assert take is False

    def test_evaluate_signal_rejected_invalid_symbol(self):
        """Verify invalid symbol rejected."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        take, setup = strategy.evaluate_signal(
            symbol="INVALID",
            direction="LONG",
            confidence=0.70,
            entry_price=100.0,
            stop_loss=99.0,
            take_profit=103.0,
        )

        assert take is False

    def test_record_trade_result(self):
        """Verify trade result recording."""
        from backend.strategies import TPTAggressiveStrategy, TradeSetup

        strategy = TPTAggressiveStrategy()

        setup = TradeSetup(
            setup_id="test_001",
            timestamp=datetime.now(),
            symbol="ES",
            direction="LONG",
            entry_price=5000.0,
            stop_loss=4996.0,
            take_profit=5012.0,
            contracts=2,
        )

        pnl = strategy.record_trade_result(setup, 5010.0, "win")

        # 10 points * 2 contracts * $50/point = $1000
        assert pnl == 1000.0
        assert strategy.state.daily_pnl == 1000.0
        assert strategy.state.total_pnl == 1000.0

    def test_daily_progress(self):
        """Verify daily progress tracking."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        strategy.state.daily_pnl = 250.0

        progress = strategy.get_daily_progress()

        assert progress["daily_pnl"] == 250.0
        assert progress["daily_target"] == 300.0
        assert progress["at_target"] is False

    def test_account_progress(self):
        """Verify account progress tracking."""
        from backend.strategies import TPTAggressiveStrategy

        strategy = TPTAggressiveStrategy()
        strategy.state.total_pnl = 1500.0
        strategy.state.trading_days = 3

        progress = strategy.get_account_progress()

        assert progress["pct_to_target"] == 50.0
        assert progress["days_remaining"] == 2

    def test_session_detection(self):
        """Verify session detection."""
        from backend.strategies import TPTAggressiveStrategy, SessionType

        strategy = TPTAggressiveStrategy()

        assert strategy.get_current_session(time(8, 30)) == SessionType.NY_OPEN
        assert strategy.get_current_session(time(3, 0)) == SessionType.LONDON
        assert strategy.get_current_session(time(21, 0)) == SessionType.ASIAN
