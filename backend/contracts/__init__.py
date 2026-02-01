"""
Service Contracts
=================
Canonical interfaces for all major services.

All implementations MUST conform to these contracts.
This is the SINGLE SOURCE OF TRUTH for service interfaces.

Architecture:
    contracts/ (interfaces)
        ↓
    services/ (implementations)
        ↓
    adapters/ (external integrations)
        ↓
    routes/ (API layer)
"""

from .market_data import MarketDataContract, Quote, Bar, MarketStatus
from .execution import ExecutionContract, OrderRequest, OrderResult, ExecutionMode
from .portfolio import PortfolioContract, Position, Holdings, PortfolioSnapshot
from .risk import RiskContract, RiskMetrics, RiskLimits, RiskCheck
from .journal import JournalContract, TradeRecord, JournalEntry

__all__ = [
    # Market Data
    'MarketDataContract', 'Quote', 'Bar', 'MarketStatus',
    # Execution
    'ExecutionContract', 'OrderRequest', 'OrderResult', 'ExecutionMode',
    # Portfolio
    'PortfolioContract', 'Position', 'Holdings', 'PortfolioSnapshot',
    # Risk
    'RiskContract', 'RiskMetrics', 'RiskLimits', 'RiskCheck',
    # Journal
    'JournalContract', 'TradeRecord', 'JournalEntry',
]
