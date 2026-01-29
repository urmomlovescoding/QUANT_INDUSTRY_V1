"""Test Phase 3 Risk Layer Integration"""
import numpy as np
from backend.brain.trading_brain import get_trading_brain

# Initialize
brain = get_trading_brain()
print('=== PHASE 3 RISK LAYER TEST ===')
print()

# Check components
print('Components Available:')
print(f'  risk_monitor: {brain.risk_monitor is not None}')
print(f'  shift_detector: {brain.shift_detector is not None}')
print()

# Simulate some returns for VaR/CVaR
equity = brain.account_equity
for ret in np.random.normal(-0.001, 0.015, 50):
    equity = equity * (1 + ret)
    brain.update_risk_state(equity, ret)

# Tail risk metrics
print('Tail Risk Metrics:')
tail = brain.get_tail_risk_metrics()
if tail:
    print(f'  VaR 95%: {tail["var_95"]*100:.2f}%')
    print(f'  VaR 99%: {tail["var_99"]*100:.2f}%')
    print(f'  CVaR 95% (Expected Shortfall): {tail["cvar_95"]*100:.2f}%')
    print(f'  Tail Ratio: {tail["tail_ratio"]:.2f}')
print()

# Circuit breaker test
print('Circuit Breaker Status:')
cb = brain.check_circuit_breaker()
print(f'  Active: {cb["active"]}')
print(f'  Current Drawdown: {cb["drawdown"]*100:.2f}%')
print(f'  Position Limit: {cb["position_limit"]*100:.0f}%')
print()

# Regime shift detection (synthetic data)
np.random.seed(42)
prices = 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, 200)))
# Add a regime shift at index 150
shift_prices = prices[150] * np.exp(np.cumsum(np.random.normal(-0.002, 0.025, 50)))
prices[150:] = shift_prices

market_data = {'ohlcv': [{'close': float(p)} for p in prices]}
shift = brain.detect_regime_shift(market_data)
print('Regime Shift Detection:')
if shift:
    print(f'  Shift Detected: {shift["has_shift"]}')
    print(f'  Current Regime: {shift["current_regime"]}')
    print(f'  Change Points: {len(shift["change_points"])}')
    if shift.get('alert'):
        print(f'  Alert: {shift["alert"]["message"]}')
print()

# Test drawdown circuit breaker
print('Circuit Breaker Trigger Test:')
# Simulate 25% drawdown
brain.risk_monitor.peak_equity = 100000
brain.risk_monitor.current_equity = 75000  # 25% drawdown
alerts = brain.update_risk_state(75000, -0.05)
print(f'  Alerts triggered: {len(alerts)}')
for a in alerts:
    print(f'    - [{a["severity"]}] {a["message"]}')

cb = brain.check_circuit_breaker()
print(f'  Circuit Breaker Active: {cb["active"]}')
print()

# Full risk report
print('Full Risk Report:')
brain.risk_monitor.current_equity = 95000  # Reset to less severe
brain.risk_monitor.peak_equity = 100000
report = brain.get_full_risk_report(market_data)
print(f'  Trading Allowed: {report["trading_allowed"]}')
print(f'  Position Limit: {report["position_limit_pct"]:.0f}%')
print(f'  Current Drawdown: {report["drawdown"]["current"]*100:.1f}%')
print()

print('Phase 3 Integration Complete!')
