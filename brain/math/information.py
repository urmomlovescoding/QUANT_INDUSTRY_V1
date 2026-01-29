"""
Information Theory for Trading
==============================
Entropy, mutual information, and information-theoretic metrics.

Uses:
- Feature selection (mutual information)
- Model comparison (KL divergence)
- Signal strength (information gain)
- Portfolio diversification (entropy)
"""

import numpy as np
from typing import Optional, Tuple
from scipy import stats
from scipy.special import digamma
import logging

logger = logging.getLogger(__name__)


class EntropyEstimator:
    """
    Entropy estimation for continuous and discrete distributions.
    
    Shannon Entropy: H(X) = -Σ p(x) log p(x)
    Differential Entropy: h(X) = -∫ p(x) log p(x) dx
    
    Uses: Uncertainty quantification, diversity measurement
    """
    
    @staticmethod
    def discrete(probs: np.ndarray, base: float = np.e) -> float:
        """
        Shannon entropy for discrete distribution.
        
        H(X) = -Σ p_i log(p_i)
        """
        probs = np.asarray(probs)
        probs = probs[probs > 0]  # Avoid log(0)
        return -np.sum(probs * np.log(probs)) / np.log(base)
    
    @staticmethod
    def gaussian(sigma: np.ndarray) -> float:
        """
        Differential entropy for multivariate Gaussian.
        
        h(X) = 0.5 * log((2πe)^d |Σ|) = 0.5 * (d*log(2πe) + log|Σ|)
        """
        d = len(sigma) if sigma.ndim == 1 else sigma.shape[0]
        
        if sigma.ndim == 1:
            log_det = np.sum(np.log(sigma))
        else:
            sign, log_det = np.linalg.slogdet(sigma)
            log_det = log_det if sign > 0 else -np.inf
        
        return 0.5 * (d * np.log(2 * np.pi * np.e) + log_det)
    
    @staticmethod
    def knn(X: np.ndarray, k: int = 5) -> float:
        """
        K-nearest neighbor entropy estimator (Kozachenko-Leonenko).
        
        Non-parametric estimator using k-NN distances.
        """
        from scipy.spatial import cKDTree
        
        n, d = X.shape
        
        # Build KD-tree
        tree = cKDTree(X)
        
        # Find k-th nearest neighbor distances
        dists, _ = tree.query(X, k=k+1)  # +1 because point is its own neighbor
        knn_dists = dists[:, -1]  # k-th neighbor distance
        
        # Kozachenko-Leonenko estimator
        # h = (d/n) Σ log(2 * ε_i) + log(n-1) - ψ(k) + d*log(V_d)
        # where V_d is volume of d-dimensional unit ball
        
        log_V_d = (d / 2) * np.log(np.pi) - np.log(np.math.gamma(d / 2 + 1))
        
        entropy = (
            d * np.mean(np.log(2 * knn_dists + 1e-10)) +
            np.log(n - 1) -
            digamma(k) +
            log_V_d
        )
        
        return entropy


