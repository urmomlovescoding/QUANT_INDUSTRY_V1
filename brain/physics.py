"""
QUANT_INDUSTRY_V1 Physics-Inspired Finance Models

Apply physics concepts to financial markets:
- Mean field theory for market dynamics
- Ising model for market sentiment
- Statistical mechanics for price formation
- Agent-based modeling
- Network effects and contagion

Rollback Plan: Delete this file
Tests Required: Model convergence, equilibrium stability
Failure Modes: Fall back to empirical estimates
"""

import numpy as np
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# ISING MODEL FOR MARKET SENTIMENT
# =============================================================================

class IsingMarket:
    """
    Ising model applied to market sentiment.

    Each agent has a spin (+1 = bullish, -1 = bearish).
    Interaction strength determines herding behavior.
    """

    def __init__(
        self,
        n_agents: int = 100,
        interaction_strength: float = 1.0,
        external_field: float = 0.0,
        temperature: float = 1.0,
    ):
        self.n_agents = n_agents
        self.J = interaction_strength  # Coupling constant
        self.h = external_field  # External influence (news, etc.)
        self.T = temperature  # Market uncertainty/volatility

        # Initialize spins randomly
        self.spins = np.random.choice([-1, 1], size=n_agents)

        # Interaction matrix (mean field approximation)
        self.adj_matrix = np.ones((n_agents, n_agents)) / n_agents
        np.fill_diagonal(self.adj_matrix, 0)

    def magnetization(self) -> float:
        """
        Calculate market magnetization (net sentiment).

        M = mean(spins)
        M > 0: Bullish market
        M < 0: Bearish market
        """
        return float(np.mean(self.spins))

    def energy(self) -> float:
        """
        Calculate system energy.

        E = -J * sum(s_i * s_j) - h * sum(s_i)
        """
        interaction_energy = -self.J * np.sum(
            self.spins.reshape(-1, 1) * self.spins * self.adj_matrix
        ) / 2
        field_energy = -self.h * np.sum(self.spins)

        return float(interaction_energy + field_energy)

    def step(self, n_steps: int = 1) -> None:
        """
        Perform Metropolis updates.

        Agents update their opinion based on neighbors and randomness.
        """
        for _ in range(n_steps):
            # Random agent
            i = np.random.randint(self.n_agents)

            # Current energy contribution from this agent
            neighbor_field = self.J * np.sum(self.spins * self.adj_matrix[i])
            delta_E = 2 * self.spins[i] * (neighbor_field + self.h)

            # Metropolis acceptance
            if delta_E < 0 or np.random.random() < np.exp(-delta_E / self.T):
                self.spins[i] *= -1

    def simulate(
        self,
        n_steps: int = 1000,
        measure_interval: int = 10
    ) -> Dict[str, List[float]]:
        """
        Run simulation and collect measurements.

        Returns:
            Dictionary with magnetization and energy time series
        """
        magnetizations = []
        energies = []

        for step in range(n_steps):
            self.step()

            if step % measure_interval == 0:
                magnetizations.append(self.magnetization())
                energies.append(self.energy())

        return {
            'magnetization': magnetizations,
            'energy': energies,
        }

    def set_external_field(self, h: float) -> None:
        """Update external field (e.g., based on news)."""
        self.h = h

    def set_temperature(self, T: float) -> None:
        """Update temperature (market uncertainty)."""
        self.T = max(0.01, T)  # Prevent division by zero

    def susceptibility(self) -> float:
        """
        Calculate magnetic susceptibility.

        Measures market's response to external influences.
        Higher susceptibility = more sensitive to news.
        """
        # Run short simulation to estimate variance
        mags = []
        for _ in range(100):
            self.step(10)
            mags.append(self.magnetization())

        variance = np.var(mags)
        return float(self.n_agents * variance / self.T)


# =============================================================================
# MEAN FIELD THEORY
# =============================================================================

class MeanFieldMarket:
    """
    Mean field approximation for market dynamics.

    Reduces many-body problem to effective single-particle problem.
    """

    def __init__(
        self,
        n_assets: int = 10,
        coupling: float = 0.5,
        noise_level: float = 0.1
    ):
        self.n_assets = n_assets
        self.coupling = coupling  # Inter-asset coupling
        self.noise = noise_level

        # State: log returns
        self.returns = np.zeros(n_assets)

        # Mean field (average market state)
        self.mean_field = 0.0

    def update_mean_field(self) -> float:
        """Calculate mean field from current state."""
        self.mean_field = np.mean(self.returns)
        return self.mean_field

    def step(self, external_shock: float = 0.0) -> np.ndarray:
        """
        Evolve system one step.

        Each asset is influenced by mean field + idiosyncratic noise.
        """
        self.update_mean_field()

        # New returns = coupling * mean_field + noise
        self.returns = (
            self.coupling * self.mean_field +
            external_shock +
            self.noise * np.random.randn(self.n_assets)
        )

        return self.returns.copy()

    def correlation_from_coupling(self) -> float:
        """
        Theoretical correlation implied by coupling.

        In mean field: rho = J^2 / (1 + J^2 * (n-1)/n)
        """
        n = self.n_assets
        J = self.coupling

        return J ** 2 / (1 + J ** 2 * (n - 1) / n)

    def phase_transition_point(self) -> float:
        """
        Critical coupling for phase transition.

        Above this, market becomes highly correlated.
        """
        return 1.0 / np.sqrt(self.n_assets - 1)


