"""
Multi-Agent Trading System
==========================
Orchestrates multiple trading agents with different strategies,
aggregates signals, and manages portfolio-level coordination.

Features:
- Agent lifecycle management
- Signal aggregation (voting, weighted, ML ensemble)
- Consensus-based decision making
- Portfolio-level risk allocation
- Performance attribution by agent
"""

import numpy as np
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from collections import defaultdict
import threading
import uuid

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class SignalType(Enum):
    """Signal types from agents."""
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


class AggregationMethod(Enum):
    """Methods for aggregating agent signals."""
    SIMPLE_VOTE = "simple_vote"      # Majority wins
    WEIGHTED_VOTE = "weighted_vote"  # Weight by performance
    AVERAGE = "average"              # Average of all signals
    CONFIDENCE_WEIGHTED = "confidence_weighted"  # Weight by confidence
    ENSEMBLE_ML = "ensemble_ml"      # ML-based combination


@dataclass
class AgentSignal:
    """Signal emitted by an agent."""
    agent_id: str
    symbol: str
    signal_type: SignalType
    confidence: float  # 0-1
    target_position_pct: float  # Target as % of portfolio
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def numeric_signal(self) -> float:
        return self.signal_type.value


@dataclass
class AggregatedSignal:
    """Combined signal from multiple agents."""
    symbol: str
    consensus_signal: SignalType
    consensus_confidence: float
    target_position_pct: float
    contributing_agents: List[str]
    agreement_ratio: float  # How many agents agree
    weighted_signal: float  # Continuous signal value
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "signal": self.consensus_signal.name,
            "confidence": round(self.consensus_confidence, 2),
            "position_pct": round(self.target_position_pct, 2),
            "agents": self.contributing_agents,
            "agreement": f"{self.agreement_ratio:.0%}",
            "weighted_signal": round(self.weighted_signal, 2)
        }


@dataclass
class AgentPerformance:
    """Track individual agent performance."""
    agent_id: str
    total_signals: int = 0
    profitable_signals: int = 0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_confidence: float = 0.0
    
    # Rolling metrics
    recent_returns: List[float] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    
    def update(self, pnl: float, confidence: float):
        """Update performance metrics."""
        self.total_signals += 1
        self.total_pnl += pnl
        if pnl > 0:
            self.profitable_signals += 1
        self.win_rate = self.profitable_signals / self.total_signals
        
        self.recent_returns.append(pnl)
        self.confidence_history.append(confidence)
        
        # Keep rolling window
        if len(self.recent_returns) > 100:
            self.recent_returns = self.recent_returns[-100:]
            self.confidence_history = self.confidence_history[-100:]
        
        self.avg_confidence = np.mean(self.confidence_history)
        
        # Sharpe (simplified)
        if len(self.recent_returns) > 10:
            returns = np.array(self.recent_returns)
            if np.std(returns) > 0:
                self.sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)


class TradingAgent:
    """
    Base class for trading agents.
    
    Each agent implements its own strategy and emits signals.
    """
    
    def __init__(
        self,
        agent_id: str = None,
        name: str = "BaseAgent",
        symbols: List[str] = None,
        weight: float = 1.0
    ):
        self.agent_id = agent_id or str(uuid.uuid4())[:8]
        self.name = name
        self.symbols = symbols or []
        self.weight = weight
        self.state = AgentState.INITIALIZED
        self.performance = AgentPerformance(agent_id=self.agent_id)
        self._lock = threading.Lock()
    
    def start(self):
        """Start the agent."""
        self.state = AgentState.RUNNING
        logger.info(f"Agent {self.name} ({self.agent_id}) started")
    
    def stop(self):
        """Stop the agent."""
        self.state = AgentState.STOPPED
        logger.info(f"Agent {self.name} ({self.agent_id}) stopped")
    
    def pause(self):
        """Pause the agent."""
        self.state = AgentState.PAUSED
    
    def generate_signal(self, symbol: str, market_data: Dict) -> Optional[AgentSignal]:
        """
        Generate trading signal for a symbol.
        Override in subclasses.
        """
        raise NotImplementedError
    
    def update_performance(self, pnl: float, confidence: float):
        """Update agent performance metrics."""
        with self._lock:
            self.performance.update(pnl, confidence)


