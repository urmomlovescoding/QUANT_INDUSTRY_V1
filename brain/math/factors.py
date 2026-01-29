"""
Factor Models
=============
Multi-factor models for alpha generation and risk decomposition.

Includes:
- CAPM
- Fama-French 3/5 Factor
- Statistical Factor Models (PCA)
- Alpha/Beta Decomposition
"""

import numpy as np
from scipy import stats
from typing import Optional, Tuple, Dict, List
import logging

logger = logging.getLogger(__name__)


class CAPM:
    """
    Capital Asset Pricing Model.
    
    r_i - r_f = α + β(r_m - r_f) + ε
    
    α (alpha): Excess return not explained by market
    β (beta): Sensitivity to market returns
    """
    
    def __init__(
        self,
        asset_returns: np.ndarray,
        market_returns: np.ndarray,
        risk_free: float = 0.0
    ):
        self.asset_returns = asset_returns - risk_free
        self.market_returns = market_returns - risk_free
        self.rf = risk_free
        
        self._fit()
    
    def _fit(self):
        """Estimate alpha and beta via OLS."""
        X = np.column_stack([np.ones(len(self.market_returns)), self.market_returns])
        
        beta_hat = np.linalg.lstsq(X, self.asset_returns, rcond=None)[0]
        
        self.alpha = beta_hat[0]
        self.beta = beta_hat[1]
        
        # Residuals
        predicted = self.alpha + self.beta * self.market_returns
        self.residuals = self.asset_returns - predicted
        
        # R-squared
        ss_res = np.sum(self.residuals ** 2)
        ss_tot = np.sum((self.asset_returns - self.asset_returns.mean()) ** 2)
        self.r_squared = 1 - ss_res / ss_tot
        
        # Standard errors
        n = len(self.asset_returns)
        mse = ss_res / (n - 2)
        
        X_inv = np.linalg.inv(X.T @ X)
        se = np.sqrt(mse * np.diag(X_inv))
        
        self.alpha_se = se[0]
        self.beta_se = se[1]
        
        # T-statistics and p-values
        self.alpha_tstat = self.alpha / self.alpha_se
        self.beta_tstat = self.beta / self.beta_se
        
        self.alpha_pvalue = 2 * (1 - stats.t.cdf(abs(self.alpha_tstat), n - 2))
        self.beta_pvalue = 2 * (1 - stats.t.cdf(abs(self.beta_tstat), n - 2))
    
    def expected_return(self, market_risk_premium: float) -> float:
        """CAPM expected return: r_f + β(E[r_m] - r_f)"""
        return self.rf + self.beta * market_risk_premium
    
    def decompose_variance(self) -> Dict[str, float]:
        """Decompose variance into systematic and idiosyncratic."""
        total_var = np.var(self.asset_returns)
        systematic_var = self.beta ** 2 * np.var(self.market_returns)
        idiosyncratic_var = np.var(self.residuals)
        
        return {
            'total': total_var,
            'systematic': systematic_var,
            'idiosyncratic': idiosyncratic_var,
            'systematic_pct': systematic_var / total_var,
            'idiosyncratic_pct': idiosyncratic_var / total_var
        }
    
    def summary(self) -> Dict:
        """Return summary statistics."""
        return {
            'alpha': self.alpha,
            'alpha_annualized': self.alpha * 252,
            'alpha_tstat': self.alpha_tstat,
            'alpha_pvalue': self.alpha_pvalue,
            'beta': self.beta,
            'beta_tstat': self.beta_tstat,
            'beta_pvalue': self.beta_pvalue,
            'r_squared': self.r_squared,
            'variance_decomposition': self.decompose_variance()
        }


