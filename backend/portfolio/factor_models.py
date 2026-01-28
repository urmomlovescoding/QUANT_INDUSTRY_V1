"""
QUANT INDUSTRY - Factor Models
==============================
Quantitative factor analysis:
- Fama-French 3/5 Factor Model
- Carhart 4 Factor (momentum)
- Quality factors (profitability, investment)
- Custom factor construction
- Factor exposure analysis
- Alpha/Beta decomposition

Factors explain ~95% of portfolio returns.
Alpha is what's left after factors are removed.

Author: QUANT INDUSTRY AI Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class FactorType(Enum):
    """Standard factor types"""
    MARKET = "market"           # Market risk premium (Rm - Rf)
    SIZE = "size"               # SMB (Small minus Big)
    VALUE = "value"             # HML (High minus Low B/M)
    MOMENTUM = "momentum"       # MOM (Winners minus Losers)
    PROFITABILITY = "profitability"  # RMW (Robust minus Weak)
    INVESTMENT = "investment"   # CMA (Conservative minus Aggressive)
    QUALITY = "quality"         # Combined quality factor
    LOW_VOL = "low_vol"         # Low volatility factor
    LIQUIDITY = "liquidity"     # Liquidity factor


@dataclass
class FactorExposure:
    """Factor exposure (beta) with statistics"""
    factor: FactorType
    beta: float
    t_stat: float
    p_value: float
    std_error: float
    
    @property
    def is_significant(self) -> bool:
        return self.p_value < 0.05
    
    def __repr__(self):
        sig = "*" if self.is_significant else ""
        return f"{self.factor.value}: β={self.beta:.3f} (t={self.t_stat:.2f}){sig}"


@dataclass
class FactorModelResult:
    """Complete factor model regression result"""
    exposures: List[FactorExposure]
    alpha: float
    alpha_t_stat: float
    alpha_p_value: float
    alpha_annualized: float
    r_squared: float
    adj_r_squared: float
    n_observations: int
    
    @property
    def alpha_significant(self) -> bool:
        return self.alpha_p_value < 0.05
    
    def summary(self) -> str:
        alpha_sig = "***" if self.alpha_p_value < 0.01 else ("**" if self.alpha_p_value < 0.05 else "")
        
        lines = [
            f"Factor Model Results (n={self.n_observations})",
            "=" * 50,
            f"Alpha: {self.alpha:.4f} (t={self.alpha_t_stat:.2f}) {alpha_sig}",
            f"Alpha (annualized): {self.alpha_annualized:.2%}",
            f"R²: {self.r_squared:.3f} (Adj: {self.adj_r_squared:.3f})",
            "",
            "Factor Exposures:",
        ]
        
        for exp in self.exposures:
            sig = "***" if exp.p_value < 0.01 else ("**" if exp.p_value < 0.05 else "*" if exp.p_value < 0.1 else "")
            lines.append(f"  {exp.factor.value:15s}: β={exp.beta:+.3f} (t={exp.t_stat:+.2f}) {sig}")
        
        return "\n".join(lines)


class FactorModel:
    """
    Factor model for return attribution and alpha extraction.
    
    Usage:
    ------
    >>> model = FactorModel()
    >>> 
    >>> # Load factor data (from Ken French's library or custom)
    >>> model.set_factors({
    ...     FactorType.MARKET: market_excess_returns,
    ...     FactorType.SIZE: smb_returns,
    ...     FactorType.VALUE: hml_returns,
    ...     FactorType.MOMENTUM: mom_returns,
    ... })
    >>>
    >>> # Analyze portfolio returns
    >>> result = model.analyze(portfolio_returns)
    >>> print(result.summary())
    >>> 
    >>> # Get alpha after removing factor exposure
    >>> alpha_series = model.extract_alpha(portfolio_returns)
    """
    
    def __init__(self, risk_free_rate: float = 0.0):
        """
        Initialize factor model.
        
        Args:
            risk_free_rate: Daily risk-free rate for excess returns
        """
        self.risk_free_rate = risk_free_rate
        self.factors: Dict[FactorType, np.ndarray] = {}
        self.factor_names: List[FactorType] = []
        
        logger.info("FactorModel initialized")
    
    def set_factors(self, factors: Dict[FactorType, np.ndarray]):
        """
        Set factor return series.
        
        Args:
            factors: Dict mapping factor type to return series
        """
        self.factors = {k: np.array(v) for k, v in factors.items()}
        self.factor_names = list(self.factors.keys())
        
        # Verify all factors have same length
        lengths = [len(f) for f in self.factors.values()]
        if len(set(lengths)) > 1:
            raise ValueError(f"Factor lengths must match: {lengths}")
        
        logger.info(f"Loaded {len(self.factors)} factors: {[f.value for f in self.factor_names]}")
    
    def analyze(
        self,
        returns: np.ndarray,
        factor_subset: List[FactorType] = None
    ) -> FactorModelResult:
        """
        Run factor regression on returns.
        
        Args:
            returns: Asset/portfolio return series
            factor_subset: Specific factors to use (default: all)
            
        Returns:
            FactorModelResult with exposures and alpha
        """
        returns = np.array(returns)
        
        # Select factors
        if factor_subset:
            factors_to_use = [f for f in factor_subset if f in self.factors]
        else:
            factors_to_use = self.factor_names
        
        if not factors_to_use:
            raise ValueError("No factors available for analysis")
        
        # Build X matrix
        n = len(returns)
        k = len(factors_to_use)
        
        X = np.column_stack([
            self.factors[f][:n] for f in factors_to_use
        ])
        
        # Add constant for alpha
        X = np.column_stack([np.ones(n), X])
        
        # Trim returns to match factors
        y = returns[:n]
        
        # OLS regression
        try:
            # (X'X)^-1 X'y
            XtX_inv = np.linalg.inv(X.T @ X)
            betas = XtX_inv @ X.T @ y
            
            # Residuals and statistics
            residuals = y - X @ betas
            sse = np.sum(residuals ** 2)
            sst = np.sum((y - np.mean(y)) ** 2)
            
            r_squared = 1 - sse / sst if sst > 0 else 0
            adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1)
            
            # Standard errors
            mse = sse / (n - k - 1)
            se = np.sqrt(np.diag(XtX_inv) * mse)
            
            # T-statistics and p-values
            t_stats = betas / se
            p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), n - k - 1))
            
        except np.linalg.LinAlgError:
            logger.error("Singular matrix in factor regression")
            return self._empty_result(n)
        
        # Extract alpha
        alpha = betas[0]
        alpha_t = t_stats[0]
        alpha_p = p_values[0]
        alpha_ann = alpha * 252  # Annualize daily alpha
        
        # Extract factor exposures
        exposures = []
        for i, factor in enumerate(factors_to_use):
            exposures.append(FactorExposure(
                factor=factor,
                beta=betas[i + 1],
                t_stat=t_stats[i + 1],
                p_value=p_values[i + 1],
                std_error=se[i + 1]
            ))
        
        return FactorModelResult(
            exposures=exposures,
            alpha=alpha,
            alpha_t_stat=alpha_t,
            alpha_p_value=alpha_p,
            alpha_annualized=alpha_ann,
            r_squared=r_squared,
            adj_r_squared=adj_r_squared,
            n_observations=n
        )
    
    def extract_alpha(self, returns: np.ndarray) -> np.ndarray:
        """
        Extract alpha (residual returns) after removing factor exposure.
        
        Args:
            returns: Return series
            
        Returns:
            Alpha series (returns - factor exposure)
        """
        result = self.analyze(returns)
        
        # Calculate factor contribution
        returns = np.array(returns)
        n = len(returns)
        
        factor_contribution = np.zeros(n)
        for exp in result.exposures:
            factor_returns = self.factors[exp.factor][:n]
            factor_contribution += exp.beta * factor_returns
        
        # Alpha = returns - factor exposure
        alpha = returns - factor_contribution
        
        return alpha
    
    def decompose_returns(
        self,
        returns: np.ndarray
    ) -> Dict[str, float]:
        """
        Decompose total return into factor contributions.
        
        Args:
            returns: Return series
            
        Returns:
            Dict with contribution from each factor and alpha
        """
        result = self.analyze(returns)
        
        returns = np.array(returns)
        n = len(returns)
        total_return = np.sum(returns)
        
        decomposition = {"alpha": result.alpha * n}
        
        for exp in result.exposures:
            factor_returns = self.factors[exp.factor][:n]
            contribution = exp.beta * np.sum(factor_returns)
            decomposition[exp.factor.value] = contribution
        
        # Verify
        decomposition["unexplained"] = total_return - sum(decomposition.values())
        
        return decomposition
    
    def _empty_result(self, n: int) -> FactorModelResult:
        """Return empty result on error"""
        return FactorModelResult(
            exposures=[],
            alpha=0.0,
            alpha_t_stat=0.0,
            alpha_p_value=1.0,
            alpha_annualized=0.0,
            r_squared=0.0,
            adj_r_squared=0.0,
            n_observations=n
        )


class FactorBuilder:
    """
    Build custom factors from price/fundamental data.
    
    Creates standard factors:
    - Momentum (12-1 month return)
    - Value (B/M, E/P, etc.)
    - Size (market cap)
    - Quality (ROE, profit margins)
    - Low volatility
    """
    
    @staticmethod
    def momentum_factor(
        prices: np.ndarray,
        lookback: int = 252,
        skip: int = 21
    ) -> np.ndarray:
        """
        Calculate momentum factor (12-1 month return).
        
        Args:
            prices: Price series (n_periods x n_assets)
            lookback: Lookback period (default 252 = 12 months)
            skip: Skip recent period (default 21 = 1 month)
            
        Returns:
            Momentum scores for each asset
        """
        if len(prices.shape) == 1:
            prices = prices.reshape(-1, 1)
        
        n_periods, n_assets = prices.shape
        
        if n_periods < lookback:
            return np.zeros(n_assets)
        
        # Return from t-lookback to t-skip
        start_prices = prices[-(lookback), :]
        end_prices = prices[-(skip), :]
        
        momentum = (end_prices / start_prices) - 1
        
        # Z-score normalize
        mom_mean = np.mean(momentum)
        mom_std = np.std(momentum)
        
        if mom_std > 0:
            momentum = (momentum - mom_mean) / mom_std
        
        return momentum
    
    @staticmethod
    def volatility_factor(
        returns: np.ndarray,
        lookback: int = 63
    ) -> np.ndarray:
        """
        Calculate low volatility factor (inverse vol).
        
        Args:
            returns: Return series (n_periods x n_assets)
            lookback: Lookback for vol calculation
            
        Returns:
            Low-vol scores (higher = lower volatility)
        """
        if len(returns.shape) == 1:
            returns = returns.reshape(-1, 1)
        
        n_periods, n_assets = returns.shape
        
        if n_periods < lookback:
            return np.zeros(n_assets)
        
        # Calculate volatility
        recent_returns = returns[-lookback:, :]
        vols = np.std(recent_returns, axis=0)
        
        # Invert (low vol = high score)
        low_vol = 1 / (vols + 1e-8)
        
        # Z-score
        lv_mean = np.mean(low_vol)
        lv_std = np.std(low_vol)
        
        if lv_std > 0:
            low_vol = (low_vol - lv_mean) / lv_std
        
        return low_vol
    
    @staticmethod
    def size_factor(market_caps: np.ndarray) -> np.ndarray:
        """
        Calculate size factor (negative of log market cap).
        
        Args:
            market_caps: Market capitalizations
            
        Returns:
            Size scores (higher = smaller company)
        """
        # Log market cap
        log_caps = np.log(market_caps + 1)
        
        # Invert (small = high score)
        size = -log_caps
        
        # Z-score
        s_mean = np.mean(size)
        s_std = np.std(size)
        
        if s_std > 0:
            size = (size - s_mean) / s_std
        
        return size
    
    @staticmethod
    def value_factor(
        book_values: np.ndarray,
        market_caps: np.ndarray
    ) -> np.ndarray:
        """
        Calculate value factor (book-to-market).
        
        Args:
            book_values: Book values
            market_caps: Market capitalizations
            
        Returns:
            Value scores (higher = more value)
        """
        # Book-to-market
        bm = book_values / (market_caps + 1e-8)
        
        # Z-score
        bm_mean = np.mean(bm)
        bm_std = np.std(bm)
        
        if bm_std > 0:
            bm = (bm - bm_mean) / bm_std
        
        return bm
    
    @staticmethod
    def quality_factor(
        roe: np.ndarray,
        profit_margin: np.ndarray = None,
        debt_equity: np.ndarray = None
    ) -> np.ndarray:
        """
        Calculate quality factor.
        
        Args:
            roe: Return on equity
            profit_margin: Net profit margin (optional)
            debt_equity: Debt to equity ratio (optional)
            
        Returns:
            Quality scores
        """
        def z_score(x):
            m, s = np.mean(x), np.std(x)
            return (x - m) / s if s > 0 else np.zeros_like(x)
        
        components = [z_score(roe)]
        
        if profit_margin is not None:
            components.append(z_score(profit_margin))
        
        if debt_equity is not None:
            # Invert D/E (low debt = high quality)
            components.append(-z_score(debt_equity))
        
        # Average components
        quality = np.mean(components, axis=0)
        
        return quality


# ============== PRE-BUILT MODELS ==============

def fama_french_3(
    returns: np.ndarray,
    market_returns: np.ndarray,
    smb: np.ndarray,
    hml: np.ndarray,
    rf: float = 0.0
) -> FactorModelResult:
    """
    Run Fama-French 3-factor model.
    
    Args:
        returns: Portfolio/asset returns
        market_returns: Market returns
        smb: Small minus Big factor
        hml: High minus Low factor
        rf: Risk-free rate
        
    Returns:
        FactorModelResult
    """
    model = FactorModel(risk_free_rate=rf)
    model.set_factors({
        FactorType.MARKET: np.array(market_returns) - rf,
        FactorType.SIZE: np.array(smb),
        FactorType.VALUE: np.array(hml),
    })
    
    return model.analyze(np.array(returns) - rf)


def carhart_4(
    returns: np.ndarray,
    market_returns: np.ndarray,
    smb: np.ndarray,
    hml: np.ndarray,
    mom: np.ndarray,
    rf: float = 0.0
) -> FactorModelResult:
    """
    Run Carhart 4-factor model (FF3 + Momentum).
    """
    model = FactorModel(risk_free_rate=rf)
    model.set_factors({
        FactorType.MARKET: np.array(market_returns) - rf,
        FactorType.SIZE: np.array(smb),
        FactorType.VALUE: np.array(hml),
        FactorType.MOMENTUM: np.array(mom),
    })
    
    return model.analyze(np.array(returns) - rf)
