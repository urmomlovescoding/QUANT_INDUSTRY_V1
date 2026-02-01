"""
Forex Data Provider - Foreign Exchange Market Data

This module provides FX market data access including spot rates,
forward rates, and cross rates.

Key Features:
- Major and minor currency pairs
- Spot and forward rates
- Cross rate calculation
- Historical data
- Real-time streaming support

Usage:
    from data.providers.forex import ForexProvider

    provider = ForexProvider()
    data = await provider.get_spot_data('EURUSD', days=30)
"""

import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Currency(Enum):
    """Major currencies."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"
    AUD = "AUD"
    CAD = "CAD"
    NZD = "NZD"
    SEK = "SEK"
    NOK = "NOK"
    CNH = "CNH"
    HKD = "HKD"
    SGD = "SGD"


class SessionType(Enum):
    """FX trading sessions."""
    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"


@dataclass
class CurrencyPairInfo:
    """Information about a currency pair."""
    symbol: str
    base: Currency
    quote: Currency
    pip_size: float
    pip_value: float
    min_trade_size: float
    typical_spread_pips: float
    is_major: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'base': self.base.value,
            'quote': self.quote.value,
            'pip_size': self.pip_size,
            'pip_value': self.pip_value,
            'min_trade_size': self.min_trade_size,
            'typical_spread_pips': self.typical_spread_pips,
            'is_major': self.is_major,
        }


@dataclass
class ForexQuote:
    """FX spot quote."""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    mid: float
    spread_pips: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'bid': self.bid,
            'ask': self.ask,
            'mid': self.mid,
            'spread_pips': self.spread_pips,
        }


@dataclass
class ForwardPoints:
    """FX forward points."""
    symbol: str
    tenor: str
    bid_points: float
    ask_points: float
    outright_bid: float
    outright_ask: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'tenor': self.tenor,
            'bid_points': self.bid_points,
            'ask_points': self.ask_points,
            'outright_bid': self.outright_bid,
            'outright_ask': self.outright_ask,
        }


# Currency pair specifications
PAIR_SPECS = {
    'EURUSD': CurrencyPairInfo('EURUSD', Currency.EUR, Currency.USD, 0.0001, 10.0, 1000, 0.5, True),
    'GBPUSD': CurrencyPairInfo('GBPUSD', Currency.GBP, Currency.USD, 0.0001, 10.0, 1000, 0.8, True),
    'USDJPY': CurrencyPairInfo('USDJPY', Currency.USD, Currency.JPY, 0.01, 1000/100, 1000, 0.5, True),
    'USDCHF': CurrencyPairInfo('USDCHF', Currency.USD, Currency.CHF, 0.0001, 10.0, 1000, 0.8, True),
    'AUDUSD': CurrencyPairInfo('AUDUSD', Currency.AUD, Currency.USD, 0.0001, 10.0, 1000, 0.6, True),
    'USDCAD': CurrencyPairInfo('USDCAD', Currency.USD, Currency.CAD, 0.0001, 10.0, 1000, 0.8, True),
    'NZDUSD': CurrencyPairInfo('NZDUSD', Currency.NZD, Currency.USD, 0.0001, 10.0, 1000, 1.0, True),
    'EURGBP': CurrencyPairInfo('EURGBP', Currency.EUR, Currency.GBP, 0.0001, 10.0, 1000, 0.8, False),
    'EURJPY': CurrencyPairInfo('EURJPY', Currency.EUR, Currency.JPY, 0.01, 1000/100, 1000, 1.0, False),
    'GBPJPY': CurrencyPairInfo('GBPJPY', Currency.GBP, Currency.JPY, 0.01, 1000/100, 1000, 1.5, False),
    'AUDJPY': CurrencyPairInfo('AUDJPY', Currency.AUD, Currency.JPY, 0.01, 1000/100, 1000, 1.2, False),
    'EURAUD': CurrencyPairInfo('EURAUD', Currency.EUR, Currency.AUD, 0.0001, 10.0, 1000, 1.5, False),
}

# Base rates for synthetic data
BASE_RATES = {
    'EURUSD': 1.0850,
    'GBPUSD': 1.2650,
    'USDJPY': 150.50,
    'USDCHF': 0.8850,
    'AUDUSD': 0.6550,
    'USDCAD': 1.3550,
    'NZDUSD': 0.6050,
}


class ForexProvider:
    """
    Provider for foreign exchange market data.

    Supports major and minor pairs with spot, forward,
    and historical data.

    Example:
        provider = ForexProvider()

        # Get spot quote
        quote = await provider.get_spot_quote('EURUSD')

        # Get historical data
        data = await provider.get_spot_data('EURUSD', days=30)

        # Calculate cross rate
        cross = provider.calculate_cross_rate('EURGBP')

        # Get forward points
        forwards = await provider.get_forward_points('EURUSD')
    """

    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}
        self._latest_quotes: Dict[str, ForexQuote] = {}

        logger.info("ForexProvider initialized")

    def get_pair_info(self, symbol: str) -> Optional[CurrencyPairInfo]:
        """Get currency pair information."""
        return PAIR_SPECS.get(symbol.upper())

    def get_all_pairs(self, majors_only: bool = False) -> List[str]:
        """Get list of supported currency pairs."""
        if majors_only:
            return [s for s, info in PAIR_SPECS.items() if info.is_major]
        return list(PAIR_SPECS.keys())

    async def get_spot_quote(self, symbol: str) -> Optional[ForexQuote]:
        """
        Get current spot quote.

        Args:
            symbol: Currency pair symbol

        Returns:
            ForexQuote with bid/ask
        """
        info = self.get_pair_info(symbol)
        if not info:
            return None

        # Get base rate (in production would call real provider)
        base_rate = BASE_RATES.get(symbol)
        if not base_rate:
            # Try to calculate cross rate
            base_rate = self._calculate_synthetic_rate(symbol)

        if not base_rate:
            return None

        # Add realistic spread
        half_spread = info.typical_spread_pips * info.pip_size / 2

        quote = ForexQuote(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            bid=base_rate - half_spread,
            ask=base_rate + half_spread,
            mid=base_rate,
            spread_pips=info.typical_spread_pips,
        )

        self._latest_quotes[symbol] = quote
        return quote

    def _calculate_synthetic_rate(self, symbol: str) -> Optional[float]:
        """Calculate synthetic rate for crosses."""
        # Common cross calculations
        if symbol == 'EURGBP':
            eurusd = BASE_RATES.get('EURUSD', 1.0)
            gbpusd = BASE_RATES.get('GBPUSD', 1.0)
            return eurusd / gbpusd
        elif symbol == 'EURJPY':
            eurusd = BASE_RATES.get('EURUSD', 1.0)
            usdjpy = BASE_RATES.get('USDJPY', 100.0)
            return eurusd * usdjpy
        elif symbol == 'GBPJPY':
            gbpusd = BASE_RATES.get('GBPUSD', 1.0)
            usdjpy = BASE_RATES.get('USDJPY', 100.0)
            return gbpusd * usdjpy
        elif symbol == 'AUDJPY':
            audusd = BASE_RATES.get('AUDUSD', 1.0)
            usdjpy = BASE_RATES.get('USDJPY', 100.0)
            return audusd * usdjpy
        elif symbol == 'EURAUD':
            eurusd = BASE_RATES.get('EURUSD', 1.0)
            audusd = BASE_RATES.get('AUDUSD', 1.0)
            return eurusd / audusd

        return None

    async def get_spot_data(
        self,
        symbol: str,
        days: int = 30,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Get historical spot data.

        Args:
            symbol: Currency pair symbol
            days: Number of days of history
            end_date: End date (defaults to today)

        Returns:
            DataFrame with OHLC data
        """
        cache_key = f"{symbol}_{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        info = self.get_pair_info(symbol)
        base_rate = BASE_RATES.get(symbol) or self._calculate_synthetic_rate(symbol) or 1.0

        end_date = end_date or date.today()
        # FX trades 24/5, so use all weekdays
        dates = pd.date_range(end=end_date, periods=days, freq='B')

        # Generate synthetic data
        np.random.seed(hash(symbol) % 2**32)

        # Daily volatility varies by pair
        if 'JPY' in symbol:
            daily_vol = 0.005
        else:
            daily_vol = 0.004

        returns = np.random.normal(0, daily_vol, len(dates))
        prices = base_rate * np.exp(np.cumsum(returns))

        # Intraday range
        daily_range = np.random.uniform(0.003, 0.008, len(dates))

        data = pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.001, 0.001, len(dates))),
            'high': prices * (1 + daily_range / 2),
            'low': prices * (1 - daily_range / 2),
            'close': prices,
            'volume': np.random.randint(100000, 1000000, len(dates)),  # Tick volume proxy
        }, index=dates)

        data.index.name = 'date'

        self._cache[cache_key] = data
        return data

    async def get_forward_points(
        self,
        symbol: str,
        tenors: Optional[List[str]] = None,
    ) -> List[ForwardPoints]:
        """
        Get forward points for various tenors.

        Args:
            symbol: Currency pair symbol
            tenors: List of tenors (default: standard tenors)

        Returns:
            List of ForwardPoints
        """
        if tenors is None:
            tenors = ['1W', '2W', '1M', '2M', '3M', '6M', '9M', '1Y']

        quote = await self.get_spot_quote(symbol)
        if not quote:
            return []

        forwards = []

        # Simplified forward points calculation
        # In production would use actual interest rate differentials
        for tenor in tenors:
            # Parse tenor to days
            if tenor.endswith('W'):
                days = int(tenor[:-1]) * 7
            elif tenor.endswith('M'):
                days = int(tenor[:-1]) * 30
            elif tenor.endswith('Y'):
                days = int(tenor[:-1]) * 365
            else:
                days = 30

            # Synthetic forward points based on rate differential proxy
            # Positive = base currency has lower rates
            rate_diff = 0.02  # 2% annual rate differential
            forward_points = quote.mid * rate_diff * (days / 365)

            if 'JPY' in symbol:
                # Points in pips for JPY pairs
                forward_points *= 100

            forwards.append(ForwardPoints(
                symbol=symbol,
                tenor=tenor,
                bid_points=forward_points - 0.5,
                ask_points=forward_points + 0.5,
                outright_bid=quote.bid + (forward_points - 0.5) / 10000,
                outright_ask=quote.ask + (forward_points + 0.5) / 10000,
            ))

        return forwards

    def calculate_cross_rate(
        self,
        target_pair: str,
        leg1_quote: Optional[ForexQuote] = None,
        leg2_quote: Optional[ForexQuote] = None,
    ) -> Optional[ForexQuote]:
        """
        Calculate cross rate from two legs.

        Args:
            target_pair: Target cross pair
            leg1_quote: First leg quote (optional)
            leg2_quote: Second leg quote (optional)

        Returns:
            Calculated ForexQuote
        """
        info = self.get_pair_info(target_pair)
        if not info:
            return None

        base = info.base.value
        quote_ccy = info.quote.value

        # Determine legs needed
        # Example: EURGBP = EURUSD / GBPUSD
        if base + 'USD' in PAIR_SPECS and quote_ccy + 'USD' in PAIR_SPECS:
            # Both vs USD
            leg1 = self._latest_quotes.get(base + 'USD')
            leg2 = self._latest_quotes.get(quote_ccy + 'USD')

            if leg1 and leg2:
                cross_mid = leg1.mid / leg2.mid
                spread = info.typical_spread_pips * info.pip_size

                return ForexQuote(
                    symbol=target_pair,
                    timestamp=datetime.now(timezone.utc),
                    bid=cross_mid - spread / 2,
                    ask=cross_mid + spread / 2,
                    mid=cross_mid,
                    spread_pips=info.typical_spread_pips,
                )

        return None

    def convert_amount(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Convert amount between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency
            to_currency: Target currency
            rate: Optional rate to use

        Returns:
            Dictionary with conversion details
        """
        if from_currency == to_currency:
            return {
                'original_amount': amount,
                'converted_amount': amount,
                'rate': 1.0,
                'pair': f"{from_currency}{to_currency}",
            }

        # Find rate
        pair = f"{from_currency}{to_currency}"
        inverse_pair = f"{to_currency}{from_currency}"

        if rate is None:
            if pair in BASE_RATES:
                rate = BASE_RATES[pair]
            elif inverse_pair in BASE_RATES:
                rate = 1.0 / BASE_RATES[inverse_pair]
            elif pair in self._latest_quotes:
                rate = self._latest_quotes[pair].mid
            elif inverse_pair in self._latest_quotes:
                rate = 1.0 / self._latest_quotes[inverse_pair].mid
            else:
                # Try synthetic
                rate = self._calculate_synthetic_rate(pair)
                if not rate:
                    inverse_rate = self._calculate_synthetic_rate(inverse_pair)
                    rate = 1.0 / inverse_rate if inverse_rate else None

        if rate is None:
            return {'error': f'No rate available for {pair}'}

        return {
            'original_amount': amount,
            'converted_amount': amount * rate,
            'rate': rate,
            'pair': pair,
        }

    def get_session_info(self) -> Dict[str, Any]:
        """Get current trading session information."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        sessions = {
            'sydney': (21, 6),    # 21:00 - 06:00 UTC
            'tokyo': (0, 9),       # 00:00 - 09:00 UTC
            'london': (7, 16),     # 07:00 - 16:00 UTC
            'new_york': (12, 21),  # 12:00 - 21:00 UTC
        }

        active_sessions = []
        for session, (start, end) in sessions.items():
            if start < end:
                if start <= hour < end:
                    active_sessions.append(session)
            else:  # Crosses midnight
                if hour >= start or hour < end:
                    active_sessions.append(session)

        return {
            'current_time_utc': now.isoformat(),
            'active_sessions': active_sessions,
            'market_open': len(active_sessions) > 0,
            'highest_liquidity': 'london' in active_sessions and 'new_york' in active_sessions,
        }

    def calculate_pip_value(
        self,
        symbol: str,
        lot_size: float = 100000,
        account_currency: str = 'USD',
    ) -> Optional[float]:
        """
        Calculate pip value for a position.

        Args:
            symbol: Currency pair
            lot_size: Position size
            account_currency: Account currency

        Returns:
            Pip value in account currency
        """
        info = self.get_pair_info(symbol)
        if not info:
            return None

        # Base pip value
        pip_value = lot_size * info.pip_size

        # Convert to account currency if needed
        quote_ccy = info.quote.value

        if quote_ccy == account_currency:
            return pip_value
        else:
            # Need to convert
            conversion = self.convert_amount(pip_value, quote_ccy, account_currency)
            return conversion.get('converted_amount')

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            'pairs_available': len(PAIR_SPECS),
            'cache_size': len(self._cache),
            'latest_quotes': len(self._latest_quotes),
            'session_info': self.get_session_info(),
        }
