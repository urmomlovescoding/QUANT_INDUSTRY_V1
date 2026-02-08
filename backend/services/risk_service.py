"""
QUANT INDUSTRY - Risk Management Service
Portfolio risk monitoring and management
"""

import logging
import math
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class RiskAlert:
    id: str
    type: AlertType
    category: str
    message: str
    value: float
    limit: float
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "category": self.category,
            "message": self.message,
            "value": self.value,
            "limit": self.limit,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
        }


@dataclass
class RiskMetrics:
    # Portfolio metrics
    total_equity: float
    portfolio_value: float
    cash: float

    # Risk measures
    var_95: float  # Value at Risk (95% confidence)
    var_99: float  # Value at Risk (99% confidence)
    cvar_95: float  # Conditional VaR
    max_drawdown: float
    current_drawdown: float

    # Position metrics
    position_count: int
    max_position_size: float
    max_position_pct: float
    sector_concentration: float

    # P&L metrics
    daily_pnl: float
    daily_pnl_pct: float
    weekly_pnl: float
    monthly_pnl: float

    # Volatility
    portfolio_volatility: float
    beta: float
    sharpe_ratio: float
    sortino_ratio: float

    # Risk score (0-100)
    risk_score: float
    risk_level: RiskLevel

    def to_dict(self) -> Dict:
        return {
            "total_equity": self.total_equity,
            "portfolio_value": self.portfolio_value,
            "cash": self.cash,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "position_count": self.position_count,
            "max_position_size": self.max_position_size,
            "max_position_pct": self.max_position_pct,
            "sector_concentration": self.sector_concentration,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": self.daily_pnl_pct,
            "weekly_pnl": self.weekly_pnl,
            "monthly_pnl": self.monthly_pnl,
            "portfolio_volatility": self.portfolio_volatility,
            "beta": self.beta,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
        }


@dataclass
class RiskLimits:
    max_position_pct: float = 15.0  # Max single position as % of portfolio
    max_position_size_pct: float = 15.0  # Alias for multi-layer checks
    max_sector_pct: float = 40.0   # Max sector concentration
    max_drawdown_pct: float = 15.0  # Max allowed drawdown
    max_daily_loss_pct: float = 3.0  # Max daily loss
    max_var_95: float = 5.0        # Max VaR (95%)
    max_leverage: float = 1.0      # Max leverage ratio
    min_cash_pct: float = 10.0     # Minimum cash reserve
    max_positions: int = 20        # Max number of positions
    max_correlation_exposure: float = 0.7  # Max portfolio correlation


# ============== SECTOR EXPOSURE TRACKING ==============

class Sector(Enum):
    """Standard market sectors (GICS)."""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    ENERGY = "energy"
    INDUSTRIALS = "industrials"
    MATERIALS = "materials"
    UTILITIES = "utilities"
    REAL_ESTATE = "real_estate"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


# Symbol to sector mapping (common stocks)
SYMBOL_SECTORS = {
    # Technology
    "AAPL": Sector.TECHNOLOGY, "MSFT": Sector.TECHNOLOGY, "GOOGL": Sector.TECHNOLOGY,
    "GOOG": Sector.TECHNOLOGY, "NVDA": Sector.TECHNOLOGY, "AMD": Sector.TECHNOLOGY,
    "INTC": Sector.TECHNOLOGY, "CRM": Sector.TECHNOLOGY, "ORCL": Sector.TECHNOLOGY,
    "ADBE": Sector.TECHNOLOGY, "NOW": Sector.TECHNOLOGY, "IBM": Sector.TECHNOLOGY,
    "CSCO": Sector.TECHNOLOGY, "AVGO": Sector.TECHNOLOGY, "QCOM": Sector.TECHNOLOGY,
    "TXN": Sector.TECHNOLOGY, "MU": Sector.TECHNOLOGY, "AMAT": Sector.TECHNOLOGY,
    "LRCX": Sector.TECHNOLOGY, "KLAC": Sector.TECHNOLOGY, "PLTR": Sector.TECHNOLOGY,

    # Consumer Discretionary (includes e-commerce, retail, auto)
    "AMZN": Sector.CONSUMER_DISCRETIONARY, "TSLA": Sector.CONSUMER_DISCRETIONARY,
    "HD": Sector.CONSUMER_DISCRETIONARY, "MCD": Sector.CONSUMER_DISCRETIONARY,
    "NKE": Sector.CONSUMER_DISCRETIONARY, "SBUX": Sector.CONSUMER_DISCRETIONARY,
    "LOW": Sector.CONSUMER_DISCRETIONARY, "TJX": Sector.CONSUMER_DISCRETIONARY,
    "BKNG": Sector.CONSUMER_DISCRETIONARY, "CMG": Sector.CONSUMER_DISCRETIONARY,

    # Communication Services
    "META": Sector.COMMUNICATION, "NFLX": Sector.COMMUNICATION,
    "DIS": Sector.COMMUNICATION, "CMCSA": Sector.COMMUNICATION,
    "T": Sector.COMMUNICATION, "VZ": Sector.COMMUNICATION,

    # Financials
    "JPM": Sector.FINANCIALS, "BAC": Sector.FINANCIALS, "WFC": Sector.FINANCIALS,
    "GS": Sector.FINANCIALS, "MS": Sector.FINANCIALS, "BLK": Sector.FINANCIALS,
    "C": Sector.FINANCIALS, "AXP": Sector.FINANCIALS, "V": Sector.FINANCIALS,
    "MA": Sector.FINANCIALS, "PYPL": Sector.FINANCIALS, "SQ": Sector.FINANCIALS,
    "COIN": Sector.FINANCIALS, "SCHW": Sector.FINANCIALS,

    # Healthcare
    "JNJ": Sector.HEALTHCARE, "UNH": Sector.HEALTHCARE, "PFE": Sector.HEALTHCARE,
    "MRK": Sector.HEALTHCARE, "ABBV": Sector.HEALTHCARE, "LLY": Sector.HEALTHCARE,
    "BMY": Sector.HEALTHCARE, "AMGN": Sector.HEALTHCARE, "GILD": Sector.HEALTHCARE,
    "TMO": Sector.HEALTHCARE, "DHR": Sector.HEALTHCARE, "ABT": Sector.HEALTHCARE,

    # Consumer Staples
    "WMT": Sector.CONSUMER_STAPLES, "COST": Sector.CONSUMER_STAPLES,
    "PG": Sector.CONSUMER_STAPLES, "KO": Sector.CONSUMER_STAPLES,
    "PEP": Sector.CONSUMER_STAPLES, "PM": Sector.CONSUMER_STAPLES,

    # Energy
    "XOM": Sector.ENERGY, "CVX": Sector.ENERGY, "COP": Sector.ENERGY,
    "SLB": Sector.ENERGY, "EOG": Sector.ENERGY, "OXY": Sector.ENERGY,
    "DVN": Sector.ENERGY, "HAL": Sector.ENERGY,

    # Industrials
    "CAT": Sector.INDUSTRIALS, "DE": Sector.INDUSTRIALS, "UPS": Sector.INDUSTRIALS,
    "FDX": Sector.INDUSTRIALS, "BA": Sector.INDUSTRIALS, "HON": Sector.INDUSTRIALS,
    "GE": Sector.INDUSTRIALS, "LMT": Sector.INDUSTRIALS, "RTX": Sector.INDUSTRIALS,

    # Materials
    "LIN": Sector.MATERIALS, "APD": Sector.MATERIALS, "FCX": Sector.MATERIALS,
    "NEM": Sector.MATERIALS, "NUE": Sector.MATERIALS,

    # Utilities
    "NEE": Sector.UTILITIES, "DUK": Sector.UTILITIES, "SO": Sector.UTILITIES,
    "D": Sector.UTILITIES, "AEP": Sector.UTILITIES,

    # Real Estate
    "AMT": Sector.REAL_ESTATE, "PLD": Sector.REAL_ESTATE, "CCI": Sector.REAL_ESTATE,
    "EQIX": Sector.REAL_ESTATE, "PSA": Sector.REAL_ESTATE,

    # ETFs - map to primary sector they track
    "SPY": Sector.UNKNOWN, "QQQ": Sector.TECHNOLOGY, "DIA": Sector.UNKNOWN,
    "IWM": Sector.UNKNOWN, "XLF": Sector.FINANCIALS, "XLK": Sector.TECHNOLOGY,
    "XLE": Sector.ENERGY, "XLV": Sector.HEALTHCARE, "XLY": Sector.CONSUMER_DISCRETIONARY,
    "XLP": Sector.CONSUMER_STAPLES, "XLI": Sector.INDUSTRIALS, "XLB": Sector.MATERIALS,
    "XLU": Sector.UTILITIES, "XLRE": Sector.REAL_ESTATE, "XLC": Sector.COMMUNICATION,
}


