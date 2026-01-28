"""
QUANT_INDUSTRY_V1 Autonomous Alpha Discovery Agent

Self-improving AI agent that autonomously discovers, tests, and deploys trading strategies.

Features:
- Continuous hypothesis generation
- Automated backtesting and validation
- Strategy evolution via genetic algorithms
- Performance monitoring and decay detection
- Automatic strategy rotation
- Research report generation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from datetime import datetime, timezone, timedelta
import threading
import time
import json
import logging
from pathlib import Path
import hashlib

from .hypothesis import (
    AlphaHypothesis, HypothesisGenerator, HypothesisTester,
    HypothesisType, HypothesisStatus, HypothesisCondition,
)
from .genetic import StrategyEvolver, IslandModel, StrategyGenome
from .backtester import (
    FastBacktester, BacktestResult,
    WalkForwardAnalyzer, MonteCarloSimulator,
)

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT STATE
# =============================================================================

class AgentState(Enum):
    """Agent operational states."""
    IDLE = "idle"
    EXPLORING = "exploring"          # Generating new hypotheses
    TESTING = "testing"              # Backtesting hypotheses
    EVOLVING = "evolving"            # Running genetic optimization
    VALIDATING = "validating"        # Final validation
    MONITORING = "monitoring"        # Watching deployed strategies
    SLEEPING = "sleeping"            # Resource conservation


@dataclass
class StrategyPerformance:
    """Tracks deployed strategy performance."""
    hypothesis_id: str
    deployed_at: datetime
    initial_sharpe: float
    current_sharpe: float
    cumulative_return: float
    num_trades: int
    last_trade_date: Optional[datetime] = None
    decay_score: float = 0.0  # 0 = healthy, 1 = fully decayed


@dataclass
class ResearchReport:
    """Auto-generated research report for a strategy."""
    hypothesis: AlphaHypothesis
    backtest_result: BacktestResult
    walk_forward_result: Dict[str, Any]
    monte_carlo_result: Dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        """Generate markdown report."""
        h = self.hypothesis
        bt = self.backtest_result
        wf = self.walk_forward_result
        mc = self.monte_carlo_result

        report = f"""# Alpha Research Report: {h.name}

**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Hypothesis ID:** {h.hypothesis_id}
**Type:** {h.hypothesis_type.value}

## Executive Summary

This strategy was autonomously discovered and validated by the QUANT_INDUSTRY_V1 Alpha Discovery Agent.

- **Sharpe Ratio:** {bt.sharpe_ratio:.2f}
- **Total Return:** {bt.total_return * 100:.1f}%
- **Max Drawdown:** {bt.max_drawdown * 100:.1f}%
- **Win Rate:** {bt.win_rate * 100:.1f}%
- **Statistical Significance:** p-value = {bt.p_value:.4f}

## Strategy Description

{h.description}

**Direction:** {'Long' if h.direction == 1 else 'Short'}

### Entry Conditions
"""
        for i, cond in enumerate(h.entry_conditions, 1):
            report += f"{i}. `{cond.feature}` {cond.operator} {cond.value:.4f}\n"

        report += """
### Exit Conditions
"""
        for i, cond in enumerate(h.exit_conditions, 1):
            report += f"{i}. `{cond.feature}` {cond.operator} {cond.value:.4f}\n"

        report += f"""
### Risk Parameters
- Stop Loss: {h.stop_loss_pct * 100:.1f}%
- Take Profit: {h.take_profit_pct * 100:.1f}%
- Max Holding Period: {h.max_holding_days} days
- Position Size: {h.position_size_pct * 100:.1f}%

## Backtest Results

| Metric | Value |
|--------|-------|
| Total Return | {bt.total_return * 100:.2f}% |
| Annualized Return | {bt.annualized_return * 100:.2f}% |
| Sharpe Ratio | {bt.sharpe_ratio:.2f} |
| Sortino Ratio | {bt.sortino_ratio:.2f} |
| Calmar Ratio | {bt.calmar_ratio:.2f} |
| Max Drawdown | {bt.max_drawdown * 100:.2f}% |
| Volatility | {bt.volatility * 100:.2f}% |
| Number of Trades | {bt.num_trades} |
| Win Rate | {bt.win_rate * 100:.1f}% |
| Profit Factor | {bt.profit_factor:.2f} |
| Avg Trade Return | {bt.avg_trade_return * 100:.3f}% |
| Avg Holding Period | {bt.avg_holding_period:.1f} days |

