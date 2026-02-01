"""
ICT & SMT STRATEGY MODULE
==========================
Inner Circle Trader (ICT) and Smart Money Techniques (SMT) for institutional-style trading.

Strategies Included:
1. Fair Value Gaps (FVG) - Imbalances for entries
2. Order Blocks (OB) - Institutional accumulation/distribution zones
3. Breaker Blocks - Failed order blocks that become support/resistance
4. Mitigation Blocks - Areas of unfilled orders
5. Liquidity Sweeps - Stop hunts and liquidity grabs
6. SMT Divergence - Correlation breaks between related instruments
7. Optimal Trade Entry (OTE) - Fibonacci-based entries
8. Kill Zones - High-probability time windows
9. Market Structure Shift (MSS) - Trend change confirmation
10. Inducement - Retail trap setups
"""

import numpy as np
import pandas as pd
from datetime import datetime, time, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum


class Bias(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class ZoneType(Enum):
    FVG_BULLISH = "FVG_BULLISH"
    FVG_BEARISH = "FVG_BEARISH"
    ORDER_BLOCK_BULLISH = "OB_BULLISH"
    ORDER_BLOCK_BEARISH = "OB_BEARISH"
    BREAKER_BULLISH = "BREAKER_BULLISH"
    BREAKER_BEARISH = "BREAKER_BEARISH"
    LIQUIDITY_HIGH = "LIQ_HIGH"
    LIQUIDITY_LOW = "LIQ_LOW"


@dataclass
class FairValueGap:
    """Fair Value Gap - price imbalance zone."""
    timestamp: datetime
    high: float
    low: float
    direction: Bias
    filled: bool = False
    filled_pct: float = 0.0
    strength: float = 0.0  # Size relative to ATR


@dataclass
class OrderBlock:
    """Order Block - institutional accumulation/distribution."""
    timestamp: datetime
    high: float
    low: float
    direction: Bias
    mitigated: bool = False
    strength: float = 0.0
    volume_confirmation: bool = False


@dataclass
class LiquidityLevel:
    """Liquidity level - stop hunt target."""
    price: float
    level_type: str  # 'HIGH', 'LOW', 'EQUAL_HIGHS', 'EQUAL_LOWS'
    strength: int  # Number of touches
    swept: bool = False


@dataclass 
class ICTSetup:
    """Complete ICT setup with all components."""
    timestamp: datetime
    ticker: str
    direction: Bias
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Components
    fvg: Optional[FairValueGap] = None
    order_block: Optional[OrderBlock] = None
    liquidity_target: Optional[LiquidityLevel] = None
    kill_zone: str = ""
    market_structure: str = ""
    smt_divergence: bool = False
    
    # Scores
    structure_score: float = 0.0
    timing_score: float = 0.0
    confluence_score: float = 0.0
    
    reason: str = ""


class ICTAnalyzer:
    """
    ICT (Inner Circle Trader) Analysis Engine.
    Implements institutional trading concepts.
    """
    
    # Kill Zone times (EST)
    KILL_ZONES = {
        'ASIAN': (time(20, 0), time(0, 0)),      # 8PM-12AM EST
        'LONDON': (time(2, 0), time(5, 0)),      # 2AM-5AM EST  
        'NY_OPEN': (time(8, 30), time(11, 0)),   # 8:30AM-11AM EST
        'NY_LUNCH': (time(12, 0), time(13, 30)), # 12PM-1:30PM EST (avoid)
        'NY_CLOSE': (time(14, 0), time(16, 0)),  # 2PM-4PM EST
    }
    
    def __init__(self):
        self.fvgs: List[FairValueGap] = []
        self.order_blocks: List[OrderBlock] = []
        self.liquidity_levels: List[LiquidityLevel] = []
        
    def analyze(self, df: pd.DataFrame, ticker: str = "") -> Dict:
        """
        Complete ICT analysis on price data.
        
        df: DataFrame with OHLCV data
        Returns: Analysis results with setups
        """
        if df is None or len(df) < 50:
            return {'error': 'Insufficient data'}
        
        # Ensure column names are correct
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        results = {
            'ticker': ticker,
            'timestamp': datetime.now(),
            'bias': Bias.NEUTRAL,
            'fvgs': [],
            'order_blocks': [],
            'liquidity_levels': [],
            'setups': [],
            'kill_zone': self._get_current_kill_zone(),
            'market_structure': 'NEUTRAL'
        }
        
        # Calculate ATR for sizing
        atr = self._calculate_atr(df)
        
        # 1. Detect Fair Value Gaps
        results['fvgs'] = self._find_fvgs(df, atr)
        
        # 2. Detect Order Blocks
        results['order_blocks'] = self._find_order_blocks(df, atr)
        
        # 3. Find Liquidity Levels
        results['liquidity_levels'] = self._find_liquidity_levels(df)
        
        # 4. Determine Market Structure
        results['market_structure'] = self._analyze_market_structure(df)
        
        # 5. Determine Bias
        results['bias'] = self._determine_bias(df, results)
        
        # 6. Generate Setups
        results['setups'] = self._generate_setups(df, results, ticker, atr)
        
        return results
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        tr = np.maximum(high[1:] - low[1:],
                       np.abs(high[1:] - close[:-1]),
                       np.abs(low[1:] - close[:-1]))
        
        return np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr)
    
    def _find_fvgs(self, df: pd.DataFrame, atr: float) -> List[FairValueGap]:
        """
        Find Fair Value Gaps (imbalances).
        Bullish FVG: Gap between candle 1 high and candle 3 low
        Bearish FVG: Gap between candle 1 low and candle 3 high
        """
        fvgs = []
        
        for i in range(2, len(df)):
            # Get three consecutive candles
            c1_high = df['high'].iloc[i-2]
            c1_low = df['low'].iloc[i-2]
            c3_high = df['high'].iloc[i]
            c3_low = df['low'].iloc[i]
            
            # Bullish FVG: C1 high < C3 low (gap up)
            if c1_high < c3_low:
                gap_size = c3_low - c1_high
                if gap_size > atr * 0.3:  # Significant gap
                    fvgs.append(FairValueGap(
                        timestamp=df.index[i] if hasattr(df.index[i], 'strftime') else datetime.now(),
                        high=c3_low,
                        low=c1_high,
                        direction=Bias.BULLISH,
                        strength=gap_size / atr
                    ))
            
            # Bearish FVG: C1 low > C3 high (gap down)
            if c1_low > c3_high:
                gap_size = c1_low - c3_high
                if gap_size > atr * 0.3:
                    fvgs.append(FairValueGap(
                        timestamp=df.index[i] if hasattr(df.index[i], 'strftime') else datetime.now(),
                        high=c1_low,
                        low=c3_high,
                        direction=Bias.BEARISH,
                        strength=gap_size / atr
                    ))
        
        # Check if FVGs have been filled
        current_price = df['close'].iloc[-1]
        for fvg in fvgs:
            if fvg.direction == Bias.BULLISH:
                if current_price < fvg.high:
                    fvg.filled_pct = (fvg.high - current_price) / (fvg.high - fvg.low)
                    fvg.filled = fvg.filled_pct >= 0.5
            else:
                if current_price > fvg.low:
                    fvg.filled_pct = (current_price - fvg.low) / (fvg.high - fvg.low)
                    fvg.filled = fvg.filled_pct >= 0.5
        
        return fvgs[-10:]  # Return most recent
    
    def _find_order_blocks(self, df: pd.DataFrame, atr: float) -> List[OrderBlock]:
        """
        Find Order Blocks (institutional accumulation/distribution).
        Bullish OB: Last bearish candle before bullish move
        Bearish OB: Last bullish candle before bearish move
        """
        order_blocks = []
        
        for i in range(5, len(df) - 3):
            # Check for bullish order block
            # Last red candle before a strong up move
            if df['close'].iloc[i] < df['open'].iloc[i]:  # Bearish candle
                # Check if followed by strong bullish move
                future_high = df['high'].iloc[i+1:i+4].max()
                if future_high > df['high'].iloc[i] + atr:
                    # Check volume confirmation
                    avg_vol = df['volume'].iloc[i-5:i].mean()
                    vol_conf = df['volume'].iloc[i] > avg_vol * 1.2
                    
                    order_blocks.append(OrderBlock(
                        timestamp=df.index[i] if hasattr(df.index[i], 'strftime') else datetime.now(),
                        high=df['high'].iloc[i],
                        low=df['low'].iloc[i],
                        direction=Bias.BULLISH,
                        strength=(future_high - df['high'].iloc[i]) / atr,
                        volume_confirmation=vol_conf
                    ))
            
            # Check for bearish order block
            if df['close'].iloc[i] > df['open'].iloc[i]:  # Bullish candle
                future_low = df['low'].iloc[i+1:i+4].min()
                if future_low < df['low'].iloc[i] - atr:
                    avg_vol = df['volume'].iloc[i-5:i].mean()
                    vol_conf = df['volume'].iloc[i] > avg_vol * 1.2
                    
                    order_blocks.append(OrderBlock(
                        timestamp=df.index[i] if hasattr(df.index[i], 'strftime') else datetime.now(),
                        high=df['high'].iloc[i],
                        low=df['low'].iloc[i],
                        direction=Bias.BEARISH,
                        strength=(df['low'].iloc[i] - future_low) / atr,
                        volume_confirmation=vol_conf
                    ))
        
        # Check mitigation
        current_price = df['close'].iloc[-1]
        for ob in order_blocks:
            if ob.direction == Bias.BULLISH:
                ob.mitigated = current_price < ob.low
            else:
                ob.mitigated = current_price > ob.high
        
        return order_blocks[-10:]
    
    def _find_liquidity_levels(self, df: pd.DataFrame) -> List[LiquidityLevel]:
        """
        Find liquidity levels (stop hunt targets).
        Equal highs, equal lows, swing points.
        """
        levels = []
        tolerance = 0.001  # 0.1% tolerance for "equal" levels
        
        highs = df['high'].values
        lows = df['low'].values
        
        # Find swing highs and lows
        for i in range(5, len(df) - 5):
            # Swing high
            if highs[i] == max(highs[i-5:i+6]):
                # Check for equal highs
                touches = sum(1 for j in range(len(highs)) 
                            if abs(highs[j] - highs[i]) / highs[i] < tolerance)
                
                levels.append(LiquidityLevel(
                    price=highs[i],
                    level_type='EQUAL_HIGHS' if touches > 2 else 'HIGH',
                    strength=touches
                ))
            
            # Swing low
            if lows[i] == min(lows[i-5:i+6]):
                touches = sum(1 for j in range(len(lows))
                            if abs(lows[j] - lows[i]) / lows[i] < tolerance)
                
                levels.append(LiquidityLevel(
                    price=lows[i],
                    level_type='EQUAL_LOWS' if touches > 2 else 'LOW',
                    strength=touches
                ))
        
        # Check if swept
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        for level in levels:
            if 'HIGH' in level.level_type:
                level.swept = current_high > level.price
            else:
                level.swept = current_low < level.price
        
        # Sort by strength and return most significant
        levels.sort(key=lambda x: -x.strength)
        return levels[:10]
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> str:
        """
        Analyze market structure (higher highs/lows or lower highs/lows).
        """
        highs = df['high'].values[-20:]
        lows = df['low'].values[-20:]
        
        # Find swing points
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(highs) - 2):
            if highs[i] == max(highs[i-2:i+3]):
                swing_highs.append(highs[i])
            if lows[i] == min(lows[i-2:i+3]):
                swing_lows.append(lows[i])
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 'NEUTRAL'
        
        # Check for HH/HL (bullish) or LH/LL (bearish)
        hh = swing_highs[-1] > swing_highs[-2] if len(swing_highs) >= 2 else False
        hl = swing_lows[-1] > swing_lows[-2] if len(swing_lows) >= 2 else False
        lh = swing_highs[-1] < swing_highs[-2] if len(swing_highs) >= 2 else False
        ll = swing_lows[-1] < swing_lows[-2] if len(swing_lows) >= 2 else False
        
        if hh and hl:
            return 'BULLISH'
        elif lh and ll:
            return 'BEARISH'
        elif hh and ll:
            return 'CONSOLIDATING'
        else:
            return 'NEUTRAL'
    
    def _determine_bias(self, df: pd.DataFrame, results: Dict) -> Bias:
        """Determine overall directional bias."""
        scores = {'BULLISH': 0, 'BEARISH': 0}
        
        # Market structure
        if results['market_structure'] == 'BULLISH':
            scores['BULLISH'] += 2
        elif results['market_structure'] == 'BEARISH':
            scores['BEARISH'] += 2
        
        # Unfilled FVGs
        for fvg in results['fvgs']:
            if not fvg.filled:
                if fvg.direction == Bias.BULLISH:
                    scores['BULLISH'] += 1
                else:
                    scores['BEARISH'] += 1
        
        # Unmitigated order blocks
        for ob in results['order_blocks']:
            if not ob.mitigated:
                if ob.direction == Bias.BULLISH:
                    scores['BULLISH'] += 1.5
                else:
                    scores['BEARISH'] += 1.5
        
        # Recent trend
        sma_20 = df['close'].rolling(20).mean().iloc[-1]
        sma_50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma_20
        current = df['close'].iloc[-1]
        
        if current > sma_20 > sma_50:
            scores['BULLISH'] += 1
        elif current < sma_20 < sma_50:
            scores['BEARISH'] += 1
        
        if scores['BULLISH'] > scores['BEARISH'] + 1:
            return Bias.BULLISH
        elif scores['BEARISH'] > scores['BULLISH'] + 1:
            return Bias.BEARISH
        return Bias.NEUTRAL
    
    def _get_current_kill_zone(self) -> str:
        """Get current kill zone based on time."""
        now = datetime.now().time()
        
        for zone_name, (start, end) in self.KILL_ZONES.items():
            if start <= end:
                if start <= now <= end:
                    return zone_name
            else:  # Crosses midnight
                if now >= start or now <= end:
                    return zone_name
        
        return 'OFF_HOURS'
    
    def _generate_setups(self, df: pd.DataFrame, results: Dict, 
                         ticker: str, atr: float) -> List[ICTSetup]:
        """Generate actionable ICT setups."""
        setups = []
        current_price = df['close'].iloc[-1]
        kill_zone = results['kill_zone']
        
        # Only generate setups during kill zones (except lunch)
        if kill_zone in ['NY_LUNCH', 'OFF_HOURS']:
            return setups
        
        # Look for setups at unfilled FVGs with bias alignment
        for fvg in results['fvgs']:
            if fvg.filled:
                continue
            
            # Check if price is near FVG
            near_fvg = False
            if fvg.direction == Bias.BULLISH:
                # Price should be near or in the FVG for long entry
                if fvg.low <= current_price <= fvg.high * 1.01:
                    near_fvg = True
            else:
                if fvg.low * 0.99 <= current_price <= fvg.high:
                    near_fvg = True
            
            if near_fvg and fvg.direction == results['bias']:
                # Find nearby order block for confirmation
                ob_conf = any(ob.direction == fvg.direction and not ob.mitigated 
                             for ob in results['order_blocks'])
                
                # Calculate entry, SL, TP
                if fvg.direction == Bias.BULLISH:
                    entry = (fvg.high + fvg.low) / 2
                    stop_loss = fvg.low - atr * 0.5
                    # Target next liquidity high
                    liq_highs = [l.price for l in results['liquidity_levels'] 
                                if 'HIGH' in l.level_type and l.price > current_price]
                    take_profit = min(liq_highs) if liq_highs else entry + atr * 2
                else:
                    entry = (fvg.high + fvg.low) / 2
                    stop_loss = fvg.high + atr * 0.5
                    liq_lows = [l.price for l in results['liquidity_levels']
                               if 'LOW' in l.level_type and l.price < current_price]
                    take_profit = max(liq_lows) if liq_lows else entry - atr * 2
                
                # Calculate confidence
                confidence = 0.5
                confidence += 0.1 if ob_conf else 0
                confidence += 0.1 if kill_zone in ['NY_OPEN', 'LONDON'] else 0
                confidence += 0.1 if results['market_structure'] == fvg.direction.value else 0
                confidence += 0.1 * min(1, fvg.strength)
                
                setups.append(ICTSetup(
                    timestamp=datetime.now(),
                    ticker=ticker,
                    direction=fvg.direction,
                    confidence=min(0.95, confidence),
                    entry_price=entry,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    fvg=fvg,
                    kill_zone=kill_zone,
                    market_structure=results['market_structure'],
                    structure_score=0.8 if results['market_structure'] == fvg.direction.value else 0.5,
                    timing_score=0.9 if kill_zone in ['NY_OPEN', 'LONDON'] else 0.6,
                    confluence_score=0.8 if ob_conf else 0.5,
                    reason=f"FVG {fvg.direction.value} + {results['market_structure']} structure + {kill_zone}"
                ))
        
        return setups