class MomentumAgent(TradingAgent):
    """Agent using momentum strategy."""
    
    def __init__(self, lookback: int = 20, **kwargs):
        super().__init__(name="MomentumAgent", **kwargs)
        self.lookback = lookback
    
    def generate_signal(self, symbol: str, market_data: Dict) -> Optional[AgentSignal]:
        closes = market_data.get('closes', [])
        if len(closes) < self.lookback + 1:
            return None
        
        # Calculate momentum
        momentum = (closes[-1] / closes[-self.lookback] - 1) * 100
        
        # Determine signal
        if momentum > 5:
            signal_type = SignalType.STRONG_BUY
            position = 0.1
        elif momentum > 2:
            signal_type = SignalType.BUY
            position = 0.05
        elif momentum < -5:
            signal_type = SignalType.STRONG_SELL
            position = -0.1
        elif momentum < -2:
            signal_type = SignalType.SELL
            position = -0.05
        else:
            signal_type = SignalType.HOLD
            position = 0
        
        confidence = min(abs(momentum) / 10, 1.0)
        
        return AgentSignal(
            agent_id=self.agent_id,
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            target_position_pct=position,
            reasoning=f"Momentum {momentum:.1f}%"
        )


class MeanReversionAgent(TradingAgent):
    """Agent using mean reversion strategy."""
    
    def __init__(self, lookback: int = 20, threshold: float = 2.0, **kwargs):
        super().__init__(name="MeanReversionAgent", **kwargs)
        self.lookback = lookback
        self.threshold = threshold
    
    def generate_signal(self, symbol: str, market_data: Dict) -> Optional[AgentSignal]:
        closes = market_data.get('closes', [])
        if len(closes) < self.lookback:
            return None
        
        # Calculate z-score
        recent = closes[-self.lookback:]
        mean = np.mean(recent)
        std = np.std(recent)
        if std == 0:
            return None
        
        z_score = (closes[-1] - mean) / std
        
        # Mean reversion: buy when oversold, sell when overbought
        if z_score < -self.threshold:
            signal_type = SignalType.STRONG_BUY
            position = 0.1
        elif z_score < -1:
            signal_type = SignalType.BUY
            position = 0.05
        elif z_score > self.threshold:
            signal_type = SignalType.STRONG_SELL
            position = -0.1
        elif z_score > 1:
            signal_type = SignalType.SELL
            position = -0.05
        else:
            signal_type = SignalType.HOLD
            position = 0
        
        confidence = min(abs(z_score) / 3, 1.0)
        
        return AgentSignal(
            agent_id=self.agent_id,
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            target_position_pct=position,
            reasoning=f"Z-score {z_score:.2f}"
        )


class BreakoutAgent(TradingAgent):
    """Agent using breakout strategy."""
    
    def __init__(self, lookback: int = 20, **kwargs):
        super().__init__(name="BreakoutAgent", **kwargs)
        self.lookback = lookback
    
    def generate_signal(self, symbol: str, market_data: Dict) -> Optional[AgentSignal]:
        highs = market_data.get('highs', [])
        lows = market_data.get('lows', [])
        closes = market_data.get('closes', [])
        
        if len(closes) < self.lookback:
            return None
        
        # Channel breakout
        recent_high = max(highs[-self.lookback:])
        recent_low = min(lows[-self.lookback:])
        current = closes[-1]
        
        channel_width = recent_high - recent_low
        if channel_width == 0:
            return None
        
        position_in_channel = (current - recent_low) / channel_width
        
        # Breakout signals
        if current > recent_high:
            signal_type = SignalType.STRONG_BUY
            position = 0.1
            confidence = 0.8
        elif position_in_channel > 0.9:
            signal_type = SignalType.BUY
            position = 0.05
            confidence = 0.6
        elif current < recent_low:
            signal_type = SignalType.STRONG_SELL
            position = -0.1
            confidence = 0.8
        elif position_in_channel < 0.1:
            signal_type = SignalType.SELL
            position = -0.05
            confidence = 0.6
        else:
            signal_type = SignalType.HOLD
            position = 0
            confidence = 0.3
        
        return AgentSignal(
            agent_id=self.agent_id,
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            target_position_pct=position,
            reasoning=f"Channel position {position_in_channel:.1%}"
        )


