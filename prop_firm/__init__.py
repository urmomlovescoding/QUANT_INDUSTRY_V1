"""
QUANT_INDUSTRY_V1 Prop Firm Trading Module

Specialized module for passing prop firm evaluations.
Supports TPT, Apex, FTMO, and other major prop firms.
"""

from prop_firm.rules import PropFirmRules, AccountConfig, EvaluationTracker
from prop_firm.manager import PropFirmManager
from prop_firm.consistency import ConsistencyMonitor

__all__ = [
    'PropFirmRules',
    'AccountConfig',
    'EvaluationTracker',
    'PropFirmManager',
    'ConsistencyMonitor',
]
