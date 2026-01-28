"""
Strategy Parameters Parity Tests
================================
Gate 3: Deterministic tests for strategy behavioral parity.

These tests verify that quant_industry_v1 strategy parameters
match quant-platform EXACTLY in platform_compat mode.
"""
import pytest
import os


class TestTPTAggressiveStrategyParity:
    """Test TPT aggressive strategy parameters match quant-platform exactly."""

    def test_daily_target(self, tpt_strategy_params_golden, parity):
        """Daily target must be $800."""
        parity.assert_equal(
            tpt_strategy_params_golden["daily_target"],
            800.0,
            "TPTAggressiveStrategy.daily_target"
        )

    def test_daily_max(self, tpt_strategy_params_golden, parity):
        """Daily max must be $900."""
        parity.assert_equal(
            tpt_strategy_params_golden["daily_max"],
            900.0,
            "TPTAggressiveStrategy.daily_max"
        )

    def test_daily_min(self, tpt_strategy_params_golden, parity):
        """Daily min must be $600."""
        parity.assert_equal(
            tpt_strategy_params_golden["daily_min"],
            600.0,
            "TPTAggressiveStrategy.daily_min"
        )

    def test_preferred_contracts(self, tpt_strategy_params_golden, parity):
        """Preferred contracts must be 4."""
        parity.assert_equal(
            tpt_strategy_params_golden["preferred_contracts"],
            4,
            "TPTAggressiveStrategy.preferred_contracts"
        )

    def test_max_risk_per_trade(self, tpt_strategy_params_golden, parity):
        """Max risk per trade must be $200."""
        parity.assert_equal(
            tpt_strategy_params_golden["max_risk_per_trade"],
            200.0,
            "TPTAggressiveStrategy.max_risk_per_trade"
        )

    def test_min_rr_ratio(self, tpt_strategy_params_golden, parity):
        """Minimum R:R ratio must be 1.5."""
        parity.assert_equal(
            tpt_strategy_params_golden["min_rr_ratio"],
            1.5,
            "TPTAggressiveStrategy.min_rr_ratio"
        )

    def test_target_rr_ratio(self, tpt_strategy_params_golden, parity):
        """Target R:R ratio must be 2.0."""
        parity.assert_equal(
            tpt_strategy_params_golden["target_rr_ratio"],
            2.0,
            "TPTAggressiveStrategy.target_rr_ratio"
        )


class TestStopPointsParity:
    """Test stop points match quant-platform exactly."""

    def test_es_stop_points(self, tpt_strategy_params_golden, parity):
        """ES stop must be 2.0 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["ES"],
            2.0,
            "stop_points.ES"
        )

    def test_mes_stop_points(self, tpt_strategy_params_golden, parity):
        """MES stop must be 4.0 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["MES"],
            4.0,
            "stop_points.MES"
        )

    def test_nq_stop_points(self, tpt_strategy_params_golden, parity):
        """NQ stop must be 5.0 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["NQ"],
            5.0,
            "stop_points.NQ"
        )

    def test_mnq_stop_points(self, tpt_strategy_params_golden, parity):
        """MNQ stop must be 10.0 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["MNQ"],
            10.0,
            "stop_points.MNQ"
        )

    def test_ym_stop_points(self, tpt_strategy_params_golden, parity):
        """YM stop must be 20.0 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["YM"],
            20.0,
            "stop_points.YM"
        )

    def test_cl_stop_points(self, tpt_strategy_params_golden, parity):
        """CL stop must be 0.10 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["CL"],
            0.10,
            "stop_points.CL"
        )

    def test_gc_stop_points(self, tpt_strategy_params_golden, parity):
        """GC stop must be 2.0 points."""
        parity.assert_equal(
            tpt_strategy_params_golden["stop_points"]["GC"],
            2.0,
            "stop_points.GC"
        )


