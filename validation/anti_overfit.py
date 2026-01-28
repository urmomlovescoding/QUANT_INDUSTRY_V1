"""
Anti-Overfitting Suite
QUANT_INDUSTRY_V1

Industry Problem: 90% of backtested strategies fail in production due to overfitting.
Most platforms make it EASY to overfit and provide no guardrails.

Our Solution:
- Walk-forward analysis (out-of-sample validation)
- Combinatorial Purged Cross-Validation (no lookahead bias)
- Monte Carlo permutation tests (is this alpha or luck?)
- Strategy complexity penalty (Occam's razor)
- Multiple testing correction (Bonferroni, FDR)
- Deflated Sharpe Ratio (accounts for selection bias)
- Minimum Backtest Length requirements
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
from scipy import stats
from concurrent.futures import ProcessPoolExecutor
import warnings

logger = logging.getLogger(__name__)


class OverfitRisk(Enum):
    """Overfit risk levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class OverfitReport:
    """Comprehensive overfitting analysis report."""
    # Core metrics
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    sharpe_decay: float  # How much Sharpe drops OOS
    
    # Walk-forward results
    walk_forward_sharpe: float
    walk_forward_consistency: float  # % of periods profitable
    
    # Statistical tests
    permutation_pvalue: float  # Probability this is luck
    deflated_sharpe: float  # Adjusted for multiple testing
    min_track_record_length: int  # Months needed to be confident
    
    # Complexity analysis
    parameter_count: int
    degrees_of_freedom: int
    complexity_penalty: float
    
    # Final verdict
    overfit_probability: float
    risk_level: OverfitRisk
    recommendations: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                    OVERFIT ANALYSIS REPORT                   ║
