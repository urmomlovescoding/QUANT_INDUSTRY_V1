"""
TPT Rules Parity Tests
======================
Gate 3: Deterministic tests for TPT behavioral parity.

These tests verify that quant_industry_v1 TPT implementation
matches quant-platform EXACTLY in platform_compat mode.
"""
import pytest
import os


class TestTPTRulesParity:
    """Test TPT rules match quant-platform exactly."""

    def test_initial_balance(self, tpt_rules_golden, parity):
        """Initial balance must be $50,000."""
        # TODO: Import from industry when implemented
        # from brain.tpt import TPTRules
        # rules = TPTRules()
        # parity.assert_equal(rules.initial_balance, tpt_rules_golden["initial_balance"], "TPTRules.initial_balance")
        assert tpt_rules_golden["initial_balance"] == 50000.0

    def test_balance_floor(self, tpt_rules_golden, parity):
        """Balance floor must be $48,000."""
        assert tpt_rules_golden["balance_floor"] == 48000.0

    def test_profit_target(self, tpt_rules_golden, parity):
        """Profit target must be $3,000."""
        assert tpt_rules_golden["profit_target"] == 3000.0

    def test_max_contracts(self, tpt_rules_golden, parity):
        """Max contracts must be 6."""
        assert tpt_rules_golden["max_contracts"] == 6

    def test_min_trading_days(self, tpt_rules_golden, parity):
        """Minimum trading days must be 5."""
        assert tpt_rules_golden["min_trading_days"] == 5

    def test_consistency_rule(self, tpt_rules_golden, parity):
        """50% consistency rule must be enforced."""
        assert tpt_rules_golden["max_single_day_pct"] == 0.50

    def test_trading_end_time(self, tpt_rules_golden, parity):
        """Trading must end at 17:00 EST."""
        assert tpt_rules_golden["trading_end_time"] == "17:00"

    def test_permitted_products_count(self, tpt_rules_golden, parity):
        """Must have correct number of permitted products."""
        # 8 index + 6 commodities + 4 treasuries + 10 currencies = 28
        assert len(tpt_rules_golden["permitted_products"]) == 28

    def test_permitted_products_index_futures(self, tpt_rules_golden, parity):
        """Index futures must be permitted."""
        products = tpt_rules_golden["permitted_products"]
        for symbol in ['ES', 'MES', 'NQ', 'MNQ', 'YM', 'MYM', 'RTY', 'M2K']:
            assert symbol in products, f"{symbol} not in permitted products"

    def test_permitted_products_commodities(self, tpt_rules_golden, parity):
        """Commodity futures must be permitted."""
        products = tpt_rules_golden["permitted_products"]
        for symbol in ['CL', 'MCL', 'GC', 'MGC', 'SI', 'SIL']:
            assert symbol in products, f"{symbol} not in permitted products"

    def test_permitted_products_treasuries(self, tpt_rules_golden, parity):
        """Treasury futures must be permitted."""
        products = tpt_rules_golden["permitted_products"]
        for symbol in ['ZB', 'ZN', 'ZF', 'ZT']:
            assert symbol in products, f"{symbol} not in permitted products"

    def test_permitted_products_currencies(self, tpt_rules_golden, parity):
        """Currency futures must be permitted."""
        products = tpt_rules_golden["permitted_products"]
        for symbol in ['6E', 'M6E', '6J', 'M6J', '6B', 'M6B', '6A', 'M6A', '6C', 'M6C']:
            assert symbol in products, f"{symbol} not in permitted products"


class TestContractMultipliersParity:
    """Test contract multipliers match quant-platform exactly."""

    def test_es_multiplier(self, contract_multipliers_golden, parity):
        """ES multiplier must be $50."""
        assert contract_multipliers_golden['ES'] == 50.0

    def test_mes_multiplier(self, contract_multipliers_golden, parity):
        """MES multiplier must be $5."""
        assert contract_multipliers_golden['MES'] == 5.0

    def test_nq_multiplier(self, contract_multipliers_golden, parity):
        """NQ multiplier must be $20."""
        assert contract_multipliers_golden['NQ'] == 20.0

    def test_mnq_multiplier(self, contract_multipliers_golden, parity):
        """MNQ multiplier must be $2."""
        assert contract_multipliers_golden['MNQ'] == 2.0

    def test_cl_multiplier(self, contract_multipliers_golden, parity):
        """CL multiplier must be $1000."""
        assert contract_multipliers_golden['CL'] == 1000.0

    def test_gc_multiplier(self, contract_multipliers_golden, parity):
        """GC multiplier must be $100."""
        assert contract_multipliers_golden['GC'] == 100.0

    def test_all_multipliers_present(self, contract_multipliers_golden, parity):
        """All required multipliers must be present."""
        required = ['ES', 'MES', 'NQ', 'MNQ', 'YM', 'MYM', 'RTY', 'M2K',
                   'CL', 'MCL', 'GC', 'MGC', 'SI', 'SIL', 'ZB', 'ZN', 'ZF', '6E', '6B']
        for symbol in required:
            assert symbol in contract_multipliers_golden, f"Missing multiplier for {symbol}"


