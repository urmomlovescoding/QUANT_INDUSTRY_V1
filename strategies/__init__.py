"""
Trading Strategies Package
==========================
Quantitative trading strategies for backtesting and live trading.
"""

from .base import (
    BaseStrategy,
    Signal,
    SignalType,
    StrategyConfig,
    # Technical indicators
    sma, ema, rsi, macd, bollinger_bands, atr,
    zscore, returns, log_returns, volatility,
    drawdown, sharpe_ratio
)

from .momentum import (
    MomentumStrategy,
    DualMomentumStrategy,
    RSIMomentumStrategy,
    MACDMomentumStrategy,
)

from .mean_reversion import (
    BollingerMeanReversion,
    ZScoreMeanReversion,
    RSIMeanReversion,
    PairsTrading,
)

# Strategy registry for easy lookup
STRATEGY_REGISTRY = {
    # Momentum strategies
    'momentum': MomentumStrategy,
    'dual_momentum': DualMomentumStrategy,
    'rsi_momentum': RSIMomentumStrategy,
    'macd_momentum': MACDMomentumStrategy,
    
    # Mean reversion strategies
    'bollinger_reversion': BollingerMeanReversion,
    'zscore_reversion': ZScoreMeanReversion,
    'rsi_reversion': RSIMeanReversion,
    'pairs_trading': PairsTrading,
}


def get_strategy(name: str, config: StrategyConfig) -> BaseStrategy:
    """
    Factory function to create strategy instances.
    
    Args:
        name: Strategy name from registry
        config: Strategy configuration
        
    Returns:
        Strategy instance
        
    Raises:
        ValueError: If strategy not found
    """
    if name not in STRATEGY_REGISTRY:
        available = ', '.join(STRATEGY_REGISTRY.keys())
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    
    strategy_class = STRATEGY_REGISTRY[name]
    return strategy_class(config)


def list_strategies() -> list:
    """List all available strategies with descriptions"""
    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        # Create temporary instance to get name/description
        temp_config = StrategyConfig(symbols=['TEST'])
        try:
            instance = cls(temp_config)
            result.append({
                'id': name,
                'name': instance.name,
                'description': instance.description,
                'required_history': instance.get_required_history(),
            })
        except Exception:
            result.append({
                'id': name,
                'name': name,
                'description': 'Strategy requires specific parameters',
                'required_history': 'N/A',
            })
    return result


__all__ = [
    # Base classes
    'BaseStrategy',
    'Signal',
    'SignalType',
    'StrategyConfig',
    
    # Indicators
    'sma', 'ema', 'rsi', 'macd', 'bollinger_bands', 'atr',
    'zscore', 'returns', 'log_returns', 'volatility',
    'drawdown', 'sharpe_ratio',
    
    # Strategies
    'MomentumStrategy',
    'DualMomentumStrategy',
    'RSIMomentumStrategy',
    'MACDMomentumStrategy',
    'BollingerMeanReversion',
    'ZScoreMeanReversion',
    'RSIMeanReversion',
    'PairsTrading',
    
    # Utilities
    'STRATEGY_REGISTRY',
    'get_strategy',
    'list_strategies',
]
