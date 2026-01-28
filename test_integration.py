#!/usr/bin/env python3
"""Quick integration test for QUANT_INDUSTRY_V1."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    print('Testing QUANT_INDUSTRY_V1 Integration...')
    print('=' * 60)

    errors = []

    # Test 1: Core engine imports
    print('\n1. Testing core engine imports...')
    try:
        from core import TradingEngine, EngineConfig, TradingMode, EngineState
        print('   Core engine: OK')
    except Exception as e:
        print(f'   Core engine: FAILED - {e}')
        errors.append(str(e))

    # Test 2: All modules import
    print('\n2. Testing all module imports...')
    modules = ['brain', 'data', 'execution', 'risk', 'strategies', 'services', 'security', 'backtest']
    for mod in modules:
        try:
            __import__(mod)
            print(f'   {mod}: OK')
        except Exception as e:
            print(f'   {mod}: FAILED - {e}')
            errors.append(f'{mod}: {e}')

    # Test 3: Engine initialization
    print('\n3. Testing engine initialization...')
    try:
        from core import TradingEngine, EngineConfig, TradingMode

        config = EngineConfig(
            mode=TradingMode.PAPER,
            symbols=['AAPL', 'MSFT'],
            initial_capital=100000,
        )
        engine = TradingEngine(config)
        print('   Engine created: OK')

        engine.initialize()
        print('   Engine initialized: OK')

        status = engine.get_status()
        print(f'   Status: {status["state"]} | Equity: ${status["equity"]:,.2f}')
    except Exception as e:
        print(f'   Engine init: FAILED - {e}')
        import traceback
        traceback.print_exc()
        errors.append(f'Engine init: {e}')

    # Test 4: Database tables
    print('\n4. Testing database tables...')
    try:
        import sqlite3
        conn = sqlite3.connect('trading.db')
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f'   Tables: {tables}')
    except Exception as e:
        print(f'   Database: FAILED - {e}')
        errors.append(f'Database: {e}')

    # Test 5: UI imports (don't launch, just import)
    print('\n5. Testing UI imports...')
    try:
        from ui import launch_ui, connect_engine
        print('   UI imports: OK')
    except Exception as e:
        print(f'   UI imports: FAILED - {e}')
        errors.append(f'UI imports: {e}')

    # Test 6: Feature computation
    print('\n6. Testing feature computation...')
    try:
        from brain import FeatureComputer
        import numpy as np

        fc = FeatureComputer()
        close = np.random.randn(100).cumsum() + 100
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_ = close + np.random.randn(100) * 0.5
        volume = np.abs(np.random.randn(100)) * 1000000

        features = fc.compute(open_, high, low, close, volume)
        print(f'   Features computed: {len(features)} values')
    except Exception as e:
        print(f'   Features: FAILED - {e}')
        errors.append(f'Features: {e}')

    # Test 7: Regime detection
    print('\n7. Testing regime detection...')
    try:
        from brain import EnsembleRegimeDetector
        import numpy as np

        detector = EnsembleRegimeDetector()
        returns = np.random.randn(100) * 0.02
        volatility = np.abs(np.random.randn(100)) * 0.02 + 0.01
        volume = np.abs(np.random.randn(100)) * 1000000

        regime_state = detector.detect(returns, volatility, volume)
        print(f'   Regime: {regime_state.regime.value} (confidence: {regime_state.confidence:.2f})')
    except Exception as e:
        print(f'   Regime detection: FAILED - {e}')
        errors.append(f'Regime detection: {e}')

    # Test 8: Risk engine
    print('\n8. Testing risk engine...')
    try:
        from risk import RiskEngine, VolatilityScaledSizer

        risk = RiskEngine(
            portfolio_value=100000,
            position_sizer=VolatilityScaledSizer(target_risk=0.02)
        )
        print(f'   Risk engine: OK')
    except Exception as e:
        print(f'   Risk engine: FAILED - {e}')
        errors.append(f'Risk engine: {e}')

    # Summary
    print('\n' + '=' * 60)
    if errors:
        print(f'Integration tests completed with {len(errors)} errors')
        return 1
    else:
        print('All integration tests passed!')
        return 0


if __name__ == '__main__':
    sys.exit(main())