class SMTAnalyzer:
    """
    Smart Money Technique (SMT) Divergence Analyzer.
    Detects correlation breaks between related instruments.
    """
    
    # Related pairs for SMT
    SMT_PAIRS = {
        'ES': ['NQ', 'YM'],      # S&P futures vs Nasdaq, Dow
        'SPY': ['QQQ', 'DIA'],   # S&P ETF vs Nasdaq, Dow ETFs
        'AAPL': ['MSFT', 'GOOGL'],
        'NVDA': ['AMD', 'INTC'],
        'GLD': ['SLV'],
        'EUR/USD': ['GBP/USD', 'DXY'],
    }
    
    def detect_smt_divergence(self, ticker: str, df1: pd.DataFrame, 
                               related_ticker: str, df2: pd.DataFrame) -> Dict:
        """
        Detect SMT divergence between two correlated instruments.
        
        SMT Divergence = One makes new high/low while the other fails to.
        """
        if len(df1) < 20 or len(df2) < 20:
            return {'divergence': False}
        
        # Get recent swing points
        highs1 = df1['high'].values[-20:]
        lows1 = df1['low'].values[-20:]
        highs2 = df2['high'].values[-20:]
        lows2 = df2['low'].values[-20:]
        
        # Check for bullish SMT (ticker makes lower low, related makes higher low)
        ll_ticker = lows1[-1] < min(lows1[-10:-1])
        hl_related = lows2[-1] > min(lows2[-10:-1])
        
        bullish_smt = ll_ticker and hl_related
        
        # Check for bearish SMT (ticker makes higher high, related makes lower high)
        hh_ticker = highs1[-1] > max(highs1[-10:-1])
        lh_related = highs2[-1] < max(highs2[-10:-1])
        
        bearish_smt = hh_ticker and lh_related
        
        return {
            'divergence': bullish_smt or bearish_smt,
            'type': 'BULLISH' if bullish_smt else 'BEARISH' if bearish_smt else None,
            'ticker': ticker,
            'related': related_ticker,
            'confidence': 0.75 if (bullish_smt or bearish_smt) else 0.0
        }


