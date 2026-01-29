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
    StrategyStatus,
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

# Strategy registry dict for easy lookup
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

# Alias for backward compatibility
MeanReversionStrategy = ZScoreMeanReversion


class StrategyRegistry:
    """Class-based strategy registry for engine compatibility."""
    
    _strategies: dict = {}
    
    @classmethod
    def register(cls, name: str, strategy_class):
        """Register a strategy class."""
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get(cls, name: str):
        """Get a strategy class by name."""
        return cls._strategies.get(name) or STRATEGY_REGISTRY.get(name)
    
    @classmethod
    def list_all(cls) -> list:
        """List all registered strategies."""
        all_strategies = {**STRATEGY_REGISTRY, **cls._strategies}
        return list(all_strategies.keys())
    
    @classmethod
    def create(cls, name: str, config: StrategyConfig) -> BaseStrategy:
        """Create a strategy instance."""
        strategy_class = cls.get(name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {name}")
        return strategy_class(config)


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
    'StrategyStatus',
    
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
    'MeanReversionStrategy',  # Alias
    
    # Registry
    'StrategyRegistry',
    'STRATEGY_REGISTRY',
    'get_strategy',
    'list_strategies',
]
