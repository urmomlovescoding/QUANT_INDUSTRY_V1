"""
FUTURES BRAIN V2 INTEGRATION
==============================
Connects FuturesBrainV2 (TFT + WaveNet + Attention) to TPT Production Bot.

This module provides:
1. Singleton access to the brain
2. Feature extraction from OHLCV DataFrames
3. Prediction interface for the bot
4. Trade result recording for feedback learning

Author: QuantBrain Integration
Version: 1.0.0
"""

import sys
import logging
import threading
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Root path - ensure it's in sys.path for imports
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("BRAIN_V2_INTEGRATION")

# Import flags
HAS_BRAIN_V2 = False
HAS_TORCH = False
HAS_FEATURE_EXTRACTOR = False

# Try importing FuturesBrainV2
try:
    from brain.futures_brain_v2 import (
        FuturesBrainV2, FuturesBrainV2Config, create_futures_brain_v2, DEVICE
    )
    HAS_BRAIN_V2 = True
    logger.info("FuturesBrainV2 module loaded")
except ImportError as e:
    logger.warning(f"FuturesBrainV2 not available: {e}")

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Try importing feature extractor
try:
    from brain.futures_feature_extractor_v2 import (
        FuturesFeatureExtractorV2, extract_features_v2
    )
    HAS_FEATURE_EXTRACTOR = True
    logger.info("FuturesFeatureExtractorV2 loaded")
except ImportError:
    try:
        from brain.futures_feature_extractor import (
            FuturesFeatureExtractor, extract_futures_features
        )
        HAS_FEATURE_EXTRACTOR = True
        logger.info("FuturesFeatureExtractor (v1) loaded as fallback")
    except ImportError as e:
        logger.warning(f"Feature extractor not available: {e}")


