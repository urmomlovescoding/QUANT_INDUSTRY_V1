"""
QUANT_INDUSTRY_V1 Genetic Algorithm for Strategy Evolution

Evolutionary optimization of trading strategies using genetic programming.

Features:
- Strategy DNA encoding/decoding
- Crossover and mutation operators
- Multi-objective fitness (Sharpe, Sortino, Max DD)
- Island model parallelization
- Elitism and diversity preservation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
import copy
import logging

from .hypothesis import (
    AlphaHypothesis, HypothesisCondition, HypothesisType,
    HypothesisStatus, HypothesisGenerator,
)

logger = logging.getLogger(__name__)


# =============================================================================
# GENETIC ENCODING
# =============================================================================

@dataclass
class StrategyGenome:
    """
    Genetic representation of a trading strategy.
    """
    # Condition genes
    entry_genes: List[Dict[str, Any]]
    exit_genes: List[Dict[str, Any]]

    # Parameter genes
    direction: int
    stop_loss: float
    take_profit: float
    position_size: float
    max_holding: int

    # Metadata
    generation: int = 0
    fitness: float = 0.0
    fitness_components: Dict[str, float] = field(default_factory=dict)

    def to_hypothesis(self) -> AlphaHypothesis:
        """Convert genome to hypothesis."""
        entry_conditions = [
            HypothesisCondition(
                feature=g['feature'],
                operator=g['operator'],
                value=g['value'],
                value2=g.get('value2'),
                lookback=g.get('lookback', 1),
            )
            for g in self.entry_genes
        ]

        exit_conditions = [
            HypothesisCondition(
                feature=g['feature'],
                operator=g['operator'],
                value=g['value'],
                value2=g.get('value2'),
                lookback=g.get('lookback', 1),
            )
            for g in self.exit_genes
        ]

        hypothesis_type = self._infer_type()

        return AlphaHypothesis(
            hypothesis_id=f"GEN_{self.generation}_{id(self) % 10000}",
            name=f"Evolved_Gen{self.generation}",
            description=f"Genetically evolved strategy (gen {self.generation})",
            hypothesis_type=hypothesis_type,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            direction=self.direction,
            stop_loss_pct=self.stop_loss,
            take_profit_pct=self.take_profit,
            position_size_pct=self.position_size,
            max_holding_days=self.max_holding,
            generation=self.generation,
        )

    def _infer_type(self) -> HypothesisType:
        """Infer hypothesis type from genes."""
        features = [g['feature'] for g in self.entry_genes]

        if any('momentum' in f or 'roc' in f for f in features):
            return HypothesisType.MOMENTUM
        elif any('zscore' in f or 'bb_pct' in f for f in features):
            return HypothesisType.MEAN_REVERSION
        elif any('breakout' in f or 'bb_upper' in f for f in features):
            return HypothesisType.BREAKOUT
        else:
            return HypothesisType.FACTOR

    @staticmethod
    def from_hypothesis(hypothesis: AlphaHypothesis) -> 'StrategyGenome':
        """Create genome from hypothesis."""
        entry_genes = [
            {
                'feature': c.feature,
                'operator': c.operator,
                'value': c.value,
                'value2': c.value2,
                'lookback': c.lookback,
            }
            for c in hypothesis.entry_conditions
        ]

        exit_genes = [
            {
                'feature': c.feature,
                'operator': c.operator,
                'value': c.value,
                'value2': c.value2,
                'lookback': c.lookback,
            }
            for c in hypothesis.exit_conditions
        ]

        return StrategyGenome(
            entry_genes=entry_genes,
            exit_genes=exit_genes,
            direction=hypothesis.direction,
            stop_loss=hypothesis.stop_loss_pct,
            take_profit=hypothesis.take_profit_pct,
            position_size=hypothesis.position_size_pct,
            max_holding=hypothesis.max_holding_days,
            generation=hypothesis.generation,
        )


# =============================================================================
# GENETIC OPERATORS
# =============================================================================

class GeneticOperators:
    """
    Genetic operators for strategy evolution.
    """

    FEATURES = HypothesisGenerator.FEATURES
    OPERATORS = HypothesisGenerator.OPERATORS

    def __init__(self, seed: int = None):
        self.rng = np.random.default_rng(seed)

    def crossover(
        self,
        parent1: StrategyGenome,
        parent2: StrategyGenome,
        crossover_rate: float = 0.7,
    ) -> Tuple[StrategyGenome, StrategyGenome]:
        """
        Perform crossover between two parent genomes.
        """
        if self.rng.random() > crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        # Entry gene crossover (uniform)
        child1_entry = []
        child2_entry = []

        max_entry = max(len(parent1.entry_genes), len(parent2.entry_genes))
        for i in range(max_entry):
            if self.rng.random() < 0.5:
                if i < len(parent1.entry_genes):
                    child1_entry.append(copy.deepcopy(parent1.entry_genes[i]))
                if i < len(parent2.entry_genes):
                    child2_entry.append(copy.deepcopy(parent2.entry_genes[i]))
            else:
                if i < len(parent2.entry_genes):
                    child1_entry.append(copy.deepcopy(parent2.entry_genes[i]))
                if i < len(parent1.entry_genes):
                    child2_entry.append(copy.deepcopy(parent1.entry_genes[i]))

        # Exit gene crossover
        child1_exit = []
        child2_exit = []

        max_exit = max(len(parent1.exit_genes), len(parent2.exit_genes))
        for i in range(max_exit):
            if self.rng.random() < 0.5:
                if i < len(parent1.exit_genes):
                    child1_exit.append(copy.deepcopy(parent1.exit_genes[i]))
                if i < len(parent2.exit_genes):
                    child2_exit.append(copy.deepcopy(parent2.exit_genes[i]))
            else:
                if i < len(parent2.exit_genes):
                    child1_exit.append(copy.deepcopy(parent2.exit_genes[i]))
                if i < len(parent1.exit_genes):
                    child2_exit.append(copy.deepcopy(parent1.exit_genes[i]))

        # Parameter blending
        alpha = self.rng.random()

        child1 = StrategyGenome(
            entry_genes=child1_entry if child1_entry else [self._random_gene()],
            exit_genes=child1_exit if child1_exit else [self._random_gene()],
            direction=parent1.direction if self.rng.random() < 0.5 else parent2.direction,
            stop_loss=alpha * parent1.stop_loss + (1 - alpha) * parent2.stop_loss,
            take_profit=alpha * parent1.take_profit + (1 - alpha) * parent2.take_profit,
            position_size=alpha * parent1.position_size + (1 - alpha) * parent2.position_size,
            max_holding=int(alpha * parent1.max_holding + (1 - alpha) * parent2.max_holding),
            generation=max(parent1.generation, parent2.generation) + 1,
        )

        child2 = StrategyGenome(
            entry_genes=child2_entry if child2_entry else [self._random_gene()],
            exit_genes=child2_exit if child2_exit else [self._random_gene()],
            direction=parent2.direction if self.rng.random() < 0.5 else parent1.direction,
            stop_loss=(1 - alpha) * parent1.stop_loss + alpha * parent2.stop_loss,
            take_profit=(1 - alpha) * parent1.take_profit + alpha * parent2.take_profit,
            position_size=(1 - alpha) * parent1.position_size + alpha * parent2.position_size,
            max_holding=int((1 - alpha) * parent1.max_holding + alpha * parent2.max_holding),
            generation=max(parent1.generation, parent2.generation) + 1,
        )

        return child1, child2

    def mutate(
        self,
        genome: StrategyGenome,
        mutation_rate: float = 0.1,
        mutation_strength: float = 0.2,
    ) -> StrategyGenome:
        """
        Mutate a genome with various mutation types.
        """
        mutated = copy.deepcopy(genome)

        # Condition mutations
        for genes in [mutated.entry_genes, mutated.exit_genes]:
            for gene in genes:
                if self.rng.random() < mutation_rate:
                    mutation_type = self.rng.choice([
                        'value', 'operator', 'feature', 'lookback'
                    ])

                    if mutation_type == 'value':
                        # Gaussian perturbation
                        gene['value'] *= (1 + self.rng.normal(0, mutation_strength))
                        if gene.get('value2'):
                            gene['value2'] *= (1 + self.rng.normal(0, mutation_strength))

                    elif mutation_type == 'operator':
                        gene['operator'] = self.rng.choice(self.OPERATORS)

                    elif mutation_type == 'feature':
                        gene['feature'] = self.rng.choice(self.FEATURES)

                    elif mutation_type == 'lookback':
                        gene['lookback'] = max(1, gene.get('lookback', 1) + self.rng.integers(-2, 3))

        # Structural mutations (add/remove conditions)
        if self.rng.random() < mutation_rate * 0.5:
            if len(mutated.entry_genes) > 1 and self.rng.random() < 0.5:
                # Remove random entry condition
                idx = self.rng.integers(0, len(mutated.entry_genes))
                mutated.entry_genes.pop(idx)
            elif len(mutated.entry_genes) < 6:
                # Add new entry condition
                mutated.entry_genes.append(self._random_gene())

        if self.rng.random() < mutation_rate * 0.5:
            if len(mutated.exit_genes) > 1 and self.rng.random() < 0.5:
                idx = self.rng.integers(0, len(mutated.exit_genes))
                mutated.exit_genes.pop(idx)
            elif len(mutated.exit_genes) < 4:
                mutated.exit_genes.append(self._random_gene())

        # Parameter mutations
        if self.rng.random() < mutation_rate:
            mutated.stop_loss = np.clip(
                mutated.stop_loss * (1 + self.rng.normal(0, mutation_strength)),
                0.005, 0.10
            )

        if self.rng.random() < mutation_rate:
            mutated.take_profit = np.clip(
                mutated.take_profit * (1 + self.rng.normal(0, mutation_strength)),
                0.01, 0.20
            )

        if self.rng.random() < mutation_rate:
            mutated.position_size = np.clip(
                mutated.position_size * (1 + self.rng.normal(0, mutation_strength)),
                0.005, 0.10
            )

        if self.rng.random() < mutation_rate:
            mutated.max_holding = max(1, min(30, mutated.max_holding + self.rng.integers(-3, 4)))

        if self.rng.random() < mutation_rate * 0.3:
            mutated.direction *= -1

        return mutated

    def _random_gene(self) -> Dict[str, Any]:
        """Generate a random condition gene."""
        feature = self.rng.choice(self.FEATURES)
        operator = self.rng.choice(self.OPERATORS)

        # Generate appropriate value
        if 'rsi' in feature:
            value = self.rng.uniform(20, 80)
        elif 'zscore' in feature:
            value = self.rng.uniform(-2, 2)
        elif 'ratio' in feature:
            value = self.rng.uniform(0.5, 2.0)
        else:
            value = self.rng.uniform(-1, 1)

        return {
            'feature': feature,
            'operator': operator,
            'value': value,
            'value2': value + abs(self.rng.normal(0, 0.5)) if operator == 'between' else None,
            'lookback': self.rng.integers(1, 5),
        }


# =============================================================================
# FITNESS EVALUATION
# =============================================================================

class MultiObjectiveFitness:
    """
    Multi-objective fitness function for strategy evaluation.
    """

    def __init__(
        self,
        sharpe_weight: float = 0.4,
        sortino_weight: float = 0.2,
        drawdown_weight: float = 0.2,
        consistency_weight: float = 0.1,
        trade_count_weight: float = 0.1,
    ):
        self.weights = {
            'sharpe': sharpe_weight,
            'sortino': sortino_weight,
            'drawdown': drawdown_weight,
            'consistency': consistency_weight,
            'trade_count': trade_count_weight,
        }

    def evaluate(
        self,
        returns: np.ndarray,
        benchmark_sharpe: float = 0.5,
        min_trades: int = 30,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Evaluate fitness of a strategy.

        Returns: (total_fitness, component_dict)
        """
        if len(returns) < min_trades:
            return -1.0, {'valid': False, 'reason': 'insufficient_trades'}

        components = {}

        # Sharpe ratio
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0
        components['sharpe'] = sharpe

        # Sortino ratio
        downside_returns = returns[returns < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 0 else std_ret
        sortino = mean_ret / downside_std * np.sqrt(252) if downside_std > 0 else sharpe
        components['sortino'] = sortino

        # Max drawdown
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = (cum_returns - running_max) / running_max
        max_dd = np.min(drawdowns)
        components['max_drawdown'] = max_dd

        # Consistency (percentage of profitable months approximation)
        # Split into ~21-day chunks
        chunk_size = 21
        n_chunks = len(returns) // chunk_size
        if n_chunks > 0:
            chunk_returns = [
                np.sum(returns[i * chunk_size:(i + 1) * chunk_size])
                for i in range(n_chunks)
            ]
            consistency = np.mean(np.array(chunk_returns) > 0)
        else:
            consistency = 0.5
        components['consistency'] = consistency

        # Trade count score (normalized)
        trade_score = min(1.0, len(returns) / (min_trades * 3))
        components['trade_count'] = trade_score

        # Win rate
        components['win_rate'] = np.mean(returns > 0)

        # Profit factor
        gross_profit = np.sum(returns[returns > 0])
        gross_loss = abs(np.sum(returns[returns < 0]))
        components['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else 10.0

        # Calculate total fitness
        # Normalize components to [0, 1] range
        sharpe_score = np.clip((sharpe - benchmark_sharpe) / 2, -1, 1) * 0.5 + 0.5
        sortino_score = np.clip(sortino / 3, 0, 1)
        dd_score = np.clip(1 + max_dd / 0.3, 0, 1)  # -30% DD = 0, 0% DD = 1

        total_fitness = (
            self.weights['sharpe'] * sharpe_score +
            self.weights['sortino'] * sortino_score +
            self.weights['drawdown'] * dd_score +
            self.weights['consistency'] * consistency +
            self.weights['trade_count'] * trade_score
        )

        components['total_fitness'] = total_fitness

        return total_fitness, components


# =============================================================================
# GENETIC ALGORITHM
# =============================================================================

class StrategyEvolver:
    """
    Genetic algorithm for evolving trading strategies.
    """

    def __init__(
        self,
        population_size: int = 100,
        elite_ratio: float = 0.1,
        crossover_rate: float = 0.7,
        mutation_rate: float = 0.1,
        tournament_size: int = 5,
        seed: int = None,
    ):
        self.population_size = population_size
        self.elite_ratio = elite_ratio
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size

        self.rng = np.random.default_rng(seed)
        self.operators = GeneticOperators(seed)
        self.fitness_fn = MultiObjectiveFitness()
        self.generator = HypothesisGenerator(seed)

        self.population: List[StrategyGenome] = []
        self.best_genome: Optional[StrategyGenome] = None
        self.generation = 0
        self.history: List[Dict[str, Any]] = []

    def initialize_population(self, seed_hypotheses: List[AlphaHypothesis] = None) -> None:
        """Initialize population with random or seed strategies."""
        self.population = []

        # Add seed hypotheses
        if seed_hypotheses:
            for h in seed_hypotheses[:self.population_size // 2]:
                genome = StrategyGenome.from_hypothesis(h)
                self.population.append(genome)

        # Fill rest with random
        while len(self.population) < self.population_size:
            h = self.generator.generate_random()
            genome = StrategyGenome.from_hypothesis(h)
            self.population.append(genome)

        logger.info(f"Initialized population with {len(self.population)} genomes")

    def evaluate_population(
        self,
        evaluate_fn: Callable[[AlphaHypothesis], np.ndarray],
    ) -> None:
        """Evaluate fitness of all genomes in population."""
        for genome in self.population:
            hypothesis = genome.to_hypothesis()
            returns = evaluate_fn(hypothesis)

            if returns is not None and len(returns) > 0:
                fitness, components = self.fitness_fn.evaluate(returns)
                genome.fitness = fitness
                genome.fitness_components = components
            else:
                genome.fitness = -1.0
                genome.fitness_components = {'valid': False}

        # Update best
        valid_genomes = [g for g in self.population if g.fitness > 0]
        if valid_genomes:
            best = max(valid_genomes, key=lambda g: g.fitness)
            if self.best_genome is None or best.fitness > self.best_genome.fitness:
                self.best_genome = copy.deepcopy(best)

    def select_parents(self) -> Tuple[StrategyGenome, StrategyGenome]:
        """Tournament selection for parents."""
        def tournament() -> StrategyGenome:
            candidates = self.rng.choice(
                self.population,
                size=min(self.tournament_size, len(self.population)),
                replace=False
            )
            return max(candidates, key=lambda g: g.fitness)

        return tournament(), tournament()

    def evolve_generation(
        self,
        evaluate_fn: Callable[[AlphaHypothesis], np.ndarray],
    ) -> Dict[str, Any]:
        """Evolve one generation."""
        self.generation += 1

        # Evaluate current population
        self.evaluate_population(evaluate_fn)

        # Sort by fitness
        self.population.sort(key=lambda g: g.fitness, reverse=True)

        # Statistics
        valid_fitness = [g.fitness for g in self.population if g.fitness > 0]
        stats = {
            'generation': self.generation,
            'best_fitness': self.population[0].fitness if self.population else 0,
            'avg_fitness': np.mean(valid_fitness) if valid_fitness else 0,
            'std_fitness': np.std(valid_fitness) if valid_fitness else 0,
            'valid_count': len(valid_fitness),
        }

        if self.best_genome:
            stats['all_time_best'] = self.best_genome.fitness
            stats['best_sharpe'] = self.best_genome.fitness_components.get('sharpe', 0)

        self.history.append(stats)

        # Elitism - keep top performers
        elite_count = int(self.population_size * self.elite_ratio)
        new_population = [copy.deepcopy(g) for g in self.population[:elite_count]]

        # Generate offspring
        while len(new_population) < self.population_size:
            parent1, parent2 = self.select_parents()
            child1, child2 = self.operators.crossover(
                parent1, parent2, self.crossover_rate
            )

            child1 = self.operators.mutate(child1, self.mutation_rate)
            child2 = self.operators.mutate(child2, self.mutation_rate)

            child1.generation = self.generation
            child2.generation = self.generation

            new_population.append(child1)
            if len(new_population) < self.population_size:
                new_population.append(child2)

        self.population = new_population

        logger.info(
            f"Generation {self.generation}: "
            f"best={stats['best_fitness']:.4f}, "
            f"avg={stats['avg_fitness']:.4f}, "
            f"valid={stats['valid_count']}/{self.population_size}"
        )

        return stats

    def evolve(
        self,
        evaluate_fn: Callable[[AlphaHypothesis], np.ndarray],
        n_generations: int = 50,
        early_stop_generations: int = 10,
        target_fitness: float = 0.8,
    ) -> List[AlphaHypothesis]:
        """
        Run full evolution process.

        Returns top strategies as hypotheses.
        """
        if not self.population:
            self.initialize_population()

        no_improvement_count = 0
        prev_best = -float('inf')

        for gen in range(n_generations):
            stats = self.evolve_generation(evaluate_fn)

            # Check improvement
            if stats['best_fitness'] > prev_best:
                prev_best = stats['best_fitness']
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            # Early stopping
            if no_improvement_count >= early_stop_generations:
                logger.info(f"Early stopping at generation {self.generation}")
                break

            if stats['best_fitness'] >= target_fitness:
                logger.info(f"Target fitness reached at generation {self.generation}")
                break

        # Return top strategies
        self.population.sort(key=lambda g: g.fitness, reverse=True)
        top_genomes = [g for g in self.population[:10] if g.fitness > 0]

        return [g.to_hypothesis() for g in top_genomes]

    def get_best_strategies(self, n: int = 5) -> List[AlphaHypothesis]:
        """Get top N strategies."""
        self.population.sort(key=lambda g: g.fitness, reverse=True)
        top = [g for g in self.population[:n] if g.fitness > 0]
        return [g.to_hypothesis() for g in top]


# =============================================================================
# ISLAND MODEL (Parallel Evolution)
# =============================================================================

class IslandModel:
    """
    Island model for parallel strategy evolution with migration.
    """

    def __init__(
        self,
        n_islands: int = 4,
        population_per_island: int = 50,
        migration_rate: float = 0.1,
        migration_interval: int = 5,
        seed: int = None,
    ):
        self.n_islands = n_islands
        self.migration_rate = migration_rate
        self.migration_interval = migration_interval

        self.rng = np.random.default_rng(seed)

        # Create islands with different configurations
        self.islands: List[StrategyEvolver] = []
        for i in range(n_islands):
            evolver = StrategyEvolver(
                population_size=population_per_island,
                mutation_rate=0.05 + i * 0.05,  # Varying mutation rates
                crossover_rate=0.6 + i * 0.1,
                seed=seed + i if seed else None,
            )
            self.islands.append(evolver)

        self.generation = 0

    def migrate(self) -> None:
        """Migrate best individuals between islands."""
        n_migrants = max(1, int(self.islands[0].population_size * self.migration_rate))

        for i in range(self.n_islands):
            source = self.islands[i]
            target = self.islands[(i + 1) % self.n_islands]

            # Get best from source
            source.population.sort(key=lambda g: g.fitness, reverse=True)
            migrants = [copy.deepcopy(g) for g in source.population[:n_migrants]]

            # Replace worst in target
            target.population.sort(key=lambda g: g.fitness)
            for j, migrant in enumerate(migrants):
                if j < len(target.population):
                    target.population[j] = migrant

        logger.info(f"Migration completed: {n_migrants} individuals per island")

    def evolve(
        self,
        evaluate_fn: Callable[[AlphaHypothesis], np.ndarray],
        n_generations: int = 50,
    ) -> List[AlphaHypothesis]:
        """Run island model evolution."""
        # Initialize all islands
        for island in self.islands:
            island.initialize_population()

        for gen in range(n_generations):
            self.generation = gen + 1

            # Evolve each island
            for i, island in enumerate(self.islands):
                island.evolve_generation(evaluate_fn)

            # Migration
            if (gen + 1) % self.migration_interval == 0:
                self.migrate()

            # Log best across all islands
            all_best = [
                island.best_genome.fitness if island.best_genome else 0
                for island in self.islands
            ]
            logger.info(
                f"Island gen {self.generation}: "
                f"best per island = {[f'{b:.3f}' for b in all_best]}"
            )

        # Collect best from all islands
        all_strategies = []
        for island in self.islands:
            all_strategies.extend(island.get_best_strategies(3))

        # Deduplicate and sort
        seen_hashes = set()
        unique_strategies = []
        for s in all_strategies:
            h = s.get_hash()
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_strategies.append(s)

        unique_strategies.sort(key=lambda s: s.sharpe_ratio, reverse=True)

        return unique_strategies[:10]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'StrategyGenome',
    'GeneticOperators',
    'MultiObjectiveFitness',
    'StrategyEvolver',
    'IslandModel',
]
