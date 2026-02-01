"""
ML Brain Orchestrator
=====================
Central intelligence that trains models, generates signals,
and coordinates with trading bots. Implements the learn-trade-feedback loop.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                      ML BRAIN                                │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
    │  │ Model Train │  │ Feature Sel │  │ Strategy Generator  │  │
    │  └─────────────┘  └─────────────┘  └─────────────────────┘  │
    │                         │                                    │
    │                    ┌────┴────┐                               │
    │                    │ Signals │                               │
    └────────────────────┴────┬────┴───────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    TRADING BOTS                              │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
    │  │ Bot TPT │  │ Bot HFT │  │ Bot Swg │  │ Bot Arbitrage   │ │
    │  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │
    └─────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                   FEEDBACK PIPELINE                          │
    │  ┌───────────┐  ┌───────────┐  ┌───────────────────────────┐│
    │  │ Backtest  │  │ Live Perf │  │ Attribution Analysis      ││
    │  └───────────┘  └───────────┘  └───────────────────────────┘│
    │                         │                                    │
    │                    ┌────┴────┐                               │
    │                    │ Metrics │ ──────────────────────────────┼──► ML BRAIN
    └─────────────────────────────────────────────────────────────┘
"""

import asyncio
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Tuple
from enum import Enum
from pathlib import Path
from collections import defaultdict
import numpy as np
import torch
from concurrent.futures import ThreadPoolExecutor