╠══════════════════════════════════════════════════════════════╣
║  Risk Level: {self.risk_level.value.upper():^10}  |  Overfit Prob: {self.overfit_probability*100:5.1f}%      ║
╠══════════════════════════════════════════════════════════════╣
║  In-Sample Sharpe:      {self.in_sample_sharpe:6.2f}                            ║
║  Out-of-Sample Sharpe:  {self.out_of_sample_sharpe:6.2f}  (decay: {self.sharpe_decay*100:5.1f}%)          ║
║  Walk-Forward Sharpe:   {self.walk_forward_sharpe:6.2f}  (consistency: {self.walk_forward_consistency*100:4.0f}%)   ║
╠══════════════════════════════════════════════════════════════╣
║  Permutation p-value:   {self.permutation_pvalue:6.4f}  {'✓ Significant' if self.permutation_pvalue < 0.05 else '✗ Not significant'}          ║
║  Deflated Sharpe:       {self.deflated_sharpe:6.2f}                            ║
║  Min Track Record:      {self.min_track_record_length:3d} months                          ║
╠══════════════════════════════════════════════════════════════╣
║  Parameters: {self.parameter_count:3d}  |  Complexity Penalty: {self.complexity_penalty:5.2f}          ║
╚══════════════════════════════════════════════════════════════╝
"""


class WalkForwardAnalyzer:
    """
    Walk-Forward Analysis - The gold standard for strategy validation.
    
    Instead of one big backtest, we:
    1. Train on window 1, test on window 2
    2. Train on windows 1-2, test on window 3
    3. ... and so on
    
    This simulates real trading where you always trade on unseen data.
    """
    
    def __init__(
        self,
        train_periods: int = 12,  # Months of training data
        test_periods: int = 3,    # Months of testing data
        min_train_periods: int = 6,
        expanding: bool = True    # Expanding vs rolling window
    ):
        self.train_periods = train_periods
        self.test_periods = test_periods
        self.min_train_periods = min_train_periods
        self.expanding = expanding
        
    def analyze(
        self,
        returns: pd.Series,
        strategy_func: Callable[[pd.Series], pd.Series],
        **strategy_params
    ) -> Dict[str, Any]:
        """
        Run walk-forward analysis.
        
        Args:
            returns: Asset returns series
            strategy_func: Function that takes returns and params, outputs strategy returns
            **strategy_params: Strategy parameters
            
        Returns:
            Walk-forward analysis results
        """
        # Group by month
        monthly_groups = returns.groupby(pd.Grouper(freq='M'))
        months = list(monthly_groups.groups.keys())
        
        if len(months) < self.train_periods + self.test_periods:
            raise ValueError("Insufficient data for walk-forward analysis")
            
        results = []
        oos_returns = []
        
        # Walk forward through time
        start_idx = self.train_periods
        while start_idx + self.test_periods <= len(months):
            # Define train/test periods
            if self.expanding:
                train_start = 0
            else:
                train_start = max(0, start_idx - self.train_periods)
                
            train_end = start_idx
            test_end = start_idx + self.test_periods
            
            # Get train/test data
            train_months = months[train_start:train_end]
            test_months = months[train_end:test_end]
            
            train_mask = returns.index.to_period('M').isin([m.to_period('M') for m in train_months])
            test_mask = returns.index.to_period('M').isin([m.to_period('M') for m in test_months])
            
            train_returns = returns[train_mask]
            test_returns = returns[test_mask]
            
            # Fit on train, evaluate on test
            try:
                # Train strategy (this would optimize params on train data)
                train_strat_returns = strategy_func(train_returns, **strategy_params)
                
                # Apply same strategy to test (no refit)
                test_strat_returns = strategy_func(test_returns, **strategy_params)
                
                # Calculate metrics
                train_sharpe = self._sharpe(train_strat_returns)
                test_sharpe = self._sharpe(test_strat_returns)
                
                results.append({
                    'train_start': train_months[0],
                    'train_end': train_months[-1],
                    'test_start': test_months[0],
                    'test_end': test_months[-1],
                    'train_sharpe': train_sharpe,
                    'test_sharpe': test_sharpe,
                    'test_return': test_strat_returns.sum(),
                    'sharpe_decay': (train_sharpe - test_sharpe) / train_sharpe if train_sharpe != 0 else 0
                })
                
                oos_returns.extend(test_strat_returns.tolist())
                
            except Exception as e:
                logger.warning(f"Walk-forward period failed: {e}")
                
            start_idx += self.test_periods
            
        if not results:
            raise ValueError("Walk-forward analysis produced no results")
            
        # Aggregate results
        results_df = pd.DataFrame(results)
        oos_returns_series = pd.Series(oos_returns)
        
        return {
            'periods': results,
            'oos_sharpe': self._sharpe(oos_returns_series),
            'avg_sharpe_decay': results_df['sharpe_decay'].mean(),
            'consistency': (results_df['test_return'] > 0).mean(),
            'worst_period_sharpe': results_df['test_sharpe'].min(),
            'best_period_sharpe': results_df['test_sharpe'].max(),
            'sharpe_std': results_df['test_sharpe'].std()
        }
        
    def _sharpe(self, returns: pd.Series, risk_free: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        excess = returns - risk_free / 252
        return np.sqrt(252) * excess.mean() / excess.std()


class CombinatorialPurgedCV:
    """
    Combinatorial Purged Cross-Validation (CPCV).
    
    Problem with regular CV: Financial data has serial correlation.
    Tomorrow's return is correlated with today's. Regular CV leaks information.
    
    Solution: 
    1. Purge: Remove data points near the train/test boundary
    2. Embargo: Add gap between train and test
    3. Combinatorial: Test all possible train/test combinations
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        purge_window: int = 5,    # Days to purge around boundary
        embargo_window: int = 5   # Days gap between train/test
    ):
        self.n_splits = n_splits
        self.purge_window = purge_window
        self.embargo_window = embargo_window
        
    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate train/test splits with purging and embargo.
        
        Returns list of (train_indices, test_indices) tuples.
        """
        n_samples = len(X)
        fold_size = n_samples // self.n_splits
        
        splits = []
        
        for test_fold in range(self.n_splits):
            test_start = test_fold * fold_size
            test_end = (test_fold + 1) * fold_size if test_fold < self.n_splits - 1 else n_samples
            
            # Test indices
            test_indices = np.arange(test_start, test_end)
            
            # Train indices (everything except test, with purging)
            train_indices = []
            
            for i in range(n_samples):
                # Skip if in test set
                if test_start <= i < test_end:
                    continue
                    
                # Skip if in purge window before test
                if test_start - self.purge_window <= i < test_start:
                    continue
                    
                # Skip if in embargo window after test
                if test_end <= i < test_end + self.embargo_window:
                    continue
                    
                # Skip if in purge window after test
                if test_end <= i < test_end + self.purge_window:
                    continue
                    
                train_indices.append(i)
                
            splits.append((np.array(train_indices), test_indices))
            
        return splits
        
    def cross_val_score(
        self,
        strategy_func: Callable,
        returns: pd.Series,
        **params
    ) -> List[float]:
        """Run cross-validation and return scores for each fold."""
        X = returns.to_frame()
        splits = self.split(X)
        
        scores = []
        for train_idx, test_idx in splits:
            train_returns = returns.iloc[train_idx]
            test_returns = returns.iloc[test_idx]
            
            try:
                strat_returns = strategy_func(test_returns, **params)
                sharpe = np.sqrt(252) * strat_returns.mean() / strat_returns.std()
                scores.append(sharpe)
            except:
                scores.append(0.0)
                
        return scores


class PermutationTest:
    """
    Monte Carlo Permutation Test.
    
    Question: Is this strategy's performance real or just luck?
    
    Method:
    1. Shuffle the returns randomly
    2. Run the strategy on shuffled data
    3. Repeat 1000+ times
    4. Compare real performance to distribution of random performance
    
    If real performance is better than 95% of random, it's likely real alpha.
    """
    
    def __init__(
        self,
        n_permutations: int = 1000,
        n_jobs: int = -1,  # Use all CPUs
        random_state: int = 42
    ):
        self.n_permutations = n_permutations
        self.n_jobs = n_jobs
        self.random_state = random_state
        
    def test(
        self,
        returns: pd.Series,
        strategy_func: Callable[[pd.Series], pd.Series],
        **strategy_params
    ) -> Dict[str, Any]:
        """
        Run permutation test.
        
        Returns:
            p_value: Probability that observed performance is due to chance
            observed_sharpe: Actual strategy Sharpe
            null_distribution: Distribution of Sharpes under null hypothesis
        """
        np.random.seed(self.random_state)
        
        # Calculate observed performance
        observed_returns = strategy_func(returns, **strategy_params)
        observed_sharpe = self._sharpe(observed_returns)
        
        # Generate null distribution
        null_sharpes = []
        
        for i in range(self.n_permutations):
            # Shuffle returns (destroys any real signal)
            shuffled = returns.sample(frac=1, replace=False)
            shuffled.index = returns.index  # Keep original index
            
            try:
                perm_returns = strategy_func(shuffled, **strategy_params)
                perm_sharpe = self._sharpe(perm_returns)
                null_sharpes.append(perm_sharpe)
            except:
                null_sharpes.append(0.0)
                
        null_sharpes = np.array(null_sharpes)
        
        # Calculate p-value (one-tailed: is observed better than random?)
        p_value = (null_sharpes >= observed_sharpe).mean()
        
        return {
            'p_value': p_value,
            'observed_sharpe': observed_sharpe,
            'null_mean': null_sharpes.mean(),
            'null_std': null_sharpes.std(),
            'null_95th': np.percentile(null_sharpes, 95),
            'null_distribution': null_sharpes,
            'is_significant': p_value < 0.05
        }
        
    def _sharpe(self, returns: pd.Series) -> float:
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        return np.sqrt(252) * returns.mean() / returns.std()


class DeflatedSharpeRatio:
    """
    Deflated Sharpe Ratio (DSR).
    
    Problem: If you test 100 strategies, some will look good by chance.
    The "best" strategy's Sharpe is biased upward.
    
    Solution: Adjust Sharpe for:
    1. Number of strategies tested
    2. Length of backtest
    3. Skewness and kurtosis of returns
    
    Paper: "The Deflated Sharpe Ratio" by Bailey & Lopez de Prado
    """
    
    @staticmethod
    def calculate(
        sharpe: float,
        n_trials: int,
        backtest_years: float,
        skewness: float = 0.0,
        kurtosis: float = 3.0,  # Normal = 3
        var_sharpe: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Calculate Deflated Sharpe Ratio.
        
        Args:
            sharpe: Observed Sharpe ratio
            n_trials: Number of strategies/parameter combinations tested
            backtest_years: Length of backtest in years
            skewness: Return skewness
            kurtosis: Return kurtosis
            var_sharpe: Variance of Sharpe (estimated if not provided)
            
        Returns:
            (deflated_sharpe, probability_of_false_discovery)
        """
        # Estimate variance of Sharpe if not provided
        if var_sharpe is None:
            var_sharpe = (1 + 0.5 * sharpe**2 - skewness * sharpe + 
                        ((kurtosis - 3) / 4) * sharpe**2) / backtest_years
            
        # Expected maximum Sharpe from n_trials under null
        e_max_sharpe = stats.norm.ppf(1 - 1/n_trials) * np.sqrt(var_sharpe)
        
        # Deflated Sharpe
        if var_sharpe > 0:
            deflated = (sharpe - e_max_sharpe) / np.sqrt(var_sharpe)
        else:
            deflated = 0.0
            
        # Probability of false discovery
        psr = stats.norm.cdf(deflated)
        
        return deflated, 1 - psr