class VolatilityAgent(TradingAgent):
    """Agent that adjusts based on volatility regime."""
    
    def __init__(self, lookback: int = 20, **kwargs):
        super().__init__(name="VolatilityAgent", **kwargs)
        self.lookback = lookback
    
    def generate_signal(self, symbol: str, market_data: Dict) -> Optional[AgentSignal]:
        closes = market_data.get('closes', [])
        if len(closes) < self.lookback + 20:
            return None
        
        # Calculate current vs historical volatility
        returns = np.diff(closes[-self.lookback:]) / closes[-self.lookback:-1]
        current_vol = np.std(returns) * np.sqrt(252)
        
        historical_returns = np.diff(closes[-self.lookback-20:-self.lookback]) / closes[-self.lookback-21:-self.lookback-1]
        historical_vol = np.std(historical_returns) * np.sqrt(252)
        
        if historical_vol == 0:
            return None
        
        vol_ratio = current_vol / historical_vol
        
        # Volatility regime signal
        if vol_ratio < 0.8:
            # Low vol: expect mean reversion
            momentum = (closes[-1] / closes[-5] - 1) * 100
            if momentum > 1:
                signal_type = SignalType.SELL
                position = -0.03
            elif momentum < -1:
                signal_type = SignalType.BUY
                position = 0.03
            else:
                signal_type = SignalType.HOLD
                position = 0
            confidence = 0.5
        elif vol_ratio > 1.5:
            # High vol: reduce exposure
            signal_type = SignalType.HOLD
            position = 0
            confidence = 0.7
        else:
            signal_type = SignalType.HOLD
            position = 0
            confidence = 0.3
        
        return AgentSignal(
            agent_id=self.agent_id,
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            target_position_pct=position,
            reasoning=f"Vol ratio {vol_ratio:.2f}"
        )


