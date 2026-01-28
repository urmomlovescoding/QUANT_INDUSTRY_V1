"""
QUANT_INDUSTRY_V1 Enhanced Physics Models

Advanced physics-inspired models for market analysis.

Additions to existing physics.py:
- Quantum-Inspired Annealing for optimization
- Fokker-Planck dynamics for price evolution
- Percolation Theory for crash prediction
- Spin Glass models for portfolio optimization
- Econophysics: Minority Games
- Information Theory: Transfer Entropy
"""

import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from scipy import stats
from scipy.linalg import expm

logger = logging.getLogger(__name__)


# =============================================================================
# QUANTUM-INSPIRED OPTIMIZATION
# =============================================================================

class QuantumAnnealer:
    """
    Quantum-Inspired Simulated Annealing.

    Uses quantum tunneling-like behavior for better optimization
    of portfolio weights and trading parameters.
    """

    def __init__(
        self,
        n_variables: int,
        bounds: List[Tuple[float, float]] = None,
        n_iterations: int = 1000,
        initial_temp: float = 1.0,
        final_temp: float = 0.001,
    ):
        self.n_variables = n_variables
        self.bounds = bounds or [(0, 1)] * n_variables
        self.n_iterations = n_iterations
        self.initial_temp = initial_temp
        self.final_temp = final_temp

        # Quantum-inspired parameters
        self.transverse_field = 1.0
        self.driver_strength = 0.5

    def optimize(
        self,
        objective_fn: callable,
        initial_state: np.ndarray = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Perform quantum-inspired optimization.

        Returns optimal state and minimum energy (loss).
        """
        # Initialize state
        if initial_state is None:
            state = np.array([np.random.uniform(b[0], b[1]) for b in self.bounds])
        else:
            state = initial_state.copy()

        best_state = state.copy()
        best_energy = objective_fn(state)

        # Temperature schedule
        temp_schedule = np.linspace(self.initial_temp, self.final_temp, self.n_iterations)
        field_schedule = np.linspace(self.transverse_field, 0.01, self.n_iterations)

        for i, (temp, field) in enumerate(zip(temp_schedule, field_schedule)):
            # Quantum tunneling probability
            tunnel_prob = np.exp(-self.driver_strength / field)

            for j in range(self.n_variables):
                # Generate candidate move
                if np.random.random() < tunnel_prob:
                    # Quantum tunneling: Jump to random location
                    new_val = np.random.uniform(self.bounds[j][0], self.bounds[j][1])
                else:
                    # Classical perturbation
                    delta = np.random.randn() * temp * (self.bounds[j][1] - self.bounds[j][0]) * 0.1
                    new_val = np.clip(state[j] + delta, self.bounds[j][0], self.bounds[j][1])

                # Evaluate candidate
                candidate = state.copy()
                candidate[j] = new_val
                candidate_energy = objective_fn(candidate)

                # Acceptance probability (Metropolis-Hastings)
                delta_e = candidate_energy - objective_fn(state)

                if delta_e < 0 or np.random.random() < np.exp(-delta_e / temp):
                    state[j] = new_val

                    if candidate_energy < best_energy:
                        best_state = candidate.copy()
                        best_energy = candidate_energy

        return best_state, best_energy

    def optimize_portfolio(
        self,
        returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_aversion: float = 1.0,
    ) -> np.ndarray:
        """
        Optimize portfolio weights using quantum annealing.
        """
        n_assets = len(returns)
        self.n_variables = n_assets
        self.bounds = [(0, 1)] * n_assets

        def portfolio_objective(weights):
            # Normalize weights
            weights = weights / np.sum(weights)

            # Expected return
            expected_return = np.dot(weights, returns)

            # Portfolio variance
            variance = np.dot(weights, np.dot(cov_matrix, weights))

            # Utility function (risk-adjusted return)
            return -expected_return + risk_aversion * variance

        optimal_weights, _ = self.optimize(portfolio_objective)

        # Normalize
        return optimal_weights / np.sum(optimal_weights)


# =============================================================================
# FOKKER-PLANCK DYNAMICS
# =============================================================================

class FokkerPlanckDynamics:
    """
    Fokker-Planck equation for price probability evolution.

    Models the evolution of the probability distribution of prices
    under drift and diffusion.
    """

    def __init__(
        self,
        n_price_levels: int = 100,
        price_range: Tuple[float, float] = (0.8, 1.2),
        dt: float = 0.01,
    ):
        self.n_levels = n_price_levels
        self.price_range = price_range
        self.dt = dt

        # Price grid
        self.prices = np.linspace(price_range[0], price_range[1], n_price_levels)
        self.dx = self.prices[1] - self.prices[0]

        # Probability distribution
        self.prob_distribution = np.zeros(n_price_levels)
        self._initialize_distribution()

    def _initialize_distribution(self, center: float = 1.0, width: float = 0.05):
        """Initialize with Gaussian distribution."""
        self.prob_distribution = np.exp(-0.5 * ((self.prices - center) / width) ** 2)
        self.prob_distribution /= np.sum(self.prob_distribution) * self.dx

    def evolve(
        self,
        drift: float,
        diffusion: float,
        n_steps: int = 1,
    ) -> np.ndarray:
        """
        Evolve probability distribution using Fokker-Planck equation.

        dp/dt = -d(drift * p)/dx + 0.5 * d²(diffusion² * p)/dx²
        """
        for _ in range(n_steps):
            # Drift term (advection)
            drift_flux = drift * self.prob_distribution
            drift_term = np.zeros_like(self.prob_distribution)
            drift_term[1:] = -(drift_flux[1:] - drift_flux[:-1]) / self.dx

            # Diffusion term
            diff_coeff = diffusion ** 2 * self.prob_distribution
            diffusion_term = np.zeros_like(self.prob_distribution)
            diffusion_term[1:-1] = 0.5 * (diff_coeff[2:] - 2 * diff_coeff[1:-1] + diff_coeff[:-2]) / self.dx ** 2

            # Update
            self.prob_distribution += self.dt * (drift_term + diffusion_term)

            # Ensure normalization and non-negativity
            self.prob_distribution = np.maximum(self.prob_distribution, 0)
            self.prob_distribution /= np.sum(self.prob_distribution) * self.dx

        return self.prob_distribution

    def calibrate_from_prices(self, prices: np.ndarray, window: int = 20) -> Tuple[float, float]:
        """
        Calibrate drift and diffusion from historical prices.
        """
        returns = np.diff(np.log(prices[-window-1:]))

        drift = np.mean(returns) / self.dt
        diffusion = np.std(returns) / np.sqrt(self.dt)

        return drift, diffusion

    def get_price_forecast(
        self,
        current_price: float,
        drift: float,
        diffusion: float,
        forecast_steps: int = 10,
    ) -> Dict[str, np.ndarray]:
        """
        Forecast price distribution.
        """
        # Re-initialize around current price
        self._initialize_distribution(center=current_price, width=diffusion * 0.5)

        # Evolve
        final_dist = self.evolve(drift, diffusion, forecast_steps)

        # Extract statistics
        expected_price = np.sum(self.prices * final_dist * self.dx)
        variance = np.sum((self.prices - expected_price) ** 2 * final_dist * self.dx)

        # Percentiles
        cdf = np.cumsum(final_dist * self.dx)
        p10 = self.prices[np.searchsorted(cdf, 0.10)]
        p50 = self.prices[np.searchsorted(cdf, 0.50)]
        p90 = self.prices[np.searchsorted(cdf, 0.90)]

        return {
            'expected_price': expected_price,
            'std': np.sqrt(variance),
            'percentile_10': p10,
            'percentile_50': p50,
            'percentile_90': p90,
            'distribution': final_dist,
            'price_grid': self.prices,
        }


# =============================================================================
# PERCOLATION THEORY FOR CRASH PREDICTION
# =============================================================================

class PercolationModel:
    """
    Percolation Theory for market crash prediction.

    Models market as a network where:
    - Nodes = Market participants
    - Edges = Trading relationships/correlations
    - Percolation threshold = Critical point for crash

    Near the percolation threshold, small perturbations
    can propagate through the entire system.
    """

    def __init__(
        self,
        n_nodes: int = 100,
        connectivity: float = 0.1,
    ):
        self.n_nodes = n_nodes
        self.connectivity = connectivity

        # Initialize network
        self.adjacency = np.random.random((n_nodes, n_nodes)) < connectivity
        np.fill_diagonal(self.adjacency, False)

        # Node states: Active (1) or Inactive (0)
        self.states = np.ones(n_nodes)

        # Critical threshold for this topology
        self.critical_threshold = self._estimate_critical_threshold()

    def _estimate_critical_threshold(self) -> float:
        """Estimate percolation threshold."""
        # For random graphs, p_c ≈ 1/<k> where <k> is average degree
        avg_degree = np.sum(self.adjacency) / self.n_nodes
        return 1.0 / (avg_degree + 1)

    def simulate_cascade(
        self,
        initial_failure_rate: float = 0.1,
        propagation_prob: float = 0.3,
        max_steps: int = 100,
    ) -> Dict[str, Any]:
        """
        Simulate failure cascade (market crash).
        """
        # Reset states
        self.states = np.ones(self.n_nodes)

        # Initial failures
        n_initial_failures = int(self.n_nodes * initial_failure_rate)
        initial_failed = np.random.choice(self.n_nodes, n_initial_failures, replace=False)
        self.states[initial_failed] = 0

        cascade_history = [1 - np.mean(self.states)]

        for step in range(max_steps):
            # Find nodes at risk (have failed neighbors)
            failed_neighbors = self.adjacency @ (1 - self.states)

            # Propagation probability increases with failed neighbors
            risk = 1 - (1 - propagation_prob) ** failed_neighbors
            risk[self.states == 0] = 0  # Already failed

            # New failures
            new_failures = (np.random.random(self.n_nodes) < risk) & (self.states == 1)
            self.states[new_failures] = 0

            cascade_history.append(1 - np.mean(self.states))

            # Check for stabilization
            if np.sum(new_failures) == 0:
                break

        return {
            'final_failure_rate': 1 - np.mean(self.states),
            'cascade_history': cascade_history,
            'cascade_size': len(cascade_history) - 1,
            'is_systemic': (1 - np.mean(self.states)) > 0.5,
        }

    def measure_criticality(
        self,
        correlation_matrix: np.ndarray,
    ) -> Dict[str, float]:
        """
        Measure how close market is to critical point.

        Uses correlation structure to assess systemic risk.
        """
        # Update network based on correlations
        threshold = 0.5
        self.adjacency = np.abs(correlation_matrix) > threshold
        np.fill_diagonal(self.adjacency, False)

        # Largest eigenvalue indicates system-wide correlation
        eigenvalues = np.linalg.eigvalsh(correlation_matrix)
        largest_eigenvalue = np.max(eigenvalues)

        # Participation ratio (how many assets move together)
        eigenvector = np.linalg.eigh(correlation_matrix)[1][:, -1]
        participation_ratio = 1.0 / np.sum(eigenvector ** 4)

        # Average cluster size
        from scipy.sparse.csgraph import connected_components
        n_components, labels = connected_components(self.adjacency)
        cluster_sizes = np.bincount(labels)
        avg_cluster_size = np.mean(cluster_sizes)

        # Susceptibility (variance in cluster sizes)
        susceptibility = np.var(cluster_sizes)

        # Criticality score (0-1, higher = closer to crash)
        criticality = min(1.0, (
            0.3 * (largest_eigenvalue / len(correlation_matrix)) +
            0.3 * (participation_ratio / len(correlation_matrix)) +
            0.2 * (avg_cluster_size / len(correlation_matrix)) +
            0.2 * (susceptibility / (len(correlation_matrix) ** 2))
        ))

        return {
            'criticality_score': criticality,
            'largest_eigenvalue': largest_eigenvalue,
            'participation_ratio': participation_ratio,
            'avg_cluster_size': avg_cluster_size,
            'susceptibility': susceptibility,
            'n_clusters': n_components,
            'near_critical': criticality > 0.7,
        }


# =============================================================================
# SPIN GLASS MODEL
# =============================================================================

class SpinGlassOptimizer:
    """
    Spin Glass model for portfolio optimization.

    Treats portfolio weights as spin states in a disordered system.
    Interactions between spins represent asset correlations.
    """

    def __init__(self, n_assets: int):
        self.n_assets = n_assets
        self.interactions = np.zeros((n_assets, n_assets))
        self.external_field = np.zeros(n_assets)

    def set_from_market(
        self,
        returns: np.ndarray,
        correlations: np.ndarray,
    ) -> None:
        """
        Set spin glass parameters from market data.

        Interactions = negative correlations (anti-ferromagnetic for diversification)
        External field = expected returns
        """
        self.interactions = -correlations  # Negative for diversification
        self.external_field = returns

    def compute_energy(self, spins: np.ndarray) -> float:
        """
        Compute Hamiltonian (energy) of spin configuration.

        H = -sum_ij J_ij s_i s_j - sum_i h_i s_i
        """
        interaction_energy = -0.5 * np.dot(spins, np.dot(self.interactions, spins))
        field_energy = -np.dot(self.external_field, spins)
        return interaction_energy + field_energy

    def find_ground_state(
        self,
        n_iterations: int = 1000,
        initial_temp: float = 1.0,
        final_temp: float = 0.01,
    ) -> np.ndarray:
        """
        Find minimum energy configuration using simulated annealing.
        """
        # Initialize with random spins
        spins = np.random.choice([-1, 1], self.n_assets).astype(float)
        best_spins = spins.copy()
        best_energy = self.compute_energy(spins)

        temps = np.linspace(initial_temp, final_temp, n_iterations)

        for temp in temps:
            # Random spin flip
            i = np.random.randint(self.n_assets)
            new_spins = spins.copy()
            new_spins[i] *= -1

            # Energy change
            delta_e = self.compute_energy(new_spins) - self.compute_energy(spins)

            # Metropolis acceptance
            if delta_e < 0 or np.random.random() < np.exp(-delta_e / temp):
                spins = new_spins

                if self.compute_energy(spins) < best_energy:
                    best_spins = spins.copy()
                    best_energy = self.compute_energy(spins)

        return best_spins

    def spins_to_weights(self, spins: np.ndarray) -> np.ndarray:
        """
        Convert spin configuration to portfolio weights.

        Spin +1 = long position
        Spin -1 = short or no position
        """
        weights = (spins + 1) / 2  # Map [-1, 1] to [0, 1]
        return weights / np.sum(weights) if np.sum(weights) > 0 else np.ones(self.n_assets) / self.n_assets


# =============================================================================
# TRANSFER ENTROPY (Information Flow)
# =============================================================================

class TransferEntropy:
    """
    Transfer Entropy for detecting information flow between assets.

    Measures directed information transfer from X to Y.
    Useful for lead-lag relationships.
    """

    def __init__(self, k: int = 1, l: int = 1, n_bins: int = 10):
        """
        Args:
            k: History length for target
            l: History length for source
            n_bins: Number of bins for discretization
        """
        self.k = k
        self.l = l
        self.n_bins = n_bins

    def compute(
        self,
        source: np.ndarray,
        target: np.ndarray,
    ) -> float:
        """
        Compute transfer entropy from source to target.

        TE(X->Y) = H(Y_t | Y_{t-k}) - H(Y_t | Y_{t-k}, X_{t-l})
        """
        # Discretize
        source_disc = self._discretize(source)
        target_disc = self._discretize(target)

        n = len(source_disc)
        max_lag = max(self.k, self.l)

        # Build joint distributions
        counts_y_yk = {}  # P(Y_t, Y_{t-k})
        counts_y_yk_xl = {}  # P(Y_t, Y_{t-k}, X_{t-l})
        counts_yk = {}  # P(Y_{t-k})
        counts_yk_xl = {}  # P(Y_{t-k}, X_{t-l})

        for t in range(max_lag, n):
            y_t = target_disc[t]
            y_k = tuple(target_disc[t-self.k:t])
            x_l = tuple(source_disc[t-self.l:t])

            # Update counts
            key_y_yk = (y_t, y_k)
            key_y_yk_xl = (y_t, y_k, x_l)
            key_yk = y_k
            key_yk_xl = (y_k, x_l)

            counts_y_yk[key_y_yk] = counts_y_yk.get(key_y_yk, 0) + 1
            counts_y_yk_xl[key_y_yk_xl] = counts_y_yk_xl.get(key_y_yk_xl, 0) + 1
            counts_yk[key_yk] = counts_yk.get(key_yk, 0) + 1
            counts_yk_xl[key_yk_xl] = counts_yk_xl.get(key_yk_xl, 0) + 1

        # Compute entropies
        n_samples = n - max_lag

        def entropy_from_counts(counts):
            probs = np.array(list(counts.values())) / n_samples
            return -np.sum(probs * np.log2(probs + 1e-10))

        h_y_yk = entropy_from_counts(counts_y_yk)
        h_y_yk_xl = entropy_from_counts(counts_y_yk_xl)
        h_yk = entropy_from_counts(counts_yk)
        h_yk_xl = entropy_from_counts(counts_yk_xl)

        # Conditional entropies
        h_y_given_yk = h_y_yk - h_yk
        h_y_given_yk_xl = h_y_yk_xl - h_yk_xl

        # Transfer entropy
        te = h_y_given_yk - h_y_given_yk_xl

        return max(0, te)  # TE is non-negative

    def _discretize(self, data: np.ndarray) -> np.ndarray:
        """Discretize continuous data into bins."""
        percentiles = np.linspace(0, 100, self.n_bins + 1)
        bin_edges = np.percentile(data, percentiles)
        return np.digitize(data, bin_edges[1:-1])

    def compute_matrix(self, returns_matrix: np.ndarray) -> np.ndarray:
        """
        Compute transfer entropy matrix for multiple assets.

        Returns n_assets x n_assets matrix where TE[i,j] = TE(i -> j)
        """
        n_assets = returns_matrix.shape[1]
        te_matrix = np.zeros((n_assets, n_assets))

        for i in range(n_assets):
            for j in range(n_assets):
                if i != j:
                    te_matrix[i, j] = self.compute(returns_matrix[:, i], returns_matrix[:, j])

        return te_matrix

    def find_leaders(self, te_matrix: np.ndarray) -> List[int]:
        """
        Find leading assets (high outgoing TE, low incoming).
        """
        outgoing = np.sum(te_matrix, axis=1)  # Row sums
        incoming = np.sum(te_matrix, axis=0)  # Column sums

        leadership_score = outgoing - incoming

        # Return indices sorted by leadership
        return np.argsort(leadership_score)[::-1].tolist()


# =============================================================================
# MINORITY GAME
# =============================================================================

class MinorityGame:
    """
    Minority Game for modeling market dynamics.

    Players choose between two options; minority wins.
    Produces realistic market statistics.
    """

    def __init__(
        self,
        n_agents: int = 101,
        memory_length: int = 3,
        n_strategies: int = 2,
    ):
        self.n_agents = n_agents
        self.memory_length = memory_length
        self.n_strategies = n_strategies

        # History of outcomes (binary)
        self.history = np.random.randint(0, 2, memory_length)

        # Agent strategies (random mappings from history to action)
        n_states = 2 ** memory_length
        self.strategies = np.random.randint(0, 2, (n_agents, n_strategies, n_states))

        # Strategy scores
        self.scores = np.zeros((n_agents, n_strategies))

    def _history_to_index(self) -> int:
        """Convert history to state index."""
        return int(''.join(map(str, self.history)), 2)

    def play_round(self) -> Tuple[int, float]:
        """
        Play one round of the minority game.

        Returns:
            outcome: Winning action (0 or 1)
            attendance: Number choosing action 1 (price proxy)
        """
        state_idx = self._history_to_index()

        # Each agent uses best strategy
        actions = np.zeros(self.n_agents, dtype=int)
        for i in range(self.n_agents):
            best_strategy = np.argmax(self.scores[i])
            actions[i] = self.strategies[i, best_strategy, state_idx]

        # Count attendances
        attendance = np.sum(actions)
        minority_action = 0 if attendance > self.n_agents / 2 else 1

        # Update strategy scores
        for i in range(self.n_agents):
            for s in range(self.n_strategies):
                if self.strategies[i, s, state_idx] == minority_action:
                    self.scores[i, s] += 1

        # Update history
        self.history = np.roll(self.history, -1)
        self.history[-1] = minority_action

        # Return price proxy (normalized attendance)
        return minority_action, (attendance - self.n_agents / 2) / (self.n_agents / 2)

    def simulate(self, n_rounds: int = 1000) -> Dict[str, np.ndarray]:
        """
        Simulate multiple rounds.
        """
        prices = np.zeros(n_rounds)
        outcomes = np.zeros(n_rounds, dtype=int)

        for t in range(n_rounds):
            outcome, price_change = self.play_round()
            outcomes[t] = outcome
            prices[t] = price_change

        # Compute cumulative price
        cumulative_price = np.cumsum(prices)

        return {
            'price_changes': prices,
            'cumulative_price': cumulative_price,
            'outcomes': outcomes,
            'volatility': np.std(prices),
            'autocorrelation': np.corrcoef(prices[:-1], prices[1:])[0, 1],
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'QuantumAnnealer',
    'FokkerPlanckDynamics',
    'PercolationModel',
    'SpinGlassOptimizer',
    'TransferEntropy',
    'MinorityGame',
]
