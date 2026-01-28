"""
Parity Test Fixtures
====================
Golden data and fixtures for deterministic parity testing.
Gate 3: Parity Harness
"""
import json
import os
import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Golden data directory
GOLDEN_DIR = Path(__file__).parent / "golden_data"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def app_mode():
    """Get current APP_MODE - platform_compat or industry_improved."""
    return os.environ.get("APP_MODE", "platform_compat")


@pytest.fixture
def tpt_rules_golden():
    """Golden TPT rules that MUST match quant-platform exactly."""
    return {
        "name": "Take Profit Trader",
        "initial_balance": 50000.0,
        "balance_floor": 48000.0,
        "profit_target": 3000.0,
        "max_contracts": 6,
        "min_trading_days": 5,
        "max_single_day_pct": 0.50,
        "trading_end_time": "17:00",
        "permitted_products": [
            'ES', 'MES', 'NQ', 'MNQ', 'YM', 'MYM', 'RTY', 'M2K',
            'CL', 'MCL', 'GC', 'MGC', 'SI', 'SIL',
            'ZB', 'ZN', 'ZF', 'ZT',
            '6E', 'M6E', '6J', 'M6J', '6B', 'M6B', '6A', 'M6A', '6C', 'M6C',
        ]
    }


@pytest.fixture
def contract_multipliers_golden():
    """Golden contract multipliers that MUST match quant-platform exactly."""
    return {
        'ES': 50.0, 'MES': 5.0,
        'NQ': 20.0, 'MNQ': 2.0,
        'YM': 5.0, 'MYM': 0.50,
        'RTY': 50.0, 'M2K': 5.0,
        'CL': 1000.0, 'MCL': 100.0,
        'GC': 100.0, 'MGC': 10.0,
        'SI': 5000.0, 'SIL': 1000.0,
        'ZB': 1000.0, 'ZN': 1000.0, 'ZF': 1000.0,
        '6E': 125000.0, '6B': 62500.0,
    }


@pytest.fixture
def execution_modes_golden():
    """Golden execution modes that MUST match quant-platform exactly."""
    return {
        "SIGNAL_ONLY": "signal_only",
        "AUTO_PAPER": "auto_paper",
        "AUTO_LIVE": "auto_live",
    }


@pytest.fixture
def deployment_stages_golden():
    """Golden deployment stages that MUST match quant-platform exactly."""
    return {
        "TRAINING": "training",
        "VALIDATION": "validation",
        "SHADOW": "shadow",
        "CANARY": "canary",
        "PRODUCTION": "production",
        "ROLLBACK": "rollback",
    }


@pytest.fixture
def model_health_golden():
    """Golden model health states that MUST match quant-platform exactly."""
    return {
        "HEALTHY": "healthy",
        "DEGRADED": "degraded",
        "UNHEALTHY": "unhealthy",
        "UNKNOWN": "unknown",
    }


@pytest.fixture
def tpt_strategy_params_golden():
    """Golden TPT aggressive strategy parameters."""
    return {
        "daily_target": 800.0,
        "daily_max": 900.0,
        "daily_min": 600.0,
        "preferred_contracts": 4,
        "max_risk_per_trade": 200.0,
        "min_rr_ratio": 1.5,
        "target_rr_ratio": 2.0,
        "stop_points": {
            'ES': 2.0,
            'MES': 4.0,
            'NQ': 5.0,
            'MNQ': 10.0,
            'YM': 20.0,
            'CL': 0.10,
            'GC': 2.0,
        }
    }


@pytest.fixture
def health_thresholds_golden():
    """Golden health check thresholds."""
    return {
        "healthy": {
            "win_rate_min": 0.50,
            "sharpe_min": 1.0,
            "max_drawdown_max": 0.15,
            "consecutive_losses_max": 5,
            "latency_max_ms": 100,
        },
        "degraded": {
            "win_rate_min": 0.40,
            "sharpe_min": 0.5,
            "max_drawdown_max": 0.20,
        },
        "unhealthy_triggers": {
            "win_rate_below": 0.40,
            "sharpe_below": 0.5,
            "max_drawdown_above": 0.20,
            "consecutive_losses_above": 10,
        }
    }


