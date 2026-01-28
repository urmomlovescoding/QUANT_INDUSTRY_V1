"""
QUANT_INDUSTRY_V1 Statistical Analysis Module

Advanced statistical methods for quantitative finance:
- Bayesian inference and updating
- Monte Carlo simulation
- Statistical hypothesis testing
- Distribution fitting
- Correlation analysis
- Cointegration testing

Rollback Plan: Delete this file
Tests Required: Statistical test accuracy, MC convergence
Failure Modes: Fall back to simple estimates
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)


# =============================================================================
# BAYESIAN INFERENCE
# =============================================================================

@dataclass
class BayesianPrior:
    """Prior distribution parameters."""
    distribution: str = 'normal'
    mean: float = 0.0
    std: float = 1.0
    alpha: float = 1.0  # For beta distribution
    beta: float = 1.0   # For beta distribution


@dataclass
class BayesianPosterior:
    """Posterior distribution result."""
    mean: float
    std: float
    ci_lower: float  # Credible interval
    ci_upper: float
    n_observations: int
    prior_mean: float
    prior_std: float


class BayesianEstimator:
    """
    Bayesian parameter estimation with conjugate priors.

    Supports online updating as new data arrives.
    """

    def __init__(
        self,
        prior: BayesianPrior = None,
        ci_level: float = 0.95
    ):
        self.prior = prior or BayesianPrior()
        self.ci_level = ci_level

        # Sufficient statistics
        self.n_obs = 0
        self.sum_x = 0.0
        self.sum_x2 = 0.0

        # Current posterior parameters
        self.posterior_mean = self.prior.mean
        self.posterior_var = self.prior.std ** 2

    def update(self, observation: float) -> BayesianPosterior:
        """
        Update posterior with new observation.

        Uses conjugate normal-normal model.
        """
        self.n_obs += 1
        self.sum_x += observation
        self.sum_x2 += observation ** 2

        # Prior parameters
        mu_0 = self.prior.mean
        sigma_0_sq = self.prior.std ** 2

        # Likelihood parameters (estimated from data)
        if self.n_obs > 1:
            sample_mean = self.sum_x / self.n_obs
            sample_var = (self.sum_x2 - self.n_obs * sample_mean ** 2) / (self.n_obs - 1)
            sample_var = max(sample_var, 1e-8)
        else:
            sample_mean = observation
            sample_var = sigma_0_sq

        # Posterior parameters (conjugate update)
        precision_0 = 1.0 / sigma_0_sq
        precision_data = self.n_obs / sample_var

        posterior_precision = precision_0 + precision_data
        posterior_var = 1.0 / posterior_precision

        posterior_mean = posterior_var * (precision_0 * mu_0 + precision_data * sample_mean)

        self.posterior_mean = posterior_mean
        self.posterior_var = posterior_var

        # Credible interval
        z = scipy_stats.norm.ppf((1 + self.ci_level) / 2)
        posterior_std = np.sqrt(posterior_var)
        ci_lower = posterior_mean - z * posterior_std
        ci_upper = posterior_mean + z * posterior_std

        return BayesianPosterior(
            mean=posterior_mean,
            std=posterior_std,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_observations=self.n_obs,
            prior_mean=mu_0,
            prior_std=self.prior.std,
        )

    def update_batch(self, observations: np.ndarray) -> BayesianPosterior:
        """Update posterior with batch of observations."""
        for obs in observations:
            result = self.update(obs)
        return result

    def predict(self, n_samples: int = 1000) -> np.ndarray:
        """Sample from posterior predictive distribution."""
        return np.random.normal(
            self.posterior_mean,
            np.sqrt(self.posterior_var),
            size=n_samples
        )

    def probability_greater_than(self, threshold: float) -> float:
        """Compute P(theta > threshold)."""
        z = (threshold - self.posterior_mean) / np.sqrt(self.posterior_var)
        return 1 - scipy_stats.norm.cdf(z)

    def reset(self) -> None:
        """Reset to prior."""
        self.n_obs = 0
        self.sum_x = 0.0
        self.sum_x2 = 0.0
        self.posterior_mean = self.prior.mean
        self.posterior_var = self.prior.std ** 2


class BayesianSharpeEstimator:
    """
    Bayesian estimation of Sharpe ratio.

    Accounts for uncertainty in both mean and variance.
    """

    def __init__(
        self,
        prior_mean: float = 0.0,
        prior_std: float = 0.1,
        risk_free_rate: float = 0.02
    ):
        self.prior_mean = prior_mean
        self.prior_std = prior_std
        self.risk_free_rate = risk_free_rate

        self.returns: List[float] = []

    def update(self, ret: float) -> Dict[str, float]:
        """Update with new return observation."""
        self.returns.append(ret)

        if len(self.returns) < 2:
            return {
                'sharpe_mean': 0.0,
                'sharpe_std': self.prior_std * np.sqrt(252),
                'n_obs': len(self.returns),
            }

        # Estimate mean and std of returns
        n = len(self.returns)
        returns_arr = np.array(self.returns)
        sample_mean = np.mean(returns_arr)
        sample_std = np.std(returns_arr, ddof=1)

        if sample_std < 1e-8:
            return {
                'sharpe_mean': 0.0,
                'sharpe_std': self.prior_std * np.sqrt(252),
                'n_obs': n,
            }

        # Bayesian posterior for mean
        prior_precision = 1.0 / (self.prior_std ** 2)
        data_precision = n / (sample_std ** 2)

        posterior_precision = prior_precision + data_precision
        posterior_mean = (prior_precision * self.prior_mean + data_precision * sample_mean) / posterior_precision
        posterior_std = np.sqrt(1.0 / posterior_precision)

        # Daily Sharpe (posterior mean)
        daily_rf = self.risk_free_rate / 252
        sharpe_daily = (posterior_mean - daily_rf) / sample_std

        # Annualized
        sharpe_annual = sharpe_daily * np.sqrt(252)

        # Uncertainty in Sharpe (approximation)
        # Standard error of Sharpe ratio
        sharpe_se = np.sqrt((1 + 0.5 * sharpe_daily ** 2) / n) * np.sqrt(252)

        return {
            'sharpe_mean': sharpe_annual,
            'sharpe_std': sharpe_se,
            'return_mean': posterior_mean * 252,  # Annualized
            'return_std': sample_std * np.sqrt(252),
            'n_obs': n,
        }

    def reset(self) -> None:
        """Reset observations."""
        self.returns = []


# =============================================================================
# MONTE CARLO SIMULATION
# =============================================================================

@dataclass
class MCResult:
    """Monte Carlo simulation result."""
    mean: float
    std: float
    median: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    samples: np.ndarray


class MonteCarloSimulator:
    """
    Monte Carlo simulation for financial modeling.

    Supports various price/return dynamics.
    """

    def __init__(self, seed: int = None):
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)

    def geometric_brownian_motion(
        self,
        s0: float,
        mu: float,
        sigma: float,
        dt: float,
        n_steps: int,
        n_paths: int
    ) -> np.ndarray:
        """
        Simulate Geometric Brownian Motion.

        dS = mu*S*dt + sigma*S*dW

        Args:
            s0: Initial price
            mu: Drift (annualized)
            sigma: Volatility (annualized)
            dt: Time step (in years)
            n_steps: Number of steps
            n_paths: Number of paths

        Returns:
            Array of shape (n_paths, n_steps + 1)
        """
        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = s0

        # Generate random increments
        dW = np.random.standard_normal((n_paths, n_steps))

        for t in range(1, n_steps + 1):
            paths[:, t] = paths[:, t-1] * np.exp(
                (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * dW[:, t-1]
            )

        return paths

    def jump_diffusion(
        self,
        s0: float,
        mu: float,
        sigma: float,
        lam: float,  # Jump intensity
        mu_j: float,  # Jump mean
        sigma_j: float,  # Jump std
        dt: float,
        n_steps: int,
        n_paths: int
    ) -> np.ndarray:
        """
        Simulate Merton Jump Diffusion.

        dS/S = mu*dt + sigma*dW + J*dN

        Args:
            s0: Initial price
            mu: Drift
            sigma: Diffusion volatility
            lam: Jump intensity (jumps per year)
            mu_j: Mean log-jump size
            sigma_j: Std of log-jump size
            dt: Time step
            n_steps: Number of steps
            n_paths: Number of paths

        Returns:
            Price paths
        """
        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = s0

        for t in range(1, n_steps + 1):
            # Diffusion component
            dW = np.random.standard_normal(n_paths)
            diffusion = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * dW

            # Jump component
            n_jumps = np.random.poisson(lam * dt, n_paths)
            jump_sizes = np.zeros(n_paths)
            for i in range(n_paths):
                if n_jumps[i] > 0:
                    jumps = np.random.normal(mu_j, sigma_j, n_jumps[i])
                    jump_sizes[i] = np.sum(jumps)

            paths[:, t] = paths[:, t-1] * np.exp(diffusion + jump_sizes)

        return paths

    def simulate_portfolio_returns(
        self,
        weights: np.ndarray,
        returns: np.ndarray,
        n_simulations: int = 10000,
        horizon: int = 252
    ) -> MCResult:
        """
        Simulate portfolio returns using bootstrap.

        Args:
            weights: Portfolio weights
            returns: Historical returns (n_samples, n_assets)
            n_simulations: Number of simulations
            horizon: Investment horizon (days)

        Returns:
            MCResult with terminal portfolio values
        """
        n_samples, n_assets = returns.shape

        terminal_values = np.zeros(n_simulations)

        for sim in range(n_simulations):
            # Bootstrap sample returns
            indices = np.random.choice(n_samples, size=horizon, replace=True)
            sampled_returns = returns[indices]

            # Portfolio returns
            portfolio_returns = sampled_returns @ weights

            # Cumulative return
            terminal_values[sim] = np.prod(1 + portfolio_returns) - 1

        return MCResult(
            mean=float(np.mean(terminal_values)),
            std=float(np.std(terminal_values)),
            median=float(np.median(terminal_values)),
            percentile_5=float(np.percentile(terminal_values, 5)),
            percentile_25=float(np.percentile(terminal_values, 25)),
            percentile_75=float(np.percentile(terminal_values, 75)),
            percentile_95=float(np.percentile(terminal_values, 95)),
            samples=terminal_values,
        )

    def value_at_risk(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
        horizon: int = 1,
        n_simulations: int = 10000
    ) -> Dict[str, float]:
        """
        Calculate Value at Risk using Monte Carlo.

        Args:
            returns: Historical returns
            confidence: Confidence level
            horizon: VaR horizon
            n_simulations: Number of simulations

        Returns:
            Dictionary with VaR metrics
        """
        # Bootstrap simulation
        n = len(returns)
        simulated_returns = np.zeros(n_simulations)

        for i in range(n_simulations):
            indices = np.random.choice(n, size=horizon, replace=True)
            simulated_returns[i] = np.prod(1 + returns[indices]) - 1

        # VaR (negative because we're looking at losses)
        var_value = np.percentile(simulated_returns, (1 - confidence) * 100)

        # Expected Shortfall (CVaR)
        cvar = np.mean(simulated_returns[simulated_returns <= var_value])

        return {
            'var': float(-var_value),
            'cvar': float(-cvar),
            'confidence': confidence,
            'horizon': horizon,
            'worst_case': float(-np.min(simulated_returns)),
            'best_case': float(np.max(simulated_returns)),
        }


# =============================================================================
# STATISTICAL TESTS
# =============================================================================

class StatisticalTests:
    """
    Collection of statistical tests for financial data.
    """

    @staticmethod
    def jarque_bera(returns: np.ndarray) -> Dict[str, float]:
        """
        Jarque-Bera test for normality.

        Tests whether returns follow normal distribution.
        """
        n = len(returns)
        if n < 20:
            return {'statistic': np.nan, 'p_value': np.nan, 'is_normal': False}

        mean = np.mean(returns)
        std = np.std(returns, ddof=1)

        skewness = np.mean(((returns - mean) / std) ** 3)
        kurtosis = np.mean(((returns - mean) / std) ** 4) - 3  # Excess kurtosis

        jb_stat = n / 6 * (skewness ** 2 + 0.25 * kurtosis ** 2)
        p_value = 1 - scipy_stats.chi2.cdf(jb_stat, 2)

        return {
            'statistic': float(jb_stat),
            'p_value': float(p_value),
            'skewness': float(skewness),
            'kurtosis': float(kurtosis),
            'is_normal': p_value > 0.05,
        }

    @staticmethod
    def adf_test(series: np.ndarray, max_lag: int = None) -> Dict[str, float]:
        """
        Augmented Dickey-Fuller test for stationarity.

        H0: Series has unit root (non-stationary)
        """
        n = len(series)
        if max_lag is None:
            max_lag = int(12 * (n / 100) ** (1/4))

        # Difference series
        diff = np.diff(series)

        # Lagged level
        y_lag = series[:-1]

        # Create lagged differences matrix
        X = np.column_stack([
            y_lag[max_lag:],
            np.ones(n - max_lag - 1),
        ])

        for lag in range(1, max_lag + 1):
            X = np.column_stack([X, diff[max_lag - lag:-lag if lag > 0 else None]])

        y = diff[max_lag:]

        # OLS regression
        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            residuals = y - X @ beta

            # Standard error of gamma
            sigma_sq = np.sum(residuals ** 2) / (len(y) - len(beta))
            var_beta = sigma_sq * np.linalg.inv(X.T @ X)
            se_gamma = np.sqrt(var_beta[0, 0])

            # ADF statistic
            gamma = beta[0]
            adf_stat = gamma / se_gamma

            # Critical values (approximation)
            cv_1pct = -3.43
            cv_5pct = -2.86
            cv_10pct = -2.57

            is_stationary = adf_stat < cv_5pct

            return {
                'statistic': float(adf_stat),
                'p_value': None,  # Would need MacKinnon tables
                'cv_1pct': cv_1pct,
                'cv_5pct': cv_5pct,
                'cv_10pct': cv_10pct,
                'is_stationary': is_stationary,
            }

        except Exception as e:
            logger.warning(f"ADF test failed: {e}")
            return {
                'statistic': np.nan,
                'p_value': np.nan,
                'is_stationary': False,
            }

    @staticmethod
    def hurst_exponent(series: np.ndarray, max_lag: int = 100) -> float:
        """
        Estimate Hurst exponent using R/S analysis.

        H < 0.5: Mean-reverting
        H = 0.5: Random walk
        H > 0.5: Trending
        """
        n = len(series)
        max_lag = min(max_lag, n // 4)

        lags = range(10, max_lag)
        rs_list = []

        for lag in lags:
            rs_values = []
            for start in range(0, n - lag, lag):
                subseries = series[start:start + lag]

                # Mean-adjusted series
                mean = np.mean(subseries)
                deviations = subseries - mean

                # Cumulative deviations
                cum_dev = np.cumsum(deviations)

                # Range
                r = np.max(cum_dev) - np.min(cum_dev)

                # Standard deviation
                s = np.std(subseries, ddof=1)

                if s > 0:
                    rs_values.append(r / s)

            if rs_values:
                rs_list.append((lag, np.mean(rs_values)))

        if len(rs_list) < 2:
            return 0.5

        # Log-log regression
        log_lags = np.log([x[0] for x in rs_list])
        log_rs = np.log([x[1] for x in rs_list])

        # Linear regression for Hurst exponent
        slope, _ = np.polyfit(log_lags, log_rs, 1)

        return float(np.clip(slope, 0, 1))

    @staticmethod
    def ljung_box(residuals: np.ndarray, lags: int = 10) -> Dict[str, float]:
        """
        Ljung-Box test for autocorrelation.

        H0: No autocorrelation up to lag k
        """
        n = len(residuals)
        if n < lags + 1:
            return {'statistic': np.nan, 'p_value': np.nan}

        # Compute autocorrelations
        mean = np.mean(residuals)
        var = np.var(residuals)

        acf = np.zeros(lags)
        for k in range(1, lags + 1):
            acf[k-1] = np.sum((residuals[k:] - mean) * (residuals[:-k] - mean)) / (n * var)

        # Ljung-Box statistic
        lb_stat = n * (n + 2) * np.sum(acf ** 2 / np.arange(n - 1, n - lags - 1, -1))

        p_value = 1 - scipy_stats.chi2.cdf(lb_stat, lags)

        return {
            'statistic': float(lb_stat),
            'p_value': float(p_value),
            'lags': lags,
            'autocorrelations': acf.tolist(),
            'has_autocorrelation': p_value < 0.05,
        }

    @staticmethod
    def cointegration_test(
        series1: np.ndarray,
        series2: np.ndarray
    ) -> Dict[str, Any]:
        """
        Engle-Granger cointegration test.

        Tests if two series are cointegrated.
        """
        n = len(series1)
        if len(series2) != n:
            raise ValueError("Series must have same length")

        # Step 1: Regress series1 on series2
        X = np.column_stack([np.ones(n), series2])
        beta = np.linalg.lstsq(X, series1, rcond=None)[0]

        # Residuals (spread)
        spread = series1 - X @ beta

        # Step 2: Test spread for stationarity
        adf_result = StatisticalTests.adf_test(spread)

        # Hedge ratio
        hedge_ratio = beta[1]

        return {
            'is_cointegrated': adf_result.get('is_stationary', False),
            'adf_statistic': adf_result.get('statistic', np.nan),
            'hedge_ratio': float(hedge_ratio),
            'intercept': float(beta[0]),
            'spread_mean': float(np.mean(spread)),
            'spread_std': float(np.std(spread)),
        }


# =============================================================================
# DISTRIBUTION FITTING
# =============================================================================

class DistributionFitter:
    """
    Fit various distributions to financial returns.
    """

    DISTRIBUTIONS = [
        'norm',
        't',
        'skewnorm',
        'nct',  # Non-central t
        'genhyperbolic',
    ]

    def fit(self, returns: np.ndarray) -> Dict[str, Any]:
        """
        Fit multiple distributions and select best.

        Args:
            returns: Return series

        Returns:
            Dictionary with best fit and all results
        """
        results = {}
        best_aic = float('inf')
        best_dist = None

        for dist_name in self.DISTRIBUTIONS:
            try:
                dist = getattr(scipy_stats, dist_name)
                params = dist.fit(returns)

                # Log-likelihood
                ll = np.sum(dist.logpdf(returns, *params))

                # AIC
                k = len(params)
                aic = 2 * k - 2 * ll

                results[dist_name] = {
                    'params': params,
                    'log_likelihood': float(ll),
                    'aic': float(aic),
                    'n_params': k,
                }

                if aic < best_aic:
                    best_aic = aic
                    best_dist = dist_name

            except Exception as e:
                logger.debug(f"Failed to fit {dist_name}: {e}")

        return {
            'best_distribution': best_dist,
            'best_aic': best_aic,
            'all_results': results,
        }

    def ks_test(
        self,
        returns: np.ndarray,
        distribution: str = 'norm'
    ) -> Dict[str, float]:
        """
        Kolmogorov-Smirnov goodness of fit test.
        """
        try:
            dist = getattr(scipy_stats, distribution)
            params = dist.fit(returns)

            stat, p_value = scipy_stats.kstest(returns, distribution, params)

            return {
                'statistic': float(stat),
                'p_value': float(p_value),
                'distribution': distribution,
                'fits_well': p_value > 0.05,
            }

        except Exception as e:
            logger.warning(f"KS test failed: {e}")
            return {'statistic': np.nan, 'p_value': np.nan, 'fits_well': False}


# =============================================================================
# CORRELATION ANALYSIS
# =============================================================================

class CorrelationAnalyzer:
    """
    Advanced correlation analysis for portfolios.
    """

    @staticmethod
    def rolling_correlation(
        series1: np.ndarray,
        series2: np.ndarray,
        window: int = 20
    ) -> np.ndarray:
        """Calculate rolling correlation."""
        n = len(series1)
        result = np.full(n, np.nan)

        for i in range(window - 1, n):
            s1 = series1[i - window + 1:i + 1]
            s2 = series2[i - window + 1:i + 1]
            result[i] = np.corrcoef(s1, s2)[0, 1]

        return result

    @staticmethod
    def correlation_matrix(returns: np.ndarray) -> np.ndarray:
        """Calculate correlation matrix."""
        return np.corrcoef(returns.T)

    @staticmethod
    def shrunk_correlation(
        returns: np.ndarray,
        shrinkage: float = 0.5
    ) -> np.ndarray:
        """
        Ledoit-Wolf shrinkage correlation estimator.

        Shrinks towards identity matrix.
        """
        sample_corr = np.corrcoef(returns.T)
        n_assets = sample_corr.shape[0]
        identity = np.eye(n_assets)

        return (1 - shrinkage) * sample_corr + shrinkage * identity

    @staticmethod
    def correlation_breakdown(
        returns: np.ndarray,
        stress_percentile: float = 5.0
    ) -> Dict[str, np.ndarray]:
        """
        Analyze correlation during stress periods.

        Correlations often increase during market stress.
        """
        # Use portfolio return as stress indicator
        portfolio_return = np.mean(returns, axis=1)
        stress_threshold = np.percentile(portfolio_return, stress_percentile)

        stress_mask = portfolio_return <= stress_threshold
        normal_mask = ~stress_mask

        stress_corr = np.corrcoef(returns[stress_mask].T) if np.sum(stress_mask) > 10 else None
        normal_corr = np.corrcoef(returns[normal_mask].T) if np.sum(normal_mask) > 10 else None

        return {
            'stress_correlation': stress_corr,
            'normal_correlation': normal_corr,
            'stress_periods': int(np.sum(stress_mask)),
            'normal_periods': int(np.sum(normal_mask)),
        }

    @staticmethod
    def pca_analysis(
        returns: np.ndarray,
        n_components: int = None
    ) -> Dict[str, Any]:
        """
        Principal Component Analysis of returns.

        Useful for factor modeling and dimensionality reduction.
        """
        # Standardize
        mean = np.mean(returns, axis=0)
        std = np.std(returns, axis=0)
        standardized = (returns - mean) / std

        # Covariance matrix
        cov_matrix = np.cov(standardized.T)

        # Eigenvalue decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        # Sort by eigenvalue (descending)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # Variance explained
        total_var = np.sum(eigenvalues)
        var_explained = eigenvalues / total_var
        cum_var_explained = np.cumsum(var_explained)

        if n_components is None:
            # Select components explaining 95% variance
            n_components = np.argmax(cum_var_explained >= 0.95) + 1

        return {
            'n_components': n_components,
            'eigenvalues': eigenvalues[:n_components].tolist(),
            'variance_explained': var_explained[:n_components].tolist(),
            'cumulative_variance': cum_var_explained[:n_components].tolist(),
            'loadings': eigenvectors[:, :n_components].tolist(),
        }