@dataclass
class SectorExposure:
    """Exposure data for a single sector."""
    sector: Sector
    value: float
    pct_of_portfolio: float
    position_count: int
    symbols: List[str]


class SectorExposureTracker:
    """
    Tracks sector exposure across portfolio positions.
    Matches quant-platform pattern for sector risk management.
    """

    def __init__(self, max_sector_pct: float = 40.0):
        self.max_sector_pct = max_sector_pct
        self._custom_mappings: Dict[str, Sector] = {}

    def set_sector_mapping(self, symbol: str, sector: Sector):
        """Add or override sector mapping for a symbol."""
        self._custom_mappings[symbol.upper()] = sector

    def get_sector(self, symbol: str) -> Sector:
        """Get sector for a symbol."""
        symbol = symbol.upper()

        # Check custom mappings first
        if symbol in self._custom_mappings:
            return self._custom_mappings[symbol]

        # Check global mapping
        if symbol in SYMBOL_SECTORS:
            return SYMBOL_SECTORS[symbol]

        # Try to infer from symbol pattern
        if symbol.startswith("XL"):  # Sector ETFs
            return Sector.UNKNOWN

        return Sector.UNKNOWN

    def calculate_exposure(
        self,
        positions: List[Dict[str, Any]],
        total_equity: float
    ) -> Dict[str, SectorExposure]:
        """
        Calculate sector exposure from positions.

        Args:
            positions: List of position dicts with 'symbol' and 'market_value'
            total_equity: Total portfolio equity

        Returns:
            Dict mapping sector name to SectorExposure
        """
        sector_data: Dict[Sector, Dict] = {}

        for pos in positions:
            symbol = pos.get('symbol', '').upper()
            value = pos.get('market_value', 0)

            sector = self.get_sector(symbol)

            if sector not in sector_data:
                sector_data[sector] = {
                    'value': 0,
                    'count': 0,
                    'symbols': []
                }

            sector_data[sector]['value'] += value
            sector_data[sector]['count'] += 1
            sector_data[sector]['symbols'].append(symbol)

        # Convert to SectorExposure objects
        result = {}
        for sector, data in sector_data.items():
            pct = (data['value'] / total_equity * 100) if total_equity > 0 else 0
            result[sector.value] = SectorExposure(
                sector=sector,
                value=data['value'],
                pct_of_portfolio=pct,
                position_count=data['count'],
                symbols=data['symbols']
            )

        return result

    def check_sector_limits(
        self,
        positions: List[Dict[str, Any]],
        total_equity: float
    ) -> List[RiskAlert]:
        """
        Check if any sector exceeds concentration limits.

        Returns list of RiskAlerts for sectors over limit.
        """
        alerts = []
        exposure = self.calculate_exposure(positions, total_equity)

        for sector_name, exp in exposure.items():
            if exp.pct_of_portfolio > self.max_sector_pct:
                alerts.append(RiskAlert(
                    id=f"sector_{uuid.uuid4().hex[:8]}",
                    type=AlertType.WARNING,
                    category="sector_concentration",
                    message=f"{sector_name} sector exceeds limit: {exp.pct_of_portfolio:.1f}% > {self.max_sector_pct}%",
                    value=exp.pct_of_portfolio,
                    limit=self.max_sector_pct
                ))
            elif exp.pct_of_portfolio > self.max_sector_pct * 0.8:
                # Warning at 80% of limit
                alerts.append(RiskAlert(
                    id=f"sector_{uuid.uuid4().hex[:8]}",
                    type=AlertType.INFO,
                    category="sector_concentration",
                    message=f"{sector_name} sector approaching limit: {exp.pct_of_portfolio:.1f}%",
                    value=exp.pct_of_portfolio,
                    limit=self.max_sector_pct
                ))

        return alerts

    def get_exposure_summary(
        self,
        positions: List[Dict[str, Any]],
        total_equity: float
    ) -> Dict[str, Any]:
        """Get comprehensive sector exposure summary."""
        exposure = self.calculate_exposure(positions, total_equity)

        # Sort by exposure percentage
        sorted_sectors = sorted(
            exposure.items(),
            key=lambda x: x[1].pct_of_portfolio,
            reverse=True
        )

        return {
            "total_equity": total_equity,
            "position_count": sum(e.position_count for e in exposure.values()),
            "sectors": [
                {
                    "sector": s.sector.value,
                    "value": s.value,
                    "pct_of_portfolio": round(s.pct_of_portfolio, 2),
                    "position_count": s.position_count,
                    "symbols": s.symbols,
                    "over_limit": s.pct_of_portfolio > self.max_sector_pct
                }
                for name, s in sorted_sectors
            ],
            "max_sector_pct": self.max_sector_pct,
            "diversification_score": self._calculate_diversification(exposure)
        }

    def _calculate_diversification(self, exposure: Dict[str, SectorExposure]) -> float:
        """
        Calculate diversification score (0-1).
        Higher is more diversified.
        Uses Herfindahl-Hirschman Index (HHI) approach.
        """
        if not exposure:
            return 0.0

        total = sum(e.pct_of_portfolio for e in exposure.values())
        if total == 0:
            return 0.0

        # Calculate HHI (sum of squared market shares)
        hhi = sum((e.pct_of_portfolio / total * 100) ** 2 for e in exposure.values())

        # Convert to 0-1 score (lower HHI = more diversified)
        # HHI ranges from 10000/n (perfectly equal) to 10000 (single sector)
        n_sectors = len([e for e in exposure.values() if e.pct_of_portfolio > 0])
        if n_sectors <= 1:
            return 0.0

        min_hhi = 10000 / n_sectors
        max_hhi = 10000
        if max_hhi - min_hhi < 1e-10:
            return 0.0
        normalized = (max_hhi - hhi) / (max_hhi - min_hhi)
        return max(0.0, min(1.0, normalized))