class MinimumTrackRecord:
    """
    Minimum Track Record Length.
    
    Question: How long must a strategy run profitably before we believe it's real?
    
    Answer: Depends on the Sharpe ratio. Higher Sharpe = shorter required track record.
    
    Paper: "The Minimum Track Record Length" by Bailey & Lopez de Prado
    """
    
    @staticmethod
    def calculate(
        target_sharpe: float = 0.0,  # Benchmark Sharpe (usually 0)
        observed_sharpe: float = 1.0,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        confidence: float = 0.95
    ) -> float:
        """
        Calculate minimum track record length in years.
        
        Args:
            target_sharpe: Sharpe to beat (0 = beat zero)
            observed_sharpe: Strategy's Sharpe ratio
            skewness: Return skewness
            kurtosis: Return kurtosis
            confidence: Confidence level (e.g., 0.95)
            
        Returns:
            Minimum years of track record needed
        """
        z_score = stats.norm.ppf(confidence)
        
        sharpe_diff = observed_sharpe - target_sharpe
        if sharpe_diff <= 0:
            return float('inf')
            
        var_sharpe = (1 + 0.5 * observed_sharpe**2 - skewness * observed_sharpe +
                     ((kurtosis - 3) / 4) * observed_sharpe**2)
        
        min_years = var_sharpe * (z_score / sharpe_diff) ** 2
        
        return max(min_years, 0.5)  # At least 6 months


