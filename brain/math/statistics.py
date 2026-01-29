"""
Statistical Tests for Trading
=============================
Hypothesis tests and statistical methods for time series analysis.

Tests:
- Stationarity (ADF, KPSS)
- Cointegration (Engle-Granger, Johansen)
- Causality (Granger)
- Change Point Detection
"""

import numpy as np
from typing import Optional, Tuple, List, Dict
from scipy import stats
from scipy.linalg import toeplitz
import logging

logger = logging.getLogger(__name__)


class StationarityTest:
    """
    Tests for time series stationarity.
    
    Stationarity is crucial for:
    - Valid statistical inference
    - Mean reversion strategies
    - Cointegration analysis
    
    Tests:
    - ADF: Null = unit root (non-stationary)
    - KPSS: Null = stationary
    """
    
    @staticmethod
    def adf(
        y: np.ndarray,
        max_lags: Optional[int] = None,
        regression: str = "c"  # 'c' = constant, 'ct' = constant + trend, 'n' = none
    ) -> Dict[str, float]:
        """
        Augmented Dickey-Fuller test.
        
        Tests H0: unit root present (non-stationary)
        vs H1: no unit root (stationary)
        
        Model: Δy_t = α + βt + γy_{t-1} + Σ δ_i Δy_{t-i} + ε_t
        
        Test statistic: t-stat for γ̂
        
        Returns:
            adf_stat: ADF statistic
            p_value: p-value
            n_lags: Number of lags used
            critical_values: 1%, 5%, 10% critical values
        """
        n = len(y)
        
        if max_lags is None:
            max_lags = int(np.floor(12 * (n / 100) ** 0.25))
        
        # First difference
        dy = np.diff(y)
        y_lag = y[:-1]
        
        # Build regressor matrix
        T = len(dy) - max_lags
        
        # Lagged differences
        X_lags = np.column_stack([
            dy[max_lags - i - 1:T + max_lags - i - 1]
            for i in range(max_lags)
        ])
        
        # y_{t-1}
        y_lag_t = y_lag[max_lags:T + max_lags]
        
        # Dependent variable
        dy_t = dy[max_lags:T + max_lags]
        
        # Build X matrix based on regression type
        if regression == "c":
            X = np.column_stack([np.ones(T), y_lag_t, X_lags])
        elif regression == "ct":
            X = np.column_stack([np.ones(T), np.arange(T), y_lag_t, X_lags])
        else:  # "n"
            X = np.column_stack([y_lag_t, X_lags])
        
        # OLS
        beta = np.linalg.lstsq(X, dy_t, rcond=None)[0]
        residuals = dy_t - X @ beta
        
        # Standard error of gamma (coefficient on y_{t-1})
        sigma_sq = np.sum(residuals ** 2) / (T - len(beta))
        var_beta = sigma_sq * np.linalg.inv(X.T @ X)
        
        if regression == "c":
            gamma_idx = 1
        elif regression == "ct":
            gamma_idx = 2
        else:
            gamma_idx = 0
        
        gamma = beta[gamma_idx]
        se_gamma = np.sqrt(var_beta[gamma_idx, gamma_idx])
        
        adf_stat = gamma / se_gamma
        
        # Critical values (approximate - from MacKinnon)
        critical_values = {
            "1%": -3.43,
            "5%": -2.86,
            "10%": -2.57
        }
        
        # Approximate p-value
        if adf_stat < -3.43:
            p_value = 0.01
        elif adf_stat < -2.86:
            p_value = 0.05
        elif adf_stat < -2.57:
            p_value = 0.10
        else:
            p_value = 0.5  # Very rough approximation
        
        return {
            "adf_stat": adf_stat,
            "p_value": p_value,
            "n_lags": max_lags,
            "critical_values": critical_values,
            "is_stationary": adf_stat < critical_values["5%"]
        }
    
    @staticmethod
    def kpss(
        y: np.ndarray,
        regression: str = "c",  # 'c' = level, 'ct' = trend
        n_lags: Optional[int] = None
    ) -> Dict[str, float]:
        """
        KPSS test for stationarity.
        
        Tests H0: stationary
        vs H1: non-stationary (unit root)
        
        Complementary to ADF - use both for robustness.
        """
        n = len(y)
        
        if n_lags is None:
            n_lags = int(np.ceil(12 * (n / 100) ** 0.25))
        
        # Detrend
        if regression == "ct":
            X = np.column_stack([np.ones(n), np.arange(n)])
        else:
            X = np.ones((n, 1))
        
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        residuals = y - X @ beta
        
        # Cumulative sum of residuals
        S = np.cumsum(residuals)
        
        # Long-run variance estimator (Newey-West)
        gamma_0 = np.sum(residuals ** 2) / n
        
        gamma_sum = 0
        for j in range(1, n_lags + 1):
            gamma_j = np.sum(residuals[j:] * residuals[:-j]) / n
            weight = 1 - j / (n_lags + 1)  # Bartlett kernel
            gamma_sum += 2 * weight * gamma_j
        
        long_run_var = gamma_0 + gamma_sum
        
        # KPSS statistic
        kpss_stat = np.sum(S ** 2) / (n ** 2 * long_run_var)
        
        # Critical values
        if regression == "c":
            critical_values = {"10%": 0.347, "5%": 0.463, "1%": 0.739}
        else:
            critical_values = {"10%": 0.119, "5%": 0.146, "1%": 0.216}
        
        return {
            "kpss_stat": kpss_stat,
            "critical_values": critical_values,
            "is_stationary": kpss_stat < critical_values["5%"]
        }


