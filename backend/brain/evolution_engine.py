"""
QUANT INDUSTRY - Evolution Engine
Genetic Algorithm-based Strategy Optimization

Features:
- Population-based strategy optimization
- Mutation and crossover operations
- Multi-objective fitness evaluation
- Elite preservation
- Parallel evaluation support
"""

import copy
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EvolutionConfig:
    """Evolution Engine Configuration"""
    # Population
    population_size: int = 50
    elite_size: int = 5
    generations: int = 100

    # Genetic operators
    mutation_rate: float = 0.1
    mutation_strength: float = 0.2
    crossover_rate: float = 0.7

    # Selection
    tournament_size: int = 3
    selection_pressure: float = 2.0

    # Fitness weights
    sharpe_weight: float = 0.3
    returns_weight: float = 0.25
    win_rate_weight: float = 0.2
    drawdown_weight: float = 0.15
    consistency_weight: float = 0.1

    # Constraints
    min_trades: int = 30
    max_drawdown: float = 0.15
    min_win_rate: float = 0.5

    # Convergence
    convergence_threshold: float = 0.001
    stagnation_limit: int = 20

    # Parallelization
    n_workers: int = 4


@dataclass
class Individual:
    """Represents a trading strategy configuration"""
    genes: Dict[str, float]
    fitness: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    generation: int = 0

    def to_dict(self) -> Dict:
        return {
            'genes': self.genes,
            'fitness': self.fitness,
            'metrics': self.metrics,
            'generation': self.generation
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Individual':
        return cls(
            genes=data['genes'],
            fitness=data.get('fitness', 0.0),
            metrics=data.get('metrics', {}),
            generation=data.get('generation', 0)
        )


class StrategyGenome:
    """Defines the genetic structure of a trading strategy"""

    # Gene definitions: (name, min_value, max_value, default)
    GENE_DEFINITIONS = {
        # Momentum parameters
        'rsi_period': (5, 30, 14),
        'rsi_oversold': (20, 40, 30),
        'rsi_overbought': (60, 80, 70),

        # Moving average parameters
        'fast_ma_period': (5, 30, 10),
        'slow_ma_period': (20, 100, 50),
        'ma_type': (0, 2, 1),  # 0=SMA, 1=EMA, 2=WMA

        # MACD parameters
        'macd_fast': (8, 15, 12),
        'macd_slow': (20, 30, 26),
        'macd_signal': (5, 12, 9),

        # Bollinger parameters
        'bb_period': (10, 30, 20),
        'bb_std': (1.5, 3.0, 2.0),

        # ATR parameters
        'atr_period': (7, 21, 14),
        'atr_multiplier': (1.5, 4.0, 2.5),

        # Position sizing
        'risk_per_trade': (0.005, 0.03, 0.01),
        'max_position_size': (0.05, 0.25, 0.1),

        # Entry/Exit thresholds
        'entry_threshold': (0.3, 0.8, 0.5),
        'exit_threshold': (0.2, 0.6, 0.4),

        # Stop loss / Take profit
        'stop_loss_pct': (0.01, 0.05, 0.02),
        'take_profit_pct': (0.02, 0.10, 0.04),
        'trailing_stop': (0.01, 0.05, 0.02),

        # Time filters
        'holding_period_min': (1, 20, 5),
        'holding_period_max': (5, 60, 20),

        # Signal weights
        'momentum_weight': (0.0, 1.0, 0.3),
        'trend_weight': (0.0, 1.0, 0.3),
        'mean_reversion_weight': (0.0, 1.0, 0.2),
        'volatility_weight': (0.0, 1.0, 0.2),
    }

    @classmethod
    def create_random(cls) -> Dict[str, float]:
        """Create random gene configuration"""
        genes = {}
        for gene_name, (min_val, max_val, _) in cls.GENE_DEFINITIONS.items():
            genes[gene_name] = random.uniform(min_val, max_val)
        return genes

    @classmethod
    def create_default(cls) -> Dict[str, float]:
        """Create default gene configuration"""
        return {name: default for name, (_, _, default) in cls.GENE_DEFINITIONS.items()}

    @classmethod
    def mutate(cls, genes: Dict[str, float], mutation_rate: float,
               mutation_strength: float) -> Dict[str, float]:
        """Mutate genes"""
        mutated = genes.copy()

        for gene_name, value in mutated.items():
            if random.random() < mutation_rate:
                min_val, max_val, _ = cls.GENE_DEFINITIONS[gene_name]
                range_val = max_val - min_val

                # Gaussian mutation
                mutation = random.gauss(0, mutation_strength * range_val)
                new_value = value + mutation

                # Clamp to valid range
                mutated[gene_name] = max(min_val, min(max_val, new_value))

        return mutated

    @classmethod
    def crossover(cls, parent1: Dict[str, float], parent2: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Two-point crossover"""
        gene_names = list(cls.GENE_DEFINITIONS.keys())
        n_genes = len(gene_names)

        # Select crossover points
        point1 = random.randint(0, n_genes - 1)
        point2 = random.randint(point1 + 1, n_genes)

        child1 = {}
        child2 = {}

        for i, gene_name in enumerate(gene_names):
            if point1 <= i < point2:
                child1[gene_name] = parent2[gene_name]
                child2[gene_name] = parent1[gene_name]
            else:
                child1[gene_name] = parent1[gene_name]
                child2[gene_name] = parent2[gene_name]

        return child1, child2

    @classmethod
    def blend_crossover(cls, parent1: Dict[str, float], parent2: Dict[str, float],
                       alpha: float = 0.5) -> Dict[str, float]:
        """Blend crossover (BLX-alpha)"""
        child = {}

        for gene_name in cls.GENE_DEFINITIONS.keys():
            min_val, max_val, _ = cls.GENE_DEFINITIONS[gene_name]

            p1_val = parent1[gene_name]
            p2_val = parent2[gene_name]

            low = min(p1_val, p2_val)
            high = max(p1_val, p2_val)
            range_val = high - low

            # Extend range by alpha
            new_low = max(min_val, low - alpha * range_val)
            new_high = min(max_val, high + alpha * range_val)

            child[gene_name] = random.uniform(new_low, new_high)

        return child


class FitnessEvaluator:
    """Evaluates fitness of trading strategies"""

    def __init__(self, config: EvolutionConfig, backtest_fn: Optional[Callable] = None):
        self.config = config
        self.backtest_fn = backtest_fn or self._default_backtest

    def evaluate(self, individual: Individual, market_data: pd.DataFrame) -> float:
        """Evaluate fitness of an individual"""
        try:
            # Run backtest
            metrics = self.backtest_fn(individual.genes, market_data)

            # Calculate weighted fitness
            fitness = self._calculate_fitness(metrics)

            # Apply constraints
            fitness = self._apply_constraints(fitness, metrics)

            individual.fitness = fitness
            individual.metrics = metrics

            return fitness

        except Exception as e:
            logger.warning(f"Error evaluating individual: {e}")
            individual.fitness = 0.0
            individual.metrics = {}
            return 0.0

    def _calculate_fitness(self, metrics: Dict[str, float]) -> float:
        """Calculate weighted fitness score"""
        sharpe = metrics.get('sharpe_ratio', 0)
        returns = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        max_dd = metrics.get('max_drawdown', 1)
        consistency = metrics.get('consistency', 0)

        # Normalize components
        sharpe_score = min(sharpe / 3.0, 1.0) if sharpe > 0 else 0
        returns_score = min(returns / 0.5, 1.0) if returns > 0 else 0
        win_rate_score = win_rate
        dd_score = 1 - min(abs(max_dd) / 0.3, 1.0)
        consistency_score = consistency

        # Weighted sum
        fitness = (
            self.config.sharpe_weight * sharpe_score +
            self.config.returns_weight * returns_score +
            self.config.win_rate_weight * win_rate_score +
            self.config.drawdown_weight * dd_score +
            self.config.consistency_weight * consistency_score
        )

        return fitness

    def _apply_constraints(self, fitness: float, metrics: Dict[str, float]) -> float:
        """Apply constraint penalties"""
        n_trades = metrics.get('n_trades', 0)
        max_dd = abs(metrics.get('max_drawdown', 1))
        win_rate = metrics.get('win_rate', 0)

        # Penalty for too few trades
        if n_trades < self.config.min_trades:
            fitness *= n_trades / self.config.min_trades

        # Penalty for excessive drawdown
        if max_dd > self.config.max_drawdown:
            penalty = 1 - (max_dd - self.config.max_drawdown) / self.config.max_drawdown
            fitness *= max(0.1, penalty)

        # Penalty for low win rate
        if win_rate < self.config.min_win_rate:
            penalty = win_rate / self.config.min_win_rate
            fitness *= max(0.1, penalty)

        return fitness

    def _default_backtest(self, genes: Dict[str, float], market_data: pd.DataFrame) -> Dict[str, float]:
        """Default backtest simulation"""
        if len(market_data) < 100:
            return {'sharpe_ratio': 0, 'total_return': 0, 'win_rate': 0, 'max_drawdown': -1, 'n_trades': 0}

        returns = market_data['close'].pct_change().dropna()

        # Simple strategy simulation based on genes
        rsi_period = int(genes.get('rsi_period', 14))
        entry_threshold = genes.get('entry_threshold', 0.5)
        risk_per_trade = genes.get('risk_per_trade', 0.01)

        # Calculate RSI
        delta = returns.rolling(rsi_period).mean()
        gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        # Generate signals
        signals = np.where(rsi < (1 - entry_threshold) * 100, 1,
                         np.where(rsi > entry_threshold * 100, -1, 0))

        # Simulate trades
        trades = []
        position = 0

        for i in range(len(signals)):
            if signals[i] == 1 and position == 0:
                position = 1
                entry_idx = i
            elif signals[i] == -1 and position == 1:
                trade_return = returns.iloc[entry_idx:i].sum()
                trades.append(trade_return * risk_per_trade * 10)
                position = 0

        if not trades:
            return {'sharpe_ratio': 0, 'total_return': 0, 'win_rate': 0, 'max_drawdown': -0.1, 'n_trades': 0, 'consistency': 0}

        trades = np.array(trades)
        winning_trades = trades[trades > 0]
        losing_trades = trades[trades < 0]

        # Calculate metrics
        total_return = np.sum(trades)
        n_trades = len(trades)
        win_rate = len(winning_trades) / n_trades if n_trades > 0 else 0

        # Sharpe ratio
        if np.std(trades) > 0:
            sharpe = np.mean(trades) / np.std(trades) * np.sqrt(252 / max(1, n_trades))
        else:
            sharpe = 0

        # Max drawdown
        cumulative = np.cumsum(trades)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / (running_max + 1e-10)
        max_dd = np.min(drawdown)

        # Consistency (monthly wins / total months)
        n_periods = max(1, n_trades // 10)
        period_returns = [np.sum(trades[i*10:(i+1)*10]) for i in range(n_periods)]
        consistency = sum(1 for r in period_returns if r > 0) / n_periods if period_returns else 0

        return {
            'sharpe_ratio': float(sharpe),
            'total_return': float(total_return),
            'win_rate': float(win_rate),
            'max_drawdown': float(max_dd),
            'n_trades': int(n_trades),
            'consistency': float(consistency),
            'avg_win': float(np.mean(winning_trades)) if len(winning_trades) > 0 else 0,
            'avg_loss': float(np.mean(losing_trades)) if len(losing_trades) > 0 else 0
        }


class EvolutionEngine:
    """
    Genetic Algorithm Evolution Engine
    Optimizes trading strategies through evolution
    """

    def __init__(self, config: Optional[EvolutionConfig] = None,
                 backtest_fn: Optional[Callable] = None):
        self.config = config or EvolutionConfig()
        self.evaluator = FitnessEvaluator(self.config, backtest_fn)

        # Population
        self.population: List[Individual] = []
        self.best_individual: Optional[Individual] = None
        self.generation = 0

        # History
        self.evolution_history: List[Dict] = []
        self.best_fitness_history: List[float] = []

        # Storage
        self.model_dir = Path("models/evolution")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Evolution Engine initialized")

    def initialize_population(self, seed_individuals: Optional[List[Dict]] = None):
        """Initialize population with random or seeded individuals"""
        self.population = []

        # Add seed individuals
        if seed_individuals:
            for genes in seed_individuals[:self.config.elite_size]:
                individual = Individual(genes=genes, generation=0)
                self.population.append(individual)

        # Add default configuration
        if len(self.population) < self.config.population_size:
            default = Individual(genes=StrategyGenome.create_default(), generation=0)
            self.population.append(default)

        # Fill rest with random individuals
        while len(self.population) < self.config.population_size:
            genes = StrategyGenome.create_random()
            individual = Individual(genes=genes, generation=0)
            self.population.append(individual)

        logger.info(f"Population initialized with {len(self.population)} individuals")

    def evolve(self, market_data: pd.DataFrame, generations: Optional[int] = None) -> Dict:
        """Run evolution process"""
        n_generations = generations or self.config.generations

        if not self.population:
            self.initialize_population()

        stagnation_counter = 0
        last_best_fitness = 0

        for gen in range(n_generations):
            self.generation = gen + 1

            # Evaluate population
            self._evaluate_population(market_data)

            # Sort by fitness
            self.population.sort(key=lambda x: x.fitness, reverse=True)

            # Track best
            current_best = self.population[0]
            if self.best_individual is None or current_best.fitness > self.best_individual.fitness:
                self.best_individual = copy.deepcopy(current_best)

            # Record history
            gen_stats = self._record_generation_stats()
            self.evolution_history.append(gen_stats)
            self.best_fitness_history.append(current_best.fitness)

            # Log progress
            if (gen + 1) % 10 == 0:
                logger.info(f"Generation {gen + 1}/{n_generations} - "
                           f"Best: {current_best.fitness:.4f}, "
                           f"Avg: {gen_stats['avg_fitness']:.4f}, "
                           f"Sharpe: {current_best.metrics.get('sharpe_ratio', 0):.2f}")

            # Check convergence
            if abs(current_best.fitness - last_best_fitness) < self.config.convergence_threshold:
                stagnation_counter += 1
            else:
                stagnation_counter = 0

            last_best_fitness = current_best.fitness

            if stagnation_counter >= self.config.stagnation_limit:
                logger.info(f"Convergence reached at generation {gen + 1}")
                break

            # Create next generation
            self._create_next_generation()

        return {
            'generations': self.generation,
            'best_individual': self.best_individual.to_dict() if self.best_individual else None,
            'best_fitness': self.best_individual.fitness if self.best_individual else 0,
            'final_population_size': len(self.population),
            'convergence': stagnation_counter >= self.config.stagnation_limit,
            'history_summary': {
                'initial_best': self.best_fitness_history[0] if self.best_fitness_history else 0,
                'final_best': self.best_fitness_history[-1] if self.best_fitness_history else 0,
                'improvement': (self.best_fitness_history[-1] - self.best_fitness_history[0]) if len(self.best_fitness_history) > 1 else 0
            }
        }

    def _evaluate_population(self, market_data: pd.DataFrame):
        """Evaluate all individuals in population"""
        # Parallel evaluation
        if self.config.n_workers > 1:
            with ThreadPoolExecutor(max_workers=self.config.n_workers) as executor:
                futures = {
                    executor.submit(self.evaluator.evaluate, ind, market_data): ind
                    for ind in self.population
                }
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.warning(f"Evaluation error: {e}")
        else:
            for individual in self.population:
                self.evaluator.evaluate(individual, market_data)

    def _create_next_generation(self):
        """Create next generation through selection, crossover, and mutation"""
        new_population = []

        # Elitism: Keep best individuals
        elite = self.population[:self.config.elite_size]
        for ind in elite:
            new_ind = Individual(
                genes=copy.deepcopy(ind.genes),
                generation=self.generation
            )
            new_population.append(new_ind)

        # Fill rest through reproduction
        while len(new_population) < self.config.population_size:
            # Selection
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()

            # Crossover
            if random.random() < self.config.crossover_rate:
                child_genes = StrategyGenome.blend_crossover(parent1.genes, parent2.genes)
            else:
                child_genes = copy.deepcopy(parent1.genes)

            # Mutation
            child_genes = StrategyGenome.mutate(
                child_genes,
                self.config.mutation_rate,
                self.config.mutation_strength
            )

            child = Individual(genes=child_genes, generation=self.generation)
            new_population.append(child)

        self.population = new_population

    def _tournament_selection(self) -> Individual:
        """Tournament selection"""
        tournament = random.sample(self.population, self.config.tournament_size)
        return max(tournament, key=lambda x: x.fitness)

    def _record_generation_stats(self) -> Dict:
        """Record statistics for current generation"""
        fitnesses = [ind.fitness for ind in self.population]

        return {
            'generation': self.generation,
            'best_fitness': max(fitnesses),
            'avg_fitness': np.mean(fitnesses),
            'std_fitness': np.std(fitnesses),
            'min_fitness': min(fitnesses),
            'best_sharpe': self.population[0].metrics.get('sharpe_ratio', 0),
            'best_return': self.population[0].metrics.get('total_return', 0),
            'best_win_rate': self.population[0].metrics.get('win_rate', 0),
            'timestamp': datetime.now().isoformat()
        }

    def get_top_strategies(self, n: int = 5) -> List[Dict]:
        """Get top N strategies"""
        if not self.population:
            return []

        sorted_pop = sorted(self.population, key=lambda x: x.fitness, reverse=True)
        return [ind.to_dict() for ind in sorted_pop[:n]]

    def save(self, path: Optional[str] = None):
        """Save evolution state"""
        save_path = Path(path) if path else self.model_dir / 'evolution_state.json'

        state = {
            'generation': self.generation,
            'best_individual': self.best_individual.to_dict() if self.best_individual else None,
            'population': [ind.to_dict() for ind in self.population],
            'best_fitness_history': self.best_fitness_history,
            'config': self.config.__dict__
        }

        with open(save_path, 'w') as f:
            json.dump(state, f, indent=2)

        logger.info(f"Evolution state saved to {save_path}")

    def load(self, path: Optional[str] = None):
        """Load evolution state"""
        load_path = Path(path) if path else self.model_dir / 'evolution_state.json'

        if not load_path.exists():
            logger.warning(f"State file not found: {load_path}")
            return

        with open(load_path) as f:
            state = json.load(f)

        self.generation = state['generation']
        self.best_fitness_history = state.get('best_fitness_history', [])

        if state['best_individual']:
            self.best_individual = Individual.from_dict(state['best_individual'])

        self.population = [Individual.from_dict(ind) for ind in state.get('population', [])]

        logger.info(f"Evolution state loaded from {load_path}")

    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            'generation': self.generation,
            'population_size': len(self.population),
            'best_fitness': self.best_individual.fitness if self.best_individual else 0,
            'best_sharpe': self.best_individual.metrics.get('sharpe_ratio', 0) if self.best_individual else 0,
            'generations_history': len(self.best_fitness_history),
            'config': self.config.__dict__
        }


# Singleton instance
_evolution_engine: Optional[EvolutionEngine] = None


def get_evolution_engine() -> EvolutionEngine:
    """Get or create Evolution Engine singleton"""
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = EvolutionEngine()
    return _evolution_engine
