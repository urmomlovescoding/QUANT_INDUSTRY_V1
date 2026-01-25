"""
Core Module for QUANT INDUSTRY
==============================
P0 Critical Features: Brain-Bot Bridge, Market Memory, System Coordination.

Implements parity with quant-platform/core/ system:
- Brain-Bot Bridge (deployment stages)
- Market Memory (episodic retrieval)
- Regime Discovery
- System Coordination
"""

from .brain_bot_bridge import (
    DeploymentStage,
    ModelHealth,
    DeploymentRecord,
    ExecutionFeedback,
    BrainToBotBridge,
    get_brain_bot_bridge,
)

from .market_memory import (
    MarketEpisode,
    EpisodeMatch,
    MarketMemory,
    get_market_memory,
)

from .regime_discovery import (
    MarketRegime,
    RegimeState,
    RegimeTransition,
    RegimeDiscovery,
    get_regime_discovery,
)

__all__ = [
    # Deployment
    "DeploymentStage",
    "ModelHealth",
    "DeploymentRecord",
    "ExecutionFeedback",
    "BrainToBotBridge",
    "get_brain_bot_bridge",
    # Market Memory
    "MarketEpisode",
    "EpisodeMatch",
    "MarketMemory",
    "get_market_memory",
    # Regime Discovery
    "MarketRegime",
    "RegimeState",
    "RegimeTransition",
    "RegimeDiscovery",
    "get_regime_discovery",
]
