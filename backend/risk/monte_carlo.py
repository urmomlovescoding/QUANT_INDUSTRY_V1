"""
QUANT INDUSTRY - Monte Carlo Stress Testing
============================================
Institutional-grade risk simulation:
- Portfolio return simulation
- Tail risk analysis (VaR, CVaR, Expected Shortfall)
- Stress scenarios (2008, 2020 March, Flash Crash)
- Correlation breakdown simulation
- Regime-conditional simulation

This answers: "What's the worst that could realistically happen?"

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class StressScenario(Enum):
    """Pre-defined stress scenarios"""
    NORMAL = "normal"                    # Normal market conditions
    HIGH_VOL = "high_vol"                # 2x normal volatility
    CRISIS_2008 = "crisis_2008"          # 2008 financial crisis
    COVID_CRASH = "covid_crash"          # March 2020 crash
    FLASH_CRASH = "flash_crash"          # May 2010 flash crash
    CORRELATION_SPIKE = "corr_spike"     # All correlations go to 1
    LIQUIDITY_CRISIS = "liquidity"       # Volume dries up
    BLACK_SWAN = "black_swan"            # 6+ sigma event


@dataclass
class StressParameters:
    """Parameters for stress scenarios"""
    vol_multiplier: float = 1.0          # Multiply normal vol
    correlation_override: Optional[float] = None  # Force correlation
    mean_shift: float = 0.0              # Shift in daily return mean
    fat_tails_df: float = 30.0           # t-distribution df (lower = fatter)
    max_daily_move: float = 0.20         # Maximum single-day move
    liquidity_factor: float = 1.0        # Multiplier for slippage
    gap_probability: float = 0.0         # Probability of gap open


# Pre-defined stress scenarios
STRESS_SCENARIOS = {
    StressScenario.NORMAL: StressParameters(),
    StressScenario.HIGH_VOL: StressParameters(
        vol_multiplier=2.0,
        fat_tails_df=10.0
    ),
    StressScenario.CRISIS_2008: StressParameters(
        vol_multiplier=4.0,
        correlation_override=0.8,
        mean_shift=-0.002,  # -0.2% daily drag
        fat_tails_df=5.0,
        liquidity_factor=3.0
    ),
    StressScenario.COVID_CRASH: StressParameters(
        vol_multiplier=5.0,
        correlation_override=0.9,
        mean_shift=-0.005,  # -0.5% daily drag
        fat_tails_df=4.0,
        max_daily_move=0.15,
        gap_probability=0.2
    ),
    StressScenario.FLASH_CRASH: StressParameters(
        vol_multiplier=10.0,
        fat_tails_df=3.0,
        max_daily_move=0.10,
        gap_probability=0.5,
        liquidity_factor=10.0
    ),
    StressScenario.CORRELATION_SPIKE: StressParameters(
        vol_multiplier=1.5,
        correlation_override=0.95
    ),
    StressScenario.LIQUIDITY_CRISIS: StressParameters(
        vol_multiplier=2.0,
        liquidity_factor=5.0,
        gap_probability=0.1
    ),
    StressScenario.BLACK_SWAN: StressParameters(
        vol_multiplier=8.0,
        fat_tails_df=2.5,
        mean_shift=-0.01,
        max_daily_move=0.25,
        gap_probability=0.3
    ),
}


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    n_simulations: int
    n_days: int
    scenario: StressScenario
    
    # Terminal wealth distribution
    final_values: np.ndarray = field(repr=False)
    
    # Summary statistics
    mean_return: float = 0.0
    median_return: float = 0.0
    std_return: float = 0.0
    
    # Risk metrics
    var_95: float = 0.0          # 5th percentile (95% VaR)
    var_99: float = 0.0          # 1st percentile (99% VaR)
    cvar_95: float = 0.0         # Expected shortfall at 95%
    cvar_99: float = 0.0         # Expected shortfall at 99%
    
    # Drawdown metrics
    max_drawdown_mean: float = 0.0
    max_drawdown_95th: float = 0.0
    max_drawdown_99th: float = 0.0
    
    # Probability metrics
    prob_loss: float = 0.0       # P(return < 0)
    prob_ruin: float = 0.0       # P(drawdown > 50%)
    prob_target: float = 0.0     # P(return > target)
    
    # Paths for visualization
    sample_paths: np.ndarray = field(default=None, repr=False)
    
    def summary(self) -> str:
        return f"""
