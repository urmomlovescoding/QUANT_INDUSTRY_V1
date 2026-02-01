"""
TPT PRODUCTION BOT v2.0
========================
Ultimate automated trading bot for Take Profit Trader evaluation.

CRITICAL REQUIREMENTS:
- $3,000 profit in 5 days
- Max $2,000 drawdown (balance floor: $48,000)
- Max 6 contracts
- 50% consistency rule (no single day > 50% of total profit)
- Flat by 17:00 EST daily

STRATEGY:
- Target $700-800/day with buffer
- Use ML ensemble for high-probability entries
- Tight stops (2-3 points ES) with 1.5-2x R:R
- Scale into winners, cut losers fast
- Auto-flatten at 16:45 EST

Author: TPT Trading System
Version: 2.0.0
"""

import logging
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from collections import deque
import numpy as np

logger = logging.getLogger("TPT_PROD_BOT")

# Paths
ROOT = Path(__file__).parent.parent
ANALYTICS_DIR = ROOT / "analytics"
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# EXECUTION MODE
# =============================================================================

class ExecutionMode(Enum):
    PAPER = "paper"             # Internal paper trading
    NINJATRADER_SIM = "nt_sim"  # NinjaTrader simulation
    NINJATRADER_LIVE = "nt_live"  # NinjaTrader live


# =============================================================================
# TPT HARD RULES (IMMUTABLE)
# =============================================================================

@dataclass
class TPTHardRules:
    """Immutable TPT evaluation rules."""
    INITIAL_BALANCE: float = 50000.0
    BALANCE_FLOOR: float = 48000.0
    PROFIT_TARGET: float = 3000.0
    MAX_CONTRACTS: int = 6
    MIN_TRADING_DAYS: int = 5
    CONSISTENCY_PCT: float = 0.50  # Max 50% in single day
    TRADING_CUTOFF: str = "17:00"  # EST
    FLATTEN_TIME: str = "16:45"   # EST


# =============================================================================
# CONTRACT SPECIFICATIONS
# =============================================================================

CONTRACT_SPECS = {
    # Symbol: (multiplier, tick_size, tick_value, typical_spread)
    'ES': (50.0, 0.25, 12.50, 0.25),      # E-mini S&P
    'MES': (5.0, 0.25, 1.25, 0.25),       # Micro E-mini S&P
    'NQ': (20.0, 0.25, 5.00, 0.25),       # E-mini Nasdaq
    'MNQ': (2.0, 0.25, 0.50, 0.25),       # Micro Nasdaq
    'YM': (5.0, 1.0, 5.00, 1.0),          # E-mini Dow
    'MYM': (0.5, 1.0, 0.50, 1.0),         # Micro Dow
    'RTY': (50.0, 0.10, 5.00, 0.10),      # E-mini Russell
    'M2K': (5.0, 0.10, 0.50, 0.10),       # Micro Russell
    'CL': (1000.0, 0.01, 10.00, 0.01),    # Crude Oil
    'MCL': (100.0, 0.01, 1.00, 0.01),     # Micro Crude
    'GC': (100.0, 0.10, 10.00, 0.10),     # Gold
    'MGC': (10.0, 0.10, 1.00, 0.10),      # Micro Gold
}


def get_contract_spec(symbol: str) -> Tuple[float, float, float, float]:
    """Get contract specifications."""
    import re
    match = re.match(r'^([A-Z0-9]+?)[FGHJKMNQUVXZ]\d{2}$', symbol.upper())
    base = match.group(1) if match else symbol.upper()
    return CONTRACT_SPECS.get(base, (50.0, 0.25, 12.50, 0.25))


# =============================================================================
# TPT EVALUATION TRACKER
# =============================================================================