class OTECalculator:
    """
    Optimal Trade Entry (OTE) Calculator.
    Uses Fibonacci retracements for entry zones.
    """
    
    # ICT OTE zone is typically 62-79% retracement
    OTE_ZONE = (0.62, 0.79)
    
    def calculate_ote(self, swing_high: float, swing_low: float, 
                      direction: Bias) -> Dict:
        """
        Calculate Optimal Trade Entry zone.
        """
        range_size = swing_high - swing_low
        
        if direction == Bias.BULLISH:
            # For longs, OTE is retracement from high
            ote_high = swing_high - range_size * self.OTE_ZONE[0]
            ote_low = swing_high - range_size * self.OTE_ZONE[1]
            entry = (ote_high + ote_low) / 2
            
            return {
                'zone_high': ote_high,
                'zone_low': ote_low,
                'optimal_entry': entry,
                'stop_loss': swing_low - range_size * 0.1,
                'tp1': swing_high,
                'tp2': swing_high + range_size * 0.618,
                'tp3': swing_high + range_size
            }
        else:
            # For shorts, OTE is retracement from low
            ote_low = swing_low + range_size * self.OTE_ZONE[0]
            ote_high = swing_low + range_size * self.OTE_ZONE[1]
            entry = (ote_high + ote_low) / 2
            
            return {
                'zone_high': ote_high,
                'zone_low': ote_low,
                'optimal_entry': entry,
                'stop_loss': swing_high + range_size * 0.1,
                'tp1': swing_low,
                'tp2': swing_low - range_size * 0.618,
                'tp3': swing_low - range_size
            }