## Walk-Forward Analysis

"""
        if wf.get('valid'):
            report += f"""
- **Out-of-Sample Sharpe:** {wf.get('oos_sharpe', 0):.2f}
- **Consistency:** {wf.get('consistency', 0) * 100:.0f}% profitable splits
- **Total OOS Trades:** {wf.get('total_trades', 0)}
"""
        else:
            report += f"Walk-forward analysis failed: {wf.get('reason', 'unknown')}\n"

        report += """
## Monte Carlo Simulation

"""
        if mc.get('valid'):
            report += f"""
Based on {1000} bootstrap simulations:

| Metric | 5th Percentile | Mean | 95th Percentile |
|--------|----------------|------|-----------------|
| Sharpe Ratio | {mc.get('sharpe_5pct', 0):.2f} | {mc.get('sharpe_mean', 0):.2f} | {mc.get('sharpe_95pct', 0):.2f} |
| Max Drawdown | {mc.get('max_dd_5pct', 0) * 100:.1f}% | {mc.get('max_dd_mean', 0) * 100:.1f}% | {mc.get('max_dd_95pct', 0) * 100:.1f}% |
| Total Return | {mc.get('return_5pct', 0) * 100:.1f}% | {mc.get('return_mean', 0) * 100:.1f}% | {mc.get('return_95pct', 0) * 100:.1f}% |

- **Probability of Profit:** {mc.get('prob_profitable', 0) * 100:.1f}%
- **Probability of Positive Sharpe:** {mc.get('prob_sharpe_positive', 0) * 100:.1f}%
"""
        else:
            report += f"Monte Carlo simulation failed: {mc.get('reason', 'unknown')}\n"

        report += """
## Statistical Validation

- **T-Statistic:** {:.2f}
- **P-Value:** {:.4f}
- **Statistically Significant:** {}

## Risk Warnings

1. Past performance does not guarantee future results
2. This strategy was discovered through automated optimization
3. Market conditions may change, reducing strategy effectiveness
4. Always use proper position sizing and risk management