# =============================================================================
# ORNSTEIN-UHLENBECK (MEAN REVERSION)
# =============================================================================

class OrnsteinUhlenbeckProcess:
    """
    Ornstein-Uhlenbeck process for mean-reverting dynamics.

    dX = theta * (mu - X) * dt + sigma * dW

    Used for:
    - Interest rates
    - Volatility modeling
    - Pairs trading spreads
    """

    def __init__(
        self,
        theta: float = 0.5,  # Mean reversion speed
        mu: float = 0.0,     # Long-term mean
        sigma: float = 0.1,  # Volatility
        x0: float = 0.0      # Initial value
    ):
        self.theta = theta
        self.mu = mu
        self.sigma = sigma
        self.x = x0

    def step(self, dt: float = 1/252) -> float:
        """Simulate one step."""
        dW = np.sqrt(dt) * np.random.randn()
        dx = self.theta * (self.mu - self.x) * dt + self.sigma * dW
        self.x += dx
        return self.x

    def simulate(
        self,
        n_steps: int = 252,
        dt: float = 1/252
    ) -> np.ndarray:
        """Simulate full path."""
        path = np.zeros(n_steps + 1)
        path[0] = self.x

        for i in range(1, n_steps + 1):
            path[i] = self.step(dt)

        return path

    def expected_value(self, t: float) -> float:
        """E[X_t] = mu + (X_0 - mu) * exp(-theta * t)"""
        return self.mu + (self.x - self.mu) * np.exp(-self.theta * t)

    def variance(self, t: float) -> float:
        """Var[X_t] = sigma^2 / (2*theta) * (1 - exp(-2*theta*t))"""
        return (self.sigma ** 2 / (2 * self.theta)) * (1 - np.exp(-2 * self.theta * t))

    def half_life(self) -> float:
        """Time for mean to halve the distance to equilibrium."""
        return np.log(2) / self.theta

    def stationary_distribution(self) -> Tuple[float, float]:
        """Return mean and variance of stationary distribution."""
        return self.mu, self.sigma ** 2 / (2 * self.theta)

    @classmethod
    def calibrate(cls, series: np.ndarray, dt: float = 1/252) -> 'OrnsteinUhlenbeckProcess':
        """
        Calibrate OU parameters from data using MLE.

        Args:
            series: Observed time series
            dt: Time step

        Returns:
            Calibrated OU process
        """
        n = len(series)

        # MLE estimators
        x = series[:-1]
        y = series[1:]

        # Regression: y = a + b*x + noise
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        b = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
        a = y_mean - b * x_mean

        residuals = y - a - b * x
        sigma_res = np.std(residuals)

        # Convert to OU parameters
        theta = -np.log(b) / dt
        mu = a / (1 - b)
        sigma = sigma_res * np.sqrt(-2 * np.log(b) / (dt * (1 - b ** 2)))

        return cls(theta=theta, mu=mu, sigma=sigma, x0=series[-1])


# =============================================================================
# AGENT-BASED MODEL
# =============================================================================

class AgentType(Enum):
    """Types of market agents."""
    FUNDAMENTALIST = "fundamentalist"  # Trade on fundamentals
    CHARTIST = "chartist"  # Trade on trends
    NOISE = "noise"  # Random trading


@dataclass
class Agent:
    """Individual market agent."""
    agent_type: AgentType
    wealth: float = 1000.0
    position: float = 0.0
    memory: int = 20  # Lookback for chartists
    risk_tolerance: float = 0.5