Monte Carlo Simulation Results
==============================
Scenario: {self.scenario.value}
Simulations: {self.n_simulations:,}
Horizon: {self.n_days} days

Return Distribution:
  Mean: {self.mean_return:.2%}
  Median: {self.median_return:.2%}
  Std Dev: {self.std_return:.2%}

Value at Risk:
  VaR 95%: {self.var_95:.2%}
  VaR 99%: {self.var_99:.2%}
  CVaR 95%: {self.cvar_95:.2%}
  CVaR 99%: {self.cvar_99:.2%}

Maximum Drawdown:
  Mean: {self.max_drawdown_mean:.2%}
  95th %ile: {self.max_drawdown_95th:.2%}
  99th %ile: {self.max_drawdown_99th:.2%}

Probabilities:
  P(Loss): {self.prob_loss:.1%}
  P(Ruin): {self.prob_ruin:.1%}
  P(Target): {self.prob_target:.1%}
"""


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for portfolio risk analysis.
    
    Features:
    1. Multiple stress scenarios
    2. Fat-tailed distributions (Student-t)
    3. Correlation matrix simulation
    4. Drawdown path analysis
    5. VaR/CVaR calculation
    
    Usage:
    ------
    >>> simulator = MonteCarloSimulator(
    ...     daily_return=0.0005,     # 0.05% daily
    ...     daily_volatility=0.015,  # 1.5% daily vol
    ...     initial_capital=100_000
    ... )
    >>> 
    >>> # Normal conditions
    >>> result = simulator.run(n_simulations=10000, n_days=252)
    >>> print(result.summary())
    >>>
    >>> # Stress test
    >>> stress_result = simulator.run_stress_test(StressScenario.CRISIS_2008)
    >>> print(f"99% VaR in crisis: {stress_result.var_99:.2%}")
    """
    
    def __init__(
        self,
        daily_return: float = 0.0005,    # Expected daily return
        daily_volatility: float = 0.015,  # Daily volatility
        initial_capital: float = 100_000,
        target_return: float = 0.20,      # Annual target for prob calc
        ruin_threshold: float = 0.50,     # Drawdown level = ruin
        seed: int = None
    ):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            daily_return: Expected daily return (e.g., 0.0005 = 0.05%)
            daily_volatility: Daily volatility (e.g., 0.015 = 1.5%)
            initial_capital: Starting capital
            target_return: Target annual return for probability calculation
            ruin_threshold: Drawdown level considered "ruin"
            seed: Random seed for reproducibility
        """
        self.daily_return = daily_return
        self.daily_volatility = daily_volatility
        self.initial_capital = initial_capital
        self.target_return = target_return
        self.ruin_threshold = ruin_threshold
        
        if seed is not None:
            np.random.seed(seed)
        
        logger.info(
            f"MonteCarloSimulator initialized: "
            f"μ={daily_return:.4f}, σ={daily_volatility:.4f}"
        )
    
    def run(
        self,
        n_simulations: int = 10000,
        n_days: int = 252,
        scenario: StressScenario = StressScenario.NORMAL,
        return_paths: bool = False,
        n_sample_paths: int = 100
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Args:
            n_simulations: Number of simulation paths
            n_days: Number of trading days to simulate
            scenario: Stress scenario to use
            return_paths: Whether to return sample paths
            n_sample_paths: Number of paths to return for visualization
            
        Returns:
            MonteCarloResult with full statistics
        """
        params = STRESS_SCENARIOS.get(scenario, StressParameters())
        
        # Adjust parameters for scenario
        mu = self.daily_return + params.mean_shift
        sigma = self.daily_volatility * params.vol_multiplier
        df = params.fat_tails_df
        
        # Generate returns
        # Use Student-t for fat tails, scaled to match target volatility
        if df < 30:
            # t-distribution has variance = df / (df - 2) for df > 2
            scale = sigma * np.sqrt((df - 2) / df) if df > 2 else sigma
            returns = stats.t.rvs(df, loc=mu, scale=scale, size=(n_simulations, n_days))
        else:
            # Normal distribution
            returns = np.random.normal(mu, sigma, size=(n_simulations, n_days))
        
        # Apply maximum daily move constraint
        returns = np.clip(returns, -params.max_daily_move, params.max_daily_move)
        
        # Apply gap opens (random large moves)
        if params.gap_probability > 0:
            gap_mask = np.random.random(size=(n_simulations, n_days)) < params.gap_probability
            gap_returns = np.random.normal(-0.03, 0.02, size=(n_simulations, n_days))  # Gap down bias
            returns = np.where(gap_mask, returns + gap_returns, returns)
        
        # Calculate cumulative returns and portfolio values
        cumulative_returns = np.cumprod(1 + returns, axis=1)
        portfolio_values = self.initial_capital * cumulative_returns
        
        # Final values
        final_values = portfolio_values[:, -1]
        total_returns = (final_values / self.initial_capital) - 1
        
        # Calculate drawdowns for each path
        running_max = np.maximum.accumulate(portfolio_values, axis=1)
        drawdowns = (running_max - portfolio_values) / running_max
        max_drawdowns = np.max(drawdowns, axis=1)
        
        # Calculate metrics
        result = MonteCarloResult(
            n_simulations=n_simulations,
            n_days=n_days,
            scenario=scenario,
            final_values=final_values,
            
            # Return stats
            mean_return=np.mean(total_returns),
            median_return=np.median(total_returns),
            std_return=np.std(total_returns),
            
            # VaR (negative returns at percentiles)
            var_95=np.percentile(total_returns, 5),
            var_99=np.percentile(total_returns, 1),
            
            # CVaR (mean of returns below VaR)
            cvar_95=np.mean(total_returns[total_returns <= np.percentile(total_returns, 5)]),
            cvar_99=np.mean(total_returns[total_returns <= np.percentile(total_returns, 1)]),
            
            # Drawdown stats
            max_drawdown_mean=np.mean(max_drawdowns),
            max_drawdown_95th=np.percentile(max_drawdowns, 95),
            max_drawdown_99th=np.percentile(max_drawdowns, 99),
            
            # Probabilities
            prob_loss=np.mean(total_returns < 0),
            prob_ruin=np.mean(max_drawdowns > self.ruin_threshold),
            prob_target=np.mean(total_returns > self.target_return),
        )
        
        # Store sample paths if requested
        if return_paths:
            indices = np.random.choice(n_simulations, min(n_sample_paths, n_simulations), replace=False)
            result.sample_paths = portfolio_values[indices]
        
        return result
    
    def run_stress_test(
        self,
        scenario: StressScenario,
        n_simulations: int = 10000,
        n_days: int = 63  # ~3 months for stress
    ) -> MonteCarloResult:
        """
        Run stress test with specific scenario.
        
        Args:
            scenario: Stress scenario to simulate
            n_simulations: Number of paths
            n_days: Stress period duration
            
        Returns:
            MonteCarloResult for stress scenario
        """
        return self.run(
            n_simulations=n_simulations,
            n_days=n_days,
            scenario=scenario,
            return_paths=True,
            n_sample_paths=50
        )
    
    def run_all_scenarios(
        self,
        n_simulations: int = 5000,
        n_days: int = 252
    ) -> Dict[StressScenario, MonteCarloResult]:
        """
        Run simulation across all stress scenarios.
        
        Returns:
            Dict mapping scenario to results
        """
        results = {}
        
        for scenario in StressScenario:
            logger.info(f"Running scenario: {scenario.value}")
            results[scenario] = self.run(
                n_simulations=n_simulations,
                n_days=n_days,
                scenario=scenario
            )
        
        return results
    
    def compare_scenarios(
        self,
        n_simulations: int = 5000,
        n_days: int = 252
    ) -> pd.DataFrame:
        """
        Compare key metrics across all scenarios.
        
        Returns:
            DataFrame with scenario comparison
        """
        results = self.run_all_scenarios(n_simulations, n_days)
        
        comparison = []
        for scenario, result in results.items():
            comparison.append({
                "Scenario": scenario.value,
                "Mean Return": f"{result.mean_return:.1%}",
                "VaR 95%": f"{result.var_95:.1%}",
                "VaR 99%": f"{result.var_99:.1%}",
                "CVaR 99%": f"{result.cvar_99:.1%}",
                "Max DD 95th": f"{result.max_drawdown_95th:.1%}",
                "P(Loss)": f"{result.prob_loss:.0%}",
                "P(Ruin)": f"{result.prob_ruin:.1%}",
            })
        
        return pd.DataFrame(comparison)
    
    def calculate_position_var(
        self,
        position_value: float,
        holding_period_days: int = 1,
        confidence: float = 0.95
    ) -> float:
        """
        Calculate VaR for a single position.
        
        Args:
            position_value: Notional value of position
            holding_period_days: How long position will be held
            confidence: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            Value at Risk in dollars
        """
        # Scale volatility for holding period
        period_vol = self.daily_volatility * np.sqrt(holding_period_days)
        
        # VaR using normal distribution
        z_score = stats.norm.ppf(1 - confidence)
        var_pct = z_score * period_vol
        
        return abs(var_pct * position_value)