class FuturesBrainV2Integration:
    """
    Integration layer between TPT Bot and FuturesBrainV2.
    
    Provides a simple interface for the bot to:
    1. Get ML predictions from the advanced deep learning models
    2. Record trade results for feedback learning
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        
        # Brain instance
        self.brain: Optional[FuturesBrainV2] = None
        self.config: Optional[FuturesBrainV2Config] = None
        
        # Feature extractor
        self.feature_extractor = None
        
        # State tracking
        self.is_ready = False
        self.last_prediction: Dict = {}
        self.prediction_count = 0
        
        # Trade history for feedback
        self.trade_history: list = []
        self.session_pnl = 0.0
        self.session_trades = 0
        
        logger.info("FuturesBrainV2Integration initialized (singleton)")
    
    def initialize(self, load_weights: bool = True) -> bool:
        """
        Initialize the FuturesBrainV2 model.
        
        Args:
            load_weights: Whether to load saved weights
        
        Returns:
            True if successful
        """
        if not HAS_BRAIN_V2 or not HAS_TORCH:
            logger.error("FuturesBrainV2 or PyTorch not available")
            return False
        
        try:
            self.config = FuturesBrainV2Config()
            
            if load_weights:
                # Factory function handles loading
                self.brain = create_futures_brain_v2(self.config)
            else:
                self.brain = FuturesBrainV2(self.config)
                self.brain = self.brain.to(DEVICE)
            
            # Set to eval mode
            self.brain.eval()
            
            # Initialize feature extractor
            self._init_feature_extractor()
            
            # Load trade history from previous sessions
            self._load_trade_history()
            
            self.is_ready = True
            logger.info(f"FuturesBrainV2 initialized on {DEVICE}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize FuturesBrainV2: {e}")
            return False
    
    def _init_feature_extractor(self):
        """Initialize the feature extractor."""
        if HAS_FEATURE_EXTRACTOR:
            try:
                # Try V2 first
                self.feature_extractor = FuturesFeatureExtractorV2()
                logger.info("Using FuturesFeatureExtractorV2")
            except Exception as e:
                logger.debug(f"V2 feature extractor unavailable ({e}), trying V1")
                try:
                    self.feature_extractor = FuturesFeatureExtractor()
                    logger.info("Using FuturesFeatureExtractor (v1)")
                except Exception as e:
                    logger.warning(f"Feature extractor init failed: {e}")
    
    def get_prediction(self, symbol: str, df: pd.DataFrame, 
                      account_state: Dict = None) -> Tuple[str, float, int, Dict]:
        """
        Get ML prediction from FuturesBrainV2.
        
        Args:
            symbol: Trading symbol (MNQ, MES, etc.)
            df: pandas DataFrame with OHLCV data
            account_state: Current account state (optional)
        
        Returns:
            (signal, confidence, contracts, details)
            - signal: 'BUY', 'SELL', or 'HOLD'
            - confidence: 0.0 to 1.0
            - contracts: suggested position size (0-6)
            - details: dict with model internals
        """
        if not self.is_ready or self.brain is None:
            return 'HOLD', 0.5, 0, {'error': 'Brain not initialized'}
        
        try:
            # Extract features from DataFrame
            features = self._extract_features(df)
            
            if features is None or len(features) < 60:
                return 'HOLD', 0.5, 0, {'error': 'Insufficient features'}
            
            # Get prediction
            prediction = self.brain.predict(features)
            
            # Map signal
            signal = prediction['signal_name']  # 'BUY', 'HOLD', or 'SELL'
            confidence = prediction['confidence']
            
            # Calculate contracts based on position fraction and confidence
            position_frac = prediction['position_fraction']
            max_contracts = 6  # TPT limit
            
            # Scale contracts: high confidence + high position = more contracts
            if signal == 'HOLD' or confidence < 0.55:
                contracts = 0
            else:
                # Base contracts on confidence and position fraction
                raw_contracts = position_frac * max_contracts * (confidence / 0.7)
                contracts = int(min(max_contracts, max(1, raw_contracts)))
            
            # Reduce contracts if uncertainty is high
            if prediction['uncertainty'] > 0.3:
                contracts = max(1, contracts // 2)
            
            details = {
                'signal_probs': prediction['signal_probs'],
                'position_fraction': position_frac,
                'uncertainty': prediction['uncertainty'],
                'regime': prediction['regime_name'],
                'regime_probs': prediction['regime_probs'],
                'model_weights': prediction['model_weights'],
                'raw_signal': prediction['signal'],
            }
            
            # Store for feedback
            self.last_prediction = {
                'symbol': symbol,
                'signal': signal,
                'confidence': confidence,
                'contracts': contracts,
                'timestamp': datetime.now().isoformat(),
                **details
            }
            self.prediction_count += 1
            
            logger.debug(f"Prediction: {signal} @ {confidence:.2%}, {contracts} contracts, "
                        f"regime={prediction['regime_name']}")
            
            return signal, confidence, contracts, details
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 'HOLD', 0.5, 0, {'error': str(e)}
    
    def _extract_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Extract features from OHLCV DataFrame.
        
        Args:
            df: DataFrame with columns: open, high, low, close, volume
        
        Returns:
            numpy array of shape (seq_len, num_features)
        """
        try:
            # Normalize column names
            df = df.copy()
            df.columns = [c.lower() for c in df.columns]
            
            # Ensure required columns
            required = ['open', 'high', 'low', 'close', 'volume']
            for col in required:
                if col not in df.columns:
                    logger.warning(f"Missing column: {col}")
                    return None
            
            # Use feature extractor if available
            if self.feature_extractor is not None:
                try:
                    features = self.feature_extractor.extract(df)
                    return features
                except Exception as e:
                    logger.debug(f"Feature extractor failed: {e}, using fallback")
            
            # Fallback: basic feature extraction
            return self._basic_feature_extraction(df)
            
        except Exception as e:
            logger.error(f"Feature extraction error: {e}")
            return None
    
    def _basic_feature_extraction(self, df: pd.DataFrame) -> np.ndarray:
        """
        Basic feature extraction fallback.
        Creates 96-dimensional feature vector per timestep.
        """
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_ = df['open'].values
        volume = df['volume'].values
        
        n = len(close)
        num_features = 96  # Match config.input_features
        features = np.zeros((n, num_features))
        
        # Price-based features (0-19)
        features[:, 0] = (close - close[0]) / (close[0] + 1e-8)  # Normalized price
        features[:, 1] = (high - low) / (close + 1e-8)  # Range
        features[:, 2] = (close - open_) / (close + 1e-8)  # Body
        features[:, 3] = (close - low) / (high - low + 1e-8)  # Position in range
        
        # Returns at different horizons
        for i, period in enumerate([1, 2, 3, 5, 8, 13, 21]):
            if i + 4 < 20:
                features[period:, 4 + i] = (close[period:] - close[:-period]) / (close[:-period] + 1e-8)
        
        # Volume features (20-29)
        vol_ma = pd.Series(volume).rolling(20, min_periods=1).mean().values
        features[:, 20] = volume / (vol_ma + 1e-8)
        features[:, 21] = np.log1p(volume)
        
        # Moving averages (30-49)
        for i, period in enumerate([5, 10, 20, 50]):
            if i * 2 + 30 < 50:
                ma = pd.Series(close).rolling(period, min_periods=1).mean().values
                features[:, 30 + i * 2] = (close - ma) / (ma + 1e-8)
                features[:, 31 + i * 2] = ma / (close + 1e-8)
        
        # RSI (50-54)
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        for i, period in enumerate([7, 14, 21]):
            if 50 + i < 55:
                avg_gain = pd.Series(gain).rolling(period, min_periods=1).mean().values
                avg_loss = pd.Series(loss).rolling(period, min_periods=1).mean().values
                rs = avg_gain / (avg_loss + 1e-8)
                features[:, 50 + i] = 1 - (1 / (1 + rs))  # Normalized RSI
        
        # MACD (55-59)
        ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
        ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
        macd = ema12 - ema26
        signal = pd.Series(macd).ewm(span=9, adjust=False).mean().values
        
        features[:, 55] = macd / (close + 1e-8)
        features[:, 56] = signal / (close + 1e-8)
        features[:, 57] = (macd - signal) / (close + 1e-8)
        
        # Bollinger Bands (60-64)
        bb_ma = pd.Series(close).rolling(20, min_periods=1).mean().values
        bb_std = pd.Series(close).rolling(20, min_periods=1).std().values
        
        features[:, 60] = (close - bb_ma) / (bb_std + 1e-8)
        features[:, 61] = bb_std / (close + 1e-8)
        
        # ATR (65-69)
        tr = np.maximum(high - low, 
                       np.maximum(np.abs(high - np.roll(close, 1)),
                                 np.abs(low - np.roll(close, 1))))
        atr = pd.Series(tr).rolling(14, min_periods=1).mean().values
        features[:, 65] = atr / (close + 1e-8)
        
        # Stochastic (70-74)
        for i, period in enumerate([5, 14, 21]):
            if 70 + i < 75:
                lowest = pd.Series(low).rolling(period, min_periods=1).min().values
                highest = pd.Series(high).rolling(period, min_periods=1).max().values
                features[:, 70 + i] = (close - lowest) / (highest - lowest + 1e-8)
        
        # Time features (placeholder, would need actual timestamps) (75-79)
        # In production, these would be: hour_sin, hour_cos, day_of_week, etc.
        
        # Fill remaining with price momentum features (80-95)
        for i in range(16):
            period = 2 + i * 3
            if 80 + i < 96 and period < n:
                momentum = close[period:] - close[:-period]
                features[period:, 80 + i] = momentum / (np.abs(momentum).mean() + 1e-8)
        
        # Handle NaN/Inf
        features = np.nan_to_num(features, nan=0.0, posinf=1.0, neginf=-1.0)
        
        return features
    
    def record_trade_result(self, trade_data: Dict[str, Any]):
        """
        Record a trade result for feedback learning.
        
        Args:
            trade_data: Dict with trade details
        """
        try:
            trade_record = {
                'trade_id': trade_data.get('trade_id', f"trade_{datetime.now().strftime('%H%M%S')}"),
                'symbol': trade_data.get('symbol', 'MNQ'),
                'direction': trade_data.get('direction', 'LONG'),
                'contracts': trade_data.get('contracts', 1),
                'entry_price': trade_data.get('entry_price', 0),
                'exit_price': trade_data.get('exit_price', 0),
                'pnl': trade_data.get('pnl', 0),
                'exit_reason': trade_data.get('exit_reason', 'MANUAL'),
                'prediction': self.last_prediction.copy() if self.last_prediction else {},
                'timestamp': datetime.now().isoformat()
            }
            
            self.trade_history.append(trade_record)
            self.session_trades += 1
            self.session_pnl += trade_record['pnl']
            
            # Update model performance tracking
            if self.brain is not None and 'prediction' in trade_record:
                pred = trade_record['prediction']
                was_correct = (
                    (pred.get('signal') == 'BUY' and trade_record['pnl'] > 0) or
                    (pred.get('signal') == 'SELL' and trade_record['pnl'] > 0)
                )
                # Update model accuracy tracking (for ensemble weight adjustment)
                accuracy = 1.0 if was_correct else 0.0
                self.brain.update_model_performance(0, accuracy)  # Primary model
                
            # Persist trade history every 5 trades
            if len(self.trade_history) % 5 == 0:
                self._save_trade_history()
                
            # Trigger online learning every 10 trades
            if len(self.trade_history) >= 10 and len(self.trade_history) % 10 == 0:
                self._trigger_online_learning()
                
            logger.info(f"Trade recorded: {trade_record['symbol']} ${trade_record['pnl']:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    def _save_trade_history(self):
        """Save trade history to disk for persistence."""
        try:
            import json
            history_file = ROOT / "analytics" / "brain_v2_trade_history.json"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(history_file, 'w') as f:
                json.dump({
                    'trades': self.trade_history[-500:],  # Keep last 500
                    'session_pnl': self.session_pnl,
                    'session_trades': self.session_trades,
                    'updated': datetime.now().isoformat()
                }, f, indent=2)
            logger.debug(f"Trade history saved ({len(self.trade_history)} trades)")
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")
    
    def _load_trade_history(self):
        """Load trade history from disk."""
        try:
            import json
            history_file = ROOT / "analytics" / "brain_v2_trade_history.json"
            
            if history_file.exists():
                with open(history_file) as f:
                    data = json.load(f)
                self.trade_history = data.get('trades', [])
                logger.info(f"Loaded {len(self.trade_history)} trades from history")
        except Exception as e:
            logger.debug(f"Could not load trade history: {e}")
    
    def _trigger_online_learning(self):
        """Trigger online learning on recent trades."""
        if not self.is_ready or len(self.trade_history) < 10:
            return
            
        try:
            # Import trainer
            from brain.futures_brain_v2_training import (
                FuturesBrainV2Trainer, TrainingExample
            )
            
            # Convert recent trades to training examples
            recent_trades = self.trade_history[-20:]
            examples = []
            
            for trade in recent_trades:
                pred = trade.get('prediction', {})
                if not pred or 'signal_probs' not in pred:
                    continue
                    
                # Create training example from trade
                # Note: In production, would need full feature data stored with prediction
                signal_label = {'BUY': 0, 'HOLD': 1, 'SELL': 2}.get(pred.get('signal', 'HOLD'), 1)
                is_win = trade['pnl'] > 0
                
                # Simple online update via model performance tracking
                if is_win:
                    self.brain.update_model_performance(0, 1.0, decay=0.98)
                else:
                    self.brain.update_model_performance(0, 0.0, decay=0.98)
            
            # Save updated weights periodically
            if self.session_trades % 20 == 0:
                self.save_state()
                logger.info("Auto-saved brain weights after 20 trades")
                
        except ImportError:
            logger.debug("Training module not available for online learning")
        except Exception as e:
            logger.error(f"Online learning failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration status."""
        return {
            'is_ready': self.is_ready,
            'has_brain_v2': HAS_BRAIN_V2,
            'has_torch': HAS_TORCH,
            'has_feature_extractor': HAS_FEATURE_EXTRACTOR,
            'device': str(DEVICE) if HAS_TORCH else 'N/A',
            'prediction_count': self.prediction_count,
            'session_trades': self.session_trades,
            'session_pnl': self.session_pnl,
            'last_prediction': self.last_prediction.get('signal', 'N/A'),
        }
    
    def save_state(self):
        """Save model weights."""
        if self.brain is not None:
            self.brain.save()
            logger.info("FuturesBrainV2 weights saved")


# =============================================================================
# SINGLETON ACCESSORS
# =============================================================================

_integration_instance: Optional[FuturesBrainV2Integration] = None

def get_brain_v2_integration() -> FuturesBrainV2Integration:
    """Get the FuturesBrainV2 integration singleton."""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = FuturesBrainV2Integration()
    return _integration_instance


def initialize_brain_v2(load_weights: bool = True) -> bool:
    """Initialize the FuturesBrainV2 integration."""
    integration = get_brain_v2_integration()
    return integration.initialize(load_weights)


def get_brain_v2_prediction(symbol: str, df: pd.DataFrame, 
                           account_state: Dict = None) -> Tuple[str, float, int, Dict]:
    """Get prediction from FuturesBrainV2."""
    integration = get_brain_v2_integration()
    return integration.get_prediction(symbol, df, account_state)


def record_brain_v2_trade(trade_data: Dict):
    """Record a trade result in FuturesBrainV2."""
    integration = get_brain_v2_integration()
    integration.record_trade_result(trade_data)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
    
    print("Testing FuturesBrainV2 Integration...")
    print(f"  HAS_BRAIN_V2: {HAS_BRAIN_V2}")
    print(f"  HAS_TORCH: {HAS_TORCH}")
    print(f"  HAS_FEATURE_EXTRACTOR: {HAS_FEATURE_EXTRACTOR}")
    
    integration = get_brain_v2_integration()
    
    if integration.initialize():
        print("\n[OK] Brain initialized")
        print(f"  Status: {integration.get_status()}")
        
        # Create test DataFrame
        np.random.seed(42)
        n = 100
        base_price = 20000
        prices = base_price + np.cumsum(np.random.randn(n) * 10)
        
        df = pd.DataFrame({
            'open': prices + np.random.randn(n) * 2,
            'high': prices + np.abs(np.random.randn(n) * 5),
            'low': prices - np.abs(np.random.randn(n) * 5),
            'close': prices,
            'volume': np.random.randint(1000, 10000, n)
        })
        
        # Test prediction
        signal, conf, contracts, details = integration.get_prediction("MNQ", df)
        print(f"\n[OK] Prediction: {signal} @ {conf:.2%} confidence, {contracts} contracts")
        print(f"  Regime: {details.get('regime', 'N/A')}")
        print(f"  Uncertainty: {details.get('uncertainty', 0):.4f}")
        print(f"  Model weights: {details.get('model_weights', {})}")
        
        # Test trade recording
        integration.record_trade_result({
            'symbol': 'MNQ',
            'direction': 'LONG',
            'contracts': 2,
            'entry_price': 20000,
            'exit_price': 20050,
            'pnl': 100,
            'exit_reason': 'TP_HIT'
        })
        print("\n[OK] Trade recorded")
        print(f"  Status: {integration.get_status()}")
    else:
        print("[FAIL] Failed to initialize brain")
        print(f"  Status: {integration.get_status()}")
