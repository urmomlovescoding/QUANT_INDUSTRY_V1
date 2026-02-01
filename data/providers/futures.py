"""
Futures Data Provider - Futures and Derivatives Data Access

This module provides data access for futures contracts across
multiple exchanges and asset classes.

Key Features:
- Multi-exchange futures data
- Contract specifications
- Roll calendar management
- Continuous futures construction
- Open interest and volume data

Usage:
    from data.providers.futures import FuturesProvider

    provider = FuturesProvider()
    data = await provider.get_futures_data('ES', expiry='2024-03')
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


class Exchange(Enum):
    """Futures exchanges."""
    CME = "CME"
    CBOT = "CBOT"
    NYMEX = "NYMEX"
    COMEX = "COMEX"
    ICE = "ICE"
    EUREX = "EUREX"


class AssetClass(Enum):
    """Futures asset classes."""
    EQUITY_INDEX = "equity_index"
    INTEREST_RATE = "interest_rate"
    FX = "fx"
    ENERGY = "energy"
    METALS = "metals"
    AGRICULTURE = "agriculture"


@dataclass
class ContractSpec:
    """Futures contract specification."""
    symbol: str
    exchange: Exchange
    asset_class: AssetClass
    tick_size: float
    point_value: float
    currency: str
    trading_hours: str
    last_trading_day_rule: str
    delivery_months: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange': self.exchange.value,
            'asset_class': self.asset_class.value,
            'tick_size': self.tick_size,
            'point_value': self.point_value,
            'currency': self.currency,
            'trading_hours': self.trading_hours,
            'last_trading_day_rule': self.last_trading_day_rule,
            'delivery_months': self.delivery_months,
        }


@dataclass
class FuturesContract:
    """Individual futures contract."""
    root_symbol: str
    expiry: date
    full_symbol: str
    spec: ContractSpec
    last_trade_date: date
    first_notice_date: Optional[date] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'root_symbol': self.root_symbol,
            'expiry': self.expiry.isoformat(),
            'full_symbol': self.full_symbol,
            'last_trade_date': self.last_trade_date.isoformat(),
            'first_notice_date': self.first_notice_date.isoformat() if self.first_notice_date else None,
        }


@dataclass
class FuturesData:
    """Futures market data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int
    settlement: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'open_interest': self.open_interest,
            'settlement': self.settlement,
        }


# Contract specifications database
CONTRACT_SPECS = {
    'ES': ContractSpec(
        symbol='ES',
        exchange=Exchange.CME,
        asset_class=AssetClass.EQUITY_INDEX,
        tick_size=0.25,
        point_value=50.0,
        currency='USD',
        trading_hours='17:00-16:00 CT',
        last_trading_day_rule='Third Friday of contract month',
        delivery_months=['H', 'M', 'U', 'Z'],
    ),
    'NQ': ContractSpec(
        symbol='NQ',
        exchange=Exchange.CME,
        asset_class=AssetClass.EQUITY_INDEX,
        tick_size=0.25,
        point_value=20.0,
        currency='USD',
        trading_hours='17:00-16:00 CT',
        last_trading_day_rule='Third Friday of contract month',
        delivery_months=['H', 'M', 'U', 'Z'],
    ),
    'CL': ContractSpec(
        symbol='CL',
        exchange=Exchange.NYMEX,
        asset_class=AssetClass.ENERGY,
        tick_size=0.01,
        point_value=1000.0,
        currency='USD',
        trading_hours='18:00-17:00 ET',
        last_trading_day_rule='Third business day before 25th of month',
        delivery_months=['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'],
    ),
    'GC': ContractSpec(
        symbol='GC',
        exchange=Exchange.COMEX,
        asset_class=AssetClass.METALS,
        tick_size=0.10,
        point_value=100.0,
        currency='USD',
        trading_hours='18:00-17:00 ET',
        last_trading_day_rule='Third to last business day of contract month',
        delivery_months=['G', 'J', 'M', 'Q', 'V', 'Z'],
    ),
    'ZN': ContractSpec(
        symbol='ZN',
        exchange=Exchange.CBOT,
        asset_class=AssetClass.INTEREST_RATE,
        tick_size=1/64,
        point_value=1000.0,
        currency='USD',
        trading_hours='17:00-16:00 CT',
        last_trading_day_rule='Seventh business day before last business day',
        delivery_months=['H', 'M', 'U', 'Z'],
    ),
    'ZC': ContractSpec(
        symbol='ZC',
        exchange=Exchange.CBOT,
        asset_class=AssetClass.AGRICULTURE,
        tick_size=0.25,
        point_value=50.0,
        currency='USD',
        trading_hours='19:00-13:20 CT',
        last_trading_day_rule='Business day before 15th of contract month',
        delivery_months=['H', 'K', 'N', 'U', 'Z'],
    ),
}


