#!/usr/bin/env python3
"""End-to-end test of the trading engine."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time


def main():
    from core import TradingEngine, EngineConfig, TradingMode

    print('Starting E2E Trading Engine Test...')
    print('=' * 60)

    config = EngineConfig(
        mode=TradingMode.PAPER,
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        initial_capital=100000,
        update_interval_seconds=2,  # Fast updates for test
    )

    engine = TradingEngine(config)
    print('Engine created')

    engine.initialize()
    print('Engine initialized')

    print('Starting engine...')
    engine.start()

    # Run for a few iterations
    try:
        for i in range(5):
            time.sleep(3)
            status = engine.get_status()
            equity = status['equity']
            pnl = status['pnl']
            positions = status['positions']
            regime = status['current_regime']
            print(f'Tick {i+1}: Equity=${equity:,.2f}, PnL=${pnl:+,.2f}, Positions={positions}, Regime={regime}')

            trades = engine.get_recent_trades(3)
            if trades:
                print(f'  Recent trades: {len(trades)}')
    except KeyboardInterrupt:
        print('\nInterrupted')

    engine.stop()
    print('Engine stopped')

    print('=' * 60)
    print('E2E Test Complete!')
    return 0


if __name__ == '__main__':
    sys.exit(main())
