"""Quick backtest with simulated data"""
import numpy as np
from datetime import datetime, timedelta
from backtest.engine import BacktestEngine, BacktestConfig
from strategies import MomentumStrategy, StrategyConfig

# Generate sample price data
np.random.seed(42)
days = 252  # 1 year

def generate_prices(start_price, drift=0.0003, vol=0.015):
    returns = np.random.normal(drift, vol, days)
    prices = start_price * np.exp(np.cumsum(returns))
    return prices.tolist()

start_date = datetime(2024, 1, 1)
dates = [(start_date + timedelta(days=i)) for i in range(days)]

# Create data dict
data = {
    'SPY': {
        'timestamp': dates,
        'open': generate_prices(475),
        'high': generate_prices(478),
        'low': generate_prices(472),
        'close': generate_prices(476, drift=0.0004),  # slight upward bias
        'volume': [int(x) for x in np.random.uniform(50e6, 100e6, days)]
    },
    'QQQ': {
        'timestamp': dates,
        'open': generate_prices(400),
        'high': generate_prices(404),
        'low': generate_prices(396),
        'close': generate_prices(401, drift=0.0005),  # tech outperforms
        'volume': [int(x) for x in np.random.uniform(30e6, 60e6, days)]
    },
    'AAPL': {
        'timestamp': dates,
        'open': generate_prices(185),
        'high': generate_prices(188),
        'low': generate_prices(182),
        'close': generate_prices(186, drift=0.0006),
        'volume': [int(x) for x in np.random.uniform(40e6, 80e6, days)]
    }
}

# Create config and strategy
config = BacktestConfig(initial_capital=100000)
strategy = MomentumStrategy(StrategyConfig(
    name='Momentum',
    symbols=['SPY', 'QQQ', 'AAPL'],
    parameters={'lookback': 20, 'threshold': 0.02}
))

# Run backtest
print("Running backtest...")
engine = BacktestEngine(config)
results = engine.run(
    strategy=strategy,
    data=data,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)

print()
print('=' * 50)
print('BACKTEST RESULTS - MOMENTUM STRATEGY 2024')
print('=' * 50)
print(f'Total Return:    {results.total_return:.2%}')
print(f'Annual Return:   {results.annualized_return:.2%}')
print(f'Sharpe Ratio:    {results.sharpe_ratio:.2f}')
print(f'Max Drawdown:    {results.max_drawdown:.2%}')
print(f'Win Rate:        {results.win_rate:.2%}')
print(f'Profit Factor:   {getattr(results, "profit_factor", 0):.2f}')
print(f'Total Trades:    {results.total_trades}')
print(f'Final Equity:    ${results.final_equity:,.2f}')
print('=' * 50)