# Global sector tracker instance
_sector_tracker: Optional[SectorExposureTracker] = None


def get_sector_tracker() -> SectorExposureTracker:
    """Get global sector exposure tracker instance."""
    global _sector_tracker
    if _sector_tracker is None:
        _sector_tracker = SectorExposureTracker()
    return _sector_tracker


# ============== CORRELATION-BASED RISK ADJUSTMENT ==============

# Pre-computed correlation estimates (simplified)
# In production, these would be calculated from historical data
SYMBOL_CORRELATIONS = {
    # Tech stocks are highly correlated
    ("AAPL", "MSFT"): 0.85, ("AAPL", "GOOGL"): 0.80, ("AAPL", "NVDA"): 0.75,
    ("MSFT", "GOOGL"): 0.82, ("MSFT", "NVDA"): 0.78, ("GOOGL", "NVDA"): 0.72,
    ("AAPL", "META"): 0.70, ("MSFT", "META"): 0.72, ("GOOGL", "META"): 0.75,
    ("AAPL", "AMZN"): 0.72, ("MSFT", "AMZN"): 0.75, ("NVDA", "AMD"): 0.88,

    # Financials
    ("JPM", "BAC"): 0.90, ("JPM", "GS"): 0.85, ("BAC", "WFC"): 0.88,
    ("V", "MA"): 0.92,

    # Energy
    ("XOM", "CVX"): 0.92, ("XOM", "COP"): 0.85, ("CVX", "COP"): 0.87,

    # Healthcare
    ("JNJ", "PFE"): 0.65, ("JNJ", "MRK"): 0.70, ("UNH", "CVS"): 0.75,

    # Sector ETF correlations
    ("SPY", "QQQ"): 0.92, ("SPY", "DIA"): 0.95, ("SPY", "IWM"): 0.88,
    ("QQQ", "XLK"): 0.95,

    # Cross-sector (lower correlations)
    ("AAPL", "XOM"): 0.35, ("MSFT", "JPM"): 0.55, ("NVDA", "JNJ"): 0.25,
    ("GOOGL", "CVX"): 0.30, ("META", "WMT"): 0.40,
}