---
*Generated by QUANT_INDUSTRY_V1 Alpha Discovery Agent*
""".format(
            bt.t_statistic,
            bt.p_value,
            "Yes" if bt.p_value < 0.05 else "No"
        )

        return report


# =============================================================================
# ALPHA DISCOVERY AGENT
# =============================================================================

class AlphaDiscoveryAgent:
    """
    Autonomous agent for discovering and managing trading strategies.

    This agent continuously:
    1. Generates new trading hypotheses
    2. Tests them via backtesting
    3. Evolves promising strategies
    4. Validates with walk-forward analysis
    5. Deploys validated strategies
    6. Monitors for performance decay
    7. Rotates underperforming strategies
    """

    def __init__(
        self,
        data_provider: Callable[[], Tuple[np.ndarray, Dict[str, np.ndarray]]],
        output_dir: str = "./alpha_research",
        max_deployed_strategies: int = 10,
        min_sharpe_threshold: float = 0.75,
        max_correlation: float = 0.7,
        decay_threshold: float = 0.5,
        exploration_interval: int = 3600,  # 1 hour
        seed: int = None,
    ):
        """
        Initialize the Alpha Discovery Agent.

        Args:
            data_provider: Callable that returns (prices, features) for backtesting
            output_dir: Directory for saving research reports
            max_deployed_strategies: Maximum concurrent strategies
            min_sharpe_threshold: Minimum Sharpe for deployment
            max_correlation: Maximum correlation between strategies
            decay_threshold: Threshold for strategy decay detection
            exploration_interval: Seconds between exploration cycles
        """
        self.data_provider = data_provider
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_deployed = max_deployed_strategies
        self.min_sharpe = min_sharpe_threshold
        self.max_correlation = max_correlation
        self.decay_threshold = decay_threshold
        self.exploration_interval = exploration_interval

        # Components
        self.generator = HypothesisGenerator(seed)
        self.tester = HypothesisTester()
        self.backtester = FastBacktester()
        self.walk_forward = WalkForwardAnalyzer()
        self.monte_carlo = MonteCarloSimulator(seed=seed)
        self.evolver = StrategyEvolver(seed=seed)

        # State
        self.state = AgentState.IDLE
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Strategy pools
        self.candidate_pool: List[AlphaHypothesis] = []
        self.validated_pool: List[AlphaHypothesis] = []
        self.deployed_strategies: Dict[str, StrategyPerformance] = {}
        self.retired_strategies: List[str] = []

        # Performance tracking
        self.exploration_count = 0
        self.hypotheses_tested = 0
        self.strategies_deployed = 0
        self.strategies_retired = 0

        # Research reports
        self.reports: Dict[str, ResearchReport] = {}

        logger.info("Alpha Discovery Agent initialized")

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def start(self) -> None:
        """Start the autonomous agent."""
        if self._thread and self._thread.is_alive():
            logger.warning("Agent already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Alpha Discovery Agent started")

    def stop(self) -> None:
        """Stop the agent."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.state = AgentState.IDLE
        logger.info("Alpha Discovery Agent stopped")

    def _run_loop(self) -> None:
        """Main agent loop."""
        while not self._stop_event.is_set():
            try:
                # Exploration phase
                self.state = AgentState.EXPLORING
                self._explore()

                # Testing phase
                self.state = AgentState.TESTING
                self._test_candidates()

                # Evolution phase (periodic)
                if self.exploration_count % 5 == 0:
                    self.state = AgentState.EVOLVING
                    self._evolve_strategies()

                # Validation phase
                self.state = AgentState.VALIDATING
                self._validate_candidates()

                # Monitoring phase
                self.state = AgentState.MONITORING
                self._monitor_deployed()

                # Deployment decisions
                self._update_deployments()

                self.exploration_count += 1

            except Exception as e:
                logger.error(f"Agent error: {e}")

            # Sleep until next cycle
            self.state = AgentState.SLEEPING
            self._stop_event.wait(self.exploration_interval)

    # =========================================================================
    # EXPLORATION
    # =========================================================================

    def _explore(self) -> None:
        """Generate new trading hypotheses."""
        logger.info("Exploring new hypotheses...")

        new_hypotheses = []

        # Generate random hypotheses
        for _ in range(20):
            h = self.generator.generate_random()
            new_hypotheses.append(h)

        # Generate type-specific hypotheses
        for _ in range(5):
            new_hypotheses.append(self.generator.generate_momentum())
            new_hypotheses.append(self.generator.generate_mean_reversion())
            new_hypotheses.append(self.generator.generate_breakout())

        # Deduplicate
        seen = set()
        for h in new_hypotheses:
            hash_key = h.get_hash()
            if hash_key not in seen:
                seen.add(hash_key)
                self.candidate_pool.append(h)

        logger.info(f"Generated {len(new_hypotheses)} new hypotheses, pool size: {len(self.candidate_pool)}")

    # =========================================================================
    # TESTING
    # =========================================================================

    def _test_candidates(self) -> None:
        """Backtest candidate hypotheses."""
        if not self.candidate_pool:
            return

        logger.info(f"Testing {len(self.candidate_pool)} candidates...")

        # Get market data
        prices, features = self.data_provider()

        # Test each candidate
        tested = []
        for hypothesis in self.candidate_pool:
            try:
                result = self.backtester.backtest(
                    hypothesis=hypothesis,
                    prices=prices,
                    features=features,
                )

                # Update hypothesis with results
                hypothesis.sharpe_ratio = result.sharpe_ratio
                hypothesis.sortino_ratio = result.sortino_ratio
                hypothesis.win_rate = result.win_rate
                hypothesis.profit_factor = result.profit_factor
                hypothesis.max_drawdown = result.max_drawdown
                hypothesis.total_return = result.total_return
                hypothesis.num_trades = result.num_trades
                hypothesis.t_statistic = result.t_statistic
                hypothesis.p_value = result.p_value
                hypothesis.last_tested = datetime.now(timezone.utc)

                if result.is_valid(min_sharpe=self.min_sharpe * 0.8):
                    hypothesis.status = HypothesisStatus.TESTING
                    tested.append(hypothesis)
                else:
                    hypothesis.status = HypothesisStatus.REJECTED

                self.hypotheses_tested += 1

            except Exception as e:
                logger.error(f"Testing error for {hypothesis.hypothesis_id}: {e}")
                hypothesis.status = HypothesisStatus.REJECTED

        # Keep promising candidates
        self.candidate_pool = tested
        logger.info(f"Retained {len(tested)} promising candidates")

    # =========================================================================
    # EVOLUTION
    # =========================================================================

    def _evolve_strategies(self) -> None:
        """Evolve strategies using genetic algorithms."""
        logger.info("Running genetic evolution...")

        prices, features = self.data_provider()

        # Define evaluation function
        def evaluate_hypothesis(h: AlphaHypothesis) -> np.ndarray:
            result = self.backtester.backtest(h, prices, features)
            if result.num_trades > 0:
                return result.daily_returns
            return np.array([])

        # Initialize with current candidates
        self.evolver.initialize_population(self.candidate_pool)

        # Evolve
        evolved = self.evolver.evolve(
            evaluate_fn=evaluate_hypothesis,
            n_generations=20,
            early_stop_generations=5,
        )

        # Add evolved strategies to candidate pool
        for h in evolved:
            if h.get_hash() not in {c.get_hash() for c in self.candidate_pool}:
                self.candidate_pool.append(h)

        logger.info(f"Evolution produced {len(evolved)} strategies")

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def _validate_candidates(self) -> None:
        """Perform rigorous validation on candidates."""
        if not self.candidate_pool:
            return

        logger.info(f"Validating {len(self.candidate_pool)} candidates...")

        prices, features = self.data_provider()
        validated = []

        for hypothesis in self.candidate_pool:
            try:
                # Walk-forward analysis
                wf_result = self.walk_forward.analyze(
                    hypothesis=hypothesis,
                    prices=prices,
                    features=features,
                    backtester=self.backtester,
                )

                if not wf_result.get('valid') or wf_result.get('oos_sharpe', 0) < self.min_sharpe * 0.7:
                    hypothesis.status = HypothesisStatus.REJECTED
                    continue

                # Monte Carlo simulation
                bt_result = self.backtester.backtest(hypothesis, prices, features)
                mc_result = self.monte_carlo.run_simulation(bt_result)

                if not mc_result.get('valid') or mc_result.get('prob_sharpe_positive', 0) < 0.6:
                    hypothesis.status = HypothesisStatus.REJECTED
                    continue

                # Check final criteria
                if (
                    hypothesis.sharpe_ratio >= self.min_sharpe and
                    hypothesis.p_value < 0.05 and
                    wf_result.get('consistency', 0) >= 0.5
                ):
                    hypothesis.status = HypothesisStatus.VALIDATED
                    validated.append(hypothesis)

                    # Generate research report
                    report = ResearchReport(
                        hypothesis=hypothesis,
                        backtest_result=bt_result,
                        walk_forward_result=wf_result,
                        monte_carlo_result=mc_result,
                    )
                    self.reports[hypothesis.hypothesis_id] = report
                    self._save_report(report)

            except Exception as e:
                logger.error(f"Validation error for {hypothesis.hypothesis_id}: {e}")

        self.validated_pool.extend(validated)
        self.candidate_pool = []  # Clear tested candidates

        logger.info(f"Validated {len(validated)} strategies")

    def _save_report(self, report: ResearchReport) -> None:
        """Save research report to disk."""
        filename = f"{report.hypothesis.hypothesis_id}_{report.generated_at.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = self.output_dir / filename

        try:
            with open(filepath, 'w') as f:
                f.write(report.to_markdown())
            logger.info(f"Saved report: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    # =========================================================================
    # MONITORING
    # =========================================================================

    def _monitor_deployed(self) -> None:
        """Monitor deployed strategies for decay."""
        if not self.deployed_strategies:
            return

        logger.info(f"Monitoring {len(self.deployed_strategies)} deployed strategies...")

        prices, features = self.data_provider()

        for strategy_id, perf in list(self.deployed_strategies.items()):
            try:
                # Find hypothesis
                hypothesis = next(
                    (h for h in self.validated_pool if h.hypothesis_id == strategy_id),
                    None
                )
                if not hypothesis:
                    continue

                # Recent backtest
                result = self.backtester.backtest(hypothesis, prices[-252:],
                    {k: v[-252:] for k, v in features.items()})

                # Update performance
                perf.current_sharpe = result.sharpe_ratio
                perf.cumulative_return += result.total_return
                perf.num_trades += result.num_trades

                # Calculate decay score
                if perf.initial_sharpe > 0:
                    decay = 1 - (perf.current_sharpe / perf.initial_sharpe)
                    perf.decay_score = max(0, min(1, decay))
                else:
                    perf.decay_score = 1.0

                # Check for retirement
                if perf.decay_score >= self.decay_threshold:
                    logger.warning(
                        f"Strategy {strategy_id} showing decay: "
                        f"initial={perf.initial_sharpe:.2f}, current={perf.current_sharpe:.2f}"
                    )

            except Exception as e:
                logger.error(f"Monitoring error for {strategy_id}: {e}")

    # =========================================================================
    # DEPLOYMENT
    # =========================================================================

    def _update_deployments(self) -> None:
        """Update strategy deployments."""
        # Retire decayed strategies
        for strategy_id, perf in list(self.deployed_strategies.items()):
            if perf.decay_score >= self.decay_threshold:
                self._retire_strategy(strategy_id)

        # Check correlation with existing strategies
        def get_strategy_returns(h: AlphaHypothesis) -> np.ndarray:
            prices, features = self.data_provider()
            result = self.backtester.backtest(h, prices, features)
            return result.daily_returns

        # Deploy new strategies if space available
        while (
            len(self.deployed_strategies) < self.max_deployed and
            self.validated_pool
        ):
            # Sort by Sharpe
            self.validated_pool.sort(key=lambda h: h.sharpe_ratio, reverse=True)
            candidate = self.validated_pool[0]

            # Check correlation with deployed
            can_deploy = True
            if self.deployed_strategies:
                candidate_returns = get_strategy_returns(candidate)
                for strategy_id in self.deployed_strategies:
                    deployed_h = next(
                        (h for h in self.validated_pool if h.hypothesis_id == strategy_id),
                        None
                    )
                    if deployed_h:
                        deployed_returns = get_strategy_returns(deployed_h)
                        if len(candidate_returns) > 0 and len(deployed_returns) > 0:
                            min_len = min(len(candidate_returns), len(deployed_returns))
                            corr = np.corrcoef(
                                candidate_returns[:min_len],
                                deployed_returns[:min_len]
                            )[0, 1]
                            if abs(corr) > self.max_correlation:
                                can_deploy = False
                                break

            if can_deploy:
                self._deploy_strategy(candidate)
                self.validated_pool.remove(candidate)
            else:
                # Try next candidate
                self.validated_pool.remove(candidate)
                self.validated_pool.append(candidate)  # Move to end
                break

    def _deploy_strategy(self, hypothesis: AlphaHypothesis) -> None:
        """Deploy a validated strategy."""
        hypothesis.status = HypothesisStatus.DEPLOYED

        perf = StrategyPerformance(
            hypothesis_id=hypothesis.hypothesis_id,
            deployed_at=datetime.now(timezone.utc),
            initial_sharpe=hypothesis.sharpe_ratio,
            current_sharpe=hypothesis.sharpe_ratio,
            cumulative_return=0.0,
            num_trades=0,
        )

        self.deployed_strategies[hypothesis.hypothesis_id] = perf
        self.strategies_deployed += 1

        logger.info(
            f"Deployed strategy {hypothesis.hypothesis_id} "
            f"(Sharpe: {hypothesis.sharpe_ratio:.2f})"
        )

    def _retire_strategy(self, strategy_id: str) -> None:
        """Retire an underperforming strategy."""
        if strategy_id in self.deployed_strategies:
            del self.deployed_strategies[strategy_id]
            self.retired_strategies.append(strategy_id)
            self.strategies_retired += 1

            # Update hypothesis status
            for h in self.validated_pool:
                if h.hypothesis_id == strategy_id:
                    h.status = HypothesisStatus.DEPRECATED
                    break

            logger.info(f"Retired strategy {strategy_id}")

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def get_deployed_strategies(self) -> List[AlphaHypothesis]:
        """Get currently deployed strategies."""
        deployed = []
        for strategy_id in self.deployed_strategies:
            for h in self.validated_pool:
                if h.hypothesis_id == strategy_id:
                    deployed.append(h)
                    break
        return deployed

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            'state': self.state.value,
            'exploration_count': self.exploration_count,
            'hypotheses_tested': self.hypotheses_tested,
            'candidate_pool_size': len(self.candidate_pool),
            'validated_pool_size': len(self.validated_pool),
            'deployed_count': len(self.deployed_strategies),
            'retired_count': self.strategies_retired,
            'deployed_strategies': [
                {
                    'id': sid,
                    'initial_sharpe': p.initial_sharpe,
                    'current_sharpe': p.current_sharpe,
                    'decay_score': p.decay_score,
                    'cumulative_return': p.cumulative_return,
                }
                for sid, p in self.deployed_strategies.items()
            ],
        }

    def force_exploration(self) -> None:
        """Trigger immediate exploration cycle."""
        if self.state == AgentState.SLEEPING:
            self._stop_event.set()  # Wake up
            time.sleep(0.1)
            self._stop_event.clear()

    def get_report(self, hypothesis_id: str) -> Optional[str]:
        """Get research report for a hypothesis."""
        report = self.reports.get(hypothesis_id)
        if report:
            return report.to_markdown()
        return None

    def export_strategies(self, filepath: str) -> None:
        """Export all strategies to JSON."""
        data = {
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'deployed': [
                h.to_dict() for h in self.get_deployed_strategies()
            ],
            'validated': [
                h.to_dict() for h in self.validated_pool
            ],
            'performance': {
                sid: {
                    'initial_sharpe': p.initial_sharpe,
                    'current_sharpe': p.current_sharpe,
                    'cumulative_return': p.cumulative_return,
                    'decay_score': p.decay_score,
                }
                for sid, p in self.deployed_strategies.items()
            }
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported strategies to {filepath}")


# =============================================================================
# FACTORY
# =============================================================================

def create_alpha_agent(
    data_provider: Callable[[], Tuple[np.ndarray, Dict[str, np.ndarray]]],
    config: Dict[str, Any] = None,
) -> AlphaDiscoveryAgent:
    """
    Factory function to create an Alpha Discovery Agent.

    Args:
        data_provider: Function that returns (prices, features)
        config: Optional configuration overrides

    Returns:
        Configured AlphaDiscoveryAgent
    """
    config = config or {}

    return AlphaDiscoveryAgent(
        data_provider=data_provider,
        output_dir=config.get('output_dir', './alpha_research'),
        max_deployed_strategies=config.get('max_deployed', 10),
        min_sharpe_threshold=config.get('min_sharpe', 0.75),
        max_correlation=config.get('max_correlation', 0.7),
        decay_threshold=config.get('decay_threshold', 0.5),
        exploration_interval=config.get('exploration_interval', 3600),
        seed=config.get('seed'),
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'AgentState',
    'StrategyPerformance',
    'ResearchReport',
    'AlphaDiscoveryAgent',
    'create_alpha_agent',
]