class MutualInformation:
    """
    Mutual Information estimation.
    
    I(X; Y) = H(X) + H(Y) - H(X, Y)
            = E[log(p(x,y) / (p(x)p(y)))]
    
    Uses: Feature selection, dependency measurement
    """
    
    @staticmethod
    def discrete(joint_probs: np.ndarray) -> float:
        """
        MI for discrete variables from joint probability table.
        
        I(X; Y) = Σ_x Σ_y p(x,y) log(p(x,y) / (p(x)p(y)))
        """
        # Marginals
        p_x = joint_probs.sum(axis=1)
        p_y = joint_probs.sum(axis=0)
        
        # Compute MI
        mi = 0
        for i in range(joint_probs.shape[0]):
            for j in range(joint_probs.shape[1]):
                if joint_probs[i, j] > 0 and p_x[i] > 0 and p_y[j] > 0:
                    mi += joint_probs[i, j] * np.log(
                        joint_probs[i, j] / (p_x[i] * p_y[j])
                    )
        
        return mi
    
    @staticmethod
    def knn(X: np.ndarray, Y: np.ndarray, k: int = 5) -> float:
        """
        KNN-based MI estimator (Kraskov et al.).
        
        Non-parametric estimator using k-NN in joint and marginal spaces.
        """
        from scipy.spatial import cKDTree
        
        n = len(X)
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        if Y.ndim == 1:
            Y = Y.reshape(-1, 1)
        
        # Joint space
        XY = np.hstack([X, Y])
        tree_XY = cKDTree(XY)
        
        # Find k-th neighbor distance in joint space
        dists_XY, _ = tree_XY.query(XY, k=k+1)
        eps = dists_XY[:, -1]
        
        # Count neighbors in marginal spaces within eps
        tree_X = cKDTree(X)
        tree_Y = cKDTree(Y)
        
        n_x = np.array([len(tree_X.query_ball_point(X[i], eps[i])) - 1 for i in range(n)])
        n_y = np.array([len(tree_Y.query_ball_point(Y[i], eps[i])) - 1 for i in range(n)])
        
        # Kraskov estimator
        mi = digamma(k) - np.mean(digamma(n_x + 1) + digamma(n_y + 1)) + digamma(n)
        
        return max(0, mi)  # MI is non-negative
    
    @staticmethod
    def regression_mi(X: np.ndarray, Y: np.ndarray) -> float:
        """
        MI estimated via regression (assumes Gaussian relationship).
        
        I(X; Y) ≈ -0.5 * log(1 - ρ²) for bivariate Gaussian
        """
        if X.ndim == 1 and Y.ndim == 1:
            corr = np.corrcoef(X, Y)[0, 1]
            return -0.5 * np.log(1 - corr ** 2 + 1e-10)
        else:
            # Multivariate: use canonical correlations
            from scipy.linalg import svd
            
            # Center data
            X = X - X.mean(axis=0)
            Y = Y - Y.mean(axis=0)
            
            # Cross-covariance
            Cxy = X.T @ Y / len(X)
            
            # SVD for canonical correlations
            _, s, _ = svd(Cxy)
            
            # MI as sum over canonical correlations
            mi = -0.5 * np.sum(np.log(1 - np.minimum(s ** 2, 0.9999)))
            
            return mi


