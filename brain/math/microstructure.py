"""
Market Microstructure Mathematics
=================================
Quantitative models for order flow, price impact, and market making.

Includes:
- Kyle Lambda (price impact)
- Almgren-Chriss (optimal execution)
- Roll Model (bid-ask spread)
- Order Flow Toxicity (VPIN)
- Information Theory of Markets
"""

import numpy as np
from scipy.optimize import minimize
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class KyleModel:
    """
    Kyle (1985) Model of Market Making.
    
    Models price impact from informed trading:
    
    ΔP = λ * ΔX + ε
    
    Where:
    - λ (Kyle's lambda): Price impact coefficient
    - ΔX: Net order flow
    - ε: Noise
    
    Higher λ = less liquid market
    """
    
    def __init__(self):
        self.lambda_ = None
        self.sigma_v = None  # Fundamental volatility
        self.sigma_u = None  # Noise trader volatility
    
    def estimate(
        self,
        price_changes: np.ndarray,
        order_flow: np.ndarray
    ) -> float:
        """
        Estimate Kyle's lambda via regression.
        
        ΔP = λ * X + ε
        """
        # OLS estimation
        X = order_flow.reshape(-1, 1)
        X_with_const = np.column_stack([np.ones(len(order_flow)), X])
        
        beta = np.linalg.lstsq(X_with_const, price_changes, rcond=None)[0]
        
        self.intercept = beta[0]
        self.lambda_ = beta[1]
        
        # R-squared
        predicted = X_with_const @ beta
        ss_res = np.sum((price_changes - predicted) ** 2)
        ss_tot = np.sum((price_changes - price_changes.mean()) ** 2)
        self.r_squared = 1 - ss_res / ss_tot
        
        return self.lambda_
    
    def theoretical_lambda(self, sigma_v: float, sigma_u: float) -> float:
        """
        Theoretical Kyle's lambda:
        λ = σ_v / (2 * σ_u)
        
        Where σ_v is fundamental value volatility
        and σ_u is noise trader order flow volatility.
        """
        return sigma_v / (2 * sigma_u)
    
    def price_impact(self, order_size: float) -> float:
        """Predicted price impact for order size."""
        if self.lambda_ is None:
            raise ValueError("Must estimate lambda first")
        return self.lambda_ * order_size


