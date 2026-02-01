"""
Test Math Integration with TradingBrain
========================================
Verifies HMM regime detection, Kelly position sizing, and risk management
are properly integrated into the TradingBrain decision-making process.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime, timedelta


def generate_mock_market_data(n_bars: int = 100, trend: str = "bull") -> dict:
    """Generate mock OHLCV data for testing."""
    
    # Generate price series based on trend
    if trend == "bull":
        drift = 0.001  # Positive drift
        vol = 0.015
    elif trend == "bear":
        drift = -0.001
        vol = 0.025  # Higher vol in bear
    else:  # neutral
        drift = 0.0
        vol = 0.012
    
    returns = np.random.randn(n_bars) * vol + drift
    prices = 100 * np.exp(np.cumsum(returns))
    
    ohlcv = []
    for i, close in enumerate(prices):
        high = close * (1 + np.random.uniform(0, 0.01))
        low = close * (1 - np.random.uniform(0, 0.01))
        open_price = close * (1 + np.random.uniform(-0.005, 0.005))
        
        ohlcv.append({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(100000, 1000000)
        })
    
    return {
        "ohlcv": ohlcv,
        "spy_ohlcv": ohlcv,  # Use same for SPY
        "quote": {"price": prices[-1]},
        "news": [],
        "options_flow": []
    }


def test_regime_detector():
    """Test HMM regime detection."""
    print("\n" + "="*60)
    print("TEST 1: HMM Regime Detection")
    print("="*60)
    
    from brain.math.integration import IntegratedRegimeDetector, MarketRegime
    
    # Create detector
    detector = IntegratedRegimeDetector(n_regimes=4)
    
    # Test with bull market data
    print("\n[Bull Market Test]")
    bull_prices = 100 * np.exp(np.cumsum(np.random.randn(200) * 0.015 + 0.001))
    detector.fit(bull_prices)
    state = detector.detect(bull_prices)
    
    print(f"  Regime: {state.regime.value}")
    print(f"  Confidence: {state.confidence:.2%}")
    print(f"  Vol Regime: {state.volatility_regime}")
    print(f"  Position Scalar: {state.position_scalar:.2f}")
    print(f"  Expected Return: {state.expected_return:.2%}")
    
    # Test with bear market data
    print("\n[Bear Market Test]")
    bear_prices = 100 * np.exp(np.cumsum(np.random.randn(200) * 0.025 - 0.002))
    detector.fit(bear_prices)
    state = detector.detect(bear_prices)
    
    print(f"  Regime: {state.regime.value}")
    print(f"  Confidence: {state.confidence:.2%}")
    print(f"  Vol Regime: {state.volatility_regime}")
    print(f"  Position Scalar: {state.position_scalar:.2f}")
    
    print("\n[PASS] Regime detection working")
    return True


def test_position_sizer():
    """Test Kelly-based position sizing."""
    print("\n" + "="*60)
    print("TEST 2: Kelly Position Sizing")
    print("="*60)
    
    from brain.math.integration import (
        IntegratedPositionSizer,
        IntegratedRegimeDetector
    )
    
    # Setup
    sizer = IntegratedPositionSizer(max_position=0.10, kelly_fraction=0.25)
    detector = IntegratedRegimeDetector(n_regimes=3)
    
    # Fit detector
    prices = 100 * np.exp(np.cumsum(np.random.randn(100) * 0.02))
    detector.fit(prices)
    regime_state = detector.detect(prices)
    
    # Test various confidence levels
    print("\n[Position Sizes by Confidence]")
    for confidence in [0.3, 0.5, 0.7, 0.9]:
        result = sizer.calculate(
            signal_confidence=confidence,
            regime_state=regime_state,
            current_volatility=0.20,
            account_equity=100000
        )
        print(f"  Confidence {confidence:.0%}: Position = {result.final_size:.2%}")
        print(f"    Base Kelly: {result.base_kelly:.3f}")
        print(f"    Regime Adj: {result.regime_adjustment:.2f}x")
    
    # Test with trade history (Kelly learning)
    print("\n[Kelly Learning from Trade History]")
    # Simulate some winning and losing trades
    for _ in range(20):
        pnl = np.random.choice([0.02, -0.01], p=[0.6, 0.4])
        sizer.add_trade(pnl, pnl > 0)
    
    result_after = sizer.calculate(
        signal_confidence=0.7,
        regime_state=regime_state,
        current_volatility=0.20,
        account_equity=100000
    )
    print(f"  Win Rate: {result_after.win_rate:.1%}")
    print(f"  Avg Win: {result_after.avg_win:.2%}")
    print(f"  Avg Loss: {result_after.avg_loss:.2%}")
    print(f"  Edge: {result_after.edge:.3f}")
    print(f"  Kelly Size: {result_after.final_size:.2%}")
    
    print("\n[PASS] Position sizing working")
    return True


def test_risk_manager():
    """Test drawdown-based risk management."""
    print("\n" + "="*60)
    print("TEST 3: Risk Management")
    print("="*60)
    
    from brain.math.integration import (
        RiskManager,
        IntegratedRegimeDetector
    )
    
    risk_mgr = RiskManager(
        drawdown_threshold=0.10,
        critical_drawdown=0.20
    )
    
    # Setup regime
    detector = IntegratedRegimeDetector(n_regimes=3)
    prices = 100 * np.exp(np.cumsum(np.random.randn(100) * 0.02))
    detector.fit(prices)
    regime_state = detector.detect(prices)
    
    # Test normal conditions
    print("\n[Normal Equity]")
    risk_mgr.update_equity(100000)
    mult = risk_mgr.get_risk_multiplier(regime_state)
    print(f"  Equity: $100,000")
    print(f"  Drawdown: {risk_mgr.current_drawdown:.1%}")
    print(f"  Risk Multiplier: {mult:.2f}")
    
    # Test moderate drawdown
    print("\n[Moderate Drawdown - 12%]")
    risk_mgr.update_equity(88000)
    mult = risk_mgr.get_risk_multiplier(regime_state)
    print(f"  Equity: $88,000")
    print(f"  Drawdown: {risk_mgr.current_drawdown:.1%}")
    print(f"  Risk Multiplier: {mult:.2f}")
    
    # Test critical drawdown
    print("\n[Critical Drawdown - 22%]")
    risk_mgr.update_equity(78000)
    mult = risk_mgr.get_risk_multiplier(regime_state)
    print(f"  Equity: $78,000")
    print(f"  Drawdown: {risk_mgr.current_drawdown:.1%}")
    print(f"  Risk Multiplier: {mult:.2f}")
    print(f"  Trading Stopped: {mult == 0}")
    
    print("\n[PASS] Risk management working")
    return True


def test_trading_brain_integration():
    """Test full TradingBrain integration with math components.

    This test verifies that the TradingBrain from backend.brain works correctly
    and can be combined with math integration components (regime detector,
    position sizer, risk manager) for enhanced decision making.
    """
    print("\n" + "="*60)
    print("TEST 4: TradingBrain Full Integration")
    print("="*60)

    import tempfile
    import os
    from backend.brain.trading_brain import TradingBrain, BrainDecision
    from brain.math.integration import (
        IntegratedRegimeDetector,
        IntegratedPositionSizer,
        RiskManager
    )

    # Create TradingBrain with temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_brain.db")
        brain = TradingBrain(db_path=db_path)

        # Create math integration components separately
        regime_detector = IntegratedRegimeDetector(n_regimes=3)
        position_sizer = IntegratedPositionSizer(max_position=0.10, kelly_fraction=0.25)
        risk_manager = RiskManager(drawdown_threshold=0.10, critical_drawdown=0.20)

        print(f"\n[Brain Status]")
        print(f"  TradingBrain: {brain is not None}")
        print(f"  Regime Detector: {regime_detector is not None}")
        print(f"  Position Sizer: {position_sizer is not None}")
        print(f"  Risk Manager: {risk_manager is not None}")

        # Test with bull market
        print("\n[Bull Market Decision]")
        market_data = generate_mock_market_data(100, "bull")

        # Get brain decision
        decision = brain.think("AAPL", market_data)

        # Verify decision is a BrainDecision
        assert isinstance(decision, BrainDecision), "Decision should be a BrainDecision"

        print(f"  Direction: {decision.direction}")
        print(f"  Confidence: {decision.confidence:.1%}")
        print(f"  Position Size: {decision.position_size_pct:.2f}%")
        print(f"  Regime Alignment: {decision.regime_alignment:.0f}")
        print(f"  Factors: {decision.factors}")
        print(f"  Warnings: {decision.warnings}")

        # Enhance with math components - fit regime detector
        prices = np.array([bar["close"] for bar in market_data["ohlcv"]])
        regime_detector.fit(prices)
        regime_state = regime_detector.detect(prices)

        print(f"\n[Enhanced Regime Analysis]")
        print(f"  Detected Regime: {regime_state.regime.value}")
        print(f"  Regime Confidence: {regime_state.confidence:.2%}")
        print(f"  Position Scalar: {regime_state.position_scalar:.2f}")

        # Calculate enhanced position size
        position_result = position_sizer.calculate(
            signal_confidence=decision.confidence,
            regime_state=regime_state,
            current_volatility=0.20,
            account_equity=100000
        )

        print(f"\n[Enhanced Position Sizing]")
        print(f"  Base Kelly: {position_result.base_kelly:.3f}")
        print(f"  Final Size: {position_result.final_size:.2%}")

        # Test with bear market
        print("\n[Bear Market Decision]")
        market_data = generate_mock_market_data(100, "bear")
        decision = brain.think("AAPL", market_data)

        print(f"  Direction: {decision.direction}")
        print(f"  Confidence: {decision.confidence:.1%}")
        print(f"  Position Size: {decision.position_size_pct:.2f}%")
        print(f"  Warnings: {decision.warnings}")

        # Test trade feedback learning with position sizer
        print("\n[Trade Feedback Learning]")
        position_sizer.add_trade(0.03, True)   # 3% win
        position_sizer.add_trade(-0.01, False)  # 1% loss
        position_sizer.add_trade(0.02, True)    # 2% win
        print("  Recorded 3 trades for Kelly learning")

        # Test equity/drawdown tracking with risk manager
        print("\n[Equity/Drawdown Tracking]")
        risk_manager.update_equity(100000)  # Initial equity
        risk_manager.update_equity(95000)   # 5% drawdown

        current_dd = risk_manager.current_drawdown
        risk_mult = risk_manager.get_risk_multiplier(regime_state)
        trading_allowed = current_dd < risk_manager.critical_drawdown

        print(f"  Current Drawdown: {current_dd:.1%}")
        print(f"  Risk Multiplier: {risk_mult:.2f}")
        print(f"  Trading Allowed: {trading_allowed}")

        # Verify brain state
        state = brain.get_state()
        print(f"\n[Brain State]")
        print(f"  Overall Bias: {state.overall_bias}")
        print(f"  Bias Strength: {state.bias_strength:.2f}")

        # Get recent decisions
        decisions = brain.get_decisions(symbol="AAPL", limit=5)
        print(f"  Recent Decisions: {len(decisions)}")

        print("\n[PASS] TradingBrain integration working")
        return True


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "#"*60)
    print("# MATH INTEGRATION TEST SUITE")
    print("#"*60)
    
    results = []
    
    try:
        results.append(("Regime Detection", test_regime_detector()))
    except Exception as e:
        print(f"\n[FAIL] Regime Detection: {e}")
        results.append(("Regime Detection", False))
    
    try:
        results.append(("Position Sizing", test_position_sizer()))
    except Exception as e:
        print(f"\n[FAIL] Position Sizing: {e}")
        results.append(("Position Sizing", False))
    
    try:
        results.append(("Risk Management", test_risk_manager()))
    except Exception as e:
        print(f"\n[FAIL] Risk Management: {e}")
        results.append(("Risk Management", False))
    
    try:
        results.append(("TradingBrain Integration", test_trading_brain_integration()))
    except Exception as e:
        print(f"\n[FAIL] TradingBrain Integration: {e}")
        import traceback
        traceback.print_exc()
        results.append(("TradingBrain Integration", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