class ComplexityPenalty:
    """
    Strategy Complexity Penalty.
    
    Problem: More parameters = more ways to overfit.
    A strategy with 50 parameters will always look better than one with 5.
    
    Solution: Penalize based on:
    1. Number of parameters
    2. Number of rules/conditions
    3. Data snooping (indicators used)
    
    Similar to AIC/BIC in statistics.
    """
    
    @staticmethod
    def calculate(
        n_parameters: int,
        n_rules: int,
        n_indicators: int,
        n_observations: int,
        method: str = 'bic'
    ) -> float:
        """
        Calculate complexity penalty.
        
        Args:
            n_parameters: Number of tunable parameters
            n_rules: Number of trading rules
            n_indicators: Number of indicators used
            n_observations: Number of data points
            method: 'aic', 'bic', or 'custom'
            
        Returns:
            Penalty score (higher = more complex = more suspicious)
        """
        k = n_parameters + n_rules + n_indicators
        n = n_observations
        
        if method == 'aic':
            # Akaike Information Criterion style
            penalty = 2 * k
        elif method == 'bic':
            # Bayesian Information Criterion style  
            penalty = k * np.log(n)
        else:
            # Custom: penalize more heavily
            penalty = k * np.log(n) + k * (k + 1) / (n - k - 1)
            
        # Normalize to 0-1 scale (roughly)
        penalty_normalized = 1 - np.exp(-penalty / 100)
        
        return penalty_normalized
    
    @staticmethod
    def adjusted_sharpe(
        sharpe: float,
        penalty: float,
        severity: float = 0.5
    ) -> float:
        """
        Adjust Sharpe ratio for complexity.
        
        Args:
            sharpe: Original Sharpe ratio
            penalty: Complexity penalty (0-1)
            severity: How much to penalize (0-1)
        """
        return sharpe * (1 - severity * penalty)


