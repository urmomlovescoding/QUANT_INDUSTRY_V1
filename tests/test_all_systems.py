"""
QUANT_INDUSTRY_V1 Comprehensive System Tests

End-to-end testing of all system components.
"""

import sys
import os
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
import numpy as np

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestResult:
    """Test result container."""
    def __init__(self, name: str, passed: bool, message: str = "", duration: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration


class SystemTester:
    """Comprehensive system tester."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = None

    def run_all(self) -> Tuple[int, int]:
        """Run all tests. Returns (passed, failed)."""
        self.start_time = datetime.now(timezone.utc)
        print("=" * 70)
        print("QUANT_INDUSTRY_V1 COMPREHENSIVE SYSTEM TEST")
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 70)

        # Run test suites
        self._test_core_imports()
        self._test_strategies()
        self._test_deep_learning()
        self._test_prop_firm()
        self._test_options_analytics()
        self._test_sec_parser()
        self._test_execution()
        self._test_features()
        self._test_advanced_training()
        self._test_physics_models()
        self._test_alpha_discovery()

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ({passed/len(self.results)*100:.1f}%)")
        print(f"Failed: {failed}")
        print("=" * 70)

        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        return passed, failed

    def _test(self, name: str, test_fn):
        """Run a single test."""
        import time
        start = time.time()
        try:
            test_fn()
            duration = time.time() - start
            self.results.append(TestResult(name, True, "", duration))
            print(f"  [PASS] {name} ({duration:.3f}s)")
        except Exception as e:
            duration = time.time() - start
            self.results.append(TestResult(name, False, str(e), duration))
            print(f"  [FAIL] {name}: {e}")

    def _test_core_imports(self):
        """Test core module imports."""
        print("\n[1] Core Imports")

        def test_core():
            from core import TradingEngine, EngineConfig, Signal
            assert TradingEngine is not None
            assert EngineConfig is not None

        def test_data():
            import data
            assert data is not None

        def test_brain():
            import brain
            assert brain is not None

        self._test("Core engine imports", test_core)
        self._test("Data module imports", test_data)
        self._test("Brain module imports", test_brain)

    def _test_strategies(self):
        """Test strategy modules."""
        print("\n[2] Strategy Modules")

        def test_ict_smc():
            from strategies.ict_smc import (
                ICTAnalyzer, FairValueGapStrategy, OrderBlockStrategy,
                LiquiditySweepStrategy, MarketStructureShiftStrategy,
            )
            # Test analyzer instantiation
            analyzer = ICTAnalyzer(swing_lookback=10)
            assert analyzer is not None

            # Test strategy instantiation
            fvg_strategy = FairValueGapStrategy()
            assert fvg_strategy is not None

        def test_strategy_imports():
            import strategies
            assert strategies is not None

        self._test("ICT/SMC strategies", test_ict_smc)
        self._test("Strategy imports", test_strategy_imports)

    def _test_deep_learning(self):
        """Test deep learning modules."""
        print("\n[3] Deep Learning")

        def test_tft():
            from brain.deep_learning.temporal_fusion import (
                TemporalFusionTransformer, TFTConfig
            )
            # Check TFTConfig fields
            config = TFTConfig()
            assert hasattr(config, 'hidden_size')

            model = TemporalFusionTransformer(config)
            assert model is not None

        def test_wavenet():
            from brain.deep_learning.wavenet import WaveNetModel, WaveNetConfig
            config = WaveNetConfig()
            model = WaveNetModel(config)
            assert model is not None

        def test_attention_flow():
            from brain.deep_learning.attention_flow import (
                AttentionFlowNetwork, AttentionFlowConfig
            )
            config = AttentionFlowConfig()
            model = AttentionFlowNetwork(config)
            assert model is not None

        self._test("Temporal Fusion Transformer", test_tft)
        self._test("WaveNet", test_wavenet)
        self._test("Attention Flow Network", test_attention_flow)

    def _test_prop_firm(self):
        """Test prop firm module."""
        print("\n[4] Prop Firm Module")

        def test_rules():
            from prop_firm.rules import PropFirmRules, AccountConfig, PropFirm, AccountTier
            config = AccountConfig(
                firm=PropFirm.TPT,
                tier=AccountTier.STANDARD,
                account_size=50000.0,
                profit_target=3000.0,
                daily_loss_limit=1250.0,
                max_drawdown=2500.0,
            )
            rules = PropFirmRules(config)
            assert rules.config.daily_loss_limit == 1250.0

        def test_manager():
            from prop_firm.manager import PropFirmManager
            from prop_firm.rules import PropFirmRules, AccountConfig, PropFirm, AccountTier
            config = AccountConfig(
                firm=PropFirm.TPT,
                tier=AccountTier.STANDARD,
                account_size=50000.0,
                profit_target=3000.0,
                daily_loss_limit=1250.0,
                max_drawdown=2500.0,
            )
            rules = PropFirmRules(config)
            manager = PropFirmManager(rules)
            assert manager is not None

        def test_consistency():
            from prop_firm.consistency import ConsistencyMonitor
            monitor = ConsistencyMonitor(profit_target=3000.0)
            assert monitor is not None

        self._test("Prop firm rules", test_rules)
        self._test("Prop firm manager", test_manager)
        self._test("Consistency monitor", test_consistency)

    def _test_options_analytics(self):
        """Test options analytics module."""
        print("\n[5] Options Analytics")

        def test_black_scholes():
            from analytics.options import BlackScholes
            bs = BlackScholes()
            price = bs.call_price(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
            assert 0 < price < 20

        def test_gex():
            from analytics.options import GammaExposure
            # Check instantiation
            gex = GammaExposure(spot_price=100.0)
            assert gex is not None

        def test_options_analyzer():
            from analytics.options import OptionsAnalyzer
            analyzer = OptionsAnalyzer()
            assert analyzer is not None

        self._test("Black-Scholes pricing", test_black_scholes)
        self._test("Gamma exposure", test_gex)
        self._test("Options analyzer", test_options_analyzer)

    def _test_sec_parser(self):
        """Test SEC 13F parser."""
        print("\n[6] SEC 13F Parser")

        def test_parser():
            from data.sec_13f import Filing13FParser, InstitutionalHoldingsTracker
            parser = Filing13FParser()
            assert parser is not None

            tracker = InstitutionalHoldingsTracker()
            assert tracker is not None

        self._test("SEC 13F parser", test_parser)

    def _test_execution(self):
        """Test execution modules."""
        print("\n[7] Execution Modules")

        def test_ninjatrader():
            from execution.ninjatrader import (
                NinjaTraderBridge, NTOrderAction, NTOrderType, ATICommands
            )
            # Test command generation
            cmd = ATICommands.place_order(
                action="BUY", quantity=1, instrument="ES 03-24",
                order_type="MARKET"
            )
            assert "PLACE" in cmd
            assert "BUY" in cmd

        def test_multi_broker():
            from execution.multi_broker import MultiBrokerEngine, BrokerAdapter
            engine = MultiBrokerEngine()
            assert engine is not None

        def test_paper_broker():
            from execution.multi_broker import PaperBrokerAdapter
            paper = PaperBrokerAdapter(initial_capital=100000)
            assert paper.initial_capital == 100000

        self._test("NinjaTrader bridge", test_ninjatrader)
        self._test("Multi-broker engine", test_multi_broker)
        self._test("Paper broker adapter", test_paper_broker)

    def _test_features(self):
        """Test feature engineering."""
        print("\n[8] Feature Engineering")

        def test_advanced_features():
            from brain.advanced_features import AdvancedFeatureComputer
            computer = AdvancedFeatureComputer()
            assert computer is not None
            assert hasattr(computer, 'feature_functions')

        self._test("Advanced features", test_advanced_features)

    def _test_advanced_training(self):
        """Test advanced training modules."""
        print("\n[9] Advanced Training")

        def test_maml():
            from brain.advanced_training import MAML, MAMLConfig
            config = MAMLConfig(inner_lr=0.01, outer_lr=0.001, inner_steps=5)
            assert config is not None

        def test_adversarial():
            from brain.advanced_training import AdversarialTrainer, AdversarialConfig
            config = AdversarialConfig(epsilon=0.1, num_steps=5)
            trainer = AdversarialTrainer(config)
            assert trainer is not None

        def test_curriculum():
            from brain.advanced_training import CurriculumLearning, CurriculumConfig
            config = CurriculumConfig()
            curriculum = CurriculumLearning(config)
            assert curriculum is not None

        self._test("MAML meta-learning", test_maml)
        self._test("Adversarial training", test_adversarial)
        self._test("Curriculum learning", test_curriculum)

    def _test_physics_models(self):
        """Test physics-enhanced models."""
        print("\n[10] Physics Models")

        def test_quantum():
            from brain.physics_enhanced import QuantumAnnealer
            annealer = QuantumAnnealer(n_variables=5, n_iterations=10)
            assert annealer is not None

        def test_fokker_planck():
            from brain.physics_enhanced import FokkerPlanckDynamics
            fp = FokkerPlanckDynamics()
            assert fp is not None

        def test_percolation():
            from brain.physics_enhanced import PercolationModel
            model = PercolationModel()
            assert model is not None

        def test_spin_glass():
            from brain.physics_enhanced import SpinGlassOptimizer
            optimizer = SpinGlassOptimizer(n_assets=5)
            assert optimizer is not None

        self._test("Quantum annealer", test_quantum)
        self._test("Fokker-Planck dynamics", test_fokker_planck)
        self._test("Percolation model", test_percolation)
        self._test("Spin glass optimizer", test_spin_glass)

    def _test_alpha_discovery(self):
        """Test alpha discovery agent."""
        print("\n[11] Alpha Discovery Agent")

        def test_hypothesis():
            from brain.alpha_discovery.hypothesis import (
                AlphaHypothesis, HypothesisGenerator, HypothesisTester,
                HypothesisType, HypothesisCondition
            )
            generator = HypothesisGenerator(seed=42)
            h = generator.generate_random()
            assert h.hypothesis_id is not None
            assert len(h.entry_conditions) > 0

            # Test momentum hypothesis
            mom_h = generator.generate_momentum()
            assert mom_h.hypothesis_type == HypothesisType.MOMENTUM

        def test_genetic():
            from brain.alpha_discovery.genetic import (
                StrategyEvolver, StrategyGenome, GeneticOperators
            )
            evolver = StrategyEvolver(population_size=20, seed=42)
            evolver.initialize_population()
            assert len(evolver.population) == 20

            # Test crossover
            ops = GeneticOperators(seed=42)
            g1 = evolver.population[0]
            g2 = evolver.population[1]
            c1, c2 = ops.crossover(g1, g2)
            assert c1 is not None
            assert c2 is not None

        def test_backtester():
            from brain.alpha_discovery.backtester import (
                FastBacktester, BacktestResult, WalkForwardAnalyzer
            )
            from brain.alpha_discovery.hypothesis import HypothesisGenerator

            backtester = FastBacktester(initial_capital=100000)
            generator = HypothesisGenerator(seed=42)
            h = generator.generate_momentum()

            # Generate sample data
            n = 500
            prices = np.random.randn(n).cumsum() + 100
            features = {
                'momentum_10': np.random.randn(n),
                'rsi_14': 50 + np.random.randn(n) * 20,
                'adx': 20 + np.random.rand(n) * 30,
            }

            result = backtester.backtest(h, prices, features)
            assert isinstance(result, BacktestResult)

        def test_agent():
            from brain.alpha_discovery.agent import (
                AlphaDiscoveryAgent, AgentState, create_alpha_agent
            )

            # Mock data provider
            def mock_data():
                n = 500
                prices = np.random.randn(n).cumsum() + 100
                features = {
                    'momentum_10': np.random.randn(n),
                    'rsi_14': 50 + np.random.randn(n) * 20,
                    'adx': 20 + np.random.rand(n) * 30,
                    'zscore_20': np.random.randn(n),
                    'bb_pct': np.random.rand(n),
                    'volume_ratio': 1 + np.random.randn(n) * 0.3,
                }
                return prices, features

            agent = create_alpha_agent(mock_data, {'seed': 42})
            assert agent.state == AgentState.IDLE
            status = agent.get_status()
            assert 'state' in status
            assert 'deployed_count' in status

        self._test("Hypothesis generation", test_hypothesis)
        self._test("Genetic evolution", test_genetic)
        self._test("Fast backtester", test_backtester)
        self._test("Alpha discovery agent", test_agent)

    def _test_signal_aggregation(self):
        """Test signal aggregation system."""
        print("\n[12] Signal Aggregation")

        def test_signal_aggregator():
            from core.signal_aggregator import (
                SignalSource, SignalDirection, TradingSignal,
                SignalAggregator
            )
            from datetime import datetime, timezone

            signals = [
                TradingSignal(
                    symbol='TEST',
                    source=SignalSource.ML_MODEL,
                    direction=SignalDirection.LONG,
                    strength=0.7,
                    confidence=0.85,
                    timestamp=datetime.now(timezone.utc)
                ),
                TradingSignal(
                    symbol='TEST',
                    source=SignalSource.TECHNICAL,
                    direction=SignalDirection.LONG,
                    strength=0.5,
                    confidence=0.7,
                    timestamp=datetime.now(timezone.utc)
                ),
            ]
            aggregator = SignalAggregator(min_sources=2)
            for s in signals:
                aggregator.add_signal(s)
            result = aggregator.get_aggregated_signal('TEST')
            assert result is not None
            assert result.direction == SignalDirection.LONG

        def test_ensemble_generator():
            from core.signal_aggregator import EnsembleSignalGenerator
            ensemble = EnsembleSignalGenerator()
            result = ensemble.generate_ensemble_signal('TEST', {
                'm1': (0.5, 0.8), 'm2': (0.6, 0.75)
            })
            assert result.strength > 0

        self._test("Signal aggregator", test_signal_aggregator)
        self._test("Ensemble generator", test_ensemble_generator)

    def _test_regime_detection(self):
        """Test regime detection module."""
        print("\n[13] Regime Detection")

        def test_hmm_detector():
            from analytics.regime_detection import HMMRegimeDetector
            returns = np.random.randn(200) * 0.02
            hmm = HMMRegimeDetector(n_regimes=3)
            hmm.fit(returns)
            states = hmm.predict(returns)
            assert len(states) == len(returns)

        def test_unified_detector():
            from analytics.regime_detection import MarketRegimeDetector
            prices = 100 * np.exp(np.random.randn(200).cumsum() * 0.02)
            returns = np.diff(prices) / prices[:-1]
            detector = MarketRegimeDetector()
            detector.fit(returns)
            state = detector.detect(prices, returns)
            assert state.primary_regime is not None

        self._test("HMM regime detector", test_hmm_detector)
        self._test("Unified regime detector", test_unified_detector)

    def _test_ensemble_combiner(self):
        """Test ensemble model combiner."""
        print("\n[14] Ensemble Combiner")

        def test_weighted_ensemble():
            from brain.ensemble import WeightedAverageEnsemble, ModelPrediction
            from datetime import datetime, timezone
            preds = {
                'm1': ModelPrediction('m1', 0.6, 0.8, datetime.now(timezone.utc)),
                'm2': ModelPrediction('m2', 0.4, 0.7, datetime.now(timezone.utc)),
            }
            ensemble = WeightedAverageEnsemble()
            result = ensemble.combine(preds)
            assert result.prediction > 0

        def test_ensemble_combiner():
            from brain.ensemble import EnsembleCombiner, EnsembleMethod, ModelPrediction
            from datetime import datetime, timezone
            preds = {
                'm1': ModelPrediction('m1', 0.6, 0.8, datetime.now(timezone.utc)),
                'm2': ModelPrediction('m2', 0.4, 0.7, datetime.now(timezone.utc)),
            }
            combiner = EnsembleCombiner()
            for method in [EnsembleMethod.SIMPLE_AVERAGE, EnsembleMethod.WEIGHTED_AVERAGE]:
                result = combiner.combine(preds, method=method)
                assert result is not None

        self._test("Weighted ensemble", test_weighted_ensemble)
        self._test("Ensemble combiner", test_ensemble_combiner)

    def _test_attribution(self):
        """Test performance attribution."""
        print("\n[15] Performance Attribution")

        def test_brinson():
            from analytics.attribution import BrinsonAttributor
            brinson = BrinsonAttributor()
            result = brinson.attribute(
                portfolio_weights={'a': 0.5, 'b': 0.5},
                portfolio_returns={'a': 0.05, 'b': 0.03},
                benchmark_weights={'a': 0.4, 'b': 0.6},
                benchmark_returns={'a': 0.04, 'b': 0.02},
            )
            assert result.total_active_return != 0

        def test_performance_analyzer():
            from analytics.attribution import PerformanceAnalyzer
            returns = np.random.randn(100) * 0.01
            benchmark = np.random.randn(100) * 0.008
            analyzer = PerformanceAnalyzer()
            result = analyzer.analyze(returns, benchmark_returns=benchmark)
            assert 'basic' in result
            assert 'sharpe_ratio' in result['basic']

        self._test("Brinson attribution", test_brinson)
        self._test("Performance analyzer", test_performance_analyzer)


def main():
    """Run all tests."""
    tester = SystemTester()
    passed, failed = tester.run_all()
    # Add new test methods
    tester._test_signal_aggregation()
    tester._test_regime_detection()
    tester._test_ensemble_combiner()
    tester._test_attribution()

    # Update summary with new tests
    passed = sum(1 for r in tester.results if r.passed)
    failed = len(tester.results) - passed

    print("\n" + "=" * 70)
    print("FINAL SUMMARY (Including New Modules)")
    print("=" * 70)
    print(f"Total Tests: {len(tester.results)}")
    print(f"Passed: {passed} ({passed/len(tester.results)*100:.1f}%)")
    print(f"Failed: {failed}")
    print("=" * 70)

    if failed > 0:
        print(f"\n[WARNING] {failed} test(s) failed!")
        return 1
    else:
        print("\n[SUCCESS] All tests passed!")
        return 0


if __name__ == "__main__":
    exit(main())
