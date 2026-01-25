"""
Market Memory with Episodic Retrieval
=====================================
P0 Critical Feature: Stores and retrieves market episodes for pattern matching.

Implements parity with quant-platform/core/market_memory.py

Market Memory allows the system to:
1. Store significant market episodes (crashes, rallies, regime changes)
2. Retrieve similar episodes when current conditions match
3. Use historical patterns to inform current decisions
4. Learn from past successes and failures
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

logger = logging.getLogger("MARKET_MEMORY")


@dataclass
class MarketEpisode:
    """
    A stored market episode.

    Episodes represent significant market events that the system
    learned from and can reference in the future.
    """
    episode_id: str
    timestamp: datetime
    episode_type: str  # 'crash', 'rally', 'reversal', 'breakout', 'regime_change'

    # Market conditions
    symbol: str
    timeframe: str
    regime: str
    volatility: float
    trend_strength: float

    # Price action
    price_at_start: float
    price_at_end: float
    price_change_pct: float
    duration_bars: int

    # Features at time of episode
    features: Dict[str, float] = field(default_factory=dict)

    # Outcome
    outcome: str = ""  # 'success', 'failure', 'neutral'
    pnl_impact: float = 0.0

    # Similarity search data
    embedding: List[float] = field(default_factory=list)

    # Metadata
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketEpisode":
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class EpisodeMatch:
    """Result of searching for similar episodes."""
    episode: MarketEpisode
    similarity_score: float
    matching_features: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode": self.episode.to_dict(),
            "similarity_score": self.similarity_score,
            "matching_features": self.matching_features,
        }


class MarketMemory:
    """
    Episodic memory for market events.

    Stores significant market episodes and retrieves
    similar ones when current conditions match.

    Implements pattern matching via:
    1. Feature-based similarity (exact match on key features)
    2. Embedding similarity (cosine similarity on feature vectors)
    3. Regime matching (same market regime)
    """

    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or Path("memory")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._episodes_file = self.state_dir / "episodes.json"

        # Episode storage
        self.episodes: List[MarketEpisode] = []
        self.max_episodes: int = 1000

        # Index for fast lookup
        self._regime_index: Dict[str, List[int]] = {}
        self._type_index: Dict[str, List[int]] = {}
        self._symbol_index: Dict[str, List[int]] = {}

        # Feature weights for similarity
        self.feature_weights: Dict[str, float] = {
            "volatility": 2.0,
            "trend_strength": 1.5,
            "regime": 3.0,  # Regime match is important
            "price_change_pct": 1.0,
        }

        # Load persisted episodes
        self._load_episodes()

        logger.info(f"MarketMemory initialized with {len(self.episodes)} episodes")

    def _load_episodes(self) -> None:
        """Load episodes from disk."""
        try:
            if self._episodes_file.exists():
                with open(self._episodes_file) as f:
                    data = json.load(f)

                self.episodes = [
                    MarketEpisode.from_dict(e) for e in data.get("episodes", [])
                ]
                self._rebuild_indices()
        except Exception as e:
            logger.error(f"Error loading episodes: {e}")

    def _save_episodes(self) -> None:
        """Save episodes to disk."""
        try:
            data = {
                "episodes": [e.to_dict() for e in self.episodes],
                "updated": datetime.now().isoformat(),
            }
            with open(self._episodes_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving episodes: {e}")

    def _rebuild_indices(self) -> None:
        """Rebuild lookup indices."""
        self._regime_index.clear()
        self._type_index.clear()
        self._symbol_index.clear()

        for i, episode in enumerate(self.episodes):
            # Regime index
            if episode.regime not in self._regime_index:
                self._regime_index[episode.regime] = []
            self._regime_index[episode.regime].append(i)

            # Type index
            if episode.episode_type not in self._type_index:
                self._type_index[episode.episode_type] = []
            self._type_index[episode.episode_type].append(i)

            # Symbol index
            if episode.symbol not in self._symbol_index:
                self._symbol_index[episode.symbol] = []
            self._symbol_index[episode.symbol].append(i)

    def store_episode(self, episode: MarketEpisode) -> str:
        """
        Store a new episode in memory.

        Args:
            episode: Episode to store

        Returns:
            Episode ID
        """
        # Generate ID if not set
        if not episode.episode_id:
            episode.episode_id = self._generate_id(episode)

        # Generate embedding if not set
        if not episode.embedding:
            episode.embedding = self._generate_embedding(episode)

        # Add to storage
        self.episodes.append(episode)

        # Trim if needed
        if len(self.episodes) > self.max_episodes:
            # Remove oldest episodes, but keep high-impact ones
            self.episodes.sort(key=lambda e: (abs(e.pnl_impact), e.timestamp))
            self.episodes = self.episodes[-self.max_episodes:]

        # Update indices
        self._rebuild_indices()

        # Persist
        self._save_episodes()

        logger.info(f"Stored episode: {episode.episode_id} ({episode.episode_type})")

        return episode.episode_id

    def _generate_id(self, episode: MarketEpisode) -> str:
        """Generate unique episode ID."""
        content = f"{episode.timestamp}_{episode.symbol}_{episode.episode_type}"
        return f"ep_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def _generate_embedding(self, episode: MarketEpisode) -> List[float]:
        """
        Generate embedding vector for similarity search.

        Simple feature-based embedding (in production would use ML embeddings).
        """
        # Normalize features to 0-1 range
        embedding = [
            min(1.0, episode.volatility / 50),  # Assume 50% max vol
            (episode.trend_strength + 1) / 2,   # -1 to 1 -> 0 to 1
            min(1.0, abs(episode.price_change_pct) / 10),  # 10% max change
            episode.duration_bars / 100,        # Normalize duration
        ]

        # Add regime as one-hot encoding
        regimes = ["trending_up", "trending_down", "ranging", "volatile", "unknown"]
        for regime in regimes:
            embedding.append(1.0 if episode.regime == regime else 0.0)

        # Add episode type as one-hot
        types = ["crash", "rally", "reversal", "breakout", "regime_change"]
        for ep_type in types:
            embedding.append(1.0 if episode.episode_type == ep_type else 0.0)

        return embedding

    def search_similar(
        self,
        current_conditions: Dict[str, Any],
        limit: int = 5,
        min_similarity: float = 0.5,
    ) -> List[EpisodeMatch]:
        """
        Search for episodes similar to current conditions.

        Args:
            current_conditions: Dict with keys:
                - regime: Current market regime
                - volatility: Current volatility
                - trend_strength: Current trend strength
                - symbol: Symbol (optional, for filtering)
            limit: Max number of results
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List of matching episodes with similarity scores
        """
        if not self.episodes:
            return []

        regime = current_conditions.get("regime", "unknown")
        volatility = current_conditions.get("volatility", 0)
        trend_strength = current_conditions.get("trend_strength", 0)
        symbol = current_conditions.get("symbol")

        # Create query embedding
        query_episode = MarketEpisode(
            episode_id="query",
            timestamp=datetime.now(),
            episode_type="query",
            symbol=symbol or "",
            timeframe="",
            regime=regime,
            volatility=volatility,
            trend_strength=trend_strength,
            price_at_start=0,
            price_at_end=0,
            price_change_pct=0,
            duration_bars=0,
        )
        query_embedding = self._generate_embedding(query_episode)

        # Calculate similarities
        matches = []
        for episode in self.episodes:
            # Filter by symbol if specified
            if symbol and episode.symbol != symbol:
                continue

            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, episode.embedding)

            # Boost for regime match
            if episode.regime == regime:
                similarity = min(1.0, similarity * 1.3)

            if similarity >= min_similarity:
                matching_features = []
                if episode.regime == regime:
                    matching_features.append("regime")
                if abs(episode.volatility - volatility) < volatility * 0.2:
                    matching_features.append("volatility")
                if abs(episode.trend_strength - trend_strength) < 0.2:
                    matching_features.append("trend_strength")

                matches.append(EpisodeMatch(
                    episode=episode,
                    similarity_score=similarity,
                    matching_features=matching_features,
                ))

        # Sort by similarity
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        return matches[:limit]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2) or len(vec1) == 0:
            return 0.0

        a = np.array(vec1)
        b = np.array(vec2)

        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot / (norm_a * norm_b))

    def get_by_type(self, episode_type: str, limit: int = 10) -> List[MarketEpisode]:
        """Get episodes by type."""
        indices = self._type_index.get(episode_type, [])
        return [self.episodes[i] for i in indices[-limit:]]

    def get_by_regime(self, regime: str, limit: int = 10) -> List[MarketEpisode]:
        """Get episodes by regime."""
        indices = self._regime_index.get(regime, [])
        return [self.episodes[i] for i in indices[-limit:]]

    def get_successful_episodes(
        self,
        episode_type: Optional[str] = None,
        regime: Optional[str] = None,
        limit: int = 10,
    ) -> List[MarketEpisode]:
        """Get successful episodes for learning."""
        filtered = self.episodes

        if episode_type:
            filtered = [e for e in filtered if e.episode_type == episode_type]

        if regime:
            filtered = [e for e in filtered if e.regime == regime]

        successful = [e for e in filtered if e.outcome == "success"]
        successful.sort(key=lambda e: e.pnl_impact, reverse=True)

        return successful[:limit]

    def get_failed_episodes(
        self,
        episode_type: Optional[str] = None,
        regime: Optional[str] = None,
        limit: int = 10,
    ) -> List[MarketEpisode]:
        """Get failed episodes to avoid repeating mistakes."""
        filtered = self.episodes

        if episode_type:
            filtered = [e for e in filtered if e.episode_type == episode_type]

        if regime:
            filtered = [e for e in filtered if e.regime == regime]

        failed = [e for e in filtered if e.outcome == "failure"]
        failed.sort(key=lambda e: e.pnl_impact)  # Most negative first

        return failed[:limit]

    def learn_from_outcome(
        self,
        episode_id: str,
        outcome: str,
        pnl_impact: float,
        notes: str = "",
    ) -> bool:
        """
        Update episode with outcome for learning.

        Args:
            episode_id: Episode to update
            outcome: 'success', 'failure', or 'neutral'
            pnl_impact: P&L impact of the episode
            notes: Additional notes

        Returns:
            True if updated
        """
        for episode in self.episodes:
            if episode.episode_id == episode_id:
                episode.outcome = outcome
                episode.pnl_impact = pnl_impact
                if notes:
                    episode.notes = notes
                self._save_episodes()
                logger.info(f"Updated episode {episode_id}: {outcome}, PnL={pnl_impact}")
                return True

        logger.warning(f"Episode not found: {episode_id}")
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if not self.episodes:
            return {"total_episodes": 0}

        by_type = {}
        by_regime = {}
        by_outcome = {"success": 0, "failure": 0, "neutral": 0}
        total_pnl = 0.0

        for episode in self.episodes:
            by_type[episode.episode_type] = by_type.get(episode.episode_type, 0) + 1
            by_regime[episode.regime] = by_regime.get(episode.regime, 0) + 1
            if episode.outcome:
                by_outcome[episode.outcome] = by_outcome.get(episode.outcome, 0) + 1
            total_pnl += episode.pnl_impact

        return {
            "total_episodes": len(self.episodes),
            "by_type": by_type,
            "by_regime": by_regime,
            "by_outcome": by_outcome,
            "total_pnl_impact": total_pnl,
            "success_rate": (
                by_outcome["success"] / (by_outcome["success"] + by_outcome["failure"])
                if (by_outcome["success"] + by_outcome["failure"]) > 0
                else 0.0
            ),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get memory status."""
        return {
            "episode_count": len(self.episodes),
            "regimes_tracked": list(self._regime_index.keys()),
            "types_tracked": list(self._type_index.keys()),
            "symbols_tracked": list(self._symbol_index.keys()),
            "max_episodes": self.max_episodes,
            "stats": self.get_stats(),
        }


# Singleton instance
_market_memory: Optional[MarketMemory] = None


def get_market_memory() -> MarketMemory:
    """Get or create market memory singleton."""
    global _market_memory
    if _market_memory is None:
        _market_memory = MarketMemory()
    return _market_memory
