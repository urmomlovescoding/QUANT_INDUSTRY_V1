"""
QUANT_INDUSTRY_V1 Options Analysis Module

Full production options analysis including:
- Black-Scholes pricing
- Greeks calculation (Delta, Gamma, Vega, Theta, Rho)
- Implied Volatility calculation
- GEX (Gamma Exposure) mapping
- Put/Call ratio analysis
- Options flow analysis
- Volatility surface modeling

Pure NumPy implementation.
"""

import numpy as np
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from scipy import stats
from scipy.optimize import brentq

logger = logging.getLogger(__name__)


# =============================================================================
# OPTIONS TYPES
# =============================================================================

class OptionType(Enum):
    """Option type."""
    CALL = "call"
    PUT = "put"


@dataclass
class OptionContract:
    """Single option contract."""
    symbol: str
    underlying: str
    strike: float
    expiry: date
    option_type: OptionType
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0

    @property
    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid > 0 and self.ask > 0 else self.last_price

    @property
    def days_to_expiry(self) -> int:
        return (self.expiry - date.today()).days

    @property
    def time_to_expiry(self) -> float:
        """Time to expiry in years."""
        return max(self.days_to_expiry / 365.0, 1/365)  # Minimum 1 day


@dataclass
class OptionGreeks:
    """Option Greeks."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


@dataclass
class OptionsChain:
    """Full options chain for an underlying."""
    underlying: str
    spot_price: float
    chain_date: date
    calls: List[OptionContract] = field(default_factory=list)
    puts: List[OptionContract] = field(default_factory=list)
    expiries: List[date] = field(default_factory=list)
    strikes: List[float] = field(default_factory=list)


# =============================================================================
# BLACK-SCHOLES MODEL
# =============================================================================

class BlackScholes:
    """
    Black-Scholes option pricing model.

    Calculates:
    - Option prices
    - All Greeks
    - Implied volatility
    """

    @staticmethod
    def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 parameter."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d2 parameter."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return BlackScholes.d1(S, K, T, r, sigma) - sigma * np.sqrt(T)

    @staticmethod
    def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate call option price."""
        if T <= 0:
            return max(0, S - K)

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)

        return S * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)

    @staticmethod
    def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate put option price."""
        if T <= 0:
            return max(0, K - S)

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)

        return K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)

    @staticmethod
    def price(S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType) -> float:
        """Calculate option price."""
        if option_type == OptionType.CALL:
            return BlackScholes.call_price(S, K, T, r, sigma)
        else:
            return BlackScholes.put_price(S, K, T, r, sigma)

    @staticmethod
    def delta(S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType) -> float:
        """Calculate delta."""
        if T <= 0:
            if option_type == OptionType.CALL:
                return 1.0 if S > K else 0.0
            else:
                return -1.0 if S < K else 0.0

        d1 = BlackScholes.d1(S, K, T, r, sigma)

        if option_type == OptionType.CALL:
            return stats.norm.cdf(d1)
        else:
            return stats.norm.cdf(d1) - 1

    @staticmethod
    def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate gamma (same for calls and puts)."""
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0.0

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        return stats.norm.pdf(d1) / (S * sigma * np.sqrt(T))

    @staticmethod
    def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate vega (same for calls and puts)."""
        if T <= 0:
            return 0.0

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        return S * stats.norm.pdf(d1) * np.sqrt(T) / 100  # Per 1% change in vol

    @staticmethod
    def theta(S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType) -> float:
        """Calculate theta (per day)."""
        if T <= 0:
            return 0.0

        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)

        first_term = -S * stats.norm.pdf(d1) * sigma / (2 * np.sqrt(T))

        if option_type == OptionType.CALL:
            second_term = -r * K * np.exp(-r * T) * stats.norm.cdf(d2)
        else:
            second_term = r * K * np.exp(-r * T) * stats.norm.cdf(-d2)

        return (first_term + second_term) / 365  # Daily theta

    @staticmethod
    def rho(S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType) -> float:
        """Calculate rho."""
        if T <= 0:
            return 0.0

        d2 = BlackScholes.d2(S, K, T, r, sigma)

        if option_type == OptionType.CALL:
            return K * T * np.exp(-r * T) * stats.norm.cdf(d2) / 100
        else:
            return -K * T * np.exp(-r * T) * stats.norm.cdf(-d2) / 100

    @staticmethod
    def calculate_greeks(
        S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType
    ) -> OptionGreeks:
        """Calculate all Greeks."""
        return OptionGreeks(
            delta=BlackScholes.delta(S, K, T, r, sigma, option_type),
            gamma=BlackScholes.gamma(S, K, T, r, sigma),
            theta=BlackScholes.theta(S, K, T, r, sigma, option_type),
            vega=BlackScholes.vega(S, K, T, r, sigma),
            rho=BlackScholes.rho(S, K, T, r, sigma, option_type),
        )

    @staticmethod
    def implied_volatility(
        price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType,
        precision: float = 1e-6,
        max_iterations: int = 100,
    ) -> float:
        """
        Calculate implied volatility using Newton-Raphson method.
        """
        if T <= 0 or price <= 0:
            return 0.0

        # Initial guess
        sigma = 0.3

        for _ in range(max_iterations):
            calc_price = BlackScholes.price(S, K, T, r, sigma, option_type)
            vega = BlackScholes.vega(S, K, T, r, sigma) * 100  # Undo the /100

            if vega < 1e-10:
                break

            diff = calc_price - price
            if abs(diff) < precision:
                return sigma

            sigma = sigma - diff / vega
            sigma = max(0.01, min(5.0, sigma))  # Bound sigma

        # Fallback to Brent's method
        try:
            def objective(vol):
                return BlackScholes.price(S, K, T, r, vol, option_type) - price

            return brentq(objective, 0.01, 5.0, xtol=precision)
        except (ValueError, RuntimeError):
            return sigma


# =============================================================================
# GAMMA EXPOSURE (GEX)
# =============================================================================

class GammaExposure:
    """
    Gamma Exposure (GEX) Analysis.

    GEX measures market maker gamma hedging activity.
    High positive GEX = market tends to mean-revert (dealers sell highs, buy lows)
    High negative GEX = market tends to trend (dealers amplify moves)
    """

    def __init__(self, spot_price: float, risk_free_rate: float = 0.05):
        self.spot_price = spot_price
        self.risk_free_rate = risk_free_rate

    def calculate_contract_gex(
        self,
        contract: OptionContract,
        spot_price: float = None,
    ) -> float:
        """
        Calculate GEX for a single contract.

        GEX = Gamma × Open Interest × 100 × Spot Price²
        """
        S = spot_price or self.spot_price
        T = contract.time_to_expiry
        K = contract.strike
        sigma = contract.implied_volatility or 0.3

        gamma = BlackScholes.gamma(S, K, T, self.risk_free_rate, sigma)

        # GEX formula (scaled to dollar value per 1% move)
        gex = gamma * contract.open_interest * 100 * S * S * 0.01

        # Flip sign for puts (dealers are short puts = long gamma)
        # Actually, convention varies - this is one common approach
        if contract.option_type == OptionType.PUT:
            gex = -gex

        return gex

    def calculate_chain_gex(self, chain: OptionsChain) -> Dict[str, Any]:
        """
        Calculate total GEX across an options chain.
        """
        total_gex = 0.0
        gex_by_strike: Dict[float, float] = {}
        gex_by_expiry: Dict[date, float] = {}

        all_contracts = chain.calls + chain.puts

        for contract in all_contracts:
            gex = self.calculate_contract_gex(contract, chain.spot_price)
            total_gex += gex

            # By strike
            if contract.strike not in gex_by_strike:
                gex_by_strike[contract.strike] = 0.0
            gex_by_strike[contract.strike] += gex

            # By expiry
            if contract.expiry not in gex_by_expiry:
                gex_by_expiry[contract.expiry] = 0.0
            gex_by_expiry[contract.expiry] += gex

        # Find key levels
        sorted_strikes = sorted(gex_by_strike.items(), key=lambda x: abs(x[1]), reverse=True)
        key_levels = [s[0] for s in sorted_strikes[:5]]

        # Find GEX flip point (where GEX changes sign)
        flip_point = self._find_gex_flip(gex_by_strike, chain.spot_price)

        return {
            'total_gex': total_gex,
            'gex_by_strike': dict(sorted(gex_by_strike.items())),
            'gex_by_expiry': {k.isoformat(): v for k, v in sorted(gex_by_expiry.items())},
            'key_levels': key_levels,
            'flip_point': flip_point,
            'regime': 'positive' if total_gex > 0 else 'negative',
            'spot_price': chain.spot_price,
        }

    def _find_gex_flip(self, gex_by_strike: Dict[float, float], spot: float) -> Optional[float]:
        """Find the strike where GEX flips from positive to negative."""
        sorted_strikes = sorted(gex_by_strike.keys())

        for i in range(len(sorted_strikes) - 1):
            s1, s2 = sorted_strikes[i], sorted_strikes[i + 1]
            g1, g2 = gex_by_strike[s1], gex_by_strike[s2]

            if g1 * g2 < 0:  # Sign change
                # Linear interpolation
                if g2 - g1 != 0:
                    flip = s1 - g1 * (s2 - s1) / (g2 - g1)
                    return flip

        return None

    def predict_support_resistance(self, chain: OptionsChain) -> Dict[str, List[float]]:
        """
        Predict support/resistance levels based on GEX.

        High positive GEX strikes act as magnets (mean reversion targets).
        High negative GEX strikes may amplify moves.
        """
        gex_result = self.calculate_chain_gex(chain)
        gex_by_strike = gex_result['gex_by_strike']

        # Positive GEX = support/resistance (price gravitates)
        # Negative GEX = acceleration zones

        supports = []
        resistances = []

        for strike, gex in gex_by_strike.items():
            if gex > 0:
                if strike < chain.spot_price:
                    supports.append(strike)
                else:
                    resistances.append(strike)

        # Sort by distance from spot
        supports = sorted(supports, key=lambda x: chain.spot_price - x)[:3]
        resistances = sorted(resistances, key=lambda x: x - chain.spot_price)[:3]

        return {
            'supports': supports,
            'resistances': resistances,
            'key_levels': gex_result['key_levels'],
            'total_gex': gex_result['total_gex'],
        }


# =============================================================================
# OPTIONS ANALYZER
# =============================================================================

class OptionsAnalyzer:
    """
    Comprehensive options analysis.

    Includes:
    - Greeks calculation
    - GEX analysis
    - Put/Call ratio
    - IV percentile/rank
    - Options flow
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
        self.gex_analyzer = None

    def analyze_contract(
        self,
        contract: OptionContract,
        spot_price: float,
    ) -> Dict[str, Any]:
        """Comprehensive single contract analysis."""
        T = contract.time_to_expiry
        K = contract.strike
        sigma = contract.implied_volatility or 0.3

        # Calculate IV if not provided
        if contract.implied_volatility <= 0 and contract.mid_price > 0:
            sigma = BlackScholes.implied_volatility(
                contract.mid_price, spot_price, K, T,
                self.risk_free_rate, contract.option_type
            )

        # Calculate Greeks
        greeks = BlackScholes.calculate_greeks(
            spot_price, K, T, self.risk_free_rate, sigma, contract.option_type
        )

        # Theoretical price
        theo_price = BlackScholes.price(
            spot_price, K, T, self.risk_free_rate, sigma, contract.option_type
        )

        # Moneyness
        if contract.option_type == OptionType.CALL:
            moneyness = spot_price / K
            itm = spot_price > K
        else:
            moneyness = K / spot_price
            itm = spot_price < K

        return {
            'contract': {
                'symbol': contract.symbol,
                'strike': K,
                'expiry': contract.expiry.isoformat(),
                'type': contract.option_type.value,
                'days_to_expiry': contract.days_to_expiry,
            },
            'pricing': {
                'bid': contract.bid,
                'ask': contract.ask,
                'mid': contract.mid_price,
                'theoretical': theo_price,
                'edge': contract.mid_price - theo_price,
            },
            'greeks': {
                'delta': greeks.delta,
                'gamma': greeks.gamma,
                'theta': greeks.theta,
                'vega': greeks.vega,
                'rho': greeks.rho,
            },
            'volatility': {
                'implied_vol': sigma,
                'implied_vol_pct': sigma * 100,
            },
            'characteristics': {
                'moneyness': moneyness,
                'in_the_money': itm,
                'intrinsic': max(0, spot_price - K) if contract.option_type == OptionType.CALL else max(0, K - spot_price),
                'extrinsic': max(0, contract.mid_price - (max(0, spot_price - K) if contract.option_type == OptionType.CALL else max(0, K - spot_price))),
            },
            'flow': {
                'volume': contract.volume,
                'open_interest': contract.open_interest,
                'volume_oi_ratio': contract.volume / contract.open_interest if contract.open_interest > 0 else 0,
            },
        }

    def analyze_chain(self, chain: OptionsChain) -> Dict[str, Any]:
        """Comprehensive chain analysis."""
        self.gex_analyzer = GammaExposure(chain.spot_price, self.risk_free_rate)

        # Calculate GEX
        gex_analysis = self.gex_analyzer.calculate_chain_gex(chain)

        # Put/Call ratios
        total_call_volume = sum(c.volume for c in chain.calls)
        total_put_volume = sum(p.volume for p in chain.puts)
        total_call_oi = sum(c.open_interest for c in chain.calls)
        total_put_oi = sum(p.open_interest for p in chain.puts)

        pc_volume_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 0
        pc_oi_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0

        # IV analysis
        call_ivs = [c.implied_volatility for c in chain.calls if c.implied_volatility > 0]
        put_ivs = [p.implied_volatility for p in chain.puts if p.implied_volatility > 0]
        all_ivs = call_ivs + put_ivs

        avg_iv = np.mean(all_ivs) if all_ivs else 0
        iv_skew = np.mean(put_ivs) - np.mean(call_ivs) if call_ivs and put_ivs else 0

        # ATM contracts
        atm_strike = min(chain.strikes, key=lambda x: abs(x - chain.spot_price)) if chain.strikes else chain.spot_price
        atm_calls = [c for c in chain.calls if c.strike == atm_strike]
        atm_puts = [p for p in chain.puts if p.strike == atm_strike]
        atm_iv = (atm_calls[0].implied_volatility if atm_calls else avg_iv)

        # Support/resistance from GEX
        levels = self.gex_analyzer.predict_support_resistance(chain)

        return {
            'underlying': chain.underlying,
            'spot_price': chain.spot_price,
            'chain_date': chain.chain_date.isoformat(),

            'volume': {
                'total_call_volume': total_call_volume,
                'total_put_volume': total_put_volume,
                'put_call_volume_ratio': pc_volume_ratio,
            },

            'open_interest': {
                'total_call_oi': total_call_oi,
                'total_put_oi': total_put_oi,
                'put_call_oi_ratio': pc_oi_ratio,
            },

            'volatility': {
                'average_iv': avg_iv,
                'atm_iv': atm_iv,
                'iv_skew': iv_skew,
                'iv_percentile': None,  # Would need historical data
            },

            'gex': gex_analysis,

            'levels': levels,

            'market_sentiment': self._interpret_sentiment(pc_volume_ratio, pc_oi_ratio, iv_skew, gex_analysis['total_gex']),

            'expiries': [e.isoformat() for e in chain.expiries],
            'strikes': chain.strikes,
            'num_contracts': len(chain.calls) + len(chain.puts),
        }

    def _interpret_sentiment(
        self,
        pc_volume: float,
        pc_oi: float,
        iv_skew: float,
        total_gex: float,
    ) -> Dict[str, Any]:
        """Interpret market sentiment from options data."""
        signals = []

        # Put/Call ratio interpretation
        if pc_volume > 1.2:
            signals.append(('bearish', 'High put/call volume ratio'))
        elif pc_volume < 0.7:
            signals.append(('bullish', 'Low put/call volume ratio'))

        if pc_oi > 1.3:
            signals.append(('bearish', 'High put/call OI ratio'))
        elif pc_oi < 0.6:
            signals.append(('bullish', 'Low put/call OI ratio'))

        # IV skew interpretation
        if iv_skew > 0.05:
            signals.append(('bearish', 'Elevated put IV (fear)'))
        elif iv_skew < -0.03:
            signals.append(('bullish', 'Elevated call IV (speculation)'))

        # GEX interpretation
        if total_gex > 0:
            signals.append(('neutral', 'Positive GEX (mean reversion likely)'))
        else:
            signals.append(('volatile', 'Negative GEX (trending likely)'))

        # Overall sentiment
        bullish_count = sum(1 for s in signals if s[0] == 'bullish')
        bearish_count = sum(1 for s in signals if s[0] == 'bearish')

        if bullish_count > bearish_count:
            overall = 'bullish'
        elif bearish_count > bullish_count:
            overall = 'bearish'
        else:
            overall = 'neutral'

        return {
            'overall': overall,
            'signals': signals,
            'bullish_signals': bullish_count,
            'bearish_signals': bearish_count,
            'confidence': abs(bullish_count - bearish_count) / max(1, len(signals)),
        }

    def calculate_expected_move(
        self,
        spot_price: float,
        atm_straddle_price: float,
        days_to_expiry: int,
    ) -> Dict[str, float]:
        """
        Calculate expected move from ATM straddle price.

        The ATM straddle price approximates the expected move.
        """
        # Expected move is approximately 85% of straddle price
        expected_move = atm_straddle_price * 0.85

        expected_move_pct = expected_move / spot_price

        # Annualized expected move
        annual_factor = np.sqrt(365 / max(1, days_to_expiry))
        annualized_move = expected_move_pct * annual_factor

        return {
            'expected_move_dollars': expected_move,
            'expected_move_pct': expected_move_pct * 100,
            'upper_bound': spot_price + expected_move,
            'lower_bound': spot_price - expected_move,
            'implied_volatility_approx': annualized_move,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OptionType',
    'OptionContract',
    'OptionGreeks',
    'OptionsChain',
    'BlackScholes',
    'GammaExposure',
    'OptionsAnalyzer',
]