# Main ICT Engine
class ICTEngine:
    """Combined ICT analysis engine."""
    
    def __init__(self):
        self.ict_analyzer = ICTAnalyzer()
        self.smt_analyzer = SMTAnalyzer()
        self.ote_calculator = OTECalculator()
    
    def full_analysis(self, df: pd.DataFrame, ticker: str = "") -> Dict:
        """Run complete ICT analysis."""
        results = self.ict_analyzer.analyze(df, ticker)
        
        # Add OTE calculations for setups
        for setup in results.get('setups', []):
            if setup.fvg:
                ote = self.ote_calculator.calculate_ote(
                    df['high'].max(), df['low'].min(), setup.direction
                )
                setup.reason += f" | OTE zone: {ote['zone_low']:.2f}-{ote['zone_high']:.2f}"
        
        return results
    
    def get_signal(self, df: pd.DataFrame, ticker: str = "", 
                   timeframe: str = "SCALP") -> Dict:
        """
        Get trading signal from ICT analysis.
        Returns dict compatible with QuantBrain signal format.
        """
        results = self.full_analysis(df, ticker)
        
        # Find best setup
        if not results.get('setups'):
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'reason': 'No ICT setups found',
                'strategy': 'ICT_FVG'
            }
        
        best_setup = max(results['setups'], key=lambda s: s.confidence)
        
        # Check kill zone timing
        if results['kill_zone'] in ['NY_LUNCH', 'OFF_HOURS']:
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'reason': f"Outside kill zone: {results['kill_zone']}",
                'strategy': 'ICT_FVG'
            }
        
        # Generate signal
        return {
            'action': 'LONG' if best_setup.direction == Bias.BULLISH else 'SHORT',
            'confidence': best_setup.confidence,
            'entry': best_setup.entry_price,
            'stop_loss': best_setup.stop_loss,
            'take_profit': best_setup.take_profit,
            'reason': best_setup.reason,
            'strategy': 'ICT_FVG',
            'kill_zone': best_setup.kill_zone,
            'market_structure': best_setup.market_structure,
            'confluence_score': best_setup.confluence_score,
            'timing_score': best_setup.timing_score
        }


