"""
QUANT_INDUSTRY_V1 Test Configuration

Shared pytest fixtures and configuration.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sample_price_data():
    """Generate sample price data."""
    import numpy as np

    np.random.seed(42)
    n = 100

    returns = np.random.randn(n) * 0.02
    prices = 100 * np.exp(np.cumsum(returns))

    return {
        'close': prices.tolist(),
        'open': (prices * 0.999).tolist(),
        'high': (prices * 1.005).tolist(),
        'low': (prices * 0.995).tolist(),
        'volume': (np.abs(np.random.randn(n)) * 1000000).tolist(),
        'returns': returns.tolist(),
    }


@pytest.fixture
def sample_metrics():
    """Generate sample performance metrics."""
    return {
        'total_return': 0.15,
        'benchmark_return': 0.10,
        'sharpe_ratio': 1.2,
        'sortino_ratio': 1.5,
        'calmar_ratio': 0.9,
        'max_drawdown': 0.12,
        'avg_drawdown': 0.05,
        'avg_recovery_days': 15,
        'win_rate': 0.54,
        'profit_factor': 1.4,
        'monthly_positive_pct': 0.65,
        'model_accuracy': 0.56,
        'model_precision': 0.54,
        'model_recall': 0.52,
        'drift_detected': False,
        'uptime_pct': 99.5,
        'error_rate': 0.3,
        'latency_p99_ms': 120,
    }


@pytest.fixture
def sample_positions():
    """Generate sample position data."""
    return {
        'AAPL': {'quantity': 100, 'avg_price': 150.0, 'current_price': 155.0},
        'MSFT': {'quantity': 50, 'avg_price': 300.0, 'current_price': 310.0},
        'GOOGL': {'quantity': 30, 'avg_price': 140.0, 'current_price': 138.0},
    }


# =============================================================================
# MARKERS
# =============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "ml: marks tests requiring ML libraries")


# =============================================================================
# HOOKS
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Add skip markers for tests requiring optional dependencies
    for item in items:
        # Skip ML tests if libraries not available
        if "ml" in item.keywords:
            try:
                import lightgbm  # noqa
                import xgboost  # noqa
            except ImportError:
                item.add_marker(pytest.mark.skip(
                    reason="ML libraries not installed"
                ))

        # Skip integration tests by default
        if "integration" in item.keywords:
            if not config.getoption("-m", default="").find("integration") >= 0:
                item.add_marker(pytest.mark.skip(
                    reason="Integration tests not selected"
                ))


# =============================================================================
# AUTO-USE FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_random_seed():
    """Reset random seed before each test."""
    import numpy as np
    np.random.seed(42)


@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress logging during tests."""
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)
