"""
Markov Models for Trading
=========================
Hidden Markov Models, Markov Decision Processes, and related theory.

Mathematical Foundation:
- HMM: P(X_t | X_{t-1}) - Markov property
- Baum-Welch algorithm (EM) for parameter estimation
- Viterbi algorithm for most likely state sequence
- MDP: (S, A, P, R, γ) tuple formulation
- Bellman equations for value functions
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from scipy.special import logsumexp
import logging

logger = logging.getLogger(__name__)


@dataclass
class HMMParameters:
    """Hidden Markov Model parameters."""
    n_states: int  # Number of hidden states
    n_features: int  # Observation dimension
    
    # Initial state distribution: π_i = P(Z_1 = i)
    initial_probs: np.ndarray  # Shape: (n_states,)
    
    # Transition matrix: A_ij = P(Z_t = j | Z_{t-1} = i)
    transition_matrix: np.ndarray  # Shape: (n_states, n_states)
    
    # Emission parameters (Gaussian): μ_k, Σ_k for each state k
    means: np.ndarray  # Shape: (n_states, n_features)
    covariances: np.ndarray  # Shape: (n_states, n_features, n_features)


class HiddenMarkovModel:
    """
    Hidden Markov Model with Gaussian emissions.
    
    Model:
        Z_t | Z_{t-1} ~ Categorical(A[Z_{t-1}, :])  (hidden states)
        X_t | Z_t ~ N(μ_{Z_t}, Σ_{Z_t})             (observations)
    
    Uses:
        - Regime detection (bull/bear/sideways markets)
        - Volatility state estimation
        - Trend identification
    
    Algorithms:
        - Forward-Backward: P(Z_t | X_{1:T}) - posterior state probabilities
        - Viterbi: argmax P(Z_{1:T} | X_{1:T}) - most likely state sequence
        - Baum-Welch: EM algorithm for parameter estimation
    """
    
    def __init__(
        self,
        n_states: int = 3,
        n_features: int = 1,
        covariance_type: str = "full"
    ):
        self.n_states = n_states
        self.n_features = n_features
        self.covariance_type = covariance_type
        
        # Initialize parameters
        self._init_params()
        
        self.is_fitted = False
    
    def _init_params(self):
        """Initialize HMM parameters randomly."""
        # Uniform initial distribution
        self.initial_probs = np.ones(self.n_states) / self.n_states
        
        # Slightly sticky transition matrix (states persist)
        self.transition_matrix = np.ones((self.n_states, self.n_states)) * 0.1
        np.fill_diagonal(self.transition_matrix, 0.8)
        self.transition_matrix /= self.transition_matrix.sum(axis=1, keepdims=True)
        
        # Random means, identity covariances
        self.means = np.random.randn(self.n_states, self.n_features)
        self.covariances = np.array([
            np.eye(self.n_features) for _ in range(self.n_states)
        ])
    
    def _log_emission_probs(self, X: np.ndarray) -> np.ndarray:
        """
        Compute log emission probabilities: log P(X_t | Z_t = k)
        
        Using multivariate Gaussian:
        log P(x|μ,Σ) = -0.5 * [d*log(2π) + log|Σ| + (x-μ)ᵀΣ⁻¹(x-μ)]
        """
        T, d = X.shape
        log_probs = np.zeros((T, self.n_states))
        
        for k in range(self.n_states):
            diff = X - self.means[k]  # (T, d)
            
            # Precision matrix (inverse covariance)
            precision = np.linalg.inv(self.covariances[k])
            
            # Log determinant
            sign, log_det = np.linalg.slogdet(self.covariances[k])
            
            # Mahalanobis distance: (x-μ)ᵀΣ⁻¹(x-μ)
            mahal = np.sum(diff @ precision * diff, axis=1)
            
            # Log probability
            log_probs[:, k] = -0.5 * (
                d * np.log(2 * np.pi) + log_det + mahal
            )
        
        return log_probs
    
    def forward(self, X: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Forward algorithm: compute α_t(k) = P(X_{1:t}, Z_t = k)
        
        Recursion:
            α_1(k) = π_k * P(X_1 | Z_1 = k)
            α_t(k) = P(X_t | Z_t = k) * Σ_j α_{t-1}(j) * A_jk
        
        Returns:
            log_alpha: Log forward probabilities (T, n_states)
            log_likelihood: log P(X_{1:T})
        """
        T = X.shape[0]
        log_emission = self._log_emission_probs(X)
        
        # Log scale for numerical stability
        log_alpha = np.zeros((T, self.n_states))
        
        # Initialize: α_1(k) = π_k * b_k(X_1)
        log_alpha[0] = np.log(self.initial_probs + 1e-10) + log_emission[0]
        
        # Forward recursion
        for t in range(1, T):
            for k in range(self.n_states):
                # log Σ_j α_{t-1}(j) * A_jk
                log_trans = log_alpha[t-1] + np.log(self.transition_matrix[:, k] + 1e-10)
                log_alpha[t, k] = logsumexp(log_trans) + log_emission[t, k]
        
        # Total log likelihood: log P(X) = log Σ_k α_T(k)
        log_likelihood = logsumexp(log_alpha[-1])
        
        return log_alpha, log_likelihood
    
    def backward(self, X: np.ndarray) -> np.ndarray:
        """
        Backward algorithm: compute β_t(k) = P(X_{t+1:T} | Z_t = k)
        
        Recursion:
            β_T(k) = 1
            β_t(k) = Σ_j A_kj * P(X_{t+1} | Z_{t+1} = j) * β_{t+1}(j)
        """
        T = X.shape[0]
        log_emission = self._log_emission_probs(X)
        
        log_beta = np.zeros((T, self.n_states))
        # β_T = 1 (log β_T = 0)
        
        # Backward recursion
        for t in range(T - 2, -1, -1):
            for k in range(self.n_states):
                log_trans = (
                    np.log(self.transition_matrix[k, :] + 1e-10) +
                    log_emission[t + 1] +
                    log_beta[t + 1]
                )
                log_beta[t, k] = logsumexp(log_trans)
        
        return log_beta
    
    def forward_backward(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Forward-Backward algorithm for posterior state probabilities.
        
        Computes:
            γ_t(k) = P(Z_t = k | X_{1:T}) = α_t(k) * β_t(k) / P(X)
            ξ_t(j,k) = P(Z_t = j, Z_{t+1} = k | X_{1:T})
        
        Returns:
            gamma: State posteriors (T, n_states)
            xi: Transition posteriors (T-1, n_states, n_states)
        """
        log_alpha, log_likelihood = self.forward(X)
        log_beta = self.backward(X)
        
        # γ_t(k) = α_t(k) * β_t(k) / P(X)
        log_gamma = log_alpha + log_beta - log_likelihood
        gamma = np.exp(log_gamma)
        
        # ξ_t(j,k) computation
        T = X.shape[0]
        log_emission = self._log_emission_probs(X)
        xi = np.zeros((T - 1, self.n_states, self.n_states))
        
        for t in range(T - 1):
            for j in range(self.n_states):
                for k in range(self.n_states):
                    xi[t, j, k] = np.exp(
                        log_alpha[t, j] +
                        np.log(self.transition_matrix[j, k] + 1e-10) +
                        log_emission[t + 1, k] +
                        log_beta[t + 1, k] -
                        log_likelihood
                    )
        
        return gamma, xi
    
    def viterbi(self, X: np.ndarray) -> np.ndarray:
        """
        Viterbi algorithm: find most likely state sequence.
        
        Z*_{1:T} = argmax P(Z_{1:T} | X_{1:T})
        
        Dynamic programming:
            δ_t(k) = max_{Z_{1:t-1}} P(Z_{1:t-1}, Z_t = k, X_{1:t})
            ψ_t(k) = argmax_j δ_{t-1}(j) * A_jk
        """
        T = X.shape[0]
        log_emission = self._log_emission_probs(X)
        
        # δ and ψ tables
        log_delta = np.zeros((T, self.n_states))
        psi = np.zeros((T, self.n_states), dtype=int)
        
        # Initialize
        log_delta[0] = np.log(self.initial_probs + 1e-10) + log_emission[0]
        
        # Forward pass
        for t in range(1, T):
            for k in range(self.n_states):
                trans_probs = log_delta[t-1] + np.log(self.transition_matrix[:, k] + 1e-10)
                psi[t, k] = np.argmax(trans_probs)
                log_delta[t, k] = trans_probs[psi[t, k]] + log_emission[t, k]
        
        # Backtrack
        states = np.zeros(T, dtype=int)
        states[-1] = np.argmax(log_delta[-1])
        
        for t in range(T - 2, -1, -1):
            states[t] = psi[t + 1, states[t + 1]]
        
        return states
    
    def fit(self, X: np.ndarray, n_iter: int = 100, tol: float = 1e-4) -> 'HiddenMarkovModel':
        """
        Baum-Welch algorithm (EM) for parameter estimation.
        
        E-step: Compute γ_t(k) and ξ_t(j,k) using forward-backward
        M-step: Update parameters:
            π_k = γ_1(k)
            A_jk = Σ_t ξ_t(j,k) / Σ_t γ_t(j)
            μ_k = Σ_t γ_t(k) X_t / Σ_t γ_t(k)
            Σ_k = Σ_t γ_t(k) (X_t - μ_k)(X_t - μ_k)ᵀ / Σ_t γ_t(k)
        """
        T, d = X.shape
        prev_ll = -np.inf
        
        for iteration in range(n_iter):
            # E-step
            gamma, xi = self.forward_backward(X)
            _, log_likelihood = self.forward(X)
            
            # Check convergence
            if abs(log_likelihood - prev_ll) < tol:
                logger.info(f"HMM converged at iteration {iteration}")
                break
            prev_ll = log_likelihood
            
            # M-step
            # Update initial probabilities
            self.initial_probs = gamma[0] + 1e-10
            self.initial_probs /= self.initial_probs.sum()
            
            # Update transition matrix
            for j in range(self.n_states):
                for k in range(self.n_states):
                    self.transition_matrix[j, k] = xi[:, j, k].sum() / (gamma[:-1, j].sum() + 1e-10)
            self.transition_matrix /= self.transition_matrix.sum(axis=1, keepdims=True)
            
            # Update emission parameters
            for k in range(self.n_states):
                gamma_sum = gamma[:, k].sum() + 1e-10
                
                # Mean
                self.means[k] = (gamma[:, k:k+1] * X).sum(axis=0) / gamma_sum
                
                # Covariance
                diff = X - self.means[k]
                self.covariances[k] = (
                    (gamma[:, k:k+1, np.newaxis] * diff[:, :, np.newaxis] * diff[:, np.newaxis, :]).sum(axis=0)
                    / gamma_sum
                )
                # Regularization for numerical stability
                self.covariances[k] += 1e-4 * np.eye(d)
        
        self.is_fitted = True
        return self
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Get posterior state probabilities P(Z_t | X_{1:T})."""
        gamma, _ = self.forward_backward(X)
        return gamma
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Get most likely state sequence."""
        return self.viterbi(X)
    
    def score(self, X: np.ndarray) -> float:
        """Compute log-likelihood of observations."""
        _, log_likelihood = self.forward(X)
        return log_likelihood


class MarkovRegimeDetector:
    """
    Regime detection using HMM with financial market interpretation.
    
    States are interpreted as market regimes:
    - State 0: Bear market (low returns, high volatility)
    - State 1: Normal market (moderate returns/volatility)
    - State 2: Bull market (high returns, low volatility)
    
    Features used:
    - Returns
    - Realized volatility
    - Trend strength
    """
    
    def __init__(self, n_regimes: int = 3):
        self.n_regimes = n_regimes
        self.hmm = HiddenMarkovModel(n_states=n_regimes, n_features=3)
        
        # Regime labels (assigned after fitting based on mean returns)
        self.regime_labels = ['bear', 'neutral', 'bull']
    
    def _extract_features(self, prices: np.ndarray, window: int = 20) -> np.ndarray:
        """Extract regime-relevant features from price series."""
        # Returns
        returns = np.diff(np.log(prices))
        
        # Realized volatility (rolling std)
        vol = np.array([
            returns[max(0, i-window):i].std() if i > 0 else 0.01
            for i in range(len(returns))
        ])
        
        # Trend (rolling mean return)
        trend = np.array([
            returns[max(0, i-window):i].mean() if i > 0 else 0
            for i in range(len(returns))
        ])
        
        # Stack features
        features = np.column_stack([returns, vol, trend])
        
        return features
    
    def fit(self, prices: np.ndarray, **kwargs) -> 'MarkovRegimeDetector':
        """Fit regime detector to price series."""
        features = self._extract_features(prices)
        self.hmm.fit(features, **kwargs)
        
        # Assign labels based on mean returns per state
        mean_returns = self.hmm.means[:, 0]  # First feature is returns
        order = np.argsort(mean_returns)
        
        self.state_to_regime = {
            order[0]: 'bear',
            order[1]: 'neutral', 
            order[2]: 'bull'
        }
        
        return self
    
    def detect(self, prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect current regime.
        
        Returns:
            regimes: Most likely regime at each time
            probabilities: Posterior probabilities for each regime
        """
        features = self._extract_features(prices)
        
        states = self.hmm.predict(features)
        probs = self.hmm.predict_proba(features)
        
        regimes = np.array([self.state_to_regime.get(s, 'neutral') for s in states])
        
        return regimes, probs
    
    def get_current_regime(self, prices: np.ndarray) -> Dict[str, float]:
        """Get current regime with probabilities."""
        regimes, probs = self.detect(prices)
        
        current_probs = probs[-1]
        
        return {
            'regime': regimes[-1],
            'probabilities': {
                self.state_to_regime.get(i, f'state_{i}'): float(p)
                for i, p in enumerate(current_probs)
            },
            'confidence': float(current_probs.max())
        }


class MarkovDecisionProcess:
    """
    Markov Decision Process formulation for trading.
    
    MDP = (S, A, P, R, γ) where:
    - S: State space (market features + position)
    - A: Action space (buy, hold, sell / position sizes)
    - P: Transition probabilities P(s' | s, a)
    - R: Reward function R(s, a, s')
    - γ: Discount factor
    
    Bellman Equation:
        V*(s) = max_a [R(s,a) + γ Σ_{s'} P(s'|s,a) V*(s')]
        Q*(s,a) = R(s,a) + γ Σ_{s'} P(s'|s,a) max_{a'} Q*(s',a')
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        gamma: float = 0.99
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
    
    def bellman_optimality_backup(
        self,
        Q: np.ndarray,
        state: int,
        rewards: np.ndarray,
        transitions: np.ndarray
    ) -> np.ndarray:
        """
        Bellman optimality backup for Q-values.
        
        Q(s,a) <- R(s,a) + γ Σ_{s'} P(s'|s,a) max_{a'} Q(s',a')
        """
        new_Q = np.zeros(self.action_dim)
        
        for a in range(self.action_dim):
            expected_future = 0
            for s_next in range(len(Q)):
                expected_future += transitions[state, a, s_next] * Q[s_next].max()
            
            new_Q[a] = rewards[state, a] + self.gamma * expected_future
        
        return new_Q
    
    def value_iteration(
        self,
        rewards: np.ndarray,
        transitions: np.ndarray,
        n_iter: int = 1000,
        tol: float = 1e-6
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Value iteration algorithm.
        
        Finds optimal value function V* and policy π*.
        """
        n_states = rewards.shape[0]
        V = np.zeros(n_states)
        
        for _ in range(n_iter):
            V_new = np.zeros(n_states)
            
            for s in range(n_states):
                action_values = []
                for a in range(self.action_dim):
                    value = rewards[s, a] + self.gamma * np.sum(
                        transitions[s, a, :] * V
                    )
                    action_values.append(value)
                V_new[s] = max(action_values)
            
            if np.abs(V_new - V).max() < tol:
                break
            V = V_new
        
        # Extract policy
        policy = np.zeros(n_states, dtype=int)
        for s in range(n_states):
            action_values = []
            for a in range(self.action_dim):
                value = rewards[s, a] + self.gamma * np.sum(
                    transitions[s, a, :] * V
                )
                action_values.append(value)
            policy[s] = np.argmax(action_values)
        
        return V, policy


class BellmanOperator:
    """
    Bellman operators for reinforcement learning.
    
    Provides:
    - Bellman expectation operator (for policy evaluation)
    - Bellman optimality operator (for value iteration)
    - TD(0) and TD(λ) updates
    - Generalized Advantage Estimation (GAE)
    """
    
    def __init__(self, gamma: float = 0.99, lambda_: float = 0.95):
        self.gamma = gamma
        self.lambda_ = lambda_  # For TD(λ) and GAE
    
    def td_target(
        self,
        reward: float,
        next_value: float,
        done: bool
    ) -> float:
        """
        TD(0) target: r + γV(s')
        """
        return reward + self.gamma * next_value * (1 - done)
    
    def td_error(
        self,
        reward: float,
        value: float,
        next_value: float,
        done: bool
    ) -> float:
        """
        TD error: δ = r + γV(s') - V(s)
        """
        return self.td_target(reward, next_value, done) - value
    
    def gae(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        next_value: float,
        dones: np.ndarray
    ) -> np.ndarray:
        """
        Generalized Advantage Estimation.
        
        A^GAE(γ,λ) = Σ_{l=0}^{∞} (γλ)^l δ_{t+l}
        
        Where δ_t = r_t + γV(s_{t+1}) - V(s_t)
        
        This provides a bias-variance tradeoff:
        - λ=0: High bias, low variance (TD(0))
        - λ=1: Low bias, high variance (Monte Carlo)
        """
        T = len(rewards)
        advantages = np.zeros(T)
        last_gae = 0
        
        for t in reversed(range(T)):
            if t == T - 1:
                next_val = next_value
            else:
                next_val = values[t + 1]
            
            # TD error
            delta = rewards[t] + self.gamma * next_val * (1 - dones[t]) - values[t]
            
            # GAE recursion
            advantages[t] = last_gae = delta + self.gamma * self.lambda_ * (1 - dones[t]) * last_gae
        
        return advantages
    
    def n_step_return(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        n: int
    ) -> np.ndarray:
        """
        N-step return: G_t^{(n)} = Σ_{k=0}^{n-1} γ^k r_{t+k} + γ^n V(s_{t+n})
        """
        T = len(rewards)
        returns = np.zeros(T)
        
        for t in range(T):
            G = 0
            for k in range(min(n, T - t)):
                G += (self.gamma ** k) * rewards[t + k]
            
            # Bootstrap from value function
            if t + n < T:
                G += (self.gamma ** n) * values[t + n]
            
            returns[t] = G
        
        return returns
    
    def lambda_return(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        next_value: float,
        dones: np.ndarray
    ) -> np.ndarray:
        """
        TD(λ) return: G_t^λ = (1-λ) Σ_{n=1}^{∞} λ^{n-1} G_t^{(n)}
        
        Equivalent to: G_t^λ = r_t + γ[(1-λ)V(s_{t+1}) + λG_{t+1}^λ]
        """
        T = len(rewards)
        returns = np.zeros(T)
        
        # Work backwards
        G = next_value
        for t in reversed(range(T)):
            if dones[t]:
                G = rewards[t]
            else:
                G = rewards[t] + self.gamma * (
                    (1 - self.lambda_) * values[t + 1 if t + 1 < T else t] +
                    self.lambda_ * G
                )
            returns[t] = G
        
        return returns