class AgentManager:
    """
    Manages multiple trading agents and aggregates their signals.
    
    Features:
    - Register/unregister agents
    - Collect signals from all agents
    - Aggregate signals using various methods
    - Track agent performance
    - Manage risk allocation across agents
    """
    
    def __init__(
        self,
        aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_VOTE,
        max_total_position: float = 1.0,  # Max 100% invested
        min_agreement: float = 0.5  # Minimum agreement for action
    ):
        self.agents: Dict[str, TradingAgent] = {}
        self.aggregation_method = aggregation_method
        self.max_total_position = max_total_position
        self.min_agreement = min_agreement
        
        # Signal history
        self.signal_history: List[Dict] = []
        self._lock = threading.Lock()
    
    def register_agent(self, agent: TradingAgent):
        """Register a new agent."""
        with self._lock:
            self.agents[agent.agent_id] = agent
            logger.info(f"Registered agent: {agent.name} ({agent.agent_id})")
    
    def unregister_agent(self, agent_id: str):
        """Remove an agent."""
        with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                logger.info(f"Unregistered agent: {agent_id}")
    
    def start_all(self):
        """Start all agents."""
        for agent in self.agents.values():
            agent.start()
    
    def stop_all(self):
        """Stop all agents."""
        for agent in self.agents.values():
            agent.stop()
    
    def get_agent_signals(
        self,
        symbol: str,
        market_data: Dict
    ) -> List[AgentSignal]:
        """Collect signals from all running agents."""
        signals = []
        
        for agent in self.agents.values():
            if agent.state != AgentState.RUNNING:
                continue
            
            if agent.symbols and symbol not in agent.symbols:
                continue
            
            try:
                signal = agent.generate_signal(symbol, market_data)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} error: {e}")
                agent.state = AgentState.ERROR
        
        return signals
    
    def aggregate_signals(
        self,
        signals: List[AgentSignal]
    ) -> Optional[AggregatedSignal]:
        """
        Aggregate signals from multiple agents.
        """
        if not signals:
            return None
        
        symbol = signals[0].symbol
        
        if self.aggregation_method == AggregationMethod.SIMPLE_VOTE:
            return self._simple_vote(signals, symbol)
        elif self.aggregation_method == AggregationMethod.WEIGHTED_VOTE:
            return self._weighted_vote(signals, symbol)
        elif self.aggregation_method == AggregationMethod.CONFIDENCE_WEIGHTED:
            return self._confidence_weighted(signals, symbol)
        elif self.aggregation_method == AggregationMethod.AVERAGE:
            return self._average_signals(signals, symbol)
        else:
            return self._simple_vote(signals, symbol)
    
    def _simple_vote(
        self,
        signals: List[AgentSignal],
        symbol: str
    ) -> AggregatedSignal:
        """Majority voting."""
        votes = defaultdict(int)
        for signal in signals:
            votes[signal.signal_type] += 1
        
        # Find majority
        total = len(signals)
        winner = max(votes.keys(), key=lambda x: votes[x])
        agreement = votes[winner] / total
        
        # Average position from agreeing agents
        agreeing = [s for s in signals if s.signal_type == winner]
        avg_position = np.mean([s.target_position_pct for s in agreeing])
        avg_confidence = np.mean([s.confidence for s in agreeing])
        
        return AggregatedSignal(
            symbol=symbol,
            consensus_signal=winner,
            consensus_confidence=avg_confidence,
            target_position_pct=avg_position,
            contributing_agents=[s.agent_id for s in agreeing],
            agreement_ratio=agreement,
            weighted_signal=winner.value * avg_confidence
        )
    
    def _weighted_vote(
        self,
        signals: List[AgentSignal],
        symbol: str
    ) -> AggregatedSignal:
        """Weight votes by agent performance."""
        weighted_sum = 0
        total_weight = 0
        
        for signal in signals:
            agent = self.agents.get(signal.agent_id)
            if agent:
                # Weight by sharpe and win rate
                perf = agent.performance
                weight = agent.weight * (1 + max(0, perf.sharpe_ratio) * perf.win_rate)
            else:
                weight = 1.0
            
            weighted_sum += signal.numeric_signal * weight * signal.confidence
            total_weight += weight
        
        if total_weight == 0:
            return self._simple_vote(signals, symbol)
        
        weighted_signal = weighted_sum / total_weight
        
        # Convert to discrete signal
        if weighted_signal > 1.5:
            consensus = SignalType.STRONG_BUY
        elif weighted_signal > 0.5:
            consensus = SignalType.BUY
        elif weighted_signal < -1.5:
            consensus = SignalType.STRONG_SELL
        elif weighted_signal < -0.5:
            consensus = SignalType.SELL
        else:
            consensus = SignalType.HOLD
        
        # Calculate agreement
        agreeing = [s for s in signals if s.signal_type.value * weighted_signal > 0]
        agreement = len(agreeing) / len(signals) if signals else 0
        
        # Position sizing
        avg_position = np.mean([s.target_position_pct for s in signals])
        
        return AggregatedSignal(
            symbol=symbol,
            consensus_signal=consensus,
            consensus_confidence=abs(weighted_signal) / 2,  # Normalize to 0-1
            target_position_pct=avg_position * (1 if weighted_signal > 0 else -1),
            contributing_agents=[s.agent_id for s in signals],
            agreement_ratio=agreement,
            weighted_signal=weighted_signal
        )
    
    def _confidence_weighted(
        self,
        signals: List[AgentSignal],
        symbol: str
    ) -> AggregatedSignal:
        """Weight by confidence scores."""
        weighted_sum = 0
        total_confidence = 0
        
        for signal in signals:
            weighted_sum += signal.numeric_signal * signal.confidence
            total_confidence += signal.confidence
        
        if total_confidence == 0:
            return self._simple_vote(signals, symbol)
        
        weighted_signal = weighted_sum / total_confidence
        
        # Convert to discrete
        if weighted_signal > 1.5:
            consensus = SignalType.STRONG_BUY
        elif weighted_signal > 0.5:
            consensus = SignalType.BUY
        elif weighted_signal < -1.5:
            consensus = SignalType.STRONG_SELL
        elif weighted_signal < -0.5:
            consensus = SignalType.SELL
        else:
            consensus = SignalType.HOLD
        
        avg_confidence = total_confidence / len(signals)
        agreeing = [s for s in signals if s.signal_type == consensus]
        avg_position = np.mean([s.target_position_pct for s in agreeing]) if agreeing else 0
        
        return AggregatedSignal(
            symbol=symbol,
            consensus_signal=consensus,
            consensus_confidence=avg_confidence,
            target_position_pct=avg_position,
            contributing_agents=[s.agent_id for s in agreeing],
            agreement_ratio=len(agreeing) / len(signals),
            weighted_signal=weighted_signal
        )
    
    def _average_signals(
        self,
        signals: List[AgentSignal],
        symbol: str
    ) -> AggregatedSignal:
        """Simple average of all signals."""
        avg_signal = np.mean([s.numeric_signal for s in signals])
        avg_confidence = np.mean([s.confidence for s in signals])
        avg_position = np.mean([s.target_position_pct for s in signals])
        
        if avg_signal > 1.5:
            consensus = SignalType.STRONG_BUY
        elif avg_signal > 0.5:
            consensus = SignalType.BUY
        elif avg_signal < -1.5:
            consensus = SignalType.STRONG_SELL
        elif avg_signal < -0.5:
            consensus = SignalType.SELL
        else:
            consensus = SignalType.HOLD
        
        return AggregatedSignal(
            symbol=symbol,
            consensus_signal=consensus,
            consensus_confidence=avg_confidence,
            target_position_pct=avg_position,
            contributing_agents=[s.agent_id for s in signals],
            agreement_ratio=1.0,  # All signals used
            weighted_signal=avg_signal
        )
    
    def get_consensus_decision(
        self,
        symbol: str,
        market_data: Dict
    ) -> Optional[AggregatedSignal]:
        """
        Get consensus decision from all agents.
        
        Returns aggregated signal if agreement threshold is met.
        """
        signals = self.get_agent_signals(symbol, market_data)
        
        if not signals:
            return None
        
        aggregated = self.aggregate_signals(signals)
        
        if not aggregated:
            return None
        
        # Check minimum agreement
        if aggregated.agreement_ratio < self.min_agreement:
            logger.debug(f"Low agreement ({aggregated.agreement_ratio:.0%}) for {symbol}")
            aggregated.consensus_signal = SignalType.HOLD
            aggregated.target_position_pct = 0
        
        # Store in history
        self.signal_history.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "signal": aggregated.to_dict()
        })
        
        # Keep history bounded
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-1000:]
        
        return aggregated
    
    def get_portfolio_allocation(
        self,
        symbols: List[str],
        market_data: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Get recommended allocation across all symbols.
        
        Returns dict of symbol -> position_pct
        """
        allocations = {}
        total_allocated = 0
        
        for symbol in symbols:
            data = market_data.get(symbol, {})
            decision = self.get_consensus_decision(symbol, data)
            
            if decision and decision.consensus_signal != SignalType.HOLD:
                allocations[symbol] = decision.target_position_pct
                total_allocated += abs(decision.target_position_pct)
        
        # Scale down if over limit
        if total_allocated > self.max_total_position:
            scale = self.max_total_position / total_allocated
            for symbol in allocations:
                allocations[symbol] *= scale
        
        return allocations
    
    def get_status(self) -> Dict:
        """Get manager status."""
        return {
            "agents": {
                agent_id: {
                    "name": agent.name,
                    "state": agent.state.value,
                    "weight": agent.weight,
                    "performance": {
                        "total_signals": agent.performance.total_signals,
                        "win_rate": f"{agent.performance.win_rate:.1%}",
                        "sharpe": round(agent.performance.sharpe_ratio, 2),
                        "total_pnl": round(agent.performance.total_pnl, 2)
                    }
                }
                for agent_id, agent in self.agents.items()
            },
            "aggregation_method": self.aggregation_method.value,
            "min_agreement": self.min_agreement,
            "max_position": self.max_total_position,
            "signals_processed": len(self.signal_history)
        }


# Factory functions
def create_default_agent_team() -> AgentManager:
    """Create a default multi-agent team."""
    manager = AgentManager(
        aggregation_method=AggregationMethod.WEIGHTED_VOTE,
        min_agreement=0.4
    )
    
    # Register diverse agents
    manager.register_agent(MomentumAgent(lookback=20, weight=1.0))
    manager.register_agent(MeanReversionAgent(lookback=20, weight=0.8))
    manager.register_agent(BreakoutAgent(lookback=20, weight=0.9))
    manager.register_agent(VolatilityAgent(lookback=20, weight=0.7))
    
    return manager


def create_momentum_team() -> AgentManager:
    """Create momentum-focused team."""
    manager = AgentManager(aggregation_method=AggregationMethod.CONFIDENCE_WEIGHTED)
    
    manager.register_agent(MomentumAgent(lookback=10, weight=1.0))
    manager.register_agent(MomentumAgent(lookback=20, weight=1.0))
    manager.register_agent(MomentumAgent(lookback=50, weight=0.8))
    manager.register_agent(BreakoutAgent(lookback=20, weight=0.9))
    
    return manager


def create_mean_reversion_team() -> AgentManager:
    """Create mean reversion team."""
    manager = AgentManager(aggregation_method=AggregationMethod.AVERAGE)
    
    manager.register_agent(MeanReversionAgent(lookback=10, threshold=1.5, weight=1.0))
    manager.register_agent(MeanReversionAgent(lookback=20, threshold=2.0, weight=1.0))
    manager.register_agent(MeanReversionAgent(lookback=50, threshold=2.5, weight=0.8))
    manager.register_agent(VolatilityAgent(lookback=20, weight=0.7))
    
    return manager