class AgentBasedMarket:
    """
    Agent-based model of financial markets.

    Heterogeneous agents interact to form prices.
    """

    def __init__(
        self,
        n_fundamentalists: int = 30,
        n_chartists: int = 50,
        n_noise: int = 20,
        fundamental_value: float = 100.0,
        price_impact: float = 0.01
    ):
        self.fundamental_value = fundamental_value
        self.price_impact = price_impact

        # Create agents
        self.agents: List[Agent] = []

        for _ in range(n_fundamentalists):
            self.agents.append(Agent(
                agent_type=AgentType.FUNDAMENTALIST,
                risk_tolerance=np.random.uniform(0.3, 0.7)
            ))

        for _ in range(n_chartists):
            self.agents.append(Agent(
                agent_type=AgentType.CHARTIST,
                memory=np.random.randint(5, 50),
                risk_tolerance=np.random.uniform(0.3, 0.7)
            ))

        for _ in range(n_noise):
            self.agents.append(Agent(
                agent_type=AgentType.NOISE,
                risk_tolerance=np.random.uniform(0.1, 0.5)
            ))

        # Market state
        self.price = fundamental_value
        self.price_history = [self.price]
        self.volume_history = []

    def get_demand(self, agent: Agent) -> float:
        """Calculate agent's demand."""
        if agent.agent_type == AgentType.FUNDAMENTALIST:
            # Trade towards fundamental value
            mispricing = (self.fundamental_value - self.price) / self.price
            demand = mispricing * agent.risk_tolerance * agent.wealth

        elif agent.agent_type == AgentType.CHARTIST:
            # Follow trends
            if len(self.price_history) >= agent.memory:
                past_price = self.price_history[-agent.memory]
                trend = (self.price - past_price) / past_price
                demand = trend * agent.risk_tolerance * agent.wealth
            else:
                demand = 0.0

        else:  # Noise trader
            demand = np.random.randn() * agent.risk_tolerance * agent.wealth * 0.1

        return demand

    def step(self) -> float:
        """Simulate one time step."""
        # Aggregate demand
        total_demand = sum(self.get_demand(agent) for agent in self.agents)

        # Price adjustment
        self.price *= (1 + self.price_impact * total_demand / 1000)
        self.price = max(self.price, 0.01)  # Floor

        # Record
        self.price_history.append(self.price)
        self.volume_history.append(abs(total_demand))

        return self.price

    def simulate(self, n_steps: int = 252) -> Dict[str, np.ndarray]:
        """Run simulation."""
        for _ in range(n_steps):
            self.step()

        return {
            'prices': np.array(self.price_history),
            'volumes': np.array(self.volume_history),
            'returns': np.diff(np.log(self.price_history)),
        }

    def set_fundamental_value(self, value: float) -> None:
        """Update fundamental value (e.g., from earnings)."""
        self.fundamental_value = value

    def shock(self, magnitude: float) -> None:
        """Apply external shock to price."""
        self.price *= (1 + magnitude)


# =============================================================================
# CONTAGION / NETWORK EFFECTS
# =============================================================================

class ContagionNetwork:
    """
    Model financial contagion through network effects.

    Nodes = institutions/assets
    Edges = exposures/correlations
    """

    def __init__(
        self,
        n_nodes: int = 50,
        edge_probability: float = 0.1,
        default_threshold: float = 0.8
    ):
        self.n_nodes = n_nodes
        self.default_threshold = default_threshold

        # Node health (0 = healthy, 1 = stressed, 2 = defaulted)
        self.health = np.zeros(n_nodes)

        # Capital ratios
        self.capital = np.ones(n_nodes)

        # Generate random network (Erdos-Renyi)
        self.adjacency = (np.random.random((n_nodes, n_nodes)) < edge_probability).astype(float)
        np.fill_diagonal(self.adjacency, 0)

        # Exposure weights (how much stress propagates)
        self.exposure = self.adjacency * np.random.uniform(0.1, 0.3, (n_nodes, n_nodes))

    def apply_shock(self, node: int, magnitude: float) -> None:
        """Apply stress shock to a node."""
        self.capital[node] -= magnitude
        self.capital[node] = max(0, self.capital[node])

        if self.capital[node] < (1 - self.default_threshold):
            self.health[node] = 2  # Defaulted

    def propagate(self) -> int:
        """
        Propagate contagion one round.

        Returns:
            Number of new defaults
        """
        new_defaults = 0

        # Calculate stress received from neighbors
        stress_received = np.zeros(self.n_nodes)

        for i in range(self.n_nodes):
            if self.health[i] < 2:  # Not defaulted
                for j in range(self.n_nodes):
                    if self.health[j] >= 1:  # Neighbor is stressed/defaulted
                        stress_received[i] += self.exposure[j, i] * (1 if self.health[j] == 2 else 0.5)

        # Apply stress
        for i in range(self.n_nodes):
            if self.health[i] < 2:
                self.capital[i] -= stress_received[i]
                self.capital[i] = max(0, self.capital[i])

                if self.capital[i] < (1 - self.default_threshold):
                    if self.health[i] < 2:
                        new_defaults += 1
                    self.health[i] = 2
                elif stress_received[i] > 0.1:
                    self.health[i] = max(self.health[i], 1)  # Stressed

        return new_defaults

    def cascade(self, initial_shock_node: int, shock_magnitude: float) -> Dict[str, Any]:
        """
        Simulate full contagion cascade.

        Args:
            initial_shock_node: Node to shock
            shock_magnitude: Size of initial shock

        Returns:
            Cascade statistics
        """
        # Reset
        self.health = np.zeros(self.n_nodes)
        self.capital = np.ones(self.n_nodes)

        # Initial shock
        self.apply_shock(initial_shock_node, shock_magnitude)

        # Cascade
        rounds = 0
        total_defaults = 1 if self.health[initial_shock_node] == 2 else 0
        defaults_per_round = [total_defaults]

        while True:
            new_defaults = self.propagate()
            defaults_per_round.append(new_defaults)
            total_defaults += new_defaults
            rounds += 1

            if new_defaults == 0 or rounds > 100:
                break

        return {
            'total_defaults': total_defaults,
            'default_rate': total_defaults / self.n_nodes,
            'rounds': rounds,
            'defaults_per_round': defaults_per_round,
            'healthy_nodes': int(np.sum(self.health == 0)),
            'stressed_nodes': int(np.sum(self.health == 1)),
            'defaulted_nodes': int(np.sum(self.health == 2)),
        }

    def systemic_risk_measure(self, n_simulations: int = 100) -> float:
        """
        Estimate systemic risk via simulation.

        Shock each node and measure average cascade size.
        """
        total_cascade = 0

        for node in range(self.n_nodes):
            result = self.cascade(node, 0.3)
            total_cascade += result['total_defaults']

        return total_cascade / (self.n_nodes * self.n_nodes)