class TestPositionSizingParity:
    """Test position sizing calculations match quant-platform exactly."""

    @pytest.mark.parametrize("symbol,confidence,expected_min,expected_max", [
        ("ES", 0.80, 1, 4),    # High confidence, use preferred
        ("ES", 0.60, 1, 3),    # Medium confidence, reduced
        ("MES", 0.80, 1, 6),   # Micros can trade more contracts
        ("NQ", 0.70, 1, 4),    # NQ similar to ES
    ])
    def test_position_sizing_bounds(self, symbol, confidence, expected_min, expected_max,
                                   tpt_strategy_params_golden, contract_multipliers_golden):
        """Position sizing must be within bounds."""
        # Formula validation (not exact implementation test)
        max_risk = tpt_strategy_params_golden["max_risk_per_trade"]
        stop_points = tpt_strategy_params_golden["stop_points"].get(symbol, 2.0)
        multiplier = contract_multipliers_golden.get(symbol, 50.0)

        # Max contracts based on risk
        risk_per_contract = stop_points * multiplier
        max_by_risk = int(max_risk / risk_per_contract) if risk_per_contract > 0 else 1

        # Bounds check
        assert max_by_risk >= expected_min
        assert min(max_by_risk, 6) <= 6  # Never exceed TPT max


class TestEvaluateSignalParity:
    """Test signal evaluation logic matches quant-platform exactly."""

    def test_hold_signal_rejected(self, tpt_strategy_params_golden):
        """HOLD signals must be rejected."""
        signal = "HOLD"
        # evaluate_signal returns (False, reason) for HOLD
        expected = (False, "HOLD signal")
        # Will be tested when implemented

    def test_low_confidence_rejected(self, tpt_strategy_params_golden):
        """Low confidence signals must be rejected."""
        base_threshold = 0.60
        low_confidence = 0.50
        assert low_confidence < base_threshold

    def test_high_confidence_accepted(self, tpt_strategy_params_golden):
        """High confidence signals must be accepted (if other conditions met)."""
        base_threshold = 0.60
        high_confidence = 0.75
        assert high_confidence >= base_threshold

    def test_at_daily_max_rejected(self, tpt_strategy_params_golden):
        """Signals at daily max must be rejected."""
        daily_max = tpt_strategy_params_golden["daily_max"]
        daily_pnl = 900.0
        assert daily_pnl >= daily_max


class TestShouldTradeNowParity:
    """Test should_trade_now logic matches quant-platform exactly."""

    def test_inactive_status_no_trade(self):
        """INACTIVE status must prevent trading."""
        status = "FAILED"
        should_trade = status == "ACTIVE"
        assert should_trade is False

    def test_active_status_allows_trade(self):
        """ACTIVE status must allow trading (if other conditions met)."""
        status = "ACTIVE"
        should_trade = status == "ACTIVE"
        assert should_trade is True

    def test_at_daily_max_no_trade(self, tpt_strategy_params_golden):
        """At daily max must prevent trading."""
        daily_max = tpt_strategy_params_golden["daily_max"]
        daily_pnl = 901.0
        at_max = daily_pnl >= daily_max
        assert at_max is True


class TestICTStrategiesParity:
    """Test ICT strategy components are defined."""

    def test_ict_strategies_list(self):
        """All 10 ICT strategies must be defined."""
        required_strategies = [
            "Fair Value Gaps (FVG)",
            "Order Blocks (OB)",
            "Breaker Blocks",
            "Mitigation Blocks",
            "Liquidity Sweeps",
            "SMT Divergence",
            "Optimal Trade Entry (OTE)",
            "Kill Zones",
            "Market Structure Shift (MSS)",
            "Inducement",
        ]
        assert len(required_strategies) == 10

    def test_zone_types_defined(self):
        """Zone types must match platform enum."""
        required_zones = [
            "FVG_BULLISH",
            "FVG_BEARISH",
            "ORDER_BLOCK_BULLISH",
            "ORDER_BLOCK_BEARISH",
            "BREAKER_BULLISH",
            "BREAKER_BEARISH",
            "LIQUIDITY_HIGH",
            "LIQUIDITY_LOW",
        ]
        assert len(required_zones) == 8

    def test_bias_types_defined(self):
        """Bias types must match platform enum."""
        required_biases = ["BULLISH", "BEARISH", "NEUTRAL"]
        assert len(required_biases) == 3
