"""
Options Flow Alpha Module
=========================
Unusual activity detection, smart money tracking, and options-based signals.

Components:
- unusual_activity: Detect abnormal options volume and sweeps
- dark_pool: Block trade and dark pool print analysis
- gamma_exposure: GEX calculations and pin risk
- flow_signals: Aggregated trading signals from options flow
- smart_money: Institutional flow tracking
"""

from .unusual_activity import UnusualActivityDetector, OptionsActivityType
from .dark_pool import DarkPoolMonitor, BlockTrade
from .gamma_exposure import GammaExposureCalculator, GEXLevel
from .flow_signals import OptionsFlowSignals, FlowSignal
from .smart_money import SmartMoneyTracker, InstitutionalFlow

__all__ = [
    "UnusualActivityDetector",
    "OptionsActivityType",
    "DarkPoolMonitor", 
    "BlockTrade",
    "GammaExposureCalculator",
    "GEXLevel",
    "OptionsFlowSignals",
    "FlowSignal",
    "SmartMoneyTracker",
    "InstitutionalFlow",
]

__version__ = "1.0.0"