class CointegrationTest:
    """
    Cointegration tests for pairs trading.
    
    Two I(1) series are cointegrated if a linear combination is I(0).
    
    If y_t ~ I(1) and x_t ~ I(1), but (y_t - βx_t) ~ I(0),
    then y_t and x_t are cointegrated with cointegrating vector (1, -β).
    
    Uses: Pairs trading, statistical arbitrage, spread trading
    """
    
    @staticmethod
    def engle_granger(
        y: np.ndarray,
        x: np.ndarray
    ) -> Dict[str, any]:
        """
        Engle-Granger two-step cointegration test.
        
        Step 1: Estimate cointegrating regression y_t = α + βx_t + ε_t
        Step 2: Test residuals for stationarity using ADF
        
        Returns:
            beta: Cointegrating coefficient
            alpha: Intercept
            adf_result: ADF test on residuals
            is_cointegrated: Boolean
        """
        n = len(y)
        
        # Step 1: OLS regression
        X = np.column_stack([np.ones(n), x])
        beta_hat = np.linalg.lstsq(X, y, rcond=None)[0]
        
        alpha = beta_hat[0]
        beta = beta_hat[1]
        
        # Residuals (spread)
        residuals = y - alpha - beta * x
        
        # Step 2: ADF test on residuals
        adf_result = StationarityTest.adf(residuals, regression="n")
        
        # Critical values are different for cointegration test
        # (more negative than standard ADF)
        coint_critical = {"1%": -3.90, "5%": -3.34, "10%": -3.04}
        
        is_cointegrated = adf_result["adf_stat"] < coint_critical["5%"]
        
        return {
            "alpha": alpha,
            "beta": beta,
            "spread": residuals,
            "adf_stat": adf_result["adf_stat"],
            "critical_values": coint_critical,
            "is_cointegrated": is_cointegrated,
            "half_life": StationarityTest._half_life(residuals) if is_cointegrated else None
        }
    
    @staticmethod
    def _half_life(spread: np.ndarray) -> float:
        """Estimate half-life of mean reversion."""
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        
        # Regression: Δspread = θ * spread_{t-1}
        theta = np.sum(spread_lag * spread_diff) / np.sum(spread_lag ** 2)
        
        if theta < 0:
            return -np.log(2) / theta
        else:
            return np.inf


class CausalityTest:
    """
    Granger Causality test.
    
    X "Granger-causes" Y if past values of X help predict Y
    beyond what past values of Y alone can predict.
    
    Model:
        Restricted: Y_t = α + Σ β_i Y_{t-i} + ε_t
        Unrestricted: Y_t = α + Σ β_i Y_{t-i} + Σ γ_i X_{t-i} + ε_t
    
    Test: F-test comparing residual sum of squares
    
    Uses: Lead-lag relationships, predictive signals
    """
    
    @staticmethod
    def granger(
        y: np.ndarray,
        x: np.ndarray,
        max_lag: int = 5
    ) -> Dict[str, any]:
        """
        Granger causality test: does X cause Y?
        
        Returns:
            f_stat: F-statistic
            p_value: p-value
            is_causal: Boolean (at 5% significance)
        """
        n = len(y)
        
        # Build lagged matrices
        Y = y[max_lag:]
        
        # Lagged Y
        Y_lags = np.column_stack([
            y[max_lag - i - 1:n - i - 1] for i in range(max_lag)
        ])
        
        # Lagged X
        X_lags = np.column_stack([
            x[max_lag - i - 1:n - i - 1] for i in range(max_lag)
        ])
        
        T = len(Y)
        
        # Restricted model (Y lags only)
        X_r = np.column_stack([np.ones(T), Y_lags])
        beta_r = np.linalg.lstsq(X_r, Y, rcond=None)[0]
        resid_r = Y - X_r @ beta_r
        RSS_r = np.sum(resid_r ** 2)
        
        # Unrestricted model (Y and X lags)
        X_u = np.column_stack([np.ones(T), Y_lags, X_lags])
        beta_u = np.linalg.lstsq(X_u, Y, rcond=None)[0]
        resid_u = Y - X_u @ beta_u
        RSS_u = np.sum(resid_u ** 2)
        
        # F-test
        df1 = max_lag  # Number of restrictions
        df2 = T - 2 * max_lag - 1
        
        f_stat = ((RSS_r - RSS_u) / df1) / (RSS_u / df2)
        p_value = 1 - stats.f.cdf(f_stat, df1, df2)
        
        return {
            "f_stat": f_stat,
            "p_value": p_value,
            "is_causal": p_value < 0.05,
            "max_lag": max_lag
        }
    
    @staticmethod
    def bidirectional(
        y: np.ndarray,
        x: np.ndarray,
        max_lag: int = 5
    ) -> Dict[str, Dict]:
        """Test causality in both directions."""
        return {
            "x_causes_y": CausalityTest.granger(y, x, max_lag),
            "y_causes_x": CausalityTest.granger(x, y, max_lag)
        }


