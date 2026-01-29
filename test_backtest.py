"""Test Backtesting Engine with Full TradingBrain Integration"""
import numpy as np
from datetime import datetime, timedelta

# Generate synthetic OHLCV data
def generate_ohlcv(n_bars=500, start_price=100, seed=42):
    """Generate realistic synthetic OHLCV data."""
    np.random.seed(seed)
    
    # Generate returns with some autocorrelation and regime changes
    returns = np.random.normal(0.0003, 0.015, n_bars)
    
    # Add a trending period
    returns[100:150] += 0.002  # Bull run
    
    # Add a crash
    returns[200:220] = np.random.normal(-0.015, 0.03, 20)  # Crash
    
    # Add recovery
    returns[220:280] += 0.001
    
    # Calculate prices
    prices = start_price * np.exp(np.cumsum(returns))
    
    # Generate OHLCV bars
    ohlcv = []
    base_date = datetime(2024, 1, 1)
    
    for i, close in enumerate(prices):
        # Add some intraday noise
        noise = np.random.uniform(0.002, 0.015)
        high = close * (1 + noise)
        low = close * (1 - noise)
        open_price = close * (1 + np.random.uniform(-0.005, 0.005))
        volume = int(np.random.uniform(500000, 2000000))
        
        ohlcv.append({
            'timestamp': (base_date + timedelta(days=i)).isoformat(),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    return ohlcv

print("=== BACKTEST ENGINE TEST ===")
print()

# Generate data
print("Generating synthetic data...")
spy_data = generate_ohlcv(500, 450, seed=42)
aapl_data = generate_ohlcv(500, 180, seed=43)
print(f"  SPY: {len(spy_data)} bars, ${spy_data[0]['close']:.2f} -> ${spy_data[-1]['close']:.2f}")
print(f"  AAPL: {len(aapl_data)} bars, ${aapl_data[0]['close']:.2f} -> ${aapl_data[-1]['close']:.2f}")
print()

# Import after data gen (avoids TF delay in output)
from backend.brain.trading_brain import TradingBrain
from brain.math.backtester import BacktestEngine, BacktestConfig, run_backtest

# Initialize brain
print("Initializing TradingBrain...")
brain = TradingBrain(account_equity=100000)
print(f"  Math integration: {brain.risk_monitor is not None}")
print()

# Configure backtest
config = BacktestConfig(
    initial_capital=100000,
    commission_per_share=0.005,
    slippage_pct=0.001,
    max_position_pct=0.10,
    max_drawdown_halt=0.25,  # Stop at 25% DD
    use_market_impact=True,
    lookback_required=60
)

# Prepare data with market context
data = {
    'AAPL': aapl_data,
}

# Add SPY as market reference in each bar
for i, bar in enumerate(data['AAPL']):
    pass  # Brain will handle this

# Run backtest
print("Running backtest...")
print("  Config:")
print(f"    Initial Capital: ${config.initial_capital:,.0f}")
print(f"    Max Position: {config.max_position_pct:.0%}")
print(f"    Max Drawdown Halt: {config.max_drawdown_halt:.0%}")
print()

# Create engine manually for progress tracking
engine = BacktestEngine(config)
engine.load_data('AAPL', aapl_data)

# Add SPY data to brain's market context
# We'll modify the market_data in the engine to include spy_ohlcv
original_get_market_data = engine._get_market_data_for_brain

def enhanced_get_market_data(symbol, bar_idx):
    market_data = original_get_market_data(symbol, bar_idx)
    # Add SPY for regime detection
    market_data['spy_ohlcv'] = spy_data[:bar_idx + 1]
    return market_data

engine._get_market_data_for_brain = enhanced_get_market_data

# Run with progress
def progress(current, total):
    pct = current / total * 100 if total > 0 else 0
    if current % 100 == 0:
        print(f"  Progress: {pct:.0f}%")

result = engine.run(brain, ['AAPL'], progress_callback=progress)

# Print results
print()
print("=" * 50)
print("BACKTEST RESULTS")
print("=" * 50)
print()
print(f"Total Return:      {result.total_return:>10.2%}")
print(f"Annual Return:     {result.annual_return:>10.2%}")
print(f"Volatility:        {result.volatility:>10.2%}")
print(f"Sharpe Ratio:      {result.sharpe_ratio:>10.2f}")
print(f"Sortino Ratio:     {result.sortino_ratio:>10.2f}")
print(f"Max Drawdown:      {result.max_drawdown:>10.2%}")
print(f"Max DD Duration:   {result.max_drawdown_duration:>10} days")
print()
print(f"Total Trades:      {result.total_trades:>10}")
print(f"Win Rate:          {result.win_rate:>10.1%}")
print(f"Profit Factor:     {result.profit_factor:>10.2f}")
print(f"Avg Win:           {result.avg_win:>10.2%}")
print(f"Avg Loss:          {result.avg_loss:>10.2%}")
print()

# Risk metrics from brain
print("Brain Risk State:")
risk_status = brain.get_risk_status()
print(f"  Current Drawdown: {risk_status['current_drawdown']:.2%}")
print(f"  Risk Level: {risk_status['risk_level']}")
print()

# Sample trades
if result.trades:
    print("Sample Trades (last 5):")
    for trade in result.trades[-5:]:
        print(f"  {trade.symbol}: {trade.pnl_pct:+.2%} ({trade.holding_period.days}d)")

print()
print("Backtest Complete!")
