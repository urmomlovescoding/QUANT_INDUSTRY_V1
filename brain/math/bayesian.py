"""
Bayesian Methods for Trading
============================
Bayesian inference, state estimation, and uncertainty quantification.

Mathematical Foundation:
- Bayes' Theorem: P(θ|X) ∝ P(X|θ)P(θ)
- Kalman Filter: Optimal linear state estimation
- Particle Filter: Sequential Monte Carlo
- Gaussian Processes: Non-parametric function approximation
- Variational Inference: Approximate posterior
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Optional, Tuple, List, Dict, Callable
from dataclasses import dataclass
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class BayesianEstimator:
    """
    Bayesian parameter estimation with conjugate priors.
    
    For Gaussian likelihood with unknown mean and known variance:
        Prior: μ ~ N(μ_0, σ_0²)
        Likelihood: X_i ~ N(μ, σ²)
        Posterior: μ | X ~ N(μ_n, σ_n²)
        
    Where:
        μ_n = (σ_0² * Σx_i + σ² * μ_0) / (n*σ_0² + σ²)
        σ_n² = (σ_0² * σ²) / (n*σ_0² + σ²)
    
    Uses: Estimating expected returns, volatility, Sharpe ratios
    """
    
    def __init__(
        self,
        prior_mean: float = 0.0,
        prior_std: float = 1.0,
        likelihood_std: float = 0.02  # Typical daily return std
    ):
        self.prior_mean = prior_mean
        self.prior_std = prior_std
        self.prior_var = prior_std ** 2
        self.likelihood_std = likelihood_std
        self.likelihood_var = likelihood_std ** 2
        
        # Posterior starts at prior
        self.posterior_mean = prior_mean
        self.posterior_var = self.prior_var
    
    def update(self, observations: np.ndarray) -> Tuple[float, float]:
        """
        Update posterior with new observations.
        
        Uses Bayesian updating formula for Gaussian conjugate prior.
        """
        n = len(observations)
        if n == 0:
            return self.posterior_mean, np.sqrt(self.posterior_var)
        
        sample_mean = observations.mean()
        
        # Posterior precision = prior precision + data precision
        prior_precision = 1 / self.prior_var
        data_precision = n / self.likelihood_var
        posterior_precision = prior_precision + data_precision
        
        # Posterior mean is precision-weighted average
        self.posterior_mean = (
            prior_precision * self.prior_mean + 
            data_precision * sample_mean
        ) / posterior_precision
        
        self.posterior_var = 1 / posterior_precision
        
        return self.posterior_mean, np.sqrt(self.posterior_var)
    
    def credible_interval(self, alpha: float = 0.05) -> Tuple[float, float]:
        """Compute Bayesian credible interval."""
        z = stats.norm.ppf(1 - alpha / 2)
        std = np.sqrt(self.posterior_var)
        
        return (
            self.posterior_mean - z * std,
            self.posterior_mean + z * std
        )
    
    def probability_positive(self) -> float:
        """P(μ > 0) - probability that true mean is positive."""
        return 1 - stats.norm.cdf(0, self.posterior_mean, np.sqrt(self.posterior_var))


class KalmanFilter:
    """
    Kalman Filter for linear state estimation.
    
    State-space model:
        x_t = F * x_{t-1} + w_t,  w_t ~ N(0, Q)  (state transition)
        y_t = H * x_t + v_t,      v_t ~ N(0, R)  (observation)
    
    Kalman recursion:
        Predict:
            x̂_{t|t-1} = F * x̂_{t-1|t-1}
            P_{t|t-1} = F * P_{t-1|t-1} * Fᵀ + Q
        
        Update:
            K_t = P_{t|t-1} * Hᵀ * (H * P_{t|t-1} * Hᵀ + R)⁻¹  (Kalman gain)
            x̂_{t|t} = x̂_{t|t-1} + K_t * (y_t - H * x̂_{t|t-1})
            P_{t|t} = (I - K_t * H) * P_{t|t-1}
    
    Uses: Trend extraction, volatility filtering, alpha estimation
    """
    
    def __init__(
        self,
        state_dim: int,
        obs_dim: int,
        F: Optional[np.ndarray] = None,  # State transition matrix
        H: Optional[np.ndarray] = None,  # Observation matrix
        Q: Optional[np.ndarray] = None,  # Process noise covariance
        R: Optional[np.ndarray] = None,  # Observation noise covariance
    ):
        self.state_dim = state_dim
        self.obs_dim = obs_dim
        
        # Default to random walk model
        self.F = F if F is not None else np.eye(state_dim)
        self.H = H if H is not None else np.eye(obs_dim, state_dim)
        self.Q = Q if Q is not None else np.eye(state_dim) * 0.01
        self.R = R if R is not None else np.eye(obs_dim) * 0.1
        
        # State estimate and covariance
        self.x = np.zeros(state_dim)
        self.P = np.eye(state_dim)
    
    def predict(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict step: propagate state forward.
        
        x̂_{t|t-1} = F * x̂_{t-1|t-1}
        P_{t|t-1} = F * P_{t-1|t-1} * Fᵀ + Q
        """
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        return self.x.copy(), self.P.copy()
    
    def update(self, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Update step: incorporate observation.
        
        K = P * Hᵀ * (H * P * Hᵀ + R)⁻¹
        x = x + K * (y - H * x)
        P = (I - K * H) * P
        """
        # Innovation
        innovation = y - self.H @ self.x
        
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        
        # Kalman gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        self.x = self.x + K @ innovation
        
        # Update covariance (Joseph form for numerical stability)
        I_KH = np.eye(self.state_dim) - K @ self.H
        self.P = I_KH @ self.P @ I_KH.T + K @ self.R @ K.T
        
        return self.x.copy(), self.P.copy()
    
    def filter(self, observations: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run Kalman filter on observation sequence.
        
        Returns filtered state estimates and covariances.
        """
        T = observations.shape[0]
        
        states = np.zeros((T, self.state_dim))
        covariances = np.zeros((T, self.state_dim, self.state_dim))
        
        for t in range(T):
            self.predict()
            self.update(observations[t])
            
            states[t] = self.x
            covariances[t] = self.P
        
        return states, covariances
    
    def smooth(self, observations: np.ndarray) -> np.ndarray:
        """
        Rauch-Tung-Striebel smoother for offline estimation.
        
        Uses future observations to improve past estimates.
        """
        # Forward pass
        T = observations.shape[0]
        
        forward_states = np.zeros((T, self.state_dim))
        forward_covs = np.zeros((T, self.state_dim, self.state_dim))
        predicted_states = np.zeros((T, self.state_dim))
        predicted_covs = np.zeros((T, self.state_dim, self.state_dim))
        
        for t in range(T):
            x_pred, P_pred = self.predict()
            predicted_states[t] = x_pred
            predicted_covs[t] = P_pred
            
            x_filt, P_filt = self.update(observations[t])
            forward_states[t] = x_filt
            forward_covs[t] = P_filt
        
        # Backward pass
        smoothed_states = forward_states.copy()
        
        for t in range(T - 2, -1, -1):
            # Smoother gain
            J = forward_covs[t] @ self.F.T @ np.linalg.inv(predicted_covs[t + 1])
            
            # Smoothed state
            smoothed_states[t] = forward_states[t] + J @ (smoothed_states[t + 1] - predicted_states[t + 1])
        
        return smoothed_states


class ParticleFilter:
    """
    Particle Filter (Sequential Monte Carlo) for nonlinear state estimation.
    
    Approximates posterior with weighted particles:
        P(x_t | y_{1:t}) ≈ Σ_i w_t^i δ(x_t - x_t^i)
    
    Algorithm:
        1. Propagate: x_t^i ~ P(x_t | x_{t-1}^i)
        2. Weight: w_t^i ∝ w_{t-1}^i * P(y_t | x_t^i)
        3. Resample if effective sample size < threshold
    
    Uses: Nonlinear dynamics, non-Gaussian noise, multimodal posteriors
    """
    
    def __init__(
        self,
        n_particles: int = 1000,
        state_dim: int = 1,
        transition_fn: Optional[Callable] = None,
        observation_fn: Optional[Callable] = None,
        transition_noise: float = 0.01,
        observation_noise: float = 0.1
    ):
        self.n_particles = n_particles
        self.state_dim = state_dim
        
        # Default to random walk with Gaussian observation
        self.transition_fn = transition_fn or (lambda x: x + np.random.randn(*x.shape) * transition_noise)
        self.observation_fn = observation_fn or (lambda x: x)
        
        self.transition_noise = transition_noise
        self.observation_noise = observation_noise
        
        # Initialize particles
        self.particles = np.random.randn(n_particles, state_dim)
        self.weights = np.ones(n_particles) / n_particles
    
    def predict(self):
        """Propagate particles through transition dynamics."""
        self.particles = self.transition_fn(self.particles)
    
    def update(self, observation: np.ndarray):
        """Update weights based on observation likelihood."""
        # Compute likelihoods
        predicted_obs = self.observation_fn(self.particles)
        
        # Gaussian likelihood
        likelihoods = np.exp(
            -0.5 * np.sum((predicted_obs - observation) ** 2, axis=-1) / self.observation_noise ** 2
        )
        
        # Update weights
        self.weights *= likelihoods
        self.weights /= self.weights.sum() + 1e-10
    
    def resample(self):
        """Resample particles based on weights (systematic resampling)."""
        n = self.n_particles
        positions = (np.arange(n) + np.random.random()) / n
        
        cumsum = np.cumsum(self.weights)
        indices = np.searchsorted(cumsum, positions)
        
        self.particles = self.particles[indices]
        self.weights = np.ones(n) / n
    
    def effective_sample_size(self) -> float:
        """Compute effective sample size: 1 / Σ w_i²"""
        return 1.0 / np.sum(self.weights ** 2)
    
    def filter_step(self, observation: np.ndarray, resample_threshold: float = 0.5):
        """Single filter step with optional resampling."""
        self.predict()
        self.update(observation)
        
        # Resample if ESS too low
        if self.effective_sample_size() < resample_threshold * self.n_particles:
            self.resample()
    
    def estimate(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get weighted mean and variance estimate."""
        mean = np.average(self.particles, weights=self.weights, axis=0)
        var = np.average((self.particles - mean) ** 2, weights=self.weights, axis=0)
        return mean, var


class GaussianProcess:
    """
    Gaussian Process for function approximation with uncertainty.
    
    f(x) ~ GP(m(x), k(x, x'))
    
    Posterior given observations (X, y):
        f(x*) | X, y ~ N(μ*, σ*²)
        μ* = k(x*, X) * [k(X, X) + σ_n² I]⁻¹ * y
        σ*² = k(x*, x*) - k(x*, X) * [k(X, X) + σ_n² I]⁻¹ * k(X, x*)
    
    Uses: Non-parametric prediction, uncertainty quantification
    """
    
    def __init__(
        self,
        kernel: str = "rbf",
        length_scale: float = 1.0,
        variance: float = 1.0,
        noise_variance: float = 0.01
    ):
        self.kernel = kernel
        self.length_scale = length_scale
        self.variance = variance
        self.noise_variance = noise_variance
        
        self.X_train = None
        self.y_train = None
        self.K_inv = None
    
    def _kernel(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        """Compute kernel matrix K(X1, X2)."""
        if self.kernel == "rbf":
            # RBF (squared exponential) kernel
            # k(x, x') = σ² * exp(-||x - x'||² / (2l²))
            diff = X1[:, np.newaxis, :] - X2[np.newaxis, :, :]
            sq_dist = np.sum(diff ** 2, axis=-1)
            return self.variance * np.exp(-sq_dist / (2 * self.length_scale ** 2))
        
        elif self.kernel == "matern32":
            # Matérn 3/2 kernel
            diff = X1[:, np.newaxis, :] - X2[np.newaxis, :, :]
            r = np.sqrt(np.sum(diff ** 2, axis=-1))
            sqrt3_r = np.sqrt(3) * r / self.length_scale
            return self.variance * (1 + sqrt3_r) * np.exp(-sqrt3_r)
        
        else:
            raise ValueError(f"Unknown kernel: {self.kernel}")
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fit GP to training data."""
        self.X_train = X
        self.y_train = y
        
        # Compute kernel matrix with noise
        K = self._kernel(X, X) + self.noise_variance * np.eye(len(X))
        
        # Compute inverse (using Cholesky for stability)
        L = np.linalg.cholesky(K + 1e-6 * np.eye(len(K)))
        self.K_inv = np.linalg.solve(L.T, np.linalg.solve(L, np.eye(len(K))))
        
        return self
    
    def predict(self, X_test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict at test points with uncertainty.
        
        Returns:
            mean: Posterior mean
            std: Posterior standard deviation
        """
        if self.X_train is None:
            raise ValueError("Must fit GP before predicting")
        
        # Cross-covariance
        K_star = self._kernel(X_test, self.X_train)
        
        # Posterior mean
        mean = K_star @ self.K_inv @ self.y_train
        
        # Posterior variance
        K_star_star = self._kernel(X_test, X_test)
        var = np.diag(K_star_star - K_star @ self.K_inv @ K_star.T)
        var = np.maximum(var, 1e-10)  # Numerical stability
        
        return mean, np.sqrt(var)


class VariationalInference:
    """
    Variational Inference for approximate Bayesian inference.
    
    Approximates intractable posterior P(z|x) with tractable q(z):
        q*(z) = argmin_q KL(q(z) || P(z|x))
    
    Equivalent to maximizing Evidence Lower Bound (ELBO):
        ELBO = E_q[log P(x,z)] - E_q[log q(z)]
             = E_q[log P(x|z)] - KL(q(z) || P(z))
    
    Uses: Approximate posteriors, Bayesian neural networks
    """
    
    def __init__(
        self,
        latent_dim: int,
        family: str = "gaussian"  # Variational family
    ):
        self.latent_dim = latent_dim
        self.family = family
        
        # Variational parameters (mean and log-variance for Gaussian)
        self.mu = np.zeros(latent_dim)
        self.log_var = np.zeros(latent_dim)
    
    def sample(self, n_samples: int = 1) -> np.ndarray:
        """Sample from variational distribution using reparameterization."""
        eps = np.random.randn(n_samples, self.latent_dim)
        std = np.exp(0.5 * self.log_var)
        return self.mu + std * eps
    
    def log_prob(self, z: np.ndarray) -> np.ndarray:
        """Log probability under variational distribution."""
        var = np.exp(self.log_var)
        return -0.5 * np.sum(
            np.log(2 * np.pi) + self.log_var + (z - self.mu) ** 2 / var,
            axis=-1
        )
    
    def kl_divergence(self, prior_mu: float = 0.0, prior_var: float = 1.0) -> float:
        """
        KL divergence from variational to prior.
        
        For Gaussian:
        KL(q||p) = 0.5 * Σ[log(σ_p²/σ_q²) + σ_q²/σ_p² + (μ_q - μ_p)²/σ_p² - 1]
        """
        var = np.exp(self.log_var)
        
        kl = 0.5 * np.sum(
            np.log(prior_var / var) +
            var / prior_var +
            (self.mu - prior_mu) ** 2 / prior_var - 1
        )
        
        return kl
    
    def elbo(
        self,
        log_likelihood_fn: Callable,
        n_samples: int = 100
    ) -> float:
        """
        Estimate ELBO using Monte Carlo.
        
        ELBO = E_q[log P(x|z)] - KL(q(z) || P(z))
        """
        # Sample from variational distribution
        z_samples = self.sample(n_samples)
        
        # Estimate E_q[log P(x|z)]
        log_lik = np.mean([log_likelihood_fn(z) for z in z_samples])
        
        # KL term
        kl = self.kl_divergence()
        
        return log_lik - kl
    
    def update(
        self,
        log_likelihood_fn: Callable,
        learning_rate: float = 0.01,
        n_samples: int = 10
    ):
        """
        One step of variational optimization using reparameterization gradient.
        """
        # Sample with reparameterization
        eps = np.random.randn(n_samples, self.latent_dim)
        std = np.exp(0.5 * self.log_var)
        z = self.mu + std * eps
        
        # Numerical gradients (would use autograd in practice)
        delta = 1e-5
        
        grad_mu = np.zeros(self.latent_dim)
        grad_log_var = np.zeros(self.latent_dim)
        
        for i in range(self.latent_dim):
            # Gradient w.r.t. mu
            self.mu[i] += delta
            elbo_plus = self.elbo(log_likelihood_fn, n_samples=5)
            self.mu[i] -= 2 * delta
            elbo_minus = self.elbo(log_likelihood_fn, n_samples=5)
            self.mu[i] += delta
            grad_mu[i] = (elbo_plus - elbo_minus) / (2 * delta)
            
            # Gradient w.r.t. log_var
            self.log_var[i] += delta
            elbo_plus = self.elbo(log_likelihood_fn, n_samples=5)
            self.log_var[i] -= 2 * delta
            elbo_minus = self.elbo(log_likelihood_fn, n_samples=5)
            self.log_var[i] += delta
            grad_log_var[i] = (elbo_plus - elbo_minus) / (2 * delta)
        
        # Gradient ascent on ELBO
        self.mu += learning_rate * grad_mu
        self.log_var += learning_rate * grad_log_var
