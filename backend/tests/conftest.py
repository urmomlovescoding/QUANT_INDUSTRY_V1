"""
Pytest configuration and fixtures
"""
import os
import sys

import pytest

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)


@pytest.fixture
def mock_market_open():
    """Mock market as open"""
    from datetime import datetime
    from unittest.mock import patch

    import pytz

    et = pytz.timezone('US/Eastern')
    open_time = et.localize(datetime(2026, 1, 26, 12, 0, 0))  # Monday noon

    with patch('services.market_hours.get_eastern_now', return_value=open_time):
        yield open_time


@pytest.fixture
def mock_market_closed():
    """Mock market as closed (weekend)"""
    from datetime import datetime
    from unittest.mock import patch

    import pytz

    et = pytz.timezone('US/Eastern')
    closed_time = et.localize(datetime(2026, 1, 24, 12, 0, 0))  # Saturday

    with patch('services.market_hours.get_eastern_now', return_value=closed_time):
        yield closed_time


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Provide a temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return str(cache_dir)