class PortfolioMonteCarloSimulator:
    """
    Multi-asset portfolio Monte Carlo simulation.
    
    Handles correlation between assets and correlation breakdown scenarios.
    """
    
    def __init__(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        weights: np.ndarray,
        initial_capital: float = 100_000,
        asset_names: List[str] = None
    ):
        """
        Initialize portfolio simulator.
        
        Args:
            expected_returns: Array of expected daily returns per asset
            covariance_matrix: Covariance matrix of returns
            weights: Portfolio weights
            initial_capital: Starting capital
            asset_names: Names for each asset
        """
        self.expected_returns = np.array(expected_returns)
        self.cov_matrix = np.array(covariance_matrix)
        self.weights = np.array(weights)
        self.initial_capital = initial_capital
        self.n_assets = len(weights)
        self.asset_names = asset_names or [f"Asset_{i}" for i in range(self.n_assets)]
        
        # Portfolio expected return and volatility
        self.portfolio_return = np.dot(weights, expected_returns)
        self.portfolio_vol = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))
        
        logger.info(
            f"PortfolioMonteCarloSimulator: {self.n_assets} assets, "
            f"μ_p={self.portfolio_return:.4f}, σ_p={self.portfolio_vol:.4f}"
        )
    
    def run(
        self,
        n_simulations: int = 10000,
        n_days: int = 252,
        correlation_stress: float = None
    ) -> MonteCarloResult:
        """
        Run portfolio Monte Carlo simulation.
        
        Args:
            n_simulations: Number of simulation paths
            n_days: Days to simulate
            correlation_stress: If provided, inflate all correlations to this level
            
        Returns:
            MonteCarloResult for portfolio
        """
        cov = self.cov_matrix.copy()
        
        # Apply correlation stress if specified
        if correlation_stress is not None:
            # Extract volatilities
            vols = np.sqrt(np.diag(cov))
            # Create stressed correlation matrix
            corr = np.full((self.n_assets, self.n_assets), correlation_stress)
            np.fill_diagonal(corr, 1.0)
            # Reconstruct covariance
            cov = np.outer(vols, vols) * corr
        
        # Cholesky decomposition for correlated sampling
        try:
            L = np.linalg.cholesky(cov)
        except np.linalg.LinAlgError:
            # If not positive definite, use eigenvalue adjustment
            eigenvalues, eigenvectors = np.linalg.eigh(cov)
            eigenvalues = np.maximum(eigenvalues, 1e-8)
            cov = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
            L = np.linalg.cholesky(cov)
        
        # Generate correlated returns
        uncorrelated = np.random.normal(size=(n_simulations, n_days, self.n_assets))
        correlated_returns = np.zeros_like(uncorrelated)
        
        for i in range(n_simulations):
            for j in range(n_days):
                correlated_returns[i, j] = self.expected_returns + L @ uncorrelated[i, j]
        
        # Calculate portfolio returns
        portfolio_returns = np.sum(correlated_returns * self.weights, axis=2)
        
        # Calculate paths
        cumulative = np.cumprod(1 + portfolio_returns, axis=1)
        portfolio_values = self.initial_capital * cumulative
        
        # Create simple simulator for metric calculation
        sim = MonteCarloSimulator(
            daily_return=self.portfolio_return,
            daily_volatility=self.portfolio_vol,
            initial_capital=self.initial_capital
        )
        
        # Use the simulator's run method logic for metrics
        final_values = portfolio_values[:, -1]
        total_returns = (final_values / self.initial_capital) - 1
        
        running_max = np.maximum.accumulate(portfolio_values, axis=1)
        drawdowns = (running_max - portfolio_values) / running_max
        max_drawdowns = np.max(drawdowns, axis=1)
        
        scenario = StressScenario.CORRELATION_SPIKE if correlation_stress else StressScenario.NORMAL
        
        return MonteCarloResult(
            n_simulations=n_simulations,
            n_days=n_days,
            scenario=scenario,
            final_values=final_values,
            mean_return=np.mean(total_returns),
            median_return=np.median(total_returns),
            std_return=np.std(total_returns),
            var_95=np.percentile(total_returns, 5),
            var_99=np.percentile(total_returns, 1),
            cvar_95=np.mean(total_returns[total_returns <= np.percentile(total_returns, 5)]),
            cvar_99=np.mean(total_returns[total_returns <= np.percentile(total_returns, 1)]),
            max_drawdown_mean=np.mean(max_drawdowns),
            max_drawdown_95th=np.percentile(max_drawdowns, 95),
            max_drawdown_99th=np.percentile(max_drawdowns, 99),
            prob_loss=np.mean(total_returns < 0),
            prob_ruin=np.mean(max_drawdowns > 0.5),
            prob_target=np.mean(total_returns > 0.20),
            sample_paths=portfolio_values[:100]
        )