class FuturesProvider:
    """
    Provider for futures market data.

    Supports multiple exchanges and asset classes with
    contract roll management and continuous futures.

    Example:
        provider = FuturesProvider()

        # Get specific contract
        data = await provider.get_contract_data('ESH24', days=30)

        # Get continuous futures
        continuous = await provider.get_continuous_futures('ES', days=252)

        # Get roll calendar
        rolls = provider.get_roll_calendar('ES', year=2024)
    """

    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}
        self._contracts: Dict[str, FuturesContract] = {}

        logger.info("FuturesProvider initialized")

    def get_contract_spec(self, root_symbol: str) -> Optional[ContractSpec]:
        """Get contract specification."""
        return CONTRACT_SPECS.get(root_symbol.upper())

    def get_active_contracts(self, root_symbol: str, num_contracts: int = 4) -> List[FuturesContract]:
        """
        Get list of active contracts for a root symbol.

        Args:
            root_symbol: Root symbol (e.g., 'ES')
            num_contracts: Number of front contracts to return

        Returns:
            List of FuturesContract objects
        """
        spec = self.get_contract_spec(root_symbol)
        if not spec:
            return []

        contracts = []
        today = date.today()

        # Generate contract months
        month_codes = {
            'F': 1, 'G': 2, 'H': 3, 'J': 4, 'K': 5, 'M': 6,
            'N': 7, 'Q': 8, 'U': 9, 'V': 10, 'X': 11, 'Z': 12
        }

        # Find delivery months
        delivery_months = []
        for code in spec.delivery_months:
            month = month_codes[code]
            for year in range(today.year, today.year + 3):
                expiry = date(year, month, 1)
                if expiry >= today:
                    delivery_months.append((expiry, code, year))

        delivery_months.sort()

        for expiry, code, year in delivery_months[:num_contracts]:
            # Calculate last trade date (simplified - third Friday)
            import calendar
            c = calendar.Calendar(firstweekday=calendar.MONDAY)
            monthcal = c.monthdatescalendar(year, expiry.month)
            fridays = [d for week in monthcal for d in week
                      if d.weekday() == calendar.FRIDAY and d.month == expiry.month]
            last_trade = fridays[2] if len(fridays) >= 3 else expiry

            year_code = str(year)[-2:]
            full_symbol = f"{root_symbol}{code}{year_code}"

            contract = FuturesContract(
                root_symbol=root_symbol,
                expiry=expiry,
                full_symbol=full_symbol,
                spec=spec,
                last_trade_date=last_trade,
            )
            contracts.append(contract)

        return contracts

    async def get_contract_data(
        self,
        symbol: str,
        days: int = 30,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Get historical data for a specific contract.

        Args:
            symbol: Full contract symbol (e.g., 'ESH24')
            days: Number of days of history
            end_date: End date (defaults to today)

        Returns:
            DataFrame with OHLCV data
        """
        # Check cache
        cache_key = f"{symbol}_{days}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # In production, would call actual data provider
        # For now, generate synthetic data
        end_date = end_date or date.today()
        dates = pd.date_range(end=end_date, periods=days, freq='B')

        # Get spec for realistic price levels
        root_symbol = symbol[:2]
        spec = self.get_contract_spec(root_symbol)

        if spec and spec.asset_class == AssetClass.EQUITY_INDEX:
            base_price = 4500
            volatility = 0.01
        elif spec and spec.asset_class == AssetClass.ENERGY:
            base_price = 75
            volatility = 0.02
        elif spec and spec.asset_class == AssetClass.METALS:
            base_price = 1900
            volatility = 0.01
        else:
            base_price = 100
            volatility = 0.015

        # Generate synthetic data
        np.random.seed(hash(symbol) % 2**32)
        returns = np.random.normal(0.0001, volatility, len(dates))
        prices = base_price * np.exp(np.cumsum(returns))

        data = pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.005, 0.005, len(dates))),
            'high': prices * (1 + np.random.uniform(0, 0.01, len(dates))),
            'low': prices * (1 - np.random.uniform(0, 0.01, len(dates))),
            'close': prices,
            'volume': np.random.randint(10000, 100000, len(dates)),
            'open_interest': np.random.randint(100000, 500000, len(dates)),
        }, index=dates)

        data.index.name = 'date'

        self._cache[cache_key] = data
        return data

    async def get_continuous_futures(
        self,
        root_symbol: str,
        days: int = 252,
        roll_days_before_expiry: int = 5,
        adjustment: str = 'ratio',
    ) -> pd.DataFrame:
        """
        Construct continuous futures series.

        Args:
            root_symbol: Root symbol (e.g., 'ES')
            days: Number of days of history
            roll_days_before_expiry: Days before expiry to roll
            adjustment: 'ratio', 'difference', or 'none'

        Returns:
            DataFrame with continuous futures data
        """
        contracts = self.get_active_contracts(root_symbol, num_contracts=8)

        if not contracts:
            return pd.DataFrame()

        # Get data for all contracts
        all_data = {}
        for contract in contracts:
            data = await self.get_contract_data(contract.full_symbol, days=days)
            all_data[contract.full_symbol] = data

        # Build continuous series
        continuous_data = []
        current_contract_idx = 0
        adjustment_factor = 1.0

        end_date = date.today()
        start_date = end_date - timedelta(days=days * 1.5)

        for single_date in pd.date_range(start=start_date, end=end_date, freq='B'):
            single_date = single_date.date()

            # Check if need to roll
            if current_contract_idx < len(contracts):
                current_contract = contracts[current_contract_idx]
                roll_date = current_contract.last_trade_date - timedelta(days=roll_days_before_expiry)

                if single_date >= roll_date and current_contract_idx < len(contracts) - 1:
                    # Roll to next contract
                    if adjustment == 'ratio':
                        # Get prices on roll day
                        old_data = all_data.get(current_contract.full_symbol)
                        new_contract = contracts[current_contract_idx + 1]
                        new_data = all_data.get(new_contract.full_symbol)

                        if old_data is not None and new_data is not None:
                            # Simplified - use close prices
                            old_price = old_data['close'].iloc[-1] if len(old_data) > 0 else 1
                            new_price = new_data['close'].iloc[-1] if len(new_data) > 0 else 1
                            adjustment_factor *= old_price / new_price

                    current_contract_idx += 1

            # Get data for current date
            current_contract = contracts[min(current_contract_idx, len(contracts) - 1)]
            contract_data = all_data.get(current_contract.full_symbol)

            if contract_data is not None:
                try:
                    day_data = contract_data.loc[pd.Timestamp(single_date)]
                    continuous_data.append({
                        'date': single_date,
                        'open': day_data['open'] * adjustment_factor,
                        'high': day_data['high'] * adjustment_factor,
                        'low': day_data['low'] * adjustment_factor,
                        'close': day_data['close'] * adjustment_factor,
                        'volume': day_data['volume'],
                        'open_interest': day_data['open_interest'],
                        'contract': current_contract.full_symbol,
                    })
                except KeyError:
                    pass

        df = pd.DataFrame(continuous_data)
        if not df.empty:
            df.set_index('date', inplace=True)

        return df

    def get_roll_calendar(
        self,
        root_symbol: str,
        year: int,
        roll_days_before_expiry: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get roll calendar for a year.

        Args:
            root_symbol: Root symbol
            year: Year
            roll_days_before_expiry: Days before expiry to roll

        Returns:
            List of roll dates with contract info
        """
        contracts = self.get_active_contracts(root_symbol, num_contracts=12)

        rolls = []
        for i, contract in enumerate(contracts):
            if contract.expiry.year == year:
                roll_date = contract.last_trade_date - timedelta(days=roll_days_before_expiry)
                next_contract = contracts[i + 1] if i + 1 < len(contracts) else None

                rolls.append({
                    'roll_date': roll_date.isoformat(),
                    'expiring_contract': contract.full_symbol,
                    'new_contract': next_contract.full_symbol if next_contract else None,
                    'last_trade_date': contract.last_trade_date.isoformat(),
                })

        return rolls

    def calculate_basis(
        self,
        front_price: float,
        spot_price: float,
        days_to_expiry: int,
    ) -> Dict[str, float]:
        """
        Calculate futures basis and implied yield.

        Args:
            front_price: Front month futures price
            spot_price: Spot/cash price
            days_to_expiry: Days until expiration

        Returns:
            Dictionary with basis metrics
        """
        basis = front_price - spot_price
        basis_percent = basis / spot_price

        # Annualized implied yield
        if days_to_expiry > 0:
            implied_yield = (basis_percent * 365) / days_to_expiry
        else:
            implied_yield = 0.0

        return {
            'basis': basis,
            'basis_percent': basis_percent,
            'implied_yield': implied_yield,
            'days_to_expiry': days_to_expiry,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            'contracts_loaded': len(self._contracts),
            'cache_size': len(self._cache),
            'supported_symbols': list(CONTRACT_SPECS.keys()),
        }