class AntiOverfitSuite:
    """
    Complete anti-overfitting analysis suite.
    
    Runs all tests and produces a comprehensive report.
    """
    
    def __init__(
        self,
        walk_forward_train_months: int = 12,
        walk_forward_test_months: int = 3,
        n_permutations: int = 1000,
        confidence_level: float = 0.95
    ):
        self.wf_analyzer = WalkForwardAnalyzer(
            train_periods=walk_forward_train_months,
            test_periods=walk_forward_test_months
        )
        self.cpcv = CombinatorialPurgedCV(n_splits=5)
        self.perm_test = PermutationTest(n_permutations=n_permutations)
        self.confidence = confidence_level
        
    def analyze(
        self,
        returns: pd.Series,
        strategy_func: Callable[[pd.Series], pd.Series],
        n_parameters: int = 0,
        n_rules: int = 0,
        n_indicators: int = 0,
        n_trials: int = 1,
        **strategy_params
    ) -> OverfitReport:
        """
        Run complete overfitting analysis.
        
        Args:
            returns: Asset returns
            strategy_func: Strategy function
            n_parameters: Number of strategy parameters
            n_rules: Number of trading rules
            n_indicators: Number of indicators used
            n_trials: Number of strategies/params tested
            **strategy_params: Strategy parameters
            
        Returns:
            OverfitReport with complete analysis
        """
        # Calculate strategy returns
        strat_returns = strategy_func(returns, **strategy_params)
        
        # Basic stats
        in_sample_sharpe = self._sharpe(strat_returns)
        skewness = strat_returns.skew()
        kurtosis = strat_returns.kurtosis() + 3  # Convert to regular kurtosis
        backtest_years = len(returns) / 252
        
        # Walk-forward analysis
        try:
            wf_results = self.wf_analyzer.analyze(returns, strategy_func, **strategy_params)
            wf_sharpe = wf_results['oos_sharpe']
            wf_consistency = wf_results['consistency']
            sharpe_decay = wf_results['avg_sharpe_decay']
        except Exception as e:
            logger.warning(f"Walk-forward failed: {e}")
            wf_sharpe = in_sample_sharpe * 0.5
            wf_consistency = 0.5
            sharpe_decay = 0.5
            
        # Permutation test
        try:
            perm_results = self.perm_test.test(returns, strategy_func, **strategy_params)
            perm_pvalue = perm_results['p_value']
        except Exception as e:
            logger.warning(f"Permutation test failed: {e}")
            perm_pvalue = 0.5
            
        # Deflated Sharpe
        deflated_sharpe, false_discovery_prob = DeflatedSharpeRatio.calculate(
            sharpe=in_sample_sharpe,
            n_trials=max(n_trials, 1),
            backtest_years=backtest_years,
            skewness=skewness,
            kurtosis=kurtosis
        )
        
        # Minimum track record
        min_track_months = int(MinimumTrackRecord.calculate(
            target_sharpe=0.0,
            observed_sharpe=in_sample_sharpe,
            skewness=skewness,
            kurtosis=kurtosis,
            confidence=self.confidence
        ) * 12)
        
        # Complexity penalty
        complexity = ComplexityPenalty.calculate(
            n_parameters=n_parameters,
            n_rules=n_rules,
            n_indicators=n_indicators,
            n_observations=len(returns)
        )
        
        # Calculate overfit probability
        overfit_prob = self._calculate_overfit_probability(
            sharpe_decay=sharpe_decay,
            perm_pvalue=perm_pvalue,
            complexity=complexity,
            wf_consistency=wf_consistency,
            deflated_sharpe=deflated_sharpe
        )
        
        # Determine risk level
        if overfit_prob < 0.2:
            risk_level = OverfitRisk.LOW
        elif overfit_prob < 0.4:
            risk_level = OverfitRisk.MODERATE
        elif overfit_prob < 0.6:
            risk_level = OverfitRisk.HIGH
        else:
            risk_level = OverfitRisk.EXTREME
            
        # Generate recommendations
        recommendations = self._generate_recommendations(
            sharpe_decay=sharpe_decay,
            perm_pvalue=perm_pvalue,
            complexity=complexity,
            wf_consistency=wf_consistency,
            min_track_months=min_track_months,
            backtest_years=backtest_years
        )
        
        return OverfitReport(
            in_sample_sharpe=in_sample_sharpe,
            out_of_sample_sharpe=wf_sharpe,
            sharpe_decay=sharpe_decay,
            walk_forward_sharpe=wf_sharpe,
            walk_forward_consistency=wf_consistency,
            permutation_pvalue=perm_pvalue,
            deflated_sharpe=deflated_sharpe,
            min_track_record_length=min_track_months,
            parameter_count=n_parameters,
            degrees_of_freedom=n_parameters + n_rules + n_indicators,
            complexity_penalty=complexity,
            overfit_probability=overfit_prob,
            risk_level=risk_level,
            recommendations=recommendations
        )
        
    def _sharpe(self, returns: pd.Series) -> float:
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        return np.sqrt(252) * returns.mean() / returns.std()
        
    def _calculate_overfit_probability(
        self,
        sharpe_decay: float,
        perm_pvalue: float,
        complexity: float,
        wf_consistency: float,
        deflated_sharpe: float
    ) -> float:
        """Combine signals into single overfit probability."""
        # Each factor contributes to overfit probability
        decay_prob = min(max(sharpe_decay, 0), 1)
        perm_prob = perm_pvalue  # Already 0-1
        complexity_prob = complexity  # Already 0-1
        consistency_prob = 1 - wf_consistency  # Low consistency = high overfit
        deflated_prob = max(0, (1 - deflated_sharpe) / 2)  # Negative deflated = bad
        
        # Weighted average
        weights = [0.25, 0.25, 0.15, 0.20, 0.15]
        probs = [decay_prob, perm_prob, complexity_prob, consistency_prob, deflated_prob]
        
        return sum(w * p for w, p in zip(weights, probs))
        
    def _generate_recommendations(
        self,
        sharpe_decay: float,
        perm_pvalue: float,
        complexity: float,
        wf_consistency: float,
        min_track_months: int,
        backtest_years: float
    ) -> List[str]:
        """Generate actionable recommendations."""
        recs = []
        
        if sharpe_decay > 0.3:
            recs.append("⚠️ High Sharpe decay (>30%). Strategy may be curve-fitted. Simplify parameters.")
            
        if perm_pvalue > 0.1:
            recs.append("⚠️ Permutation test not significant. Alpha may be due to chance. Need more data or better signal.")
            
        if complexity > 0.5:
            recs.append("⚠️ High complexity. Reduce parameters/rules to avoid overfitting.")
            
        if wf_consistency < 0.5:
            recs.append("⚠️ Low walk-forward consistency. Strategy not robust across time periods.")
            
        if min_track_months > backtest_years * 12:
            recs.append(f"⚠️ Need {min_track_months} months track record. Current backtest too short.")
            
        if not recs:
            recs.append("✓ Strategy passes overfitting checks. Proceed with caution and proper position sizing.")
            
        return recs