class KLDivergence:
    """
    Kullback-Leibler Divergence.
    
    KL(P || Q) = Σ p(x) log(p(x) / q(x))
               = E_P[log(P/Q)]
    
    Properties:
    - Non-negative: KL ≥ 0
    - Not symmetric: KL(P||Q) ≠ KL(Q||P)
    - KL = 0 iff P = Q
    
    Uses: Model comparison, distribution matching, VAE loss
    """
    
    @staticmethod
    def discrete(p: np.ndarray, q: np.ndarray) -> float:
        """KL divergence between discrete distributions."""
        p = np.asarray(p) + 1e-10
        q = np.asarray(q) + 1e-10
        
        return np.sum(p * np.log(p / q))
    
    @staticmethod
    def gaussian(
        mu_p: np.ndarray, cov_p: np.ndarray,
        mu_q: np.ndarray, cov_q: np.ndarray
    ) -> float:
        """
        KL divergence between multivariate Gaussians.
        
        KL(P || Q) = 0.5 * [log|Σ_Q|/|Σ_P| - d + tr(Σ_Q⁻¹Σ_P) + (μ_Q-μ_P)ᵀΣ_Q⁻¹(μ_Q-μ_P)]
        """
        d = len(mu_p)
        
        # Log determinant ratio
        sign_p, logdet_p = np.linalg.slogdet(cov_p)
        sign_q, logdet_q = np.linalg.slogdet(cov_q)
        log_det_ratio = logdet_q - logdet_p
        
        # Inverse of Q covariance
        cov_q_inv = np.linalg.inv(cov_q)
        
        # Trace term
        trace_term = np.trace(cov_q_inv @ cov_p)
        
        # Mahalanobis term
        diff = mu_q - mu_p
        mahal = diff @ cov_q_inv @ diff
        
        kl = 0.5 * (log_det_ratio - d + trace_term + mahal)
        
        return kl
    
    @staticmethod
    def sample_estimate(
        samples_p: np.ndarray,
        samples_q: np.ndarray,
        k: int = 5
    ) -> float:
        """
        KL divergence estimation from samples using k-NN.
        
        KL(P || Q) ≈ (d/n) Σ log(ν_k(x_i) / ρ_k(x_i)) + log(m / (n-1))
        
        Where ν_k is k-NN distance to Q, ρ_k is k-NN distance to P.
        """
        from scipy.spatial import cKDTree
        
        n = len(samples_p)
        m = len(samples_q)
        d = samples_p.shape[1] if samples_p.ndim > 1 else 1
        
        if samples_p.ndim == 1:
            samples_p = samples_p.reshape(-1, 1)
            samples_q = samples_q.reshape(-1, 1)
        
        tree_p = cKDTree(samples_p)
        tree_q = cKDTree(samples_q)
        
        # k-NN distances
        dists_p, _ = tree_p.query(samples_p, k=k+1)
        dists_q, _ = tree_q.query(samples_p, k=k)
        
        rho = dists_p[:, -1]  # Distance to k-th neighbor in P
        nu = dists_q[:, -1]   # Distance to k-th neighbor in Q
        
        # Estimator
        kl = (d / n) * np.sum(np.log(nu / (rho + 1e-10) + 1e-10)) + np.log(m / (n - 1))
        
        return max(0, kl)


class InformationGain:
    """
    Information Gain for feature selection.
    
    IG(X, Y) = H(Y) - H(Y | X) = I(X; Y)
    
    Measures how much knowing X reduces uncertainty about Y.
    
    Uses: Feature importance, decision trees, signal strength
    """
    
    @staticmethod
    def for_classification(
        X: np.ndarray,
        y: np.ndarray,
        n_bins: int = 10
    ) -> float:
        """
        Information gain for classification.
        
        IG = H(Y) - H(Y|X)
        """
        # Entropy of target
        _, counts = np.unique(y, return_counts=True)
        p_y = counts / len(y)
        H_Y = EntropyEstimator.discrete(p_y)
        
        # Conditional entropy H(Y|X)
        # Discretize X if continuous
        if X.dtype == float:
            X_binned = np.digitize(X, np.linspace(X.min(), X.max(), n_bins))
        else:
            X_binned = X
        
        H_Y_given_X = 0
        for x_val in np.unique(X_binned):
            mask = X_binned == x_val
            p_x = np.sum(mask) / len(y)
            
            if p_x > 0:
                _, counts_given_x = np.unique(y[mask], return_counts=True)
                p_y_given_x = counts_given_x / np.sum(mask)
                H_Y_given_X += p_x * EntropyEstimator.discrete(p_y_given_x)
        
        return H_Y - H_Y_given_X
    
    @staticmethod
    def for_regression(X: np.ndarray, y: np.ndarray) -> float:
        """
        Information gain for regression using correlation-based MI.
        """
        return MutualInformation.regression_mi(X, y)
    
    @staticmethod
    def rank_features(
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[list] = None
    ) -> list:
        """
        Rank features by information gain.
        
        Returns list of (feature_name, IG_score) sorted by score.
        """
        n_features = X.shape[1]
        
        if feature_names is None:
            feature_names = [f"feature_{i}" for i in range(n_features)]
        
        scores = []
        for i in range(n_features):
            ig = InformationGain.for_regression(X[:, i], y)
            scores.append((feature_names[i], ig))
        
        return sorted(scores, key=lambda x: x[1], reverse=True)