# Import stale confidence detector for RMDP critical fix
from .safety import StaleConfidenceDetector, StaleConfidenceResult

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of signals the brain can generate."""
    DIRECTIONAL = "directional"      # Long/short signal
    MOMENTUM = "momentum"            # Momentum-based
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"        # Vol-based positioning
    REGIME = "regime"                # Regime change signal
    COMPOSITE = "composite"          # Combined signal


@dataclass
class TradingSignal:
    """Signal sent from ML Brain to Trading Bots."""
    signal_id: str
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    
    # Core signal
    direction: int  # -1, 0, 1
    strength: float  # 0 to 1
    confidence: float  # 0 to 1
    
    # Position guidance
    suggested_size: float  # Fraction of portfolio
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Context
    regime: str = "unknown"
    features_used: List[str] = field(default_factory=list)
    model_version: str = "v1"
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'signal_id': self.signal_id,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'direction': self.direction,
            'strength': self.strength,
            'confidence': self.confidence,
            'suggested_size': self.suggested_size,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'regime': self.regime,
            'features_used': self.features_used,
            'model_version': self.model_version,
        }


@dataclass
class BotPerformance:
    """Performance data sent from Bot back to Brain."""
    bot_id: str
    signal_id: str
    timestamp: datetime
    
    # Execution
    executed: bool
    execution_price: Optional[float] = None
    slippage: float = 0.0
    
    # Outcome (after trade closed)
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_period: float = 0.0  # Hours
    
    # Attribution
    signal_was_correct: bool = False
    exit_reason: str = "unknown"  # stop_loss, take_profit, signal_reversal, timeout
    
    # Context
    market_conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class FeatureImportance:
    """Feature importance learned by the brain."""
    feature_name: str
    importance_score: float
    stability: float  # How stable across time
    regime_dependency: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """Strategy configuration generated by the brain."""
    strategy_id: str
    name: str
    
    # Entry/exit rules
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    
    # Position sizing
    base_position_size: float
    max_position_size: float
    
    # Risk
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_hours: float
    
    # Valid regimes
    valid_regimes: List[str]
    
    # Performance expectations
    expected_win_rate: float
    expected_sharpe: float


class MLBrain:
    """
    Central ML Brain that trains models and generates signals.
    
    Responsibilities:
    1. Train and update neural network models
    2. Perform feature selection and importance analysis
    3. Generate trading strategies
    4. Send signals to trading bots
    5. Learn from bot performance feedback
    """
    
    def __init__(
        self,
        model_dir: str = "models",
        config_path: Optional[str] = None
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Models
        self.trading_brain = None  # Main neural network
        self.feature_selector = None
        self.regime_detector = None
        
        # State
        self.feature_importance: Dict[str, FeatureImportance] = {}
        self.active_strategies: Dict[str, StrategyConfig] = {}
        self.signal_history: List[TradingSignal] = []
        self.performance_history: List[BotPerformance] = []
        
        # Learning state
        self.learning_rate_schedule = {
            'initial': 1e-3,
            'decay': 0.99,
            'min': 1e-5
        }
        self.current_lr = self.learning_rate_schedule['initial']
        
        # Signal generation
        self._signal_counter = 0
        
        # Stale confidence detector (RMDP Critical Fix)
        # Detects when model isn't properly updating confidence between trades
        self.stale_detector = StaleConfidenceDetector(
            epsilon=0.001,  # 0.1% change threshold
            stale_threshold=2,  # Flag after 2 consecutive stale signals
            critical_threshold=5,  # Skip trade after 5 stale signals
            size_decay_rate=0.5  # Halve position size each stale signal
        )
        
        # Callbacks for bots
        self._bot_callbacks: Dict[str, Callable] = {}
        
        logger.info("ML Brain initialized")
    
    def register_bot(self, bot_id: str, callback: Callable[[TradingSignal], None]):
        """Register a trading bot to receive signals."""
        self._bot_callbacks[bot_id] = callback
        logger.info(f"Bot registered: {bot_id}")
    
    def unregister_bot(self, bot_id: str):
        """Unregister a trading bot."""
        if bot_id in self._bot_callbacks:
            del self._bot_callbacks[bot_id]
    
    async def initialize(self, trading_brain=None, multi_timeframe: bool = False):
        """Initialize the brain with models."""
        if trading_brain is not None:
            self.trading_brain = trading_brain
            self.multi_timeframe = hasattr(trading_brain, 'get_all_signals')
        elif multi_timeframe:
            # Create multi-timeframe brain
            from brain.nn import create_multi_timeframe_brain
            self.trading_brain = create_multi_timeframe_brain(
                input_dim=32,
                timeframes=['1m', '5m', '15m', '1h', '4h', '1d', '1w']
            )
            self.multi_timeframe = True
        else:
            # Create default single-timeframe brain
            from brain.nn import create_trading_brain
            self.trading_brain = create_trading_brain(
                input_dim=32,
                seq_len=60,
                action_type="discrete",
                use_meta_learner=True
            )
            self.multi_timeframe = False
        
        logger.info(f"ML Brain models initialized (multi_timeframe={self.multi_timeframe})")
    
    async def train(
        self,
        train_data: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 64
    ) -> Dict[str, float]:
        """
        Train the neural network models.
        
        Args:
            train_data: Training data [samples, seq_len, features]
            val_data: Validation data
            epochs: Number of training epochs
            batch_size: Batch size
            
        Returns:
            Training metrics
        """
        logger.info(f"Starting training: {len(train_data)} samples, {epochs} epochs")
        
        # Convert to tensors
        train_tensor = torch.FloatTensor(train_data)
        
        # Training loop would go here
        # For now, placeholder metrics
        metrics = {
            'train_loss': 0.0,
            'val_loss': 0.0,
            'epochs_completed': epochs,
        }
        
        # Update learning rate
        self.current_lr = max(
            self.current_lr * self.learning_rate_schedule['decay'],
            self.learning_rate_schedule['min']
        )
        
        logger.info(f"Training complete: {metrics}")
        return metrics
    
    def analyze_features(self, data: np.ndarray, feature_names: List[str]) -> Dict[str, FeatureImportance]:
        """
        Analyze feature importance to determine what "matters".
        
        Uses multiple methods:
        - Gradient-based importance
        - Permutation importance
        - SHAP values (if available)
        """
        logger.info(f"Analyzing {len(feature_names)} features")
        
        importance_scores = {}
        
        # Method 1: Variance-based (simple baseline)
        variances = np.var(data, axis=(0, 1))
        
        # Method 2: Correlation with returns (if available)
        # Method 3: Gradient-based (requires model)
        
        for i, name in enumerate(feature_names):
            if i < len(variances):
                score = float(variances[i]) if i < len(variances) else 0.5
            else:
                score = 0.5
            
            importance_scores[name] = FeatureImportance(
                feature_name=name,
                importance_score=min(score * 10, 1.0),  # Normalize
                stability=0.8,  # Placeholder
                regime_dependency={}
            )
        
        self.feature_importance = importance_scores
        
        # Log top features
        top_features = sorted(
            importance_scores.items(),
            key=lambda x: x[1].importance_score,
            reverse=True
        )[:10]
        
        logger.info(f"Top features: {[f[0] for f in top_features]}")
        
        return importance_scores
    
    def generate_strategy(
        self,
        strategy_type: str,
        performance_data: Optional[List[BotPerformance]] = None
    ) -> StrategyConfig:
        """
        Generate or refine a trading strategy based on learned patterns.
        
        Args:
            strategy_type: Type of strategy to generate
            performance_data: Historical performance to learn from
        """
        # Get top features
        top_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1].importance_score,
            reverse=True
        )[:5]
        feature_names = [f[0] for f in top_features]
        
        # Adjust parameters based on performance
        if performance_data:
            avg_win_rate = np.mean([
                1 if p.signal_was_correct else 0 
                for p in performance_data
            ])
            avg_pnl = np.mean([p.pnl_pct for p in performance_data])
        else:
            avg_win_rate = 0.5
            avg_pnl = 0.0
        
        # Generate strategy config
        strategy = StrategyConfig(
            strategy_id=f"strat_{strategy_type}_{datetime.now().strftime('%Y%m%d')}",
            name=f"{strategy_type.title()} Strategy",
            entry_conditions={
                'features': feature_names,
                'threshold': 0.6 if avg_pnl > 0 else 0.7,  # Stricter if losing
            },
            exit_conditions={
                'stop_loss': True,
                'take_profit': True,
                'max_holding': True,
            },
            base_position_size=0.1 if avg_pnl < 0 else 0.15,
            max_position_size=0.25,
            stop_loss_pct=0.02 if avg_win_rate > 0.5 else 0.015,
            take_profit_pct=0.03 if avg_win_rate > 0.5 else 0.025,
            max_holding_hours=24,
            valid_regimes=['trending_up', 'trending_down'] if strategy_type == 'momentum' else ['ranging'],
            expected_win_rate=avg_win_rate,
            expected_sharpe=1.5,
        )
        
        self.active_strategies[strategy.strategy_id] = strategy
        logger.info(f"Generated strategy: {strategy.strategy_id}")
        
        return strategy
    
    async def generate_signal(
        self,
        symbol: str,
        market_data: torch.Tensor,
        current_price: float
    ) -> Optional[TradingSignal]:
        """
        Generate trading signal from current market data.
        
        This is what gets sent to the trading bots.
        Includes stale confidence detection (RMDP critical fix).
        """
        if self.trading_brain is None:
            logger.warning("Trading brain not initialized")
            return None
        
        # Get brain's decision
        brain_output = self.trading_brain.get_trading_signal(
            market_data,
            current_position=0.0
        )
        
        # Convert to TradingSignal
        self._signal_counter += 1
        
        # Map brain output to signal
        if brain_output['signal'] == 'buy':
            direction = 1
        elif brain_output['signal'] == 'sell':
            direction = -1
        else:
            direction = 0
        
        # ============================================================
        # STALE CONFIDENCE CHECK (RMDP Critical Fix)
        # Detects when confidence hasn't changed between signals,
        # indicating the model may not be processing new data properly.
        # ============================================================
        stale_result = self.stale_detector.check(
            symbol=symbol,
            confidence=brain_output['confidence'],
            direction=direction
        )
        
        # Apply stale detection action
        if stale_result.recommended_action == 'skip':
            logger.warning(
                f"SKIPPING trade for {symbol}: {stale_result.reason}. "
                f"Model refresh may be required."
            )
            return None
        
        # Adjust position size based on stale status
        base_position_size = brain_output['position_size']
        adjusted_position_size = base_position_size * stale_result.size_multiplier
        
        if stale_result.is_stale and stale_result.size_multiplier < 1.0:
            logger.info(
                f"Position size adjusted for {symbol}: "
                f"{base_position_size:.2f} -> {adjusted_position_size:.2f} "
                f"(stale confidence: {stale_result.stale_count} signals)"
            )
        
        # Get regime
        regime_probs = brain_output['regime']
        regime = max(regime_probs.items(), key=lambda x: x[1])[0]
        
        signal = TradingSignal(
            signal_id=f"SIG_{self._signal_counter:08d}",
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=SignalType.COMPOSITE,
            direction=direction,
            strength=adjusted_position_size,  # Use adjusted size
            confidence=brain_output['confidence'],
            suggested_size=adjusted_position_size * 0.1,  # Scale down
            entry_price=current_price,
            stop_loss=current_price * (1 - 0.02 * direction) if direction != 0 else None,
            take_profit=current_price * (1 + 0.03 * direction) if direction != 0 else None,
            regime=regime,
            features_used=list(self.feature_importance.keys())[:5],
            model_version="v1.0",
            metadata={
                'stale_confidence': stale_result.is_stale,
                'stale_count': stale_result.stale_count,
                'size_multiplier': stale_result.size_multiplier,
                'original_position_size': base_position_size,
            }
        )
        
        # Store in history
        self.signal_history.append(signal)
        
        # Broadcast to registered bots
        await self._broadcast_signal(signal)
        
        return signal
    
    async def generate_multi_timeframe_signals(
        self,
        symbol: str,
        timeframe_data: Dict[str, torch.Tensor],
        current_price: float
    ) -> Dict[str, TradingSignal]:
        """
        Generate signals for ALL trading horizons from multi-timeframe data.
        
        Args:
            symbol: Trading symbol
            timeframe_data: Dict mapping timeframe name to data tensor
                           e.g., {'1m': tensor, '5m': tensor, '1h': tensor, ...}
            current_price: Current market price
            
        Returns:
            Dict mapping horizon name to TradingSignal
            e.g., {'scalp': signal, 'intraday': signal, 'swing': signal}
        """
        if self.trading_brain is None:
            logger.warning("Trading brain not initialized")
            return {}
        
        if not self.multi_timeframe:
            logger.warning("Brain not configured for multi-timeframe. Use single generate_signal.")
            return {}
        
        # Get all horizon signals from brain
        all_signals = self.trading_brain.get_all_signals(timeframe_data)
        
        # Convert to TradingSignal objects
        result = {}
        
        # Horizon-specific parameters
        horizon_params = {
            'scalp': {'sl_pct': 0.005, 'tp_pct': 0.003, 'signal_type': SignalType.MOMENTUM},
            'intraday': {'sl_pct': 0.015, 'tp_pct': 0.02, 'signal_type': SignalType.COMPOSITE},
            'swing': {'sl_pct': 0.03, 'tp_pct': 0.05, 'signal_type': SignalType.COMPOSITE},
            'position': {'sl_pct': 0.05, 'tp_pct': 0.10, 'signal_type': SignalType.REGIME},
            'macro': {'sl_pct': 0.10, 'tp_pct': 0.20, 'signal_type': SignalType.REGIME},
        }
        
        for horizon, brain_output in all_signals.items():
            if 'error' in brain_output:
                continue
            
            self._signal_counter += 1
            params = horizon_params.get(horizon, horizon_params['intraday'])
            
            # Map action to direction
            action = brain_output['action']
            if action == 'buy':
                direction = 1
            elif action == 'sell':
                direction = -1
            else:
                direction = 0
            
            signal = TradingSignal(
                signal_id=f"SIG_{self._signal_counter:08d}_{horizon.upper()}",
                timestamp=datetime.now(),
                symbol=symbol,
                signal_type=params['signal_type'],
                direction=direction,
                strength=brain_output['suggested_size'],
                confidence=brain_output['confidence'],
                suggested_size=brain_output['suggested_size'] * 0.1,
                entry_price=current_price,
                stop_loss=current_price * (1 - params['sl_pct'] * direction) if direction != 0 else None,
                take_profit=current_price * (1 + params['tp_pct'] * direction) if direction != 0 else None,
                regime=brain_output['regime'],
                features_used=list(self.feature_importance.keys())[:5],
                model_version="v1.0-mtf",
                metadata={'horizon': horizon, 'regime_probs': brain_output.get('regime_probs', {})}
            )
            
            self.signal_history.append(signal)
            result[horizon] = signal
        
        # Broadcast all signals
        for signal in result.values():
            await self._broadcast_signal(signal)
        
        logger.info(f"Generated {len(result)} multi-timeframe signals for {symbol}")
        
        return result
    
    async def _broadcast_signal(self, signal: TradingSignal):
        """Send signal to all registered bots."""
        for bot_id, callback in self._bot_callbacks.items():
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"Failed to send signal to {bot_id}: {e}")
    
    def receive_performance(self, performance: BotPerformance):
        """
        Receive performance feedback from a trading bot.
        
        This closes the feedback loop and allows the brain to learn.
        """
        self.performance_history.append(performance)
        
        # Find corresponding signal
        signal = next(
            (s for s in self.signal_history if s.signal_id == performance.signal_id),
            None
        )
        
        if signal is None:
            logger.warning(f"Signal not found for performance: {performance.signal_id}")
            return
        
        # Learn from outcome
        self._learn_from_outcome(signal, performance)
        
        logger.info(
            f"Received performance: {performance.bot_id} | "
            f"Signal {performance.signal_id} | "
            f"PnL: {performance.pnl_pct:.2%} | "
            f"Correct: {performance.signal_was_correct}"
        )
    
    def _learn_from_outcome(self, signal: TradingSignal, performance: BotPerformance):
        """
        Update models and strategies based on trade outcome.
        
        This is where the brain refines itself.
        """
        # Update trading brain's meta-learner
        if self.trading_brain is not None:
            metrics = {
                'returns': performance.pnl_pct,
                'win_rate': 1.0 if performance.signal_was_correct else 0.0,
                'sharpe': performance.pnl_pct / 0.02,  # Rough estimate
            }
            self.trading_brain.update_performance(metrics)
        
        # Adjust feature importance based on outcome
        for feature in signal.features_used:
            if feature in self.feature_importance:
                fi = self.feature_importance[feature]
                
                # If signal was correct, increase importance slightly
                # If wrong, decrease it
                adjustment = 0.01 if performance.signal_was_correct else -0.01
                fi.importance_score = max(0, min(1, fi.importance_score + adjustment))
                
                # Update regime dependency
                if signal.regime not in fi.regime_dependency:
                    fi.regime_dependency[signal.regime] = 0.5
                
                regime_adj = 0.05 if performance.signal_was_correct else -0.05
                fi.regime_dependency[signal.regime] = max(
                    0, min(1, fi.regime_dependency[signal.regime] + regime_adj)
                )
        
        # Log learning
        if len(self.performance_history) % 100 == 0:
            self._log_learning_summary()
    
    def _log_learning_summary(self):
        """Log summary of learning progress."""
        recent = self.performance_history[-100:]
        
        if not recent:
            return
        
        win_rate = np.mean([1 if p.signal_was_correct else 0 for p in recent])
        avg_pnl = np.mean([p.pnl_pct for p in recent])
        
        logger.info(
            f"Learning summary (last 100): "
            f"Win rate: {win_rate:.2%} | "
            f"Avg PnL: {avg_pnl:.2%}"
        )
    
    def get_brain_state(self) -> Dict[str, Any]:
        """Get current state of the brain for monitoring."""
        return {
            'signals_generated': len(self.signal_history),
            'performance_received': len(self.performance_history),
            'active_strategies': len(self.active_strategies),
            'top_features': sorted(
                [(k, v.importance_score) for k, v in self.feature_importance.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10],
            'registered_bots': list(self._bot_callbacks.keys()),
            'learning_rate': self.current_lr,
        }
    
    async def save_state(self, path: Optional[str] = None):
        """Save brain state and models."""
        save_path = Path(path) if path else self.model_dir / "brain_state.pt"
        
        state = {
            'feature_importance': {
                k: {
                    'score': v.importance_score,
                    'stability': v.stability,
                    'regime_dep': v.regime_dependency
                }
                for k, v in self.feature_importance.items()
            },
            'strategies': {k: v.__dict__ for k, v in self.active_strategies.items()},
            'learning_rate': self.current_lr,
            'signal_count': self._signal_counter,
        }
        
        if self.trading_brain is not None:
            state['trading_brain_state'] = self.trading_brain.state_dict()
        
        torch.save(state, save_path)
        logger.info(f"Brain state saved to {save_path}")
    
    async def load_state(self, path: Optional[str] = None):
        """Load brain state and models."""
        load_path = Path(path) if path else self.model_dir / "brain_state.pt"
        
        if not load_path.exists():
            logger.warning(f"No state file found at {load_path}")
            return
        
        state = torch.load(load_path)
        
        # Restore feature importance
        for k, v in state.get('feature_importance', {}).items():
            self.feature_importance[k] = FeatureImportance(
                feature_name=k,
                importance_score=v['score'],
                stability=v['stability'],
                regime_dependency=v['regime_dep']
            )
        
        self.current_lr = state.get('learning_rate', self.current_lr)
        self._signal_counter = state.get('signal_count', 0)
        
        if self.trading_brain is not None and 'trading_brain_state' in state:
            self.trading_brain.load_state_dict(state['trading_brain_state'])
        
        logger.info(f"Brain state loaded from {load_path}")


class BrainBotInterface:
    """
    Interface for trading bots to communicate with the ML Brain.
    
    Each bot uses this to:
    1. Receive signals from the brain
    2. Report execution and performance back
    """
    
    def __init__(self, bot_id: str, brain: MLBrain):
        self.bot_id = bot_id
        self.brain = brain
        
        # Signal queue
        self.pending_signals: List[TradingSignal] = []
        
        # Register with brain
        self.brain.register_bot(bot_id, self._on_signal)
    
    def _on_signal(self, signal: TradingSignal):
        """Callback when brain sends a signal."""
        self.pending_signals.append(signal)
    
    def get_pending_signals(self) -> List[TradingSignal]:
        """Get and clear pending signals."""
        signals = self.pending_signals.copy()
        self.pending_signals.clear()
        return signals
    
    def report_execution(
        self,
        signal_id: str,
        executed: bool,
        execution_price: Optional[float] = None,
        slippage: float = 0.0
    ):
        """Report trade execution to the brain."""
        perf = BotPerformance(
            bot_id=self.bot_id,
            signal_id=signal_id,
            timestamp=datetime.now(),
            executed=executed,
            execution_price=execution_price,
            slippage=slippage,
        )
        self.brain.receive_performance(perf)
    
    def report_outcome(
        self,
        signal_id: str,
        pnl: float,
        pnl_pct: float,
        holding_period: float,
        signal_was_correct: bool,
        exit_reason: str
    ):
        """Report trade outcome to the brain."""
        perf = BotPerformance(
            bot_id=self.bot_id,
            signal_id=signal_id,
            timestamp=datetime.now(),
            executed=True,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_period=holding_period,
            signal_was_correct=signal_was_correct,
            exit_reason=exit_reason,
        )
        self.brain.receive_performance(perf)
    
    def disconnect(self):
        """Disconnect from the brain."""
        self.brain.unregister_bot(self.bot_id)