class ChangePointDetection:
    """
    Change point detection in time series.
    
    Detects structural breaks in:
    - Mean (regime shifts)
    - Variance (volatility regimes)
    - Trend (trend reversals)
    
    Uses: Regime detection, adaptive strategies
    """
    
    @staticmethod
    def cusum(
        y: np.ndarray,
        threshold: float = 1.0
    ) -> Dict[str, any]:
        """
        CUSUM (Cumulative Sum) test for mean change.
        
        S_t = Σ_{i=1}^t (y_i - μ̂)
        
        Change point detected when S_t exceeds threshold.
        """
        n = len(y)
        mean = np.mean(y)
        std = np.std(y)
        
        # Standardized CUSUM
        cusum = np.cumsum(y - mean) / (std * np.sqrt(n))
        
        # Find potential change points
        change_points = []
        max_cusum = 0
        max_idx = 0
        
        for i in range(n):
            if abs(cusum[i]) > threshold:
                if abs(cusum[i]) > max_cusum:
                    max_cusum = abs(cusum[i])
                    max_idx = i
        
        if max_cusum > threshold:
            change_points.append(max_idx)
        
        return {
            "cusum": cusum,
            "change_points": change_points,
            "max_cusum": max_cusum,
            "detected": len(change_points) > 0
        }
    
    @staticmethod
    def binary_segmentation(
        y: np.ndarray,
        min_segment: int = 20,
        threshold: float = None
    ) -> List[int]:
        """
        Binary segmentation for multiple change points.
        
        Recursively splits series at most likely change points.
        """
        n = len(y)
        
        if threshold is None:
            threshold = np.log(n)  # BIC-type penalty
        
        change_points = []
        
        def find_change_point(start: int, end: int) -> Optional[int]:
            if end - start < 2 * min_segment:
                return None
            
            segment = y[start:end]
            m = len(segment)
            
            best_gain = 0
            best_idx = None
            
            for t in range(min_segment, m - min_segment):
                left = segment[:t]
                right = segment[t:]
                
                # Gain = reduction in RSS
                total_var = np.var(segment) * m
                left_var = np.var(left) * len(left)
                right_var = np.var(right) * len(right)
                
                gain = total_var - left_var - right_var
                
                if gain > best_gain:
                    best_gain = gain
                    best_idx = t
            
            if best_gain > threshold:
                return start + best_idx
            return None
        
        # Recursive segmentation
        def segment(start: int, end: int):
            cp = find_change_point(start, end)
            if cp is not None:
                change_points.append(cp)
                segment(start, cp)
                segment(cp, end)
        
        segment(0, n)
        
        return sorted(change_points)
    
    @staticmethod
    def pelt(
        y: np.ndarray,
        penalty: Optional[float] = None
    ) -> List[int]:
        """
        PELT (Pruned Exact Linear Time) algorithm.
        
        Optimal change point detection with linear complexity.
        
        Minimizes: Σ C(y_{τ_i:τ_{i+1}}) + β * (number of change points)
        
        Where C is the cost function (e.g., negative log-likelihood).
        """
        n = len(y)
        
        if penalty is None:
            penalty = 2 * np.log(n)  # Modified BIC
        
        # Cost function: negative log-likelihood for Gaussian
        def cost(start: int, end: int) -> float:
            if end - start < 2:
                return np.inf
            segment = y[start:end]
            m = len(segment)
            var = np.var(segment)
            if var < 1e-10:
                var = 1e-10
            return m * (np.log(2 * np.pi * var) + 1)
        
        # Dynamic programming
        F = np.zeros(n + 1)
        F[0] = -penalty
        
        cp = [[] for _ in range(n + 1)]
        
        # Candidate set (PELT pruning)
        R = {0}
        
        for t in range(1, n + 1):
            candidates = []
            
            for s in R:
                candidates.append((F[s] + cost(s, t) + penalty, s))
            
            F[t], best_s = min(candidates)
            
            if best_s > 0:
                cp[t] = cp[best_s] + [best_s]
            
            # Pruning
            R = {s for s in R if F[s] + cost(s, t) <= F[t]} | {t}
        
        return cp[n]