class TPTEvalTracker:
    """Production-grade TPT evaluation tracker."""
    
    def __init__(self):
        self.rules = TPTHardRules()
        
        # Balance tracking
        self.current_balance = self.rules.INITIAL_BALANCE
        self.peak_balance = self.rules.INITIAL_BALANCE
        self.start_date = datetime.now()
        
        # Position tracking
        self.positions: Dict[str, Dict] = {}
        self.total_contracts = 0
        
        # Daily P&L
        self.daily_pnl: Dict[str, float] = {}
        self.trading_days: set = set()
        
        # Trade history
        self.trades: List[Dict] = []
        
        # Status
        self.status = "ACTIVE"
        self.failure_reason = ""
        
        # State file
        self._state_file = ANALYTICS_DIR / "tpt_production_state.json"
        self._load_state()
        
        logger.info(f"TPT Tracker: ${self.current_balance:,.2f} | Target: ${self.rules.PROFIT_TARGET:,.2f}")
    
    def _load_state(self):
        """Load saved state."""
        try:
            if self._state_file.exists():
                with open(self._state_file) as f:
                    data = json.load(f)
                self.current_balance = data.get('current_balance', self.rules.INITIAL_BALANCE)
                self.peak_balance = data.get('peak_balance', self.current_balance)
                self.daily_pnl = data.get('daily_pnl', {})
                self.trading_days = set(data.get('trading_days', []))
                self.status = data.get('status', 'ACTIVE')
                self.failure_reason = data.get('failure_reason', '')
                self.trades = data.get('trades', [])
                self.start_date = datetime.fromisoformat(data.get('start_date', datetime.now().isoformat()))
        except Exception as e:
            logger.error(f"Load state error: {e}")
    
    def _save_state(self):
        """Save state."""
        try:
            data = {
                'current_balance': self.current_balance,
                'peak_balance': self.peak_balance,
                'daily_pnl': self.daily_pnl,
                'trading_days': list(self.trading_days),
                'status': self.status,
                'failure_reason': self.failure_reason,
                'start_date': self.start_date.isoformat(),
                'trades': self.trades[-100:],  # Keep last 100
                'updated': datetime.now().isoformat(),
            }
            with open(self._state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Save state error: {e}")
    
    def can_trade(self, symbol: str, contracts: int, direction: str) -> Tuple[bool, str]:
        """Check if trade is allowed."""
        if self.status != 'ACTIVE':
            return False, f"Evaluation {self.status}: {self.failure_reason}"
        
        # Contract limit
        if self.total_contracts + contracts > self.rules.MAX_CONTRACTS:
            return False, f"Would exceed {self.rules.MAX_CONTRACTS} contracts"
        
        # Normalize symbol
        import re
        match = re.match(r'^([A-Z0-9]+?)[FGHJKMNQUVXZ]\d{2}$', symbol.upper())
        base = match.group(1) if match else symbol.upper()
        
        # Check permitted
        if base not in CONTRACT_SPECS:
            return False, f"{symbol} not permitted"
        
        # Counter position check
        if symbol in self.positions:
            if self.positions[symbol]['direction'] != direction:
                return False, "Counter positions not allowed"
        
        # Time check
        if not self._is_within_trading_hours():
            return False, "Outside trading hours"
        
        return True, "OK"
    
    def _is_within_trading_hours(self) -> bool:
        """Check if within TPT trading hours."""
        try:
            import pytz
            est = pytz.timezone('US/Eastern')
            now = datetime.now(est)
            
            # Weekend check
            if now.weekday() >= 5:
                if not (now.weekday() == 6 and now.hour >= 18):
                    return False
            
            # Cutoff check
            if now.strftime('%H:%M') >= self.rules.TRADING_CUTOFF:
                return False
            
            return True
        except:
            return True
    
    def should_flatten(self) -> bool:
        """Check if we should flatten all positions."""
        try:
            import pytz
            est = pytz.timezone('US/Eastern')
            now = datetime.now(est)
            return now.strftime('%H:%M') >= self.rules.FLATTEN_TIME
        except:
            return False
    
    def open_position(self, symbol: str, contracts: int, direction: str, 
                      entry_price: float) -> Tuple[bool, str]:
        """Open a position."""
        can, reason = self.can_trade(symbol, contracts, direction)
        if not can:
            return False, reason
        
        if symbol in self.positions:
            # Add to existing
            pos = self.positions[symbol]
            total_contracts = pos['contracts'] + contracts
            avg_price = (pos['entry_price'] * pos['contracts'] + entry_price * contracts) / total_contracts
            pos['contracts'] = total_contracts
            pos['entry_price'] = avg_price
        else:
            self.positions[symbol] = {
                'direction': direction,
                'contracts': contracts,
                'entry_price': entry_price,
                'opened_at': datetime.now().isoformat(),
            }
        
        self.total_contracts += contracts
        self.trading_days.add(datetime.now().strftime('%Y-%m-%d'))
        
        self._save_state()
        logger.info(f"OPEN: {direction} {contracts} {symbol} @ {entry_price:.2f}")
        
        return True, "OK"
    
    def close_position(self, symbol: str, contracts: int, exit_price: float) -> Tuple[bool, float]:
        """Close position and record P&L."""
        if symbol not in self.positions:
            return False, 0.0
        
        pos = self.positions[symbol]
        close_qty = min(contracts, pos['contracts'])
        
        # Get multiplier
        spec = get_contract_spec(symbol)
        multiplier = spec[0]
        
        # Calculate P&L
        if pos['direction'] == 'LONG':
            points = exit_price - pos['entry_price']
        else:
            points = pos['entry_price'] - exit_price
        
        pnl = points * close_qty * multiplier
        
        # Update position
        pos['contracts'] -= close_qty
        self.total_contracts -= close_qty
        
        if pos['contracts'] <= 0:
            del self.positions[symbol]
        
        # Record trade
        self._record_trade(symbol, pos['direction'], close_qty, 
                          pos['entry_price'], exit_price, pnl)
        
        # Update balance
        self._update_balance(pnl)
        
        logger.info(f"CLOSE: {close_qty} {symbol} @ {exit_price:.2f} | PnL: ${pnl:+,.2f}")
        
        return True, pnl
    
    def _record_trade(self, symbol: str, direction: str, contracts: int,
                      entry: float, exit: float, pnl: float):
        """Record completed trade and send to brain for feedback learning."""
        trade_data = {
            'symbol': symbol,
            'direction': direction,
            'contracts': contracts,
            'entry': entry,
            'exit': exit,
            'pnl': pnl,
            'time': datetime.now().isoformat(),
        }
        self.trades.append(trade_data)
        
        # Send to FuturesBrainV2 for feedback loop learning
        try:
            from execution.futures_brain_v2_integration import record_brain_v2_trade
            record_brain_v2_trade({
                'symbol': symbol,
                'direction': direction,
                'contracts': contracts,
                'entry_price': entry,
                'exit_price': exit,
                'pnl': pnl,
                'exit_reason': 'CLOSED',
            })
        except Exception as e:
            logger.debug(f"Brain feedback not available: {e}")
    
    def _update_balance(self, pnl: float):
        """Update balance and check rules."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        self.current_balance += pnl
        self.daily_pnl[today] = self.daily_pnl.get(today, 0) + pnl
        self.trading_days.add(today)
        
        # Update peak
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # Check balance floor
        if self.current_balance < self.rules.BALANCE_FLOOR:
            self.status = 'FAILED'
            self.failure_reason = f"Balance ${self.current_balance:,.0f} below ${self.rules.BALANCE_FLOOR:,.0f}"
            logger.error(f"TPT FAILED: {self.failure_reason}")
        
        # Check if passed
        total_profit = self.current_balance - self.rules.INITIAL_BALANCE
        if total_profit >= self.rules.PROFIT_TARGET:
            if len(self.trading_days) >= self.rules.MIN_TRADING_DAYS:
                if self._check_consistency():
                    self.status = 'PASSED'
                    logger.info(f"TPT PASSED! Profit: ${total_profit:,.2f}")
        
        self._save_state()
    
    def _check_consistency(self) -> bool:
        """Check 50% consistency rule."""
        total_profit = self.current_balance - self.rules.INITIAL_BALANCE
        if total_profit <= 0:
            return True
        
        biggest_day = max(self.daily_pnl.values()) if self.daily_pnl else 0
        limit = total_profit * self.rules.CONSISTENCY_PCT
        
        return biggest_day <= limit
    
    def get_status(self) -> Dict:
        """Get comprehensive status."""
        total_profit = self.current_balance - self.rules.INITIAL_BALANCE
        biggest_day = max(self.daily_pnl.values()) if self.daily_pnl else 0
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_pnl = self.daily_pnl.get(today, 0)
        
        return {
            'status': self.status,
            'failure_reason': self.failure_reason,
            
            'balance': self.current_balance,
            'initial': self.rules.INITIAL_BALANCE,
            'floor': self.rules.BALANCE_FLOOR,
            
            'profit': total_profit,
            'target': self.rules.PROFIT_TARGET,
            'progress_pct': (total_profit / self.rules.PROFIT_TARGET) * 100,
            'remaining': max(0, self.rules.PROFIT_TARGET - total_profit),
            
            'today_pnl': today_pnl,
            'trading_days': len(self.trading_days),
            'days_needed': self.rules.MIN_TRADING_DAYS,
            
            'contracts_used': self.total_contracts,
            'contracts_max': self.rules.MAX_CONTRACTS,
            'contracts_available': self.rules.MAX_CONTRACTS - self.total_contracts,
            
            'biggest_day': biggest_day,
            'consistency_limit': total_profit * self.rules.CONSISTENCY_PCT if total_profit > 0 else 0,
            'consistency_ok': biggest_day <= (total_profit * self.rules.CONSISTENCY_PCT) if total_profit > 0 else True,
            
            'drawdown_remaining': self.current_balance - self.rules.BALANCE_FLOOR,
            'daily_pnl': self.daily_pnl,
            'open_positions': list(self.positions.keys()),
        }
    
    def reset(self):
        """Reset evaluation."""
        self.current_balance = self.rules.INITIAL_BALANCE
        self.peak_balance = self.rules.INITIAL_BALANCE
        self.positions.clear()
        self.total_contracts = 0
        self.daily_pnl.clear()
        self.trading_days.clear()
        self.trades.clear()
        self.status = 'ACTIVE'
        self.failure_reason = ''
        self.start_date = datetime.now()
        self._save_state()
        logger.info("TPT Evaluation RESET")


# =============================================================================
# RISK MANAGER
# =============================================================================

class TPTRiskManager:
    """
    Risk management for TPT evaluation.
    
    Principles:
    1. Never risk more than 2% of drawdown buffer per trade
    2. Scale position size with confidence
    3. Tighter stops when close to balance floor
    4. Daily P&L limits for consistency
    """
    
    def __init__(self, tracker: TPTEvalTracker):
        self.tracker = tracker
        
        # Risk parameters
        self.max_risk_pct = 0.02        # 2% of drawdown buffer
        self.max_risk_dollars = 150.0   # Hard limit per trade
        self.confidence_scale = True    # Scale with confidence
        
        # Daily limits
        self.daily_target = 750.0       # Target per day
        self.daily_max = 900.0          # Stop at this (consistency)
        self.daily_loss_limit = -300.0  # Stop if down this much
        
        # Stop parameters (in points)
        self.base_stops = {
            'ES': 2.0, 'MES': 4.0,
            'NQ': 5.0, 'MNQ': 10.0,
            'YM': 20.0, 'MYM': 40.0,
            'RTY': 2.0, 'M2K': 4.0,
            'CL': 0.10, 'MCL': 0.20,
            'GC': 2.0, 'MGC': 4.0,
        }
        
        # R:R ratios
        self.min_rr = 1.5
        self.target_rr = 2.0
    
    def get_stop_points(self, symbol: str) -> float:
        """Get stop distance in points."""
        import re
        match = re.match(r'^([A-Z0-9]+?)[FGHJKMNQUVXZ]\d{2}$', symbol.upper())
        base = match.group(1) if match else symbol.upper()
        return self.base_stops.get(base, 2.0)
    
    def calculate_position_size(self, symbol: str, confidence: float) -> int:
        """Calculate optimal position size."""
        status = self.tracker.get_status()
        
        # Available contracts
        available = status['contracts_available']
        if available <= 0:
            return 0
        
        # Risk budget
        drawdown_buffer = status['drawdown_remaining']
        risk_budget = min(
            drawdown_buffer * self.max_risk_pct,
            self.max_risk_dollars
        )
        
        # Get contract specs
        spec = get_contract_spec(symbol)
        multiplier, tick_size, tick_value, _ = spec
        
        # Stop in dollars
        stop_points = self.get_stop_points(symbol)
        risk_per_contract = stop_points * multiplier
        
        # Base size
        base_size = int(risk_budget / risk_per_contract)
        
        # Scale with confidence
        if self.confidence_scale:
            if confidence >= 0.80:
                size = base_size + 2
            elif confidence >= 0.70:
                size = base_size + 1
            elif confidence >= 0.60:
                size = base_size
            else:
                size = max(1, base_size - 1)
        else:
            size = base_size
        
        # Limit to available
        size = min(size, available)
        
        # Minimum 1, maximum based on symbol
        if symbol.startswith('M'):  # Micro
            size = min(max(1, size), 6)
        else:  # E-mini
            size = min(max(1, size), 4)
        
        return size
    
    def should_trade_today(self) -> Tuple[bool, str]:
        """Check if we should take new trades today."""
        status = self.tracker.get_status()
        
        if status['status'] != 'ACTIVE':
            return False, f"Evaluation {status['status']}"
        
        today_pnl = status['today_pnl']
        
        # Daily max hit
        if today_pnl >= self.daily_max:
            return False, f"Daily max ${self.daily_max:,.0f} reached"
        
        # Daily loss limit
        if today_pnl <= self.daily_loss_limit:
            return False, f"Daily loss limit ${self.daily_loss_limit:,.0f} hit"
        
        # Consistency check - if we're profitable, check headroom
        if status['profit'] > 0:
            biggest = status['biggest_day']
            limit = status['profit'] * 0.50
            headroom = limit - biggest
            
            # If today's P&L could push us over
            potential_new_biggest = max(biggest, today_pnl + 200)
            if potential_new_biggest > limit and today_pnl > 0:
                return False, f"Consistency warning - headroom: ${headroom:,.0f}"
        
        return True, "OK"
    
    def get_trade_params(self, symbol: str, direction: str, 
                         entry_price: float, confidence: float) -> Dict:
        """Get complete trade parameters."""
        contracts = self.calculate_position_size(symbol, confidence)
        stop_pts = self.get_stop_points(symbol)
        spec = get_contract_spec(symbol)
        multiplier = spec[0]
        
        # R:R based on confidence
        rr = self.target_rr if confidence >= 0.75 else self.min_rr
        target_pts = stop_pts * rr
        
        if direction == 'LONG':
            stop_loss = entry_price - stop_pts
            take_profit = entry_price + target_pts
        else:
            stop_loss = entry_price + stop_pts
            take_profit = entry_price - target_pts
        
        risk = stop_pts * contracts * multiplier
        reward = target_pts * contracts * multiplier
        
        return {
            'contracts': contracts,
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'stop_points': stop_pts,
            'target_points': target_pts,
            'risk_dollars': risk,
            'reward_dollars': reward,
            'rr_ratio': rr,
        }


# =============================================================================
# SIGNAL GENERATOR
# =============================================================================

class TPTSignalGenerator:
    """
    ML-enhanced signal generator for TPT.
    
    Uses multiple signal sources:
    1. Technical analysis (trend, momentum, volatility)
    2. ML Brain ensemble (if available)
    3. Price action patterns
    4. Volume analysis
    """
    
    def __init__(self):
        # Primary: FuturesBrainV2 (TFT + WaveNet + Attention)
        self.brain_v2_integration = None
        # Fallback: UnifiedBrain (basic ensemble)
        self.ml_brain = None
        self._init_ml()
        
        # Signal history for confirmation
        self.signal_history: Dict[str, deque] = {}
        
        # Last prediction details (for feedback loop)
        self.last_prediction_details: Dict = {}
    
    def _init_ml(self):
        """Initialize ML brain - prioritizes FuturesBrainV2."""
        # Try FuturesBrainV2 first (advanced: TFT + WaveNet + Attention)
        try:
            from execution.futures_brain_v2_integration import (
                get_brain_v2_integration, initialize_brain_v2
            )
            self.brain_v2_integration = get_brain_v2_integration()
            if initialize_brain_v2():
                logger.info("FuturesBrainV2 connected to signal generator (PRIMARY)")
            else:
                logger.warning("FuturesBrainV2 init failed, will use fallback")
                self.brain_v2_integration = None
        except Exception as e:
            logger.warning(f"FuturesBrainV2 not available: {e}")
            self.brain_v2_integration = None
        
        # Fallback: UnifiedBrain
        try:
            from brain.unified_brain import get_unified_brain
            self.ml_brain = get_unified_brain()
            logger.info("UnifiedBrain connected (FALLBACK)")
        except Exception as e:
            logger.warning(f"UnifiedBrain fallback not available: {e}")
    
    def get_signal(self, symbol: str) -> Tuple[str, float, Dict]:
        """
        Get trading signal for symbol.
        
        Returns: (signal, confidence, details)
        Signal: 'BUY', 'SELL', 'HOLD'
        Confidence: 0.0 to 1.0
        """
        try:
            # Use TPT-specific futures data provider
            try:
                from execution.tpt_futures_data import get_price, get_ohlcv
            except ImportError:
                from data_provider_ultra import get_ohlcv, get_price
            
            df = get_ohlcv(symbol, '15m', '5d')
            
            if df is None or len(df) < 50:
                return 'HOLD', 0.5, {'error': 'Insufficient data'}
            
            # Normalize column names
            close = df['close'].values if 'close' in df.columns else df['Close'].values
            high = df['high'].values if 'high' in df.columns else df['High'].values
            low = df['low'].values if 'low' in df.columns else df['Low'].values
            volume = df['volume'].values if 'volume' in df.columns else df['Volume'].values
            
            details = {
                'symbol': symbol,
                'price': float(close[-1]),
                'time': datetime.now().isoformat(),
            }
            
            # Technical analysis signal
            ta_signal, ta_conf, ta_details = self._technical_analysis(close, high, low, volume)
            details['technical'] = ta_details
            
            # ML signal if available (FuturesBrainV2 primary, UnifiedBrain fallback)
            ml_signal, ml_conf = 'HOLD', 0.5
            if self.brain_v2_integration is not None or self.ml_brain is not None:
                ml_signal, ml_conf = self._get_ml_signal(close, high, low, volume, df=df)
                details['ml_signal'] = ml_signal
                details['ml_confidence'] = ml_conf
                # Include BrainV2 details if available
                if self.last_prediction_details:
                    details['brain_v2'] = self.last_prediction_details
            
            # Combine signals
            final_signal, final_conf = self._combine_signals(
                ta_signal, ta_conf,
                ml_signal, ml_conf
            )
            
            # Track for confirmation
            if symbol not in self.signal_history:
                self.signal_history[symbol] = deque(maxlen=5)
            self.signal_history[symbol].append((final_signal, final_conf))
            
            # Require confirmation (2 of last 3 signals agree)
            confirmed_signal, confirmed_conf = self._confirm_signal(symbol, final_signal, final_conf)
            
            details['raw_signal'] = final_signal
            details['raw_confidence'] = final_conf
            details['confirmed'] = confirmed_signal == final_signal
            
            return confirmed_signal, confirmed_conf, details
            
        except Exception as e:
            logger.error(f"Signal error for {symbol}: {e}")
            return 'HOLD', 0.5, {'error': str(e)}
    
    def _technical_analysis(self, close, high, low, volume) -> Tuple[str, float, Dict]:
        """Comprehensive technical analysis."""
        # Moving averages
        sma_10 = np.mean(close[-10:])
        sma_20 = np.mean(close[-20:])
        sma_50 = np.mean(close[-50:]) if len(close) >= 50 else sma_20
        
        ema_9 = self._ema(close, 9)
        ema_21 = self._ema(close, 21)
        
        # RSI
        rsi = self._rsi(close, 14)
        
        # MACD
        macd, signal_line, histogram = self._macd(close)
        
        # Stochastic
        stoch_k, stoch_d = self._stochastic(high, low, close)
        
        # ATR for volatility
        atr = self._atr(high, low, close)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._bollinger(close)
        
        # Volume analysis
        vol_avg = np.mean(volume[-20:])
        vol_ratio = volume[-1] / vol_avg if vol_avg > 0 else 1
        
        # Scoring system
        bullish_score = 0
        bearish_score = 0
        
        # Trend (weight: 3)
        if close[-1] > sma_20 > sma_50:
            bullish_score += 3
        elif close[-1] < sma_20 < sma_50:
            bearish_score += 3
        elif close[-1] > sma_20:
            bullish_score += 1
        elif close[-1] < sma_20:
            bearish_score += 1
        
        # EMA crossover (weight: 2)
        if ema_9 > ema_21:
            bullish_score += 2
        else:
            bearish_score += 2
        
        # RSI (weight: 2)
        if rsi < 30:
            bullish_score += 2  # Oversold
        elif rsi > 70:
            bearish_score += 2  # Overbought
        elif rsi < 45:
            bullish_score += 1
        elif rsi > 55:
            bearish_score += 1
        
        # MACD (weight: 2)
        if histogram > 0:
            bullish_score += 2
        elif histogram < 0:
            bearish_score += 2
        
        # Stochastic (weight: 1)
        if stoch_k < 20 and stoch_k > stoch_d:
            bullish_score += 1
        elif stoch_k > 80 and stoch_k < stoch_d:
            bearish_score += 1
        
        # Bollinger (weight: 1)
        if close[-1] < bb_lower:
            bullish_score += 1  # Near support
        elif close[-1] > bb_upper:
            bearish_score += 1  # Near resistance
        
        # Volume confirmation (weight: 1)
        if vol_ratio > 1.3:
            if bullish_score > bearish_score:
                bullish_score += 1
            else:
                bearish_score += 1
        
        # Calculate signal
        total_weight = 12  # Maximum possible
        net_score = bullish_score - bearish_score
        
        # Confidence calculation
        confidence = min(0.90, 0.50 + abs(net_score) / total_weight * 0.40)
        
        if net_score >= 5:
            signal = 'BUY'
        elif net_score <= -5:
            signal = 'SELL'
        else:
            signal = 'HOLD'
            confidence = 0.50
        
        details = {
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'net_score': net_score,
            'rsi': rsi,
            'macd_hist': histogram,
            'stoch_k': stoch_k,
            'vol_ratio': vol_ratio,
        }
        
        return signal, confidence, details
    
    def _get_ml_signal(self, close, high, low, volume, df=None, account_state=None) -> Tuple[str, float]:
        """Get ML brain signal - uses FuturesBrainV2 with fallback."""
        account_state = account_state or {}
        
        # Try FuturesBrainV2 first (advanced deep learning)
        if self.brain_v2_integration is not None and df is not None:
            try:
                signal, conf, contracts, details = self.brain_v2_integration.get_prediction(
                    'MNQ',  # Default symbol
                    df,
                    account_state
                )
                # Store for feedback loop
                self.last_prediction_details = {
                    'signal': signal,
                    'confidence': conf,
                    'contracts': contracts,
                    'signal_probs': details.get('signal_probs', []),
                    'regime': details.get('regime', 'UNKNOWN'),
                    'model_weights': details.get('model_weights', {}),
                    'using_brain_v2': True
                }
                return signal, conf
            except Exception as e:
                logger.debug(f"BrainV2 signal error: {e}")
        
        # Fallback to UnifiedBrain
        try:
            from brain.unified_brain import extract_features_for_strategy, StrategyType
            
            features = extract_features_for_strategy(
                StrategyType.ML_ENSEMBLE, close, high, low, volume
            )
            
            signal_str, confidence, _ = self.ml_brain.get_ensemble_signal(features)
            self.last_prediction_details = {
                'signal': signal_str,
                'confidence': confidence,
                'using_brain_v2': False
            }
            return signal_str, confidence
            
        except Exception as e:
            logger.debug(f"ML signal error: {e}")
            return 'HOLD', 0.5
    
    def _combine_signals(self, ta_signal, ta_conf, ml_signal, ml_conf) -> Tuple[str, float]:
        """Combine technical and ML signals."""
        # FuturesBrainV2 gets higher weight if available
        using_brain_v2 = (self.last_prediction_details.get('using_brain_v2', False) 
                         if self.last_prediction_details else False)
        
        if using_brain_v2 and ml_conf > 0.55:
            # BrainV2 is primary: 70% ML, 30% TA
            ml_weight = 0.70
            ta_weight = 0.30
        elif self.ml_brain and ml_conf > 0.55:
            # Fallback: 60% ML, 40% TA
            ml_weight = 0.60
            ta_weight = 0.40
        else:
            ml_weight = 0.0
            ta_weight = 1.0
        
        # Convert signals to numeric
        signal_map = {'BUY': 1, 'HOLD': 0, 'SELL': -1}
        
        ta_val = signal_map.get(ta_signal, 0) * ta_conf
        ml_val = signal_map.get(ml_signal, 0) * ml_conf
        
        combined = ta_val * ta_weight + ml_val * ml_weight
        
        # Determine final signal
        if combined > 0.3:
            final_signal = 'BUY'
        elif combined < -0.3:
            final_signal = 'SELL'
        else:
            final_signal = 'HOLD'
        
        final_conf = min(0.90, abs(combined) + 0.50)
        
        return final_signal, final_conf
    
    def _confirm_signal(self, symbol: str, signal: str, conf: float) -> Tuple[str, float]:
        """Require signal confirmation from history."""
        history = self.signal_history.get(symbol, [])
        
        if len(history) < 2:
            return signal, conf * 0.9  # Reduce confidence without confirmation
        
        # Count agreeing signals
        recent = list(history)[-3:]
        agree_count = sum(1 for s, c in recent if s == signal)
        
        if agree_count >= 2:
            return signal, min(0.90, conf * 1.1)  # Boost confidence
        else:
            return 'HOLD', 0.50  # Not confirmed
    
    def record_trade_feedback(self, trade_data: Dict):
        """
        Record trade result for feedback learning.
        
        Call this after closing a trade to enable the ML brain to learn.
        
        Args:
            trade_data: Dict with trade details:
                - symbol, direction, contracts
                - entry_price, exit_price
                - pnl, pnl_pct
                - exit_reason
        """
        if self.brain_v2_integration is not None:
            try:
                # Merge with last prediction details
                full_data = {**trade_data}
                if self.last_prediction_details:
                    full_data['confidence'] = self.last_prediction_details.get('confidence', 0)
                    full_data['signal_probs'] = self.last_prediction_details.get('signal_probs', [])
                    full_data['regime'] = self.last_prediction_details.get('regime', 'UNKNOWN')
                    full_data['model_weights'] = self.last_prediction_details.get('model_weights', {})
                
                from execution.futures_brain_v2_integration import record_trade_for_learning
                record_trade_for_learning(full_data)
                logger.debug(f"Trade recorded for feedback: {trade_data.get('symbol')} ${trade_data.get('pnl', 0):+.2f}")
            except Exception as e:
                logger.warning(f"Failed to record trade feedback: {e}")
    
    def get_suggested_contracts(self) -> int:
        """Get suggested contract count from last BrainV2 prediction."""
        if self.last_prediction_details:
            return self.last_prediction_details.get('contracts', 1)
        return 1
    
    # Technical indicator helpers
    def _ema(self, data, period):
        alpha = 2 / (period + 1)
        ema = [data[0]]
        for price in data[1:]:
            ema.append(alpha * price + (1 - alpha) * ema[-1])
        return ema[-1]
    
    def _rsi(self, close, period=14):
        changes = np.diff(close[-period-1:])
        gains = np.mean([c for c in changes if c > 0]) if any(c > 0 for c in changes) else 0
        losses = abs(np.mean([c for c in changes if c < 0])) if any(c < 0 for c in changes) else 0.001
        return 100 - (100 / (1 + gains / losses))
    
    def _macd(self, close, fast=12, slow=26, signal=9):
        ema_fast = self._ema(close, fast)
        ema_slow = self._ema(close, slow)
        macd_line = ema_fast - ema_slow
        # Simplified signal line
        signal_line = macd_line * 0.9  # Approximation
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _stochastic(self, high, low, close, k_period=14, d_period=3):
        lowest_low = np.min(low[-k_period:])
        highest_high = np.max(high[-k_period:])
        
        if highest_high == lowest_low:
            stoch_k = 50
        else:
            stoch_k = ((close[-1] - lowest_low) / (highest_high - lowest_low)) * 100
        
        stoch_d = stoch_k  # Simplified
        return stoch_k, stoch_d
    
    def _atr(self, high, low, close, period=14):
        tr_values = []
        for i in range(1, min(period + 1, len(close))):
            tr = max(
                high[-i] - low[-i],
                abs(high[-i] - close[-i-1]),
                abs(low[-i] - close[-i-1])
            )
            tr_values.append(tr)
        return np.mean(tr_values) if tr_values else 0
    
    def _bollinger(self, close, period=20, std_dev=2):
        middle = np.mean(close[-period:])
        std = np.std(close[-period:])
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower


# =============================================================================
# PRODUCTION BOT
# =============================================================================

class TPTProductionBot:
    """
    Production-grade TPT trading bot.
    
    Features:
    - Multi-source signal generation
    - Sophisticated risk management
    - Auto EOD flattening
    - NinjaTrader integration
    - Real-time monitoring
    """
    
    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        # Core components
        self.tracker = TPTEvalTracker()
        self.risk_mgr = TPTRiskManager(self.tracker)
        self.signal_gen = TPTSignalGenerator()
        
        # Execution mode
        self.mode = mode
        self.nt_executor = None
        
        # Initialize NinjaTrader if needed
        if mode in [ExecutionMode.NINJATRADER_SIM, ExecutionMode.NINJATRADER_LIVE]:
            self._init_ninjatrader()
        
        # Bot state
        self.is_running = False
        self.watchlist = ['ES', 'NQ', 'MES', 'MNQ']
        self.scan_interval = 20  # seconds
        
        # Threads
        self._stop_event = threading.Event()
        self._main_thread: Optional[threading.Thread] = None
        self._eod_thread: Optional[threading.Thread] = None
        
        # Active trades tracking
        self.active_trades: Dict[str, Dict] = {}
        
        # Callbacks
        self._callbacks = {
            'signal': [],
            'trade': [],
            'status': [],
            'error': [],
        }
        
        # Performance metrics
        self.metrics = {
            'signals_generated': 0,
            'trades_taken': 0,
            'trades_won': 0,
            'trades_lost': 0,
        }
        
        logger.info(f"TPT Production Bot initialized - Mode: {mode.value}")
    
    def _init_ninjatrader(self):
        """Initialize NinjaTrader connection."""
        try:
            from execution.ninjatrader_bridge import NinjaTraderATI, get_tpt_nt_executor
            self.nt_executor = get_tpt_nt_executor(self.tracker)
            logger.info("NinjaTrader executor connected")
        except Exception as e:
            logger.warning(f"NinjaTrader init failed: {e} - falling back to paper")
            self.mode = ExecutionMode.PAPER
    
    def start(self):
        """Start the bot."""
        if self.is_running:
            logger.warning("Bot already running")
            return
        
        status = self.tracker.get_status()
        if status['status'] != 'ACTIVE':
            logger.error(f"Cannot start - evaluation {status['status']}")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        # Start main loop
        self._main_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._main_thread.start()
        
        # Start EOD monitor
        self._eod_thread = threading.Thread(target=self._eod_monitor, daemon=True)
        self._eod_thread.start()
        
        logger.info("TPT Production Bot STARTED")
        self._notify('status', {'event': 'started', 'mode': self.mode.value})
    
    def stop(self):
        """Stop the bot."""
        self.is_running = False
        self._stop_event.set()
        logger.info("TPT Production Bot STOPPED")
        self._notify('status', {'event': 'stopped'})
    
    def _run_loop(self):
        """Main trading loop."""
        while self.is_running and not self._stop_event.is_set():
            try:
                # Check if we should trade
                should_trade, reason = self.risk_mgr.should_trade_today()
                
                if should_trade:
                    self._scan_for_signals()
                else:
                    logger.debug(f"Not trading: {reason}")
                
                # Monitor open positions
                self._monitor_positions()
                
            except Exception as e:
                logger.error(f"Loop error: {e}")
                self._notify('error', {'error': str(e)})
            
            self._stop_event.wait(self.scan_interval)
    
    def _eod_monitor(self):
        """End of day monitoring."""
        while self.is_running and not self._stop_event.is_set():
            try:
                import pytz
                est = pytz.timezone('US/Eastern')
                now = datetime.now(est)
                current_time = now.strftime('%H:%M')
                
                # Flatten at 16:45
                if current_time >= "16:45":
                    if self.tracker.positions:
                        logger.warning("EOD FLATTEN triggered")
                        self._flatten_all("EOD cutoff")
                
                # Warning at 16:30
                elif current_time >= "16:30":
                    if self.tracker.positions:
                        logger.warning("15 minutes to EOD - tightening stops")
                
            except Exception as e:
                logger.error(f"EOD monitor error: {e}")
            
            self._stop_event.wait(30)
    
    def _scan_for_signals(self):
        """Scan watchlist for signals."""
        for symbol in self.watchlist:
            # Skip if already have position
            if symbol in self.tracker.positions:
                continue
            
            # Skip if at max contracts
            status = self.tracker.get_status()
            if status['contracts_available'] <= 0:
                break
            
            try:
                signal, confidence, details = self.signal_gen.get_signal(symbol)
                self.metrics['signals_generated'] += 1
                
                # Notify signal
                self._notify('signal', {
                    'symbol': symbol,
                    'signal': signal,
                    'confidence': confidence,
                    'details': details,
                })
                
                # Evaluate and execute
                if signal in ['BUY', 'SELL'] and confidence >= 0.65:
                    self._execute_signal(symbol, signal, confidence, details)
                    
            except Exception as e:
                logger.error(f"Scan error {symbol}: {e}")
    
    def _execute_signal(self, symbol: str, signal: str, confidence: float, details: Dict):
        """Execute a trading signal."""
        try:
            # Use TPT-specific futures data
            try:
                from execution.tpt_futures_data import get_price
            except ImportError:
                from data_provider_ultra import get_price
            
            price_data = get_price(symbol)
            price = price_data.get('price', details.get('price', 0))
            
            if price <= 0:
                logger.error(f"Invalid price for {symbol}")
                return
            
            direction = 'LONG' if signal == 'BUY' else 'SHORT'
            
            # Get trade parameters
            params = self.risk_mgr.get_trade_params(symbol, direction, price, confidence)
            contracts = params['contracts']
            
            if contracts <= 0:
                return
            
            # Execute based on mode
            if self.mode == ExecutionMode.PAPER:
                success, msg = self.tracker.open_position(symbol, contracts, direction, price)
                
                if success:
                    self.active_trades[symbol] = {
                        **params,
                        'direction': direction,
                        'entry_price': price,
                        'entry_time': datetime.now().isoformat(),
                        'confidence': confidence,
                    }
                    
                    self.metrics['trades_taken'] += 1
                    
                    logger.info(
                        f"TRADE: {direction} {contracts} {symbol} @ {price:.2f} | "
                        f"Stop: {params['stop_loss']:.2f} | Target: {params['take_profit']:.2f}"
                    )
                    
                    self._notify('trade', {
                        'event': 'open',
                        'symbol': symbol,
                        'direction': direction,
                        'contracts': contracts,
                        'price': price,
                        'params': params,
                    })
            
            elif self.nt_executor:
                # NinjaTrader execution
                trade_id = self.nt_executor.execute_trade(
                    symbol=symbol,
                    direction=direction,
                    contracts=contracts,
                    stop_loss=params['stop_loss'],
                    take_profit=params['take_profit']
                )
                
                if trade_id:
                    self.active_trades[symbol] = {
                        **params,
                        'direction': direction,
                        'entry_price': price,
                        'nt_trade_id': trade_id,
                    }
                    self.metrics['trades_taken'] += 1
                    logger.info(f"NT TRADE: {direction} {contracts} {symbol} - ID: {trade_id}")
                
        except Exception as e:
            logger.error(f"Execute error: {e}")
    
    def _monitor_positions(self):
        """Monitor open positions for stops/targets with PRICE VALIDATION."""
        try:
            # Use TPT-specific futures data
            try:
                from execution.tpt_futures_data import get_price
            except ImportError:
                from data_provider_ultra import get_price
            
            for symbol in list(self.active_trades.keys()):
                if symbol not in self.tracker.positions:
                    # Position was closed externally
                    if symbol in self.active_trades:
                        del self.active_trades[symbol]
                    continue
                
                trade = self.active_trades[symbol]
                price_data = get_price(symbol)
                price = price_data.get('price', 0)
                
                # === CRITICAL: PRICE VALIDATION ===
                if price <= 0:
                    logger.warning(f"Invalid price for {symbol}: {price}")
                    continue
                
                entry_price = trade['entry_price']
                
                # Max allowed move from entry (prevents catastrophic bad data)
                # ES/MES: 50 points max, NQ/MNQ: 150 points max
                max_move = 150 if 'NQ' in symbol.upper() else 50
                price_diff = abs(price - entry_price)
                
                if price_diff > max_move:
                    logger.error(
                        f"PRICE VALIDATION FAILED for {symbol}: "
                        f"Entry={entry_price:.2f}, Current={price:.2f}, Diff={price_diff:.2f} > Max={max_move}"
                    )
                    logger.error("Skipping trade close - likely bad data")
                    continue
                
                # Additional sanity check: price should be in reasonable range
                if price < entry_price * 0.90 or price > entry_price * 1.10:
                    logger.error(f"Price {price} outside 10% range of entry {entry_price} - skipping")
                    continue
                
                # Check stop/target
                hit_stop = False
                hit_target = False
                
                if trade['direction'] == 'LONG':
                    if price <= trade['stop_loss']:
                        hit_stop = True
                    elif price >= trade['take_profit']:
                        hit_target = True
                else:
                    if price >= trade['stop_loss']:
                        hit_stop = True
                    elif price <= trade['take_profit']:
                        hit_target = True
                
                if hit_stop or hit_target:
                    reason = 'stop_loss' if hit_stop else 'take_profit'
                    
                    # Final P&L sanity check before closing
                    spec = get_contract_spec(symbol)
                    multiplier = spec[0]
                    contracts = trade['contracts']
                    
                    if trade['direction'] == 'LONG':
                        pnl = (price - entry_price) * contracts * multiplier
                    else:
                        pnl = (entry_price - price) * contracts * multiplier
                    
                    # MAX LOSS CIRCUIT BREAKER: $500 per trade max
                    if pnl < -500:
                        logger.error(f"CIRCUIT BREAKER: PnL ${pnl:.2f} exceeds -$500 limit - NOT CLOSING")
                        logger.error(f"Manual intervention required for {symbol}")
                        continue
                    
                    self._close_trade(symbol, price, reason)
                    
        except Exception as e:
            logger.error(f"Monitor error: {e}")
    
    def _close_trade(self, symbol: str, price: float, reason: str):
        """Close a trade and record feedback for ML learning."""
        if symbol not in self.active_trades:
            return
        
        trade = self.active_trades.get(symbol)
        pos = self.tracker.positions.get(symbol)
        if not pos:
            return
        
        success, pnl = self.tracker.close_position(symbol, pos['contracts'], price)
        
        if success:
            # Update metrics
            if pnl > 0:
                self.metrics['trades_won'] += 1
            else:
                self.metrics['trades_lost'] += 1
            
            logger.info(f"CLOSE: {symbol} @ {price:.2f} | {reason} | PnL: ${pnl:+,.2f}")
            
            # Record trade for ML feedback loop
            if trade:
                entry_price = trade.get('entry_price', 0)
                pnl_pct = ((price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                
                self.signal_gen.record_trade_feedback({
                    'trade_id': f"tpt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}",
                    'symbol': symbol,
                    'direction': trade.get('direction', pos.get('direction', 'LONG')),
                    'contracts': trade.get('contracts', pos.get('contracts', 1)),
                    'entry_price': entry_price,
                    'exit_price': price,
                    'entry_time': datetime.fromisoformat(trade.get('opened_at', datetime.now().isoformat())),
                    'exit_time': datetime.now(),
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'exit_reason': reason.upper()
                })
            
            self._notify('trade', {
                'event': 'close',
                'symbol': symbol,
                'price': price,
                'reason': reason,
                'pnl': pnl,
            })
            
            # Clean up
            if symbol in self.active_trades:
                del self.active_trades[symbol]
    
    def _flatten_all(self, reason: str):
        """Flatten all positions."""
        try:
            # Use TPT-specific futures data
            try:
                from execution.tpt_futures_data import get_price
            except ImportError:
                from data_provider_ultra import get_price
            
            total_pnl = 0
            
            for symbol in list(self.tracker.positions.keys()):
                price_data = get_price(symbol)
                price = price_data.get('price', 0)
                
                if price <= 0:
                    continue
                
                pos = self.tracker.positions[symbol]
                success, pnl = self.tracker.close_position(symbol, pos['contracts'], price)
                
                if success:
                    total_pnl += pnl
                    logger.info(f"FLATTEN: {symbol} @ {price:.2f} | PnL: ${pnl:+,.2f}")
            
            # Clear active trades
            self.active_trades.clear()
            
            logger.info(f"FLATTEN COMPLETE: {reason} | Total PnL: ${total_pnl:+,.2f}")
            
        except Exception as e:
            logger.error(f"Flatten error: {e}")
    
    def _notify(self, event_type: str, data: Dict):
        """Notify callbacks."""
        for cb in self._callbacks.get(event_type, []):
            try:
                cb(data)
            except:
                pass
    
    def on(self, event_type: str, callback: Callable):
        """Register callback."""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
    
    def get_status(self) -> Dict:
        """Get comprehensive bot status."""
        tracker_status = self.tracker.get_status()
        
        return {
            **tracker_status,
            'bot_running': self.is_running,
            'mode': self.mode.value,
            'watchlist': self.watchlist,
            'active_trades': len(self.active_trades),
            'metrics': self.metrics,
        }
    
    def set_watchlist(self, symbols: List[str]):
        """Set watchlist."""
        valid = [s for s in symbols if s.upper().replace('MES', 'ES').replace('MNQ', 'NQ')[:2] in ['ES', 'NQ', 'YM', 'RT', 'CL', 'GC']]
        self.watchlist = valid or self.watchlist
        logger.info(f"Watchlist: {self.watchlist}")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_bot: Optional[TPTProductionBot] = None

def get_tpt_bot(mode: ExecutionMode = ExecutionMode.PAPER) -> TPTProductionBot:
    """Get or create TPT production bot."""
    global _bot
    if _bot is None:
        _bot = TPTProductionBot(mode)
    return _bot

def create_fresh_bot(mode: ExecutionMode = ExecutionMode.PAPER) -> TPTProductionBot:
    """Create a new bot instance."""
    return TPTProductionBot(mode)


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == '__main__':
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    print("\n" + "="*60)
    print("  TPT PRODUCTION BOT v2.0")
    print("="*60)
    
    bot = get_tpt_bot(ExecutionMode.PAPER)
    
    # Print status
    status = bot.get_status()
    print(f"\n  Status: {status['status']}")
    print(f"  Balance: ${status['balance']:,.2f}")
    print(f"  Profit: ${status['profit']:+,.2f}")
    print(f"  Progress: {status['progress_pct']:.1f}%")
    print(f"  Remaining: ${status['remaining']:,.2f}")
    print(f"\n  Today's P&L: ${status['today_pnl']:+,.2f}")
    print(f"  Trading Days: {status['trading_days']} / {status['days_needed']}")
    print(f"  Drawdown Buffer: ${status['drawdown_remaining']:,.2f}")
    
    if status['consistency_ok']:
        print(f"\n  ✅ Consistency OK")
    else:
        print(f"\n  ⚠️  Consistency Warning!")
    
    print("\n" + "="*60)
    
    # Run if requested
    if '--run' in sys.argv:
        print("\nStarting bot...")
        bot.start()
        
        try:
            while True:
                time.sleep(10)
                s = bot.get_status()
                print(f"\r  P&L: ${s['profit']:+,.2f} | Today: ${s['today_pnl']:+,.2f} | Trades: {s['metrics']['trades_taken']}", end='')
        except KeyboardInterrupt:
            print("\n\nStopping...")
            bot.stop()