class AlmgrenChriss:
    """
    Almgren-Chriss Optimal Execution Model (2001).
    
    Minimize: E[Cost] + λ * Var[Cost]
    
    For liquidating X shares over T periods with:
    - Temporary impact: g(v) = ε * sign(v) + η * v
    - Permanent impact: h(v) = γ * v
    
    Optimal trajectory is deterministic and depends on risk aversion.
    """
    
    def __init__(
        self,
        total_shares: float,
        time_periods: int,
        volatility: float,
        eta: float = 0.01,      # Temporary impact coefficient
        gamma: float = 0.001,    # Permanent impact coefficient
        epsilon: float = 0.0005  # Fixed temporary cost
    ):
        self.X = total_shares
        self.T = time_periods
        self.sigma = volatility
        self.eta = eta
        self.gamma = gamma
        self.epsilon = epsilon
    
    def optimal_trajectory(self, risk_aversion: float) -> np.ndarray:
        """
        Compute optimal execution trajectory.
        
        x_j = X * sinh(κ(T-j)) / sinh(κT)
        
        Where κ = sqrt(λσ² / η)
        """
        kappa_sq = risk_aversion * self.sigma ** 2 / self.eta
        
        if kappa_sq <= 0:
            # Risk-neutral: uniform execution
            trajectory = np.linspace(self.X, 0, self.T + 1)
        else:
            kappa = np.sqrt(kappa_sq)
            
            trajectory = np.zeros(self.T + 1)
            trajectory[0] = self.X
            
            for j in range(1, self.T + 1):
                trajectory[j] = self.X * np.sinh(kappa * (self.T - j)) / np.sinh(kappa * self.T)
        
        return trajectory
    
    def execution_cost(
        self,
        trajectory: np.ndarray,
        prices: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        Compute execution cost breakdown.
        
        Returns:
        - permanent_impact: Cost from permanent price impact
        - temporary_impact: Cost from temporary impact
        - volatility_cost: Expected cost from price volatility
        - total: Total expected cost
        """
        # Trade sizes
        trades = -np.diff(trajectory)
        
        # Permanent impact cost: γ * Σ(x_j * Σ_{k<=j} n_k)
        cumulative_trades = np.cumsum(trades)
        permanent = self.gamma * np.sum(trajectory[:-1] * cumulative_trades)
        
        # Temporary impact cost: Σ(η * n_j² / τ + ε * |n_j|)
        temporary = np.sum(self.eta * trades ** 2 + self.epsilon * np.abs(trades))
        
        # Volatility cost (expected from random price moves)
        remaining = trajectory[:-1]
        volatility_cost = 0.5 * self.sigma ** 2 * np.sum(remaining ** 2)
        
        return {
            'permanent_impact': permanent,
            'temporary_impact': temporary,
            'volatility_cost': volatility_cost,
            'total': permanent + temporary + volatility_cost
        }
    
    def twap_trajectory(self) -> np.ndarray:
        """Time-Weighted Average Price trajectory (uniform)."""
        return np.linspace(self.X, 0, self.T + 1)
    
    def vwap_weights(self, volume_profile: np.ndarray) -> np.ndarray:
        """
        Volume-Weighted trajectory given typical volume profile.
        """
        normalized = volume_profile / volume_profile.sum()
        trades = self.X * normalized
        trajectory = np.concatenate([[self.X], self.X - np.cumsum(trades)])
        return trajectory


class RollModel:
    """
    Roll (1984) Bid-Ask Spread Model.
    
    Estimates effective spread from transaction prices.
    
    If market is efficient:
        Cov(ΔP_t, ΔP_{t-1}) = -c²
    
    Where c = half-spread (effective spread = 2c)
    
    Uses: Spread estimation when quotes unavailable
    """
    
    @staticmethod
    def estimate_spread(prices: np.ndarray) -> Dict[str, float]:
        """
        Estimate bid-ask spread from transaction prices.
        
        Returns effective spread and related statistics.
        """
        returns = np.diff(np.log(prices))
        
        # Autocovariance at lag 1
        cov_1 = np.cov(returns[1:], returns[:-1])[0, 1]
        
        # Roll estimator: c = sqrt(-cov) if cov < 0
        if cov_1 < 0:
            half_spread = np.sqrt(-cov_1)
            effective_spread = 2 * half_spread
        else:
            # Positive autocovariance indicates non-bounce behavior
            half_spread = 0
            effective_spread = 0
        
        # Spread as percentage
        avg_price = np.mean(prices)
        spread_pct = effective_spread / avg_price * 100
        
        return {
            'half_spread': half_spread,
            'effective_spread': effective_spread,
            'spread_pct': spread_pct,
            'autocovariance': cov_1
        }


class VPIN:
    """
    Volume-Synchronized Probability of Informed Trading.
    
    VPIN = |V_buy - V_sell| / V_total
    
    Measures order flow toxicity / probability of informed trading.
    
    High VPIN = High probability of adverse selection
    
    Uses: Flash crash prediction, market making risk
    """
    
    def __init__(
        self,
        bucket_size: int = 50,  # Trades per bucket
        n_buckets: int = 50     # Rolling window
    ):
        self.bucket_size = bucket_size
        self.n_buckets = n_buckets
    
    def classify_trades(
        self,
        prices: np.ndarray,
        volumes: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Classify trades as buy or sell using tick rule.
        
        Buy: Price > previous price
        Sell: Price < previous price
        """
        price_changes = np.diff(prices)
        
        # Tick rule
        buy_volume = np.zeros(len(volumes) - 1)
        sell_volume = np.zeros(len(volumes) - 1)
        
        buy_mask = price_changes > 0
        sell_mask = price_changes < 0
        
        buy_volume[buy_mask] = volumes[1:][buy_mask]
        sell_volume[sell_mask] = volumes[1:][sell_mask]
        
        # Unchanged: split 50/50
        unchanged = price_changes == 0
        buy_volume[unchanged] = volumes[1:][unchanged] / 2
        sell_volume[unchanged] = volumes[1:][unchanged] / 2
        
        return buy_volume, sell_volume
    
    def compute(
        self,
        prices: np.ndarray,
        volumes: np.ndarray
    ) -> np.ndarray:
        """
        Compute rolling VPIN.
        
        Returns VPIN time series.
        """
        buy_vol, sell_vol = self.classify_trades(prices, volumes)
        
        # Aggregate into buckets
        n = len(buy_vol)
        n_complete_buckets = n // self.bucket_size
        
        bucket_buy = np.zeros(n_complete_buckets)
        bucket_sell = np.zeros(n_complete_buckets)
        
        for i in range(n_complete_buckets):
            start = i * self.bucket_size
            end = (i + 1) * self.bucket_size
            bucket_buy[i] = buy_vol[start:end].sum()
            bucket_sell[i] = sell_vol[start:end].sum()
        
        # Rolling VPIN
        vpin = np.zeros(len(bucket_buy))
        
        for i in range(self.n_buckets - 1, len(bucket_buy)):
            window_buy = bucket_buy[i - self.n_buckets + 1:i + 1].sum()
            window_sell = bucket_sell[i - self.n_buckets + 1:i + 1].sum()
            total = window_buy + window_sell
            
            if total > 0:
                vpin[i] = abs(window_buy - window_sell) / total
        
        return vpin


class MarketMaking:
    """
    Optimal Market Making (Avellaneda-Stoikov style).
    
    Models optimal bid/ask quotes for market maker.
    
    Optimal spread: δ = γσ²T + (2/γ)ln(1 + γ/k)
    
    Where:
    - γ: Risk aversion
    - σ: Volatility
    - T: Time horizon
    - k: Order arrival rate parameter
    """
    
    def __init__(
        self,
        volatility: float,
        gamma: float = 0.1,  # Risk aversion
        k: float = 1.5       # Order arrival intensity parameter
    ):
        self.sigma = volatility
        self.gamma = gamma
        self.k = k
    
    def optimal_spread(self, time_remaining: float) -> float:
        """
        Compute optimal bid-ask spread.
        
        δ* = γσ²T + (2/γ)ln(1 + γ/k)
        """
        term1 = self.gamma * self.sigma ** 2 * time_remaining
        term2 = (2 / self.gamma) * np.log(1 + self.gamma / self.k)
        
        return term1 + term2
    
    def reservation_price(
        self,
        mid_price: float,
        inventory: float,
        time_remaining: float
    ) -> float:
        """
        Reservation price adjusted for inventory.
        
        r = S - q * γ * σ² * T
        
        Where q is inventory (positive = long, negative = short)
        """
        return mid_price - inventory * self.gamma * self.sigma ** 2 * time_remaining
    
    def optimal_quotes(
        self,
        mid_price: float,
        inventory: float,
        time_remaining: float
    ) -> Tuple[float, float]:
        """
        Compute optimal bid and ask prices.
        
        Returns (bid, ask) tuple.
        """
        r = self.reservation_price(mid_price, inventory, time_remaining)
        spread = self.optimal_spread(time_remaining)
        
        bid = r - spread / 2
        ask = r + spread / 2
        
        return bid, ask
    
    def inventory_skew(self, inventory: float, max_inventory: float) -> float:
        """
        Compute quote skew based on inventory.
        
        Skew shifts quotes to reduce inventory risk.
        """
        return -self.gamma * inventory / max_inventory


class InformationShare:
    """
    Hasbrouck Information Share.
    
    Measures contribution of each venue to price discovery.
    
    Uses VAR/VEC model to decompose variance of efficient price
    innovations across markets.
    
    Uses: Multi-venue trading, price discovery analysis
    """
    
    @staticmethod
    def compute(
        prices: np.ndarray,  # (T, n_venues)
        max_lag: int = 5
    ) -> np.ndarray:
        """
        Compute information share for each venue.
        
        Simplified version using variance contribution.
        """
        n_venues = prices.shape[1]
        
        # Price changes
        returns = np.diff(prices, axis=0)
        
        # Covariance matrix
        cov = np.cov(returns.T)
        
        # Total variance
        total_var = cov.sum()
        
        # Information share: variance contribution
        info_share = np.diag(cov) / total_var
        
        # Normalize
        info_share = info_share / info_share.sum()
        
        return info_share