class CorrelationRiskManager:
    """
    Manages correlation-based position sizing adjustments.
    Reduces position sizes when portfolio correlation is high.

    Matches quant-platform pattern for correlation risk management.
    """

    def __init__(
        self,
        max_portfolio_correlation: float = 0.7,
        correlation_penalty_factor: float = 0.5
    ):
        self.max_portfolio_correlation = max_portfolio_correlation
        self.correlation_penalty_factor = correlation_penalty_factor
        self._custom_correlations: Dict[Tuple[str, str], float] = {}

    def set_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """Set custom correlation between two symbols."""
        key = tuple(sorted([symbol1.upper(), symbol2.upper()]))
        self._custom_correlations[key] = max(-1.0, min(1.0, correlation))

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols."""
        if symbol1.upper() == symbol2.upper():
            return 1.0

        key = tuple(sorted([symbol1.upper(), symbol2.upper()]))

        # Check custom correlations first
        if key in self._custom_correlations:
            return self._custom_correlations[key]

        # Check pre-computed correlations
        if key in SYMBOL_CORRELATIONS:
            return SYMBOL_CORRELATIONS[key]

        # Estimate based on sector
        sector_tracker = get_sector_tracker()
        sector1 = sector_tracker.get_sector(symbol1)
        sector2 = sector_tracker.get_sector(symbol2)

        # Same sector = moderate correlation
        if sector1 == sector2 and sector1 != Sector.UNKNOWN:
            return 0.6

        # Different sectors = low correlation
        return 0.3

    def calculate_portfolio_correlation(
        self,
        positions: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate weighted average correlation of the portfolio.
        Uses market value weights.
        """
        if len(positions) < 2:
            return 0.0

        total_value = sum(p.get('market_value', 0) for p in positions)
        if total_value <= 0:
            return 0.0

        # Calculate weighted correlation matrix
        total_weighted_corr = 0.0
        total_weight = 0.0

        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions):
                if i >= j:  # Only upper triangle (excluding diagonal)
                    continue

                symbol1 = pos1.get('symbol', '')
                symbol2 = pos2.get('symbol', '')
                value1 = pos1.get('market_value', 0)
                value2 = pos2.get('market_value', 0)

                # Weight by combined market value
                weight = (value1 + value2) / total_value
                corr = self.get_correlation(symbol1, symbol2)

                total_weighted_corr += weight * corr
                total_weight += weight

        if total_weight <= 0:
            return 0.0

        return total_weighted_corr / total_weight

    def calculate_position_correlation_penalty(
        self,
        new_symbol: str,
        current_positions: List[Dict[str, Any]],
        total_equity: float
    ) -> float:
        """
        Calculate penalty factor for adding a new position based on correlation.

        Args:
            new_symbol: Symbol being considered for new position
            current_positions: Current portfolio positions
            total_equity: Total portfolio equity

        Returns:
            Penalty factor (0-1) to multiply position size by
        """
        if not current_positions:
            return 0.0  # No penalty for first position

        # Calculate average correlation with existing positions
        total_corr = 0.0
        total_weight = 0.0

        for pos in current_positions:
            symbol = pos.get('symbol', '')
            value = pos.get('market_value', 0)

            if not symbol or value <= 0:
                continue

            weight = value / total_equity if total_equity > 0 else 0
            corr = self.get_correlation(new_symbol, symbol)

            total_corr += weight * abs(corr)  # Use absolute correlation
            total_weight += weight

        if total_weight <= 0:
            return 0.0

        avg_correlation = total_corr / total_weight

        # Calculate penalty
        # No penalty below threshold, linear penalty above
        if avg_correlation <= self.max_portfolio_correlation:
            return 0.0

        excess = avg_correlation - self.max_portfolio_correlation
        penalty = min(1.0, excess * self.correlation_penalty_factor * 5)

        return penalty

    def get_correlation_analysis(
        self,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get detailed correlation analysis for the portfolio."""
        if len(positions) < 2:
            return {
                'portfolio_correlation': 0.0,
                'position_count': len(positions),
                'pairs': [],
                'high_correlation_pairs': [],
                'diversification_benefit': 1.0
            }

        # Calculate all pairwise correlations
        pairs = []
        high_corr_pairs = []

        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions):
                if i >= j:
                    continue

                symbol1 = pos1.get('symbol', '')
                symbol2 = pos2.get('symbol', '')
                corr = self.get_correlation(symbol1, symbol2)

                pair_data = {
                    'symbol1': symbol1,
                    'symbol2': symbol2,
                    'correlation': round(corr, 2)
                }
                pairs.append(pair_data)

                if corr >= 0.7:
                    high_corr_pairs.append(pair_data)

        portfolio_corr = self.calculate_portfolio_correlation(positions)

        # Diversification benefit: 1 - portfolio_correlation
        diversification_benefit = 1.0 - portfolio_corr

        return {
            'portfolio_correlation': round(portfolio_corr, 3),
            'position_count': len(positions),
            'pairs': sorted(pairs, key=lambda x: -x['correlation']),
            'high_correlation_pairs': high_corr_pairs,
            'high_correlation_count': len(high_corr_pairs),
            'diversification_benefit': round(diversification_benefit, 3),
            'max_allowed_correlation': self.max_portfolio_correlation
        }


# Global correlation manager instance
_correlation_manager: Optional[CorrelationRiskManager] = None


def get_correlation_manager() -> CorrelationRiskManager:
    """Get global correlation risk manager instance."""
    global _correlation_manager
    if _correlation_manager is None:
        _correlation_manager = CorrelationRiskManager()
    return _correlation_manager


# ============== POSITION SIZING UTILITIES ==============

def calculate_vix_position_scale(vix: float) -> float:
    """
    Calculate position size multiplier based on VIX level.
    Matches quant-platform pattern - reduce exposure in high volatility.

    VIX < 15: 100% (normal conditions)
    VIX 15-20: 80% (slightly elevated)
    VIX 20-25: 60% (elevated risk)
    VIX 25-30: 40% (high risk)
    VIX > 30: 20% (extreme risk)
    VIX > 40: 10% (crisis mode)
    """
    if vix <= 0:
        return 1.0  # Invalid VIX, no scaling

    if vix < 15:
        return 1.0
    elif vix < 20:
        return 0.8
    elif vix < 25:
        return 0.6
    elif vix < 30:
        return 0.4
    elif vix < 40:
        return 0.2
    else:
        return 0.1


def calculate_kelly_position_size(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    kelly_fraction: float = 0.25
) -> float:
    """
    Calculate position size using fractional Kelly criterion.
    Matches quant-platform pattern.

    Args:
        win_rate: Historical win rate (0-1)
        avg_win: Average winning trade return
        avg_loss: Average losing trade return (positive number)
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)

    Returns:
        Recommended position size as fraction of portfolio (0-1)
    """
    if win_rate <= 0 or win_rate >= 1:
        return 0.0
    if avg_loss <= 0:
        return 0.0

    # Kelly formula: f* = (bp - q) / b
    # where b = avg_win/avg_loss, p = win_rate, q = 1-p
    b = avg_win / max(avg_loss, 1e-10)
    p = win_rate
    q = 1 - p

    if b <= 0:
        return 0.0

    kelly = (b * p - q) / b

    # Apply fraction and clamp to reasonable bounds
    position_size = kelly * kelly_fraction
    return max(0.0, min(0.25, position_size))  # Cap at 25%


def calculate_adjusted_position_size(
    base_size_pct: float,
    vix: float,
    confidence: float,
    regime: str,
    correlation_penalty: float = 0.0
) -> float:
    """
    Calculate final position size with all adjustments.

    Args:
        base_size_pct: Base position size percentage
        vix: Current VIX level
        confidence: Signal confidence (0-1)
        regime: Market regime string
        correlation_penalty: Reduction for correlated positions (0-1)

    Returns:
        Adjusted position size percentage
    """
    # Start with base size
    size = base_size_pct

    # Apply VIX scaling
    vix_scale = calculate_vix_position_scale(vix)
    size *= vix_scale

    # Apply confidence scaling (square root to not penalize too harshly)
    confidence_scale = math.sqrt(max(0.1, min(1.0, confidence)))
    size *= confidence_scale

    # Apply regime-based adjustment
    regime_scales = {
        'trending_up': 1.0,
        'trending_down': 1.0,
        'breakout': 0.9,
        'mean_reverting': 0.85,
        'ranging': 0.7,
        'quiet': 0.6,
        'volatile': 0.4,
        'unknown': 0.3,
    }
    regime_scale = regime_scales.get(regime.lower(), 0.5)
    size *= regime_scale

    # Apply correlation penalty
    size *= (1.0 - correlation_penalty)

    # Ensure minimum and maximum bounds
    return max(0.5, min(20.0, size))


# ============== MULTI-LAYER RISK CHECK SYSTEM ==============

class RiskCheckLayer(Enum):
    """Risk check layers - ordered by priority."""
    KILL_SWITCH = "kill_switch"       # Layer 0: Emergency stop
    ACCOUNT_LIMITS = "account_limits" # Layer 1: Account-level limits
    POSITION_LIMITS = "position_limits"  # Layer 2: Position limits
    DRAWDOWN = "drawdown"             # Layer 3: Drawdown checks
    VOLATILITY = "volatility"         # Layer 4: Volatility checks
    CORRELATION = "correlation"       # Layer 5: Correlation checks
    TIME_BASED = "time_based"         # Layer 6: Time-based restrictions


@dataclass
class RiskCheckResult:
    """Result of a single risk check."""
    layer: RiskCheckLayer
    passed: bool
    message: str
    severity: RiskLevel
    value: Optional[float] = None
    limit: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "layer": self.layer.value,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity.value,
            "value": self.value,
            "limit": self.limit,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MultiLayerRiskResult:
    """Combined result from multi-layer risk check."""
    approved: bool
    checks: List[RiskCheckResult]
    blocking_layer: Optional[RiskCheckLayer] = None
    total_checks: int = 0
    passed_checks: int = 0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "approved": self.approved,
            "blocking_layer": self.blocking_layer.value if self.blocking_layer else None,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "checks": [c.to_dict() for c in self.checks],
            "warnings": self.warnings
        }


class MultiLayerRiskEngine:
    """
    Multi-layer risk engine for comprehensive trade validation.
    Matches quant-platform pattern for defense-in-depth risk management.

    Layers (checked in order):
    1. Kill Switch - emergency halt check
    2. Account Limits - daily loss, total equity limits
    3. Position Limits - position size, count, sector exposure
    4. Drawdown - max drawdown, trailing drawdown
    5. Volatility - VIX-based, realized volatility
    6. Correlation - portfolio correlation limits
    7. Time-based - market hours, blackout periods
    """

    def __init__(self, limits: 'RiskLimits' = None):
        self.limits = limits or RiskLimits()
        self._custom_checks: Dict[RiskCheckLayer, List[callable]] = {
            layer: [] for layer in RiskCheckLayer
        }

    def register_custom_check(
        self,
        layer: RiskCheckLayer,
        check_fn: callable,
        name: str = ""
    ):
        """Register a custom check function for a layer."""
        self._custom_checks[layer].append({
            "name": name or f"custom_{len(self._custom_checks[layer])}",
            "fn": check_fn
        })

    def check_trade(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        quantity: int,
        price: float,
        account_equity: float,
        current_positions: List[Dict],
        current_drawdown_pct: float = 0.0,
        daily_pnl: float = 0.0,
        vix: float = 0.0,
        correlation_exposure: float = 0.0
    ) -> MultiLayerRiskResult:
        """
        Run multi-layer risk checks on a proposed trade.

        Returns MultiLayerRiskResult with approval status and all check details.
        """
        checks = []
        warnings = []
        blocking_layer = None
        trade_value = quantity * price

        # Layer 0: Kill Switch
        check = self._check_kill_switch()
        checks.append(check)
        if not check.passed:
            blocking_layer = RiskCheckLayer.KILL_SWITCH
            return self._build_result(checks, False, blocking_layer, warnings)

        # Layer 1: Account Limits
        account_checks = self._check_account_limits(
            trade_value, account_equity, daily_pnl
        )
        checks.extend(account_checks)
        failed = [c for c in account_checks if not c.passed and c.severity == RiskLevel.CRITICAL]
        if failed:
            blocking_layer = RiskCheckLayer.ACCOUNT_LIMITS
            return self._build_result(checks, False, blocking_layer, warnings)
        warnings.extend([c.message for c in account_checks if not c.passed])

        # Layer 2: Position Limits
        position_checks = self._check_position_limits(
            symbol, trade_value, account_equity, current_positions
        )
        checks.extend(position_checks)
        failed = [c for c in position_checks if not c.passed and c.severity == RiskLevel.CRITICAL]
        if failed:
            blocking_layer = RiskCheckLayer.POSITION_LIMITS
            return self._build_result(checks, False, blocking_layer, warnings)
        warnings.extend([c.message for c in position_checks if not c.passed])

        # Layer 3: Drawdown
        drawdown_checks = self._check_drawdown(current_drawdown_pct)
        checks.extend(drawdown_checks)
        failed = [c for c in drawdown_checks if not c.passed and c.severity == RiskLevel.CRITICAL]
        if failed:
            blocking_layer = RiskCheckLayer.DRAWDOWN
            return self._build_result(checks, False, blocking_layer, warnings)
        warnings.extend([c.message for c in drawdown_checks if not c.passed])

        # Layer 4: Volatility
        volatility_checks = self._check_volatility(vix)
        checks.extend(volatility_checks)
        failed = [c for c in volatility_checks if not c.passed and c.severity == RiskLevel.CRITICAL]
        if failed:
            blocking_layer = RiskCheckLayer.VOLATILITY
            return self._build_result(checks, False, blocking_layer, warnings)
        warnings.extend([c.message for c in volatility_checks if not c.passed])

        # Layer 5: Correlation
        correlation_checks = self._check_correlation(correlation_exposure)
        checks.extend(correlation_checks)
        failed = [c for c in correlation_checks if not c.passed and c.severity == RiskLevel.CRITICAL]
        if failed:
            blocking_layer = RiskCheckLayer.CORRELATION
            return self._build_result(checks, False, blocking_layer, warnings)
        warnings.extend([c.message for c in correlation_checks if not c.passed])

        # Layer 6: Time-based
        time_checks = self._check_time_based()
        checks.extend(time_checks)
        failed = [c for c in time_checks if not c.passed and c.severity == RiskLevel.CRITICAL]
        if failed:
            blocking_layer = RiskCheckLayer.TIME_BASED
            return self._build_result(checks, False, blocking_layer, warnings)
        warnings.extend([c.message for c in time_checks if not c.passed])

        # Run custom checks
        for layer in RiskCheckLayer:
            for custom in self._custom_checks[layer]:
                try:
                    result = custom["fn"](
                        symbol=symbol, side=side, quantity=quantity,
                        price=price, account_equity=account_equity
                    )
                    if isinstance(result, RiskCheckResult):
                        checks.append(result)
                        if not result.passed and result.severity == RiskLevel.CRITICAL:
                            blocking_layer = layer
                            return self._build_result(checks, False, blocking_layer, warnings)
                except Exception as e:
                    logger.error(f"Custom check '{custom['name']}' error: {e}")

        return self._build_result(checks, True, None, warnings)

    def _build_result(
        self,
        checks: List[RiskCheckResult],
        approved: bool,
        blocking_layer: Optional[RiskCheckLayer],
        warnings: List[str]
    ) -> MultiLayerRiskResult:
        """Build the final result."""
        return MultiLayerRiskResult(
            approved=approved,
            checks=checks,
            blocking_layer=blocking_layer,
            total_checks=len(checks),
            passed_checks=len([c for c in checks if c.passed]),
            warnings=warnings
        )

    def _check_kill_switch(self) -> RiskCheckResult:
        """Layer 0: Check kill switch status."""
        try:
            from execution.broker_adapter import get_kill_switch
            kill_switch = get_kill_switch()
            if kill_switch.active:
                return RiskCheckResult(
                    layer=RiskCheckLayer.KILL_SWITCH,
                    passed=False,
                    message=f"Kill switch active: {kill_switch.reason}",
                    severity=RiskLevel.CRITICAL
                )
        except ImportError:
            pass

        return RiskCheckResult(
            layer=RiskCheckLayer.KILL_SWITCH,
            passed=True,
            message="Kill switch not active",
            severity=RiskLevel.LOW
        )

    def _check_account_limits(
        self,
        trade_value: float,
        account_equity: float,
        daily_pnl: float
    ) -> List[RiskCheckResult]:
        """Layer 1: Check account-level limits."""
        results = []

        # Daily loss limit
        daily_loss_pct = abs(min(0, daily_pnl)) / account_equity * 100 if account_equity > 0 else 0
        passed = daily_loss_pct < self.limits.max_daily_loss_pct
        results.append(RiskCheckResult(
            layer=RiskCheckLayer.ACCOUNT_LIMITS,
            passed=passed,
            message=f"Daily loss: {daily_loss_pct:.2f}%" if passed else f"Daily loss limit exceeded: {daily_loss_pct:.2f}%",
            severity=RiskLevel.CRITICAL if not passed else RiskLevel.LOW,
            value=daily_loss_pct,
            limit=self.limits.max_daily_loss_pct
        ))

        # Trade size relative to account
        trade_pct = trade_value / account_equity * 100 if account_equity > 0 else 100
        passed = trade_pct <= self.limits.max_position_size_pct
        results.append(RiskCheckResult(
            layer=RiskCheckLayer.ACCOUNT_LIMITS,
            passed=passed,
            message=f"Trade size: {trade_pct:.2f}% of account" if passed else f"Trade too large: {trade_pct:.2f}%",
            severity=RiskLevel.HIGH if not passed else RiskLevel.LOW,
            value=trade_pct,
            limit=self.limits.max_position_size_pct
        ))

        return results

    def _check_position_limits(
        self,
        symbol: str,
        trade_value: float,
        account_equity: float,
        current_positions: List[Dict]
    ) -> List[RiskCheckResult]:
        """Layer 2: Check position limits."""
        results = []

        # Position count
        position_count = len(current_positions)
        passed = position_count < self.limits.max_positions
        results.append(RiskCheckResult(
            layer=RiskCheckLayer.POSITION_LIMITS,
            passed=passed,
            message=f"Position count: {position_count}" if passed else f"Max positions reached: {position_count}",
            severity=RiskLevel.HIGH if not passed else RiskLevel.LOW,
            value=float(position_count),
            limit=float(self.limits.max_positions)
        ))

        # Check existing position in same symbol
        existing = next((p for p in current_positions if p.get('symbol') == symbol), None)
        if existing:
            existing_value = existing.get('market_value', 0)
            total_exposure = (existing_value + trade_value) / max(account_equity, 1e-10) * 100
            passed = total_exposure <= self.limits.max_position_size_pct * 1.5  # Allow 1.5x for adding
            results.append(RiskCheckResult(
                layer=RiskCheckLayer.POSITION_LIMITS,
                passed=passed,
                message=f"Total {symbol} exposure: {total_exposure:.2f}%" if passed else f"Excessive {symbol} exposure: {total_exposure:.2f}%",
                severity=RiskLevel.HIGH if not passed else RiskLevel.LOW,
                value=total_exposure,
                limit=self.limits.max_position_size_pct * 1.5
            ))

        return results

    def _check_drawdown(self, current_drawdown_pct: float) -> List[RiskCheckResult]:
        """Layer 3: Check drawdown limits."""
        results = []

        passed = current_drawdown_pct < self.limits.max_drawdown_pct
        severity = RiskLevel.LOW
        if current_drawdown_pct >= self.limits.max_drawdown_pct:
            severity = RiskLevel.CRITICAL
        elif current_drawdown_pct >= self.limits.max_drawdown_pct * 0.8:
            severity = RiskLevel.HIGH
        elif current_drawdown_pct >= self.limits.max_drawdown_pct * 0.5:
            severity = RiskLevel.MODERATE

        results.append(RiskCheckResult(
            layer=RiskCheckLayer.DRAWDOWN,
            passed=passed,
            message=f"Current drawdown: {current_drawdown_pct:.2f}%",
            severity=severity,
            value=current_drawdown_pct,
            limit=self.limits.max_drawdown_pct
        ))

        return results

    def _check_volatility(self, vix: float) -> List[RiskCheckResult]:
        """Layer 4: Check volatility conditions."""
        results = []

        if vix <= 0:
            results.append(RiskCheckResult(
                layer=RiskCheckLayer.VOLATILITY,
                passed=True,
                message="VIX data not available",
                severity=RiskLevel.LOW
            ))
            return results

        # VIX check
        passed = vix < 40  # Extreme volatility threshold
        severity = RiskLevel.LOW
        if vix >= 40:
            severity = RiskLevel.CRITICAL
        elif vix >= 30:
            severity = RiskLevel.HIGH
        elif vix >= 25:
            severity = RiskLevel.MODERATE

        results.append(RiskCheckResult(
            layer=RiskCheckLayer.VOLATILITY,
            passed=passed,
            message=f"VIX level: {vix:.2f}",
            severity=severity,
            value=vix,
            limit=40.0
        ))

        return results

    def _check_correlation(self, correlation_exposure: float) -> List[RiskCheckResult]:
        """Layer 5: Check correlation exposure."""
        results = []

        passed = correlation_exposure < self.limits.max_correlation_exposure
        severity = RiskLevel.LOW
        if correlation_exposure >= self.limits.max_correlation_exposure:
            severity = RiskLevel.HIGH
        elif correlation_exposure >= self.limits.max_correlation_exposure * 0.8:
            severity = RiskLevel.MODERATE

        results.append(RiskCheckResult(
            layer=RiskCheckLayer.CORRELATION,
            passed=passed,
            message=f"Correlation exposure: {correlation_exposure:.2f}",
            severity=severity,
            value=correlation_exposure,
            limit=self.limits.max_correlation_exposure
        ))

        return results

    def _check_time_based(self) -> List[RiskCheckResult]:
        """Layer 6: Check time-based restrictions."""
        results = []

        now = datetime.now()
        hour = now.hour

        # Market hours check (simplified - assumes US market)
        is_market_hours = 9 <= hour < 16  # 9:30 AM - 4:00 PM ET approximation

        results.append(RiskCheckResult(
            layer=RiskCheckLayer.TIME_BASED,
            passed=True,  # Warning only, not blocking
            message="Within market hours" if is_market_hours else "Outside regular market hours",
            severity=RiskLevel.LOW if is_market_hours else RiskLevel.MODERATE
        ))

        return results


# Global multi-layer risk engine instance
_multi_layer_risk_engine: Optional[MultiLayerRiskEngine] = None


def get_multi_layer_risk_engine() -> MultiLayerRiskEngine:
    """Get global multi-layer risk engine instance."""
    global _multi_layer_risk_engine
    if _multi_layer_risk_engine is None:
        _multi_layer_risk_engine = MultiLayerRiskEngine()
    return _multi_layer_risk_engine


class RiskService:
    """
    Risk management service for portfolio monitoring
    """

    def __init__(self, limits: RiskLimits = None, db_path: str = None):
        self.limits = limits or RiskLimits()
        self.alerts: List[RiskAlert] = []
        self.equity_history: List[tuple] = []  # (timestamp, equity)
        self.high_water_mark: float = 0
        self.lock = threading.Lock()

        # Database
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "risk.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        logger.info("RiskService initialized")

    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_alerts (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                value REAL,
                limit_value REAL,
                timestamp TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equity_history (
                timestamp TEXT PRIMARY KEY,
                equity REAL NOT NULL,
                drawdown REAL,
                daily_pnl REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                details TEXT
            )
        """)

        conn.commit()
        conn.close()

    def calculate_metrics(self) -> RiskMetrics:
        """Calculate current risk metrics"""
        from .data_service import get_data_service
        from .trading_service import get_trading_service

        trading = get_trading_service()
        data = get_data_service()

        account = trading.get_account_info()
        positions = trading.get_all_positions()

        # Update high water mark
        self.high_water_mark = max(self.high_water_mark, account.equity)

        # Calculate drawdown
        current_drawdown = 0
        if self.high_water_mark > 0:
            current_drawdown = ((self.high_water_mark - account.equity) / self.high_water_mark) * 100

        # Calculate position metrics
        position_values = [p.market_value for p in positions]
        max_position_size = max(position_values) if position_values else 0
        max_position_pct = (max_position_size / account.equity * 100) if account.equity > 0 else 0

        # Calculate sector concentration (simplified - assume tech heavy)
        sector_concentration = (sum(p.market_value for p in positions) / max(account.equity, 1e-10) * 100) if positions else 0

        # Calculate VaR (simplified parametric)
        portfolio_volatility = self._estimate_portfolio_volatility(positions)
        var_95 = account.equity * portfolio_volatility * 1.645  # 95% confidence
        var_99 = account.equity * portfolio_volatility * 2.326  # 99% confidence
        cvar_95 = var_95 * 1.2  # Approximate CVaR

        # Calculate risk score (0-100)
        risk_score = self._calculate_risk_score(
            current_drawdown=current_drawdown,
            var_pct=(var_95 / account.equity * 100) if account.equity > 0 else 0,
            position_concentration=max_position_pct,
            sector_concentration=sector_concentration,
            daily_loss_pct=abs(account.day_pnl_pct) if account.day_pnl < 0 else 0
        )

        # Determine risk level
        if risk_score < 25:
            risk_level = RiskLevel.LOW
        elif risk_score < 50:
            risk_level = RiskLevel.MODERATE
        elif risk_score < 75:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        metrics = RiskMetrics(
            total_equity=account.equity,
            portfolio_value=account.portfolio_value,
            cash=account.cash,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            max_drawdown=current_drawdown,  # For now, same as current
            current_drawdown=current_drawdown,
            position_count=len(positions),
            max_position_size=max_position_size,
            max_position_pct=max_position_pct,
            sector_concentration=sector_concentration,
            daily_pnl=account.day_pnl,
            daily_pnl_pct=account.day_pnl_pct,
            weekly_pnl=account.day_pnl * 5,  # Estimate
            monthly_pnl=account.day_pnl * 22,  # Estimate
            portfolio_volatility=portfolio_volatility * 100,
            beta=1.15,  # Estimate
            sharpe_ratio=1.5,  # Estimate
            sortino_ratio=2.0,  # Estimate
            risk_score=risk_score,
            risk_level=risk_level
        )

        # Check for limit breaches
        self._check_limits(metrics)

        return metrics

    def _estimate_portfolio_volatility(self, positions) -> float:
        """Estimate portfolio volatility"""
        if not positions:
            return 0.0

        # Simplified: assume 20% annualized volatility for equities
        # Convert to daily: 20% / sqrt(252) ≈ 1.26%
        base_volatility = 0.20 / math.sqrt(252)

        # Adjust for concentration
        total_value = sum(p.market_value for p in positions)
        if total_value == 0:
            return base_volatility

        weights = [p.market_value / total_value for p in positions]
        concentration = sum(w ** 2 for w in weights)  # Herfindahl index

        # Higher concentration = higher portfolio volatility
        return base_volatility * (1 + concentration)

    def _calculate_risk_score(
        self,
        current_drawdown: float,
        var_pct: float,
        position_concentration: float,
        sector_concentration: float,
        daily_loss_pct: float
    ) -> float:
        """Calculate overall risk score (0-100)"""
        # Weight each risk factor
        dd_score = min(100, (current_drawdown / max(self.limits.max_drawdown_pct, 1e-10)) * 100 * 0.25)
        var_score = min(100, (var_pct / max(self.limits.max_var_95, 1e-10)) * 100 * 0.2)
        pos_score = min(100, (position_concentration / max(self.limits.max_position_pct, 1e-10)) * 100 * 0.2)
        sec_score = min(100, (sector_concentration / max(self.limits.max_sector_pct, 1e-10)) * 100 * 0.15)
        loss_score = min(100, (daily_loss_pct / max(self.limits.max_daily_loss_pct, 1e-10)) * 100 * 0.2)

        return dd_score + var_score + pos_score + sec_score + loss_score

    def _check_limits(self, metrics: RiskMetrics):
        """Check if any limits are breached"""

        # Position size limit
        if metrics.max_position_pct > self.limits.max_position_pct:
            self._create_alert(
                AlertType.WARNING,
                "position_size",
                f"Position size ({metrics.max_position_pct:.1f}%) exceeds limit ({self.limits.max_position_pct}%)",
                metrics.max_position_pct,
                self.limits.max_position_pct
            )

        # Sector concentration limit
        if metrics.sector_concentration > self.limits.max_sector_pct:
            self._create_alert(
                AlertType.WARNING,
                "sector_concentration",
                f"Sector concentration ({metrics.sector_concentration:.1f}%) exceeds limit ({self.limits.max_sector_pct}%)",
                metrics.sector_concentration,
                self.limits.max_sector_pct
            )

        # Drawdown limit
        if metrics.current_drawdown > self.limits.max_drawdown_pct:
            self._create_alert(
                AlertType.CRITICAL,
                "drawdown",
                f"Drawdown ({metrics.current_drawdown:.1f}%) exceeds limit ({self.limits.max_drawdown_pct}%)",
                metrics.current_drawdown,
                self.limits.max_drawdown_pct
            )

        # Daily loss limit
        if abs(metrics.daily_pnl_pct) > self.limits.max_daily_loss_pct and metrics.daily_pnl < 0:
            self._create_alert(
                AlertType.CRITICAL,
                "daily_loss",
                f"Daily loss ({abs(metrics.daily_pnl_pct):.1f}%) exceeds limit ({self.limits.max_daily_loss_pct}%)",
                abs(metrics.daily_pnl_pct),
                self.limits.max_daily_loss_pct
            )

        # VaR limit
        var_pct = (metrics.var_95 / metrics.total_equity * 100) if metrics.total_equity > 0 else 0
        if var_pct > self.limits.max_var_95:
            self._create_alert(
                AlertType.WARNING,
                "var",
                f"VaR ({var_pct:.1f}%) exceeds limit ({self.limits.max_var_95}%)",
                var_pct,
                self.limits.max_var_95
            )

    def _create_alert(
        self,
        alert_type: AlertType,
        category: str,
        message: str,
        value: float,
        limit: float
    ):
        """Create a new risk alert"""
        alert = RiskAlert(
            id=str(uuid.uuid4())[:8],
            type=alert_type,
            category=category,
            message=message,
            value=value,
            limit=limit
        )

        with self.lock:
            self.alerts.append(alert)
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]

        self._save_alert(alert)
        logger.warning(f"Risk alert: {message}")

    def get_alerts(self, unacknowledged_only: bool = False) -> List[RiskAlert]:
        """Get risk alerts"""
        with self.lock:
            if unacknowledged_only:
                return [a for a in self.alerts if not a.acknowledged]
            return list(self.alerts)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a risk alert"""
        with self.lock:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
        return False

    def get_limits(self) -> Dict:
        """Get current risk limits"""
        return {
            "max_position_pct": self.limits.max_position_pct,
            "max_sector_pct": self.limits.max_sector_pct,
            "max_drawdown_pct": self.limits.max_drawdown_pct,
            "max_daily_loss_pct": self.limits.max_daily_loss_pct,
            "max_var_95": self.limits.max_var_95,
            "max_leverage": self.limits.max_leverage,
            "min_cash_pct": self.limits.min_cash_pct,
        }

    def update_limits(self, **kwargs):
        """Update risk limits"""
        for key, value in kwargs.items():
            if hasattr(self.limits, key):
                setattr(self.limits, key, value)

    def can_open_position(self, symbol: str, value: float) -> tuple:
        """Check if a new position can be opened within risk limits"""
        metrics = self.calculate_metrics()

        # Check position size
        new_position_pct = (value / max(metrics.total_equity, 1e-10)) * 100
        if new_position_pct > self.limits.max_position_pct:
            return False, f"Position size ({new_position_pct:.1f}%) would exceed limit"

        # Check cash availability
        if value > metrics.cash:
            return False, f"Insufficient cash (${metrics.cash:,.2f}) for position (${value:,.2f})"

        # Check drawdown
        if metrics.current_drawdown > self.limits.max_drawdown_pct:
            return False, f"Current drawdown ({metrics.current_drawdown:.1f}%) exceeds limit"

        return True, "OK"

    def _save_alert(self, alert: RiskAlert):
        """Save alert to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_alerts
            (id, type, category, message, value, limit_value, timestamp, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.id, alert.type.value, alert.category, alert.message,
            alert.value, alert.limit, alert.timestamp.isoformat(),
            1 if alert.acknowledged else 0
        ))
        conn.commit()
        conn.close()


# Singleton instance
_risk_service: Optional[RiskService] = None

def get_risk_service() -> RiskService:
    global _risk_service
    if _risk_service is None:
        _risk_service = RiskService()
    return _risk_service