@pytest.fixture
def pnl_test_cases_golden():
    """Golden P&L calculation test cases."""
    return [
        # (symbol, direction, contracts, entry, exit, expected_pnl)
        ("ES", "LONG", 1, 4500.00, 4502.00, 100.0),   # 2 points * $50 = $100
        ("ES", "SHORT", 1, 4502.00, 4500.00, 100.0),  # 2 points * $50 = $100
        ("ES", "LONG", 4, 4500.00, 4505.00, 1000.0),  # 5 points * 4 * $50 = $1000
        ("MES", "LONG", 2, 4500.00, 4510.00, 100.0),  # 10 points * 2 * $5 = $100
        ("NQ", "LONG", 1, 18000.00, 18010.00, 200.0), # 10 points * $20 = $200
        ("CL", "SHORT", 1, 75.50, 75.40, 100.0),      # 0.10 * $1000 = $100
        ("GC", "LONG", 2, 2000.00, 2005.00, 1000.0),  # 5 * 2 * $100 = $1000
    ]


@pytest.fixture
def can_trade_test_cases_golden():
    """Golden can_trade test cases."""
    return [
        # (symbol, contracts, direction, current_contracts, expected_result, expected_reason_contains)
        ("ES", 2, "LONG", 0, True, "OK"),
        ("ES", 7, "LONG", 0, False, "exceed"),              # Over max
        ("ES", 2, "LONG", 5, False, "exceed"),              # Would exceed
        ("INVALID", 1, "LONG", 0, False, "not permitted"),  # Invalid symbol
        ("ES", 1, "SHORT", 0, True, "OK"),                  # Valid short
    ]


@pytest.fixture
def consistency_test_cases_golden():
    """Golden 50% consistency rule test cases."""
    return [
        # (total_profit, biggest_day_profit, expected_consistent)
        (3000.0, 1500.0, True),   # Exactly 50% - OK
        (3000.0, 1400.0, True),   # Under 50% - OK
        (3000.0, 1600.0, False),  # Over 50% - FAIL
        (3000.0, 1501.0, False),  # Just over - FAIL
        (0.0, 100.0, True),       # No profit yet - OK
        (2000.0, 900.0, True),    # 45% - OK
    ]


def save_golden(name: str, data: Any) -> Path:
    """Save golden data to file."""
    path = GOLDEN_DIR / f"{name}.json"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    return path


def load_golden(name: str) -> Any:
    """Load golden data from file."""
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden data not found: {path}")
    with open(path) as f:
        return json.load(f)


class ParityAssertion:
    """Helper for parity assertions with detailed error messages."""

    @staticmethod
    def assert_equal(actual, expected, context: str):
        """Assert equality with context."""
        assert actual == expected, (
            f"PARITY VIOLATION in {context}:\n"
            f"  Expected (platform): {expected}\n"
            f"  Actual (industry):   {actual}"
        )

    @staticmethod
    def assert_pnl_equal(actual: float, expected: float, context: str, tolerance: float = 0.01):
        """Assert P&L equality within tolerance."""
        diff = abs(actual - expected)
        assert diff <= tolerance, (
            f"PNL PARITY VIOLATION in {context}:\n"
            f"  Expected (platform): ${expected:.2f}\n"
            f"  Actual (industry):   ${actual:.2f}\n"
            f"  Difference: ${diff:.2f} (tolerance: ${tolerance:.2f})"
        )

    @staticmethod
    def assert_enum_parity(industry_enum, golden_values: Dict[str, str], context: str):
        """Assert enum values match golden data."""
        for name, value in golden_values.items():
            assert hasattr(industry_enum, name), (
                f"ENUM PARITY VIOLATION in {context}: Missing {name}"
            )
            actual_value = getattr(industry_enum, name).value
            assert actual_value == value, (
                f"ENUM VALUE PARITY VIOLATION in {context}.{name}:\n"
                f"  Expected (platform): {value}\n"
                f"  Actual (industry):   {actual_value}"
            )


@pytest.fixture
def parity():
    """Parity assertion helper."""
    return ParityAssertion()
