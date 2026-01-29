"""
Stochastic Processes for Financial Modeling
============================================
Mathematical models for price dynamics and volatility.

Models:
- Geometric Brownian Motion (GBM): Classic Black-Scholes dynamics
- Ornstein-Uhlenbeck (OU): Mean-reverting processes
- Jump-Diffusion: Merton's model with jumps
- Stochastic Volatility: Heston model
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class OrnsteinUhlenbeck:
    """
    Ornstein-Uhlenbeck (OU) Process - Mean-reverting dynamics.
    
    SDE: dX_t = θ(μ - X_t)dt + σdW_t
    
    Parameters:
        θ (kappa): Speed of mean reversion
        μ (mu): Long-term mean
        σ (sigma): Volatility
    
    Properties:
        E[X_t | X_0] = μ + (X_0 - μ)e^{-θt}
        Var[X_t | X_0] = (σ²/2θ)(1 - e^{-2θt})
        Stationary distribution: N(μ, σ²/2θ)
    
    Uses: Mean-reverting spreads, volatility, interest rates
    """
    
    def __init__(
        self,
        kappa: float = 1.0,   # Mean reversion speed
        mu: float = 0.0,      # Long-term mean
        sigma: float = 0.1    # Volatility
    ):
        self.kappa = kappa
        self.mu = mu
        self.sigma = sigma
    
    def expected_value(self, x0: float, t: float) -> float:
        """E[X_t | X_0 = x0]"""
        return self.mu + (x0 - self.mu) * np.exp(-self.kappa * t)
    
    def variance(self, t: float) -> float:
        """Var[X_t | X_0]"""
        return (self.sigma ** 2 / (2 * self.kappa)) * (1 - np.exp(-2 * self.kappa * t))
    
    def stationary_variance(self) -> float:
        """Long-run variance σ²/2θ"""
        return self.sigma ** 2 / (2 * self.kappa)
    
    def half_life(self) -> float:
        """Time for deviation to decay by half: ln(2)/θ"""
        return np.log(2) / self.kappa
    
    def simulate(
        self,
        x0: float,
        T: float,
        n_steps: int,
        n_paths: int = 1
    ) -> np.ndarray:
        """
        Exact simulation using analytic solution.
        
        X_{t+Δt} | X_t ~ N(μ + (X_t - μ)e^{-θΔt}, (σ²/2θ)(1 - e^{-2θΔt}))
        """
        dt = T / n_steps
        
        # Precompute constants
        exp_kappa = np.exp(-self.kappa * dt)
        std = np.sqrt(self.variance(dt))
        
        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = x0
        
        for t in range(n_steps):
            mean = self.mu + (paths[:, t] - self.mu) * exp_kappa
            paths[:, t + 1] = mean + std * np.random.randn(n_paths)
        
        return paths
    
    def fit(self, data: np.ndarray, dt: float = 1.0) -> 'OrnsteinUhlenbeck':
        """
        Estimate OU parameters from time series using MLE.
        
        For discrete observations X_1, ..., X_n with spacing Δt:
            X_{i+1} = α + β*X_i + ε,  ε ~ N(0, σ_ε²)
        
        Where:
            α = μ(1 - e^{-θΔt})
            β = e^{-θΔt}
            σ_ε² = (σ²/2θ)(1 - e^{-2θΔt})
        """
        n = len(data)
        
        # OLS regression: X_{t+1} = α + β*X_t + ε
        X = data[:-1]
        Y = data[1:]
        
        # Estimates
        beta = np.cov(X, Y)[0, 1] / np.var(X)
        alpha = np.mean(Y) - beta * np.mean(X)
        
        # Residual variance
        residuals = Y - (alpha + beta * X)
        sigma_e_sq = np.var(residuals)
        
        # Convert to OU parameters
        # β = e^{-θΔt} → θ = -ln(β)/Δt
        if beta > 0 and beta < 1:
            self.kappa = -np.log(beta) / dt
            self.mu = alpha / (1 - beta)
            self.sigma = np.sqrt(sigma_e_sq * 2 * self.kappa / (1 - beta ** 2))
        else:
            logger.warning("Invalid beta for OU fit, using defaults")
        
        return self
    
    def log_likelihood(self, data: np.ndarray, dt: float = 1.0) -> float:
        """Compute log-likelihood of observations."""
        exp_kappa = np.exp(-self.kappa * dt)
        var = self.variance(dt)
        
        ll = 0
        for i in range(len(data) - 1):
            mean = self.mu + (data[i] - self.mu) * exp_kappa
            ll += -0.5 * (np.log(2 * np.pi * var) + (data[i + 1] - mean) ** 2 / var)
        
        return ll


class GeometricBrownianMotion:
    """
    Geometric Brownian Motion (GBM) - Standard price dynamics.
    
    SDE: dS_t = μS_t dt + σS_t dW_t
    
    Solution: S_t = S_0 exp((μ - σ²/2)t + σW_t)
    
    Properties:
        E[S_t | S_0] = S_0 e^{μt}
        Var[S_t | S_0] = S_0² e^{2μt} (e^{σ²t} - 1)
        log(S_t/S_0) ~ N((μ - σ²/2)t, σ²t)
    """
    
    def __init__(self, mu: float = 0.05, sigma: float = 0.2):
        self.mu = mu      # Drift (annual)
        self.sigma = sigma  # Volatility (annual)
    
    def simulate(
        self,
        S0: float,
        T: float,
        n_steps: int,
        n_paths: int = 1
    ) -> np.ndarray:
        """Simulate GBM paths using exact solution."""
        dt = T / n_steps
        
        # Generate increments
        dW = np.random.randn(n_paths, n_steps) * np.sqrt(dt)
        
        # Cumulative sum for W_t
        W = np.cumsum(dW, axis=1)
        W = np.hstack([np.zeros((n_paths, 1)), W])
        
        # Time grid
        t = np.linspace(0, T, n_steps + 1)
        
        # Exact solution
        paths = S0 * np.exp((self.mu - 0.5 * self.sigma ** 2) * t + self.sigma * W)
        
        return paths
    
    def expected_price(self, S0: float, t: float) -> float:
        """E[S_t | S_0]"""
        return S0 * np.exp(self.mu * t)
    
    def price_quantile(self, S0: float, t: float, q: float) -> float:
        """q-th quantile of S_t distribution."""
        from scipy.stats import norm
        
        log_mean = np.log(S0) + (self.mu - 0.5 * self.sigma ** 2) * t
        log_std = self.sigma * np.sqrt(t)
        
        return np.exp(norm.ppf(q, log_mean, log_std))
    
    def fit(self, prices: np.ndarray, dt: float = 1/252) -> 'GeometricBrownianMotion':
        """Estimate parameters from price series."""
        log_returns = np.diff(np.log(prices))
        
        # MLE estimates
        mean_return = np.mean(log_returns) / dt
        var_return = np.var(log_returns) / dt
        
        self.sigma = np.sqrt(var_return)
        self.mu = mean_return + 0.5 * self.sigma ** 2
        
        return self


class JumpDiffusion:
    """
    Merton Jump-Diffusion Model.
    
    SDE: dS_t = (μ - λκ)S_t dt + σS_t dW_t + S_t dJ_t
    
    Where:
        J_t = Σ_{i=1}^{N_t} (Y_i - 1)  (compound Poisson process)
        N_t ~ Poisson(λt)              (number of jumps)
        Y_i ~ LogNormal(μ_J, σ_J²)     (jump size)
        κ = E[Y - 1] = exp(μ_J + σ_J²/2) - 1
    
    Uses: Fat tails, discontinuous price moves, crash modeling
    """
    
    def __init__(
        self,
        mu: float = 0.05,       # Drift
        sigma: float = 0.15,    # Diffusion volatility
        lam: float = 1.0,       # Jump intensity (jumps per year)
        mu_J: float = -0.1,     # Mean log jump size
        sigma_J: float = 0.1    # Jump size volatility
    ):
        self.mu = mu
        self.sigma = sigma
        self.lam = lam
        self.mu_J = mu_J
        self.sigma_J = sigma_J
        
        # Expected jump contribution
        self.kappa = np.exp(mu_J + 0.5 * sigma_J ** 2) - 1
    
    def simulate(
        self,
        S0: float,
        T: float,
        n_steps: int,
        n_paths: int = 1
    ) -> np.ndarray:
        """Simulate jump-diffusion paths."""
        dt = T / n_steps
        
        paths = np.zeros((n_paths, n_steps + 1))
        paths[:, 0] = S0
        
        for t in range(n_steps):
            # Diffusion component
            dW = np.random.randn(n_paths) * np.sqrt(dt)
            
            # Jump component
            n_jumps = np.random.poisson(self.lam * dt, n_paths)
            jump_sizes = np.zeros(n_paths)
            
            for i in range(n_paths):
                if n_jumps[i] > 0:
                    jumps = np.exp(
                        self.mu_J + self.sigma_J * np.random.randn(n_jumps[i])
                    ) - 1
                    jump_sizes[i] = np.prod(1 + jumps) - 1
            
            # Update price
            drift = (self.mu - self.lam * self.kappa - 0.5 * self.sigma ** 2) * dt
            diffusion = self.sigma * dW
            
            paths[:, t + 1] = paths[:, t] * np.exp(drift + diffusion) * (1 + jump_sizes)
        
        return paths
    
    def characteristic_function(self, u: complex, t: float) -> complex:
        """
        Characteristic function φ(u) = E[exp(iu log(S_t/S_0))]
        
        Used for option pricing via FFT.
        """
        iu = 1j * u
        
        # Diffusion part
        cf_diffusion = np.exp(
            iu * (self.mu - 0.5 * self.sigma ** 2) * t -
            0.5 * self.sigma ** 2 * u ** 2 * t
        )
        
        # Jump part
        jump_cf = np.exp(iu * self.mu_J - 0.5 * self.sigma_J ** 2 * u ** 2) - 1
        cf_jump = np.exp(self.lam * t * jump_cf)
        
        return cf_diffusion * cf_jump


class StochasticVolatility:
    """
    Heston Stochastic Volatility Model.
    
    SDEs:
        dS_t = μS_t dt + √V_t S_t dW_t^S
        dV_t = κ(θ - V_t)dt + ξ√V_t dW_t^V
        
    With correlation: dW_t^S dW_t^V = ρ dt
    
    Parameters:
        μ: Drift of price
        κ: Mean reversion speed of variance
        θ: Long-term variance
        ξ: Vol of vol
        ρ: Correlation between price and vol
        V_0: Initial variance
    
    Feller condition: 2κθ > ξ² (ensures V_t > 0)
    """
    
    def __init__(
        self,
        mu: float = 0.05,
        kappa: float = 2.0,
        theta: float = 0.04,    # Long-term variance (vol = 20%)
        xi: float = 0.3,        # Vol of vol
        rho: float = -0.7,      # Typically negative (leverage effect)
        V0: float = 0.04
    ):
        self.mu = mu
        self.kappa = kappa
        self.theta = theta
        self.xi = xi
        self.rho = rho
        self.V0 = V0
        
        # Check Feller condition
        if 2 * kappa * theta <= xi ** 2:
            logger.warning("Feller condition not satisfied: variance can hit zero")
    
    def simulate(
        self,
        S0: float,
        T: float,
        n_steps: int,
        n_paths: int = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simulate Heston model using Euler-Maruyama with full truncation.
        
        Returns price paths and variance paths.
        """
        dt = T / n_steps
        
        # Correlated Brownian motions
        dW1 = np.random.randn(n_paths, n_steps) * np.sqrt(dt)
        dW2_indep = np.random.randn(n_paths, n_steps) * np.sqrt(dt)
        dW2 = self.rho * dW1 + np.sqrt(1 - self.rho ** 2) * dW2_indep
        
        S = np.zeros((n_paths, n_steps + 1))
        V = np.zeros((n_paths, n_steps + 1))
        
        S[:, 0] = S0
        V[:, 0] = self.V0
        
        for t in range(n_steps):
            V_pos = np.maximum(V[:, t], 0)  # Full truncation
            sqrt_V = np.sqrt(V_pos)
            
            # Variance update
            V[:, t + 1] = (
                V[:, t] +
                self.kappa * (self.theta - V_pos) * dt +
                self.xi * sqrt_V * dW2[:, t]
            )
            V[:, t + 1] = np.maximum(V[:, t + 1], 0)  # Ensure non-negative
            
            # Price update (log scheme)
            S[:, t + 1] = S[:, t] * np.exp(
                (self.mu - 0.5 * V_pos) * dt +
                sqrt_V * dW1[:, t]
            )
        
        return S, V
    
    def implied_volatility_surface(
        self,
        S0: float,
        strikes: np.ndarray,
        maturities: np.ndarray,
        r: float = 0.0
    ) -> np.ndarray:
        """
        Compute implied volatility surface using Monte Carlo.
        
        Note: In practice, use semi-analytic formula via characteristic function.
        """
        n_strikes = len(strikes)
        n_maturities = len(maturities)
        iv_surface = np.zeros((n_maturities, n_strikes))
        
        # Monte Carlo pricing (simplified)
        n_paths = 10000
        
        for i, T in enumerate(maturities):
            S_paths, _ = self.simulate(S0, T, int(252 * T), n_paths)
            S_T = S_paths[:, -1]
            
            for j, K in enumerate(strikes):
                # Call option payoff
                payoff = np.maximum(S_T - K, 0)
                price = np.exp(-r * T) * np.mean(payoff)
                
                # Invert Black-Scholes for implied vol (Newton-Raphson)
                iv_surface[i, j] = self._implied_vol_newton(
                    price, S0, K, T, r
                )
        
        return iv_surface
    
    def _implied_vol_newton(
        self,
        price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        tol: float = 1e-6,
        max_iter: int = 100
    ) -> float:
        """Compute implied vol using Newton-Raphson."""
        from scipy.stats import norm
        
        sigma = 0.2  # Initial guess
        
        for _ in range(max_iter):
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            bs_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            vega = S * norm.pdf(d1) * np.sqrt(T)
            
            if vega < 1e-10:
                break
            
            diff = bs_price - price
            if abs(diff) < tol:
                break
            
            sigma = sigma - diff / vega
            sigma = max(0.001, min(sigma, 5.0))  # Bounds
        
        return sigma
