"""
ML Brain Pipeline
=================
Complete pipeline integrating ML Brain, Trading Bots, and Feedback Loop.

This is the main entry point for the brain-bot-feedback system.

Usage:
    from brain.pipeline import TradingPipeline
    
    pipeline = TradingPipeline()
    await pipeline.initialize()
    await pipeline.run()
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import numpy as np
import torch

from .orchestrator import MLBrain, BrainBotInterface, TradingSignal, BotPerformance
from .nn import create_trading_brain

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the trading pipeline."""
    # Bots to run
    active_bots: List[str] = None  # None = all
    
    # Data
    symbols: List[str] = None
    data_lookback: int = 60  # Bars
    
    # Timing
    signal_interval: float = 60.0  # Seconds between signal generation
    monitoring_interval: float = 5.0  # Seconds between trade monitoring
    
    # Training
    retrain_interval: int = 86400  # Seconds (24 hours)
    min_samples_for_retrain: int = 100
    
    # Persistence
    model_dir: str = "models"
    save_interval: int = 3600  # Save state every hour
    
    def __post_init__(self):
        if self.active_bots is None:
            self.active_bots = ['tpt', 'momentum', 'swing']
        if self.symbols is None:
            self.symbols = ['BTC/USD', 'ETH/USD', 'SPY']


class DataFeed:
    """
    Data feed for market data.
    Replace with actual data source in production.
    """
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.prices: Dict[str, float] = {s: 100.0 for s in symbols}
        self.data_cache: Dict[str, np.ndarray] = {}
    
    async def get_latest_data(self, symbol: str, lookback: int = 60) -> torch.Tensor:
        """Get latest market data as tensor."""
        # Simulate data - replace with actual data feed
        if symbol not in self.data_cache:
            self.data_cache[symbol] = np.random.randn(1000, 32).astype(np.float32)
        
        data = self.data_cache[symbol][-lookback:]
        return torch.FloatTensor(data).unsqueeze(0)  # [1, seq, features]
    
    async def get_price(self, symbol: str) -> float:
        """Get current price."""
        # Simulate price movement
        self.prices[symbol] *= 1 + np.random.randn() * 0.001
        return self.prices[symbol]
    
    def update_data(self, symbol: str, new_data: np.ndarray):
        """Add new data to cache."""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = new_data
        else:
            self.data_cache[symbol] = np.vstack([
                self.data_cache[symbol][-900:],
                new_data
            ])


class SimpleBroker:
    """Simple broker for paper trading."""
    
    def __init__(self, data_feed: DataFeed, initial_balance: float = 100000):
        self.data_feed = data_feed
        self.balance = initial_balance
        self.positions: Dict[str, float] = {}
    
    async def get_price(self, symbol: str) -> float:
        return await self.data_feed.get_price(symbol)
    
    async def get_portfolio_value(self) -> float:
        positions_value = sum(
            qty * await self.get_price(sym)
            for sym, qty in self.positions.items()
        )
        return self.balance + positions_value
    
    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        price = await self.get_price(symbol)
        
        # Apply slippage
        slippage = 0.001
        if side == 'buy':
            fill_price = price * (1 + slippage)
            self.balance -= fill_price * quantity
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            fill_price = price * (1 - slippage)
            self.balance += fill_price * quantity
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
        
        return {
            'filled_price': fill_price,
            'filled_quantity': quantity,
        }