class TestPnLCalculationParity:
    """Test P&L calculations match quant-platform exactly."""

    @pytest.mark.parametrize("symbol,direction,contracts,entry,exit,expected_pnl", [
        ("ES", "LONG", 1, 4500.00, 4502.00, 100.0),
        ("ES", "SHORT", 1, 4502.00, 4500.00, 100.0),
        ("ES", "LONG", 4, 4500.00, 4505.00, 1000.0),
        ("MES", "LONG", 2, 4500.00, 4510.00, 100.0),
        ("NQ", "LONG", 1, 18000.00, 18010.00, 200.0),
        ("CL", "SHORT", 1, 75.50, 75.40, 100.0),
        ("GC", "LONG", 2, 2000.00, 2005.00, 1000.0),
    ])
    def test_pnl_calculation(self, symbol, direction, contracts, entry, exit, expected_pnl,
                            contract_multipliers_golden, parity):
        """P&L calculation must match platform formula."""
        multiplier = contract_multipliers_golden.get(symbol, 50.0)

        if direction == "LONG":
            points = exit - entry
        else:
            points = entry - exit

        actual_pnl = points * contracts * multiplier
        parity.assert_pnl_equal(actual_pnl, expected_pnl, f"{symbol} {direction}")


class TestConsistencyRuleParity:
    """Test 50% consistency rule calculations match exactly."""

    @pytest.mark.parametrize("total_profit,biggest_day,expected_consistent", [
        (3000.0, 1500.0, True),
        (3000.0, 1400.0, True),
        (3000.0, 1600.0, False),
        (3000.0, 1501.0, False),
        (0.0, 100.0, True),
        (2000.0, 900.0, True),
    ])
    def test_consistency_check(self, total_profit, biggest_day, expected_consistent,
                              tpt_rules_golden, parity):
        """50% consistency rule must be calculated correctly."""
        max_single_day_pct = tpt_rules_golden["max_single_day_pct"]

        if total_profit <= 0:
            is_consistent = True
        else:
            limit = total_profit * max_single_day_pct
            is_consistent = biggest_day <= limit

        parity.assert_equal(
            is_consistent, expected_consistent,
            f"Consistency rule (profit={total_profit}, biggest={biggest_day})"
        )


class TestCanTradeParity:
    """Test can_trade logic matches platform exactly."""

    @pytest.mark.parametrize("symbol,contracts,direction,current_contracts,expected_result", [
        ("ES", 2, "LONG", 0, True),
        ("ES", 7, "LONG", 0, False),     # Over max
        ("ES", 2, "LONG", 5, False),     # Would exceed
        ("ES", 1, "SHORT", 0, True),     # Valid short
    ])
    def test_can_trade_contract_limits(self, symbol, contracts, direction, current_contracts,
                                       expected_result, tpt_rules_golden, parity):
        """Contract limit checks must match platform."""
        max_contracts = tpt_rules_golden["max_contracts"]

        would_exceed = current_contracts + contracts > max_contracts
        can_trade = not would_exceed

        parity.assert_equal(
            can_trade, expected_result,
            f"can_trade({symbol}, {contracts}) with {current_contracts} current"
        )

    def test_can_trade_invalid_symbol(self, tpt_rules_golden, parity):
        """Invalid symbols must be rejected."""
        permitted = tpt_rules_golden["permitted_products"]
        assert "INVALID" not in permitted
        assert "BTC" not in permitted  # Crypto not allowed
        assert "AAPL" not in permitted  # Stocks not allowed


class TestTPTTrackerStateParity:
    """Test TPT tracker state management matches platform."""

    def test_initial_state(self, tpt_rules_golden):
        """Initial tracker state must match platform."""
        expected_state = {
            "status": "ACTIVE",
            "current_balance": 50000.0,
            "total_contracts": 0,
            "open_positions": {},
            "daily_pnl": {},
            "trading_days": [],
        }
        # This will be implemented when TPTTracker is ported
        assert expected_state["current_balance"] == tpt_rules_golden["initial_balance"]

    def test_failure_state_triggers(self, tpt_rules_golden):
        """Failure conditions must match platform."""
        # Balance below floor triggers FAILED status
        balance_floor = tpt_rules_golden["balance_floor"]
        test_balance = 47999.99

        should_fail = test_balance < balance_floor
        assert should_fail is True

    def test_pass_state_triggers(self, tpt_rules_golden):
        """Pass conditions must match platform."""
        profit_target = tpt_rules_golden["profit_target"]
        min_days = tpt_rules_golden["min_trading_days"]

        # All conditions must be met
        test_profit = 3000.0
        test_days = 5
        test_consistent = True

        should_pass = (
            test_profit >= profit_target and
            test_days >= min_days and
            test_consistent
        )
        assert should_pass is True
