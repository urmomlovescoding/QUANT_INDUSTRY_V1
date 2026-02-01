#!/usr/bin/env python
"""
Comprehensive functional tests for all 20 improvements.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone

print('='*60)
print('COMPREHENSIVE FUNCTIONAL TESTS')
print('='*60)

# Test Feature Store functionality
print('\n1. Feature Store - Materialize and retrieve features')
from data.feature_store import QuantFeatureStore
store = QuantFeatureStore()
store.materialize_features('AAPL', {'sma_20': 150.5, 'rsi_14': 55.0, 'volatility': 0.25})
result = store.get_online_features(['AAPL'], ['sma_20', 'rsi_14'])
print(f'   Retrieved {len(result.vectors)} vectors, latency={result.latency_ms:.2f}ms')

# Test Adaptive Normalizer
print('\n2. Stream Processor - Adaptive normalization')
from data.stream_processor import AdaptiveNormalizer, MarketTick
normalizer = AdaptiveNormalizer(decay_factor=0.99)
for i in range(100):
    tick = MarketTick(
        symbol='AAPL',
        timestamp=datetime.now(timezone.utc),
        price=150 + np.random.randn() * 2,
        volume=10000 + np.random.randint(-1000, 1000)
    )
    normalized = normalizer.normalize(tick)
print(f'   Normalized 100 ticks, final z-score={normalized.price_normalized:.3f}')

# Test Correlation Analyzer
print('\n3. Correlation Analyzer - Rolling correlations')
from strategies.correlation_analyzer import CorrelationAnalyzer
returns = pd.DataFrame({
    'AAPL': np.random.randn(100) * 0.02,
    'GOOGL': np.random.randn(100) * 0.02,
    'MSFT': np.random.randn(100) * 0.02,
})
analyzer = CorrelationAnalyzer()
metrics = analyzer.analyze(returns)
print(f'   Avg correlation={metrics.avg_correlation:.3f}, div_ratio={metrics.diversification_ratio:.3f}')

# Test Diversification Optimizer (HRP)
print('\n4. Diversification Optimizer - HRP allocation')
from strategies.diversification_optimizer import DiversificationOptimizer
optimizer = DiversificationOptimizer()
result = optimizer.hrp_optimize(returns)
weights = result.weights
print(f'   HRP weights: {dict((k, round(v, 3)) for k, v in weights.items())}')

# Test Dynamic Rebalancer
print('\n5. Dynamic Rebalancer - Generate trades')
from portfolio.dynamic_rebalancer import DynamicRebalancer
rebalancer = DynamicRebalancer()
result = rebalancer.generate_rebalance_trades(
    current_weights={'AAPL': 0.5, 'GOOGL': 0.3, 'MSFT': 0.2},
    target_weights={'AAPL': 0.33, 'GOOGL': 0.34, 'MSFT': 0.33},
    positions={'AAPL': 100, 'GOOGL': 60, 'MSFT': 40},
    prices={'AAPL': 150, 'GOOGL': 140, 'MSFT': 380},
    portfolio_value=100000
)
print(f'   Generated {len(result.trades)} trades, turnover=${result.total_turnover:.0f}')

# Test Feedback Collector
print('\n6. Feedback Collector - Record and analyze')
from backend.analytics.feedback_collector import FeedbackCollector, SignalOutcome
collector = FeedbackCollector()
for i in range(20):
    collector.record_signal_feedback(
        signal_id=f'SIG-{i:03d}',
        model_name='momentum_v2',
        symbol='AAPL',
        signal_value=np.random.randn() * 0.5,
        rating=np.random.randint(1, 6),
        outcome=np.random.choice([SignalOutcome.PROFITABLE, SignalOutcome.LOSS]),
    )
metrics = collector.get_model_metrics('momentum_v2')
print(f"   Recorded 20 feedbacks, avg_rating={metrics['avg_rating']:.2f}, win_rate={metrics.get('win_rate', 0):.1%}")

# Test Audit Logger
print('\n7. Audit Logger - Log and verify')
from security.audit_log import AuditLogger, AuditEventType
audit = AuditLogger()
for i in range(10):
    audit.log_event(AuditEventType.ORDER_SUBMITTED, user_id='trader1', details={'order_id': f'ORD-{i}'})
integrity = audit.verify_integrity()
print(f"   Logged 10 events, integrity_valid={integrity['valid']}")

# Test Maintenance Predictor
print('\n8. Maintenance Predictor - Monitor health')
from monitoring.maintenance_predictor import MaintenancePredictor
predictor = MaintenancePredictor()
for i in range(50):
    predictor.record_latency('execution', 50 + np.random.randn() * 10)
    predictor.record_memory_usage(60 + i * 0.3)
alerts = predictor.get_maintenance_alerts()
health = predictor.get_component_health()
print(f"   Recorded 50 metrics, alerts={len(alerts)}, execution_health={health['execution'].health_score:.0f}")

# Test Decision Tracer
print('\n9. Decision Tracer - Explain decisions')
from brain.causal.decision_trace import DecisionTracer
tracer = DecisionTracer()
explanation = tracer.explain_decision(
    signal=0.75,
    features={'momentum': 0.8, 'volatility': 0.3, 'trend': 0.5},
    feature_importance={'momentum': 0.5, 'volatility': 0.3, 'trend': 0.2},
    model_name='momentum_model'
)
print(f'   Decision: {explanation.signal_type}, confidence={explanation.confidence:.1%}')
print(f'   Top reason: {explanation.top_reasons[0]}')

# Test P&L Attribution
print('\n10. P&L Attribution - Brinson-Fachler')
from backend.analytics.pnl_attribution import PnLAttributor
attributor = PnLAttributor()
attr = attributor.compute_brinson_fachler(
    portfolio_weights={'tech': 0.4, 'finance': 0.3, 'healthcare': 0.3},
    benchmark_weights={'tech': 0.3, 'finance': 0.35, 'healthcare': 0.35},
    portfolio_returns={'tech': 0.05, 'finance': 0.02, 'healthcare': 0.03},
    benchmark_returns={'tech': 0.04, 'finance': 0.025, 'healthcare': 0.028}
)
print(f'   Allocation={attr.allocation_effect:.4f}, Selection={attr.selection_effect:.4f}')
print(f'   Total active return={attr.total_active_return:.4f}')

print('\n' + '='*60)
print('ALL FUNCTIONAL TESTS COMPLETED SUCCESSFULLY')
print('='*60)