class FamaFrench:
    """
    Fama-French Multi-Factor Model.
    
    3-Factor: r - r_f = α + β_mkt(MKT) + β_smb(SMB) + β_hml(HML) + ε
    5-Factor: + β_rmw(RMW) + β_cma(CMA)
    
    Factors:
    - MKT: Market excess return
    - SMB: Small Minus Big (size)
    - HML: High Minus Low (value)
    - RMW: Robust Minus Weak (profitability)
    - CMA: Conservative Minus Aggressive (investment)
    """
    
    def __init__(
        self,
        asset_returns: np.ndarray,
        factor_returns: np.ndarray,  # (T, n_factors)
        factor_names: List[str] = None
    ):
        self.asset_returns = asset_returns
        self.factor_returns = factor_returns
        self.n_factors = factor_returns.shape[1]
        
        if factor_names is None:
            factor_names = [f'Factor_{i}' for i in range(self.n_factors)]
        self.factor_names = factor_names
        
        self._fit()
    
    def _fit(self):
        """Estimate factor loadings via OLS."""
        X = np.column_stack([np.ones(len(self.asset_returns)), self.factor_returns])
        
        beta_hat = np.linalg.lstsq(X, self.asset_returns, rcond=None)[0]
        
        self.alpha = beta_hat[0]
        self.betas = {
            name: beta_hat[i + 1]
            for i, name in enumerate(self.factor_names)
        }
        
        # Residuals and R-squared
        predicted = X @ beta_hat
        self.residuals = self.asset_returns - predicted
        
        ss_res = np.sum(self.residuals ** 2)
        ss_tot = np.sum((self.asset_returns - self.asset_returns.mean()) ** 2)
        self.r_squared = 1 - ss_res / ss_tot
        self.adj_r_squared = 1 - (1 - self.r_squared) * (len(self.asset_returns) - 1) / (len(self.asset_returns) - self.n_factors - 1)
        
        # Standard errors
        n = len(self.asset_returns)
        mse = ss_res / (n - self.n_factors - 1)
        
        X_inv = np.linalg.inv(X.T @ X)
        se = np.sqrt(mse * np.diag(X_inv))
        
        self.alpha_se = se[0]
        self.beta_ses = {
            name: se[i + 1]
            for i, name in enumerate(self.factor_names)
        }
        
        # T-statistics
        self.alpha_tstat = self.alpha / self.alpha_se
        self.beta_tstats = {
            name: self.betas[name] / self.beta_ses[name]
            for name in self.factor_names
        }
    
    def factor_attribution(self) -> Dict[str, float]:
        """Attribute returns to each factor."""
        factor_contributions = {}
        
        for i, name in enumerate(self.factor_names):
            contribution = self.betas[name] * self.factor_returns[:, i].mean() * 252
            factor_contributions[name] = contribution
        
        factor_contributions['alpha'] = self.alpha * 252
        factor_contributions['total'] = sum(factor_contributions.values())
        
        return factor_contributions
    
    def summary(self) -> Dict:
        return {
            'alpha': self.alpha,
            'alpha_annualized': self.alpha * 252,
            'betas': self.betas,
            'r_squared': self.r_squared,
            'adj_r_squared': self.adj_r_squared,
            'factor_attribution': self.factor_attribution()
        }