class TradingPipeline:
    """
    Complete trading pipeline integrating ML Brain, Bots, and Feedback.
    
    Flow:
        1. ML Brain trains on data and learns feature importance
        2. Brain generates signals and sends to bots
        3. Bots execute trades based on their strategies
        4. Bot performance feeds back to brain
        5. Brain refines models based on feedback
        6. Repeat
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        
        # Components
        self.brain: Optional[MLBrain] = None
        self.data_feed: Optional[DataFeed] = None
        self.broker: Optional[SimpleBroker] = None
        self.bots: Dict[str, Any] = {}
        self.bot_interfaces: Dict[str, BrainBotInterface] = {}
        
        # State
        self.running = False
        self.last_retrain: Optional[datetime] = None
        self.last_save: Optional[datetime] = None
        
        logger.info("Trading Pipeline created")
    
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Trading Pipeline...")
        
        # 1. Create data feed
        self.data_feed = DataFeed(self.config.symbols)
        
        # 2. Create broker
        self.broker = SimpleBroker(self.data_feed)
        
        # 3. Create ML Brain
        self.brain = MLBrain(model_dir=self.config.model_dir)
        
        # Create trading brain model
        trading_brain = create_trading_brain(
            input_dim=32,
            seq_len=self.config.data_lookback,
            action_type="discrete",
            use_meta_learner=True
        )
        
        await self.brain.initialize(trading_brain)
        
        # 4. Load previous state if exists
        try:
            await self.brain.load_state()
        except Exception as e:
            logger.info(f"No previous state to load: {e}")
        
        # 5. Analyze features with initial data
        sample_data = np.random.randn(1000, 60, 32).astype(np.float32)
        feature_names = [f"feature_{i}" for i in range(32)]
        self.brain.analyze_features(sample_data, feature_names)
        
        # 6. Create bots
        from bots import BotFactory
        
        for bot_type in self.config.active_bots:
            # Create interface
            interface = BrainBotInterface(f"{bot_type}_bot", self.brain)
            self.bot_interfaces[bot_type] = interface
            
            # Create bot
            bot = BotFactory.create(bot_type, interface, self.broker)
            self.bots[bot_type] = bot
        
        logger.info(f"Pipeline initialized with {len(self.bots)} bots")
    
    async def run(self):
        """Run the trading pipeline."""
        if not self.brain:
            await self.initialize()
        
        self.running = True
        self.last_retrain = datetime.now()
        self.last_save = datetime.now()
        
        logger.info("Starting Trading Pipeline...")
        
        # Start all bots
        bot_tasks = []
        for bot in self.bots.values():
            task = asyncio.create_task(bot.start())
            bot_tasks.append(task)
        
        # Main loop
        try:
            while self.running:
                await self._tick()
                await asyncio.sleep(self.config.signal_interval)
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted")
        finally:
            await self.stop()
    
    async def _tick(self):
        """Main tick - generate signals and check for retraining."""
        now = datetime.now()
        
        # 1. Generate signals for each symbol
        for symbol in self.config.symbols:
            try:
                # Get latest data
                data = await self.data_feed.get_latest_data(
                    symbol, 
                    self.config.data_lookback
                )
                price = await self.data_feed.get_price(symbol)
                
                # Generate signal
                signal = await self.brain.generate_signal(symbol, data, price)
                
                if signal and signal.direction != 0:
                    logger.info(
                        f"Signal generated: {symbol} | "
                        f"{'BUY' if signal.direction > 0 else 'SELL'} | "
                        f"Confidence: {signal.confidence:.2f}"
                    )
                    
            except Exception as e:
                logger.error(f"Error generating signal for {symbol}: {e}")
        
        # 2. Check if retraining needed
        if (now - self.last_retrain).total_seconds() > self.config.retrain_interval:
            await self._retrain()
            self.last_retrain = now
        
        # 3. Save state periodically
        if (now - self.last_save).total_seconds() > self.config.save_interval:
            await self.brain.save_state()
            self.last_save = now
        
        # 4. Log status
        await self._log_status()
    
    async def _retrain(self):
        """Retrain the brain with recent data."""
        logger.info("Starting brain retraining...")
        
        # Collect recent data
        all_data = []
        for symbol in self.config.symbols:
            data = await self.data_feed.get_latest_data(symbol, 500)
            all_data.append(data.numpy())
        
        if all_data:
            train_data = np.concatenate(all_data, axis=0)
            
            # Only retrain if we have enough samples
            if len(train_data) >= self.config.min_samples_for_retrain:
                metrics = await self.brain.train(train_data, epochs=10)
                logger.info(f"Retraining complete: {metrics}")
            else:
                logger.info("Not enough samples for retraining")
    
    async def _log_status(self):
        """Log pipeline status."""
        brain_state = self.brain.get_brain_state()
        
        bot_status = {}
        for name, bot in self.bots.items():
            bot_status[name] = bot.get_status()
        
        total_trades = sum(s['closed_trades'] for s in bot_status.values())
        total_pnl = sum(s['total_pnl_pct'] for s in bot_status.values())
        
        logger.info(
            f"Pipeline Status: "
            f"Signals: {brain_state['signals_generated']} | "
            f"Trades: {total_trades} | "
            f"Total PnL: {total_pnl:.2%}"
        )
    
    async def stop(self):
        """Stop the pipeline."""
        self.running = False
        
        # Stop all bots
        for bot in self.bots.values():
            await bot.stop()
        
        # Save final state
        await self.brain.save_state()
        
        logger.info("Trading Pipeline stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status."""
        return {
            'running': self.running,
            'brain': self.brain.get_brain_state() if self.brain else {},
            'bots': {name: bot.get_status() for name, bot in self.bots.items()},
            'last_retrain': self.last_retrain.isoformat() if self.last_retrain else None,
        }


async def run_demo():
    """Run a demo of the trading pipeline."""
    logging.basicConfig(level=logging.INFO)
    
    config = PipelineConfig(
        active_bots=['tpt', 'momentum'],
        symbols=['BTC/USD', 'ETH/USD'],
        signal_interval=5.0,  # Fast for demo
    )
    
    pipeline = TradingPipeline(config)
    await pipeline.initialize()
    
    # Run for a bit
    print("\nRunning pipeline demo for 30 seconds...")
    print("=" * 60)
    
    pipeline.running = True
    
    for _ in range(6):  # 6 ticks * 5 seconds = 30 seconds
        await pipeline._tick()
        await asyncio.sleep(5)
    
    print("\n" + "=" * 60)
    print("Final Status:")
    print(pipeline.get_status())
    
    await pipeline.stop()


if __name__ == "__main__":
    asyncio.run(run_demo())