# ============== CONVENIENCE FUNCTIONS ==============

def quick_var(
    position_value: float,
    daily_vol: float = 0.02,
    confidence: float = 0.95,
    holding_days: int = 1
) -> float:
    """
    Quick VaR calculation for a position.
    
    Args:
        position_value: Position notional
        daily_vol: Daily volatility
        confidence: VaR confidence level
        holding_days: Holding period
        
    Returns:
        VaR in dollars
    """
    period_vol = daily_vol * np.sqrt(holding_days)
    z = stats.norm.ppf(1 - confidence)
    return abs(z * period_vol * position_value)


def stress_test_portfolio(
    daily_return: float,
    daily_vol: float,
    capital: float = 100_000,
    scenarios: List[StressScenario] = None
) -> pd.DataFrame:
    """
    Quick stress test across scenarios.
    
    Args:
        daily_return: Expected daily return
        daily_vol: Daily volatility
        capital: Portfolio capital
        scenarios: Scenarios to test (default: all)
        
    Returns:
        DataFrame with stress test results
    """
    if scenarios is None:
        scenarios = list(StressScenario)
    
    sim = MonteCarloSimulator(
        daily_return=daily_return,
        daily_volatility=daily_vol,
        initial_capital=capital
    )
    
    results = []
    for scenario in scenarios:
        result = sim.run_stress_test(scenario)
        results.append({
            "Scenario": scenario.value,
            "VaR 95%": result.var_95,
            "CVaR 99%": result.cvar_99,
            "Max DD 99%": result.max_drawdown_99th,
            "P(Ruin)": result.prob_ruin,
        })
    
    return pd.DataFrame(results)
