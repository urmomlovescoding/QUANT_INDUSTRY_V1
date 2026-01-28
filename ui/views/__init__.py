"""
QUANT_INDUSTRY_V1 UI Views

Screen views for the application.
"""

from .dashboard import DashboardView
from .signals import SignalsView
from .positions import PositionsView
from .health import HealthView

__all__ = [
    'DashboardView',
    'SignalsView',
    'PositionsView',
    'HealthView',
]
