"""
QUANT_INDUSTRY_V1 Validation Utilities

Provides validation functions for common data types.
"""

import re
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np


# Valid timeframes
VALID_TIMEFRAMES = {'1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'}

# Symbol pattern (US stocks)
SYMBOL_PATTERN = re.compile(r'^[A-Z]{1,5}$')


def validate_symbol(symbol: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a trading symbol.

    Args:
        symbol: Symbol to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not symbol:
        return False, "Symbol cannot be empty"

    if not isinstance(symbol, str):
        return False, f"Symbol must be string, got {type(symbol)}"

    symbol = symbol.upper().strip()

    if not SYMBOL_PATTERN.match(symbol):
        return False, f"Invalid symbol format: {symbol}"

    return True, None


def validate_timeframe(timeframe: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a timeframe string.

    Args:
        timeframe: Timeframe to validate (e.g., '1d', '1h')

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not timeframe:
        return False, "Timeframe cannot be empty"

    if timeframe not in VALID_TIMEFRAMES:
        return False, f"Invalid timeframe: {timeframe}. Valid: {VALID_TIMEFRAMES}"

    return True, None


def validate_ohlc(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate OHLC data integrity.

    Checks:
    - Required columns exist
    - High >= Low
    - Open/Close within High-Low range
    - No negative prices
    - Volume >= 0

    Args:
        df: DataFrame with OHLC data

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required columns
    required = {'open', 'high', 'low', 'close', 'volume'}
    available = set(df.columns.str.lower())
    missing = required - available
    if missing:
        errors.append(f"Missing columns: {missing}")
        return False, errors

    # Normalize column names
    df = df.rename(columns={c: c.lower() for c in df.columns})

    # Check High >= Low
    bad_hl = df[df['high'] < df['low']]
    if len(bad_hl) > 0:
        errors.append(f"{len(bad_hl)} rows with High < Low")

    # Check Open within range
    bad_open = df[(df['open'] > df['high']) | (df['open'] < df['low'])]
    if len(bad_open) > 0:
        errors.append(f"{len(bad_open)} rows with Open outside High-Low range")

    # Check Close within range
    bad_close = df[(df['close'] > df['high']) | (df['close'] < df['low'])]
    if len(bad_close) > 0:
        errors.append(f"{len(bad_close)} rows with Close outside High-Low range")

    # Check for negative prices
    neg_price = df[(df['open'] < 0) | (df['high'] < 0) | (df['low'] < 0) | (df['close'] < 0)]
    if len(neg_price) > 0:
        errors.append(f"{len(neg_price)} rows with negative prices")

    # Check for negative volume
    neg_vol = df[df['volume'] < 0]
    if len(neg_vol) > 0:
        errors.append(f"{len(neg_vol)} rows with negative volume")

    return len(errors) == 0, errors


def validate_features(
    features: dict,
    expected_names: List[str],
    allow_nan: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate feature dictionary.

    Args:
        features: Dictionary of feature name -> value
        expected_names: List of expected feature names
        allow_nan: Whether to allow NaN values

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check for missing features
    missing = set(expected_names) - set(features.keys())
    if missing:
        errors.append(f"Missing features: {missing}")

    # Check for unexpected features
    extra = set(features.keys()) - set(expected_names)
    if extra:
        errors.append(f"Unexpected features: {extra}")

    # Check for NaN/Inf values
    for name, value in features.items():
        if value is None:
            errors.append(f"Feature {name} is None")
        elif isinstance(value, float):
            if np.isnan(value) and not allow_nan:
                errors.append(f"Feature {name} is NaN")
            elif np.isinf(value):
                errors.append(f"Feature {name} is Inf")

    return len(errors) == 0, errors


def validate_signal(
    direction: str,
    strength: float,
    confidence: float
) -> Tuple[bool, List[str]]:
    """
    Validate signal parameters.

    Args:
        direction: Signal direction ('long', 'short', 'flat')
        strength: Signal strength (-1 to 1)
        confidence: Signal confidence (0 to 1)

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Validate direction
    valid_directions = {'long', 'short', 'flat'}
    if direction not in valid_directions:
        errors.append(f"Invalid direction: {direction}. Valid: {valid_directions}")

    # Validate strength
    if not -1.0 <= strength <= 1.0:
        errors.append(f"Strength must be in [-1, 1], got {strength}")

    # Validate confidence
    if not 0.0 <= confidence <= 1.0:
        errors.append(f"Confidence must be in [0, 1], got {confidence}")

    return len(errors) == 0, errors


def validate_position_size(
    size: float,
    max_size: float,
    account_equity: float,
    max_pct: float = 0.25
) -> Tuple[bool, List[str], float]:
    """
    Validate and adjust position size.

    Args:
        size: Proposed position size (dollars or shares * price)
        max_size: Maximum allowed size
        account_equity: Current account equity
        max_pct: Maximum percentage of equity (default 25%)

    Returns:
        Tuple of (is_valid, warnings, adjusted_size)
    """
    warnings = []
    adjusted = size

    # Check against max_size
    if size > max_size:
        warnings.append(f"Size {size} exceeds max {max_size}, adjusted")
        adjusted = max_size

    # Check against max percentage
    max_by_pct = account_equity * max_pct
    if adjusted > max_by_pct:
        warnings.append(f"Size {adjusted} exceeds {max_pct*100}% of equity, adjusted")
        adjusted = max_by_pct

    # Check for zero/negative
    if adjusted <= 0:
        return False, ["Position size must be positive"], 0.0

    return True, warnings, adjusted