# Singleton instance
ict_engine = ICTEngine()


def get_ict_signal(df: pd.DataFrame, ticker: str = "", timeframe: str = "SCALP") -> Dict:
    """Convenience function for ICT signal."""
    return ict_engine.get_signal(df, ticker, timeframe)


def analyze_ict(df: pd.DataFrame, ticker: str = "") -> Dict:
    """Convenience function for full ICT analysis."""
    return ict_engine.full_analysis(df, ticker)


# Test
if __name__ == "__main__":
    import yfinance as yf
    
    # Test with SPY data
    spy = yf.Ticker("SPY").history(period="5d", interval="5m")
    
    print("=" * 60)
    print("ICT ANALYSIS TEST")
    print("=" * 60)
    
    results = analyze_ict(spy, "SPY")
    
    print(f"Bias: {results['bias'].value}")
    print(f"Market Structure: {results['market_structure']}")
    print(f"Kill Zone: {results['kill_zone']}")
    print(f"FVGs Found: {len(results['fvgs'])}")
    print(f"Order Blocks: {len(results['order_blocks'])}")
    print(f"Liquidity Levels: {len(results['liquidity_levels'])}")
    print(f"Setups: {len(results['setups'])}")
    
    for setup in results['setups']:
        print(f"\n  Setup: {setup.direction.value}")
        print(f"  Entry: ${setup.entry_price:.2f}")
        print(f"  SL: ${setup.stop_loss:.2f}")
        print(f"  TP: ${setup.take_profit:.2f}")
        print(f"  Confidence: {setup.confidence:.1%}")
        print(f"  Reason: {setup.reason}")