# =============================================================================
# MARKET MICROSTRUCTURE
# =============================================================================

class OrderBook:
    """
    Simple limit order book model.

    Tracks bid/ask dynamics.
    """

    def __init__(
        self,
        initial_mid: float = 100.0,
        spread: float = 0.05,
        depth: int = 10
    ):
        self.mid_price = initial_mid
        self.spread = spread
        self.depth = depth

        # Order book levels
        self.bids: List[Tuple[float, float]] = []  # (price, size)
        self.asks: List[Tuple[float, float]] = []

        self._initialize_book()

    def _initialize_book(self) -> None:
        """Initialize order book around mid price."""
        self.bids = []
        self.asks = []

        for i in range(self.depth):
            # Bids below mid
            bid_price = self.mid_price - self.spread / 2 - i * 0.01
            bid_size = np.random.exponential(100)
            self.bids.append((bid_price, bid_size))

            # Asks above mid
            ask_price = self.mid_price + self.spread / 2 + i * 0.01
            ask_size = np.random.exponential(100)
            self.asks.append((ask_price, ask_size))

        self.bids.sort(reverse=True, key=lambda x: x[0])
        self.asks.sort(key=lambda x: x[0])

    def best_bid(self) -> float:
        """Get best bid price."""
        return self.bids[0][0] if self.bids else self.mid_price - self.spread / 2

    def best_ask(self) -> float:
        """Get best ask price."""
        return self.asks[0][0] if self.asks else self.mid_price + self.spread / 2

    def current_spread(self) -> float:
        """Get current bid-ask spread."""
        return self.best_ask() - self.best_bid()

    def market_buy(self, size: float) -> Tuple[float, float]:
        """
        Execute market buy order.

        Returns:
            (execution_price, remaining_size)
        """
        executed_value = 0.0
        remaining = size

        while remaining > 0 and self.asks:
            price, available = self.asks[0]

            if available <= remaining:
                executed_value += price * available
                remaining -= available
                self.asks.pop(0)
            else:
                executed_value += price * remaining
                self.asks[0] = (price, available - remaining)
                remaining = 0

        if size > remaining:
            avg_price = executed_value / (size - remaining)
            self.mid_price = (self.best_bid() + self.best_ask()) / 2
            return avg_price, remaining

        return self.best_ask(), remaining

    def market_sell(self, size: float) -> Tuple[float, float]:
        """
        Execute market sell order.

        Returns:
            (execution_price, remaining_size)
        """
        executed_value = 0.0
        remaining = size

        while remaining > 0 and self.bids:
            price, available = self.bids[0]

            if available <= remaining:
                executed_value += price * available
                remaining -= available
                self.bids.pop(0)
            else:
                executed_value += price * remaining
                self.bids[0] = (price, available - remaining)
                remaining = 0

        if size > remaining:
            avg_price = executed_value / (size - remaining)
            self.mid_price = (self.best_bid() + self.best_ask()) / 2
            return avg_price, remaining

        return self.best_bid(), remaining

    def market_impact(self, size: float, side: str = 'buy') -> float:
        """
        Estimate market impact of order.

        Uses square-root impact model.
        """
        # Kyle's lambda approximation
        daily_volume = sum(s for _, s in self.bids) + sum(s for _, s in self.asks)
        sigma = self.spread / self.mid_price

        impact = sigma * np.sqrt(size / daily_volume)

        return impact if side == 'buy' else -impact