class StatisticalFactorModel:
    """
    Statistical Factor Model via PCA.
    
    R = F @ Λ' + ε
    
    Where:
    - F: Factor returns (derived from PCA)
    - Λ: Factor loadings
    - ε: Idiosyncratic returns
    
    No economic interpretation, but captures covariance structure.
    """
    
    def __init__(
        self,
        returns: np.ndarray,  # (T, n_assets)
        n_factors: Optional[int] = None,
        variance_explained: float = 0.9
    ):
        self.returns = returns
        self.n_assets = returns.shape[1]
        
        self._fit_pca(n_factors, variance_explained)
    
    def _fit_pca(self, n_factors: Optional[int], variance_explained: float):
        """Extract factors using PCA."""
        # Center returns
        self.means = self.returns.mean(axis=0)
        centered = self.returns - self.means
        
        # Covariance matrix
        cov = np.cov(centered.T)
        
        # Eigendecomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # Sort by eigenvalue (descending)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Determine number of factors
        if n_factors is None:
            cumulative_var = np.cumsum(eigenvalues) / eigenvalues.sum()
            n_factors = np.searchsorted(cumulative_var, variance_explained) + 1
        
        self.n_factors = min(n_factors, self.n_assets)
        
        # Factor loadings
        self.loadings = eigenvectors[:, :self.n_factors]  # (n_assets, n_factors)
        
        # Factor returns
        self.factor_returns = centered @ self.loadings  # (T, n_factors)
        
        # Idiosyncratic returns
        reconstructed = self.factor_returns @ self.loadings.T
        self.idiosyncratic = centered - reconstructed
        
        # Variance explained
        self.eigenvalues = eigenvalues[:self.n_factors]
        self.variance_explained = self.eigenvalues / eigenvalues.sum()
        self.cumulative_variance = np.cumsum(self.variance_explained)
    
    def get_factor_exposures(self, new_returns: np.ndarray) -> np.ndarray:
        """Project new returns onto factors."""
        centered = new_returns - self.means
        return centered @ self.loadings
    
    def reconstruct(self, factor_scores: np.ndarray) -> np.ndarray:
        """Reconstruct returns from factor scores."""
        return factor_scores @ self.loadings.T + self.means
    
    def factor_covariance(self) -> np.ndarray:
        """Covariance matrix of factors."""
        return np.cov(self.factor_returns.T)
    
    def summary(self) -> Dict:
        return {
            'n_factors': self.n_factors,
            'variance_explained': self.variance_explained.tolist(),
            'cumulative_variance': self.cumulative_variance.tolist(),
            'factor_correlations': np.corrcoef(self.factor_returns.T).tolist()
        }


class AlphaModel:
    """
    Alpha Signal Generation and Combination.
    
    Combines multiple alpha signals with proper normalization,
    decay, and combination methods.
    """
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
        self.signals: Dict[str, np.ndarray] = {}
        self.weights: Dict[str, float] = {}
    
    def add_signal(
        self,
        name: str,
        values: np.ndarray,
        weight: float = 1.0
    ):
        """Add an alpha signal."""
        # Normalize: z-score over lookback
        if len(values) >= self.lookback:
            mean = np.mean(values[-self.lookback:])
            std = np.std(values[-self.lookback:])
            normalized = (values - mean) / (std + 1e-8)
        else:
            normalized = (values - values.mean()) / (values.std() + 1e-8)
        
        self.signals[name] = normalized
        self.weights[name] = weight
    
    def combine(self, method: str = 'weighted_average') -> np.ndarray:
        """Combine signals into composite alpha."""
        if not self.signals:
            raise ValueError("No signals added")
        
        if method == 'weighted_average':
            total_weight = sum(self.weights.values())
            combined = sum(
                self.signals[name] * (self.weights[name] / total_weight)
                for name in self.signals
            )
            
        elif method == 'rank_average':
            # Rank each signal, average ranks
            ranks = []
            for name in self.signals:
                signal = self.signals[name]
                rank = stats.rankdata(signal) / len(signal)
                ranks.append(rank)
            combined = np.mean(ranks, axis=0)
            
        elif method == 'ic_weighted':
            # Weight by information coefficient (would need forward returns)
            # Placeholder: use equal weights
            combined = np.mean(list(self.signals.values()), axis=0)
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Final normalization
        combined = (combined - combined.mean()) / (combined.std() + 1e-8)
        
        return combined
    
    def decay_signal(
        self,
        signal: np.ndarray,
        half_life: int = 5
    ) -> np.ndarray:
        """Apply exponential decay to signal."""
        decay = np.exp(-np.log(2) / half_life)
        
        decayed = np.zeros_like(signal)
        decayed[0] = signal[0]
        
        for t in range(1, len(signal)):
            decayed[t] = decay * decayed[t-1] + (1 - decay) * signal[t]
        
        return decayed
    
    def neutralize(
        self,
        signal: np.ndarray,
        groups: np.ndarray
    ) -> np.ndarray:
        """Market/sector neutralize signal."""
        neutralized = signal.copy()
        
        for group in np.unique(groups):
            mask = groups == group
            group_mean = signal[mask].mean()
            neutralized[mask] -= group_mean
        
        return neutralized
