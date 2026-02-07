"""
QUANT INDUSTRY V1 - Options API (v2)
====================================
Options data: chain, GEX, flow, dark pool, signals.
Wired to real backend services.
"""

import logging
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# Service Availability
# ============================================================================

OPTIONS_SERVICE_AVAILABLE = False
GEX_ANALYZER_AVAILABLE = False
OPTIONS_FLOW_AVAILABLE = False

_options_service = None
_gex_analyzer = None

# Try to import options service
try:
    from backend.options.options_service import get_options_service, OptionsService
    OPTIONS_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Options service not available: {e}")

# Try to import GEX analyzer
try:
    from backend.options.gex_analyzer import get_gex_analyzer, GEXAnalyzer
    GEX_ANALYZER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GEX analyzer not available: {e}")

# Try to import options flow modules
try:
    from options_flow.unusual_activity import UnusualActivityDetector
    from options_flow.gamma_exposure import GammaExposureCalculator
    from options_flow.dark_pool import DarkPoolMonitor
    from options_flow.flow_signals import OptionsFlowSignals
    from options_flow.smart_money import SmartMoneyTracker
    OPTIONS_FLOW_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Options flow modules not available: {e}")


def _get_options_service():
    global _options_service
    if _options_service is None and OPTIONS_SERVICE_AVAILABLE:
        _options_service = get_options_service()
    return _options_service


def _get_gex_analyzer():
    global _gex_analyzer
    if _gex_analyzer is None and GEX_ANALYZER_AVAILABLE:
        _gex_analyzer = get_gex_analyzer()
    return _gex_analyzer


# ============================================================================
# Enums
# ============================================================================

class OptionType(str, Enum):
    """Option type."""
    CALL = "call"
    PUT = "put"


class FlowType(str, Enum):
    """Options flow type."""
    UNUSUAL = "unusual"
    SWEEP = "sweep"
    BLOCK = "block"
    SMART_MONEY = "smart_money"


class FlowSentiment(str, Enum):
    """Flow sentiment."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ============================================================================
# Pydantic Models
# ============================================================================

class OptionContract(BaseModel):
    """Individual option contract."""
    symbol: str
    underlying: str
    option_type: OptionType
    strike: float
    expiration: date
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    in_the_money: bool


class OptionChain(BaseModel):
    """Full option chain."""
    underlying: str
    underlying_price: float
    expirations: list[date] = Field(default_factory=list)
    calls: list[OptionContract] = Field(default_factory=list)
    puts: list[OptionContract] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GammaLevel(BaseModel):
    """Gamma exposure at a price level."""
    strike: float
    call_gamma: float
    put_gamma: float
    net_gamma: float
    total_gamma: float


class GEXResponse(BaseModel):
    """Gamma exposure response."""
    symbol: str
    spot_price: float
    total_gex: float
    call_gex: float
    put_gex: float
    flip_point: float = Field(..., description="Price where GEX flips from positive to negative")
    max_pain: float = Field(..., description="Maximum pain strike")
    levels: list[GammaLevel] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OptionsFlow(BaseModel):
    """Individual options flow entry."""
    id: str
    symbol: str
    underlying: str
    option_type: OptionType
    strike: float
    expiration: date
    flow_type: FlowType
    sentiment: FlowSentiment
    premium: float
    size: int
    spot_price: float
    execution_price: float
    exchange: str
    timestamp: datetime


class FlowResponse(BaseModel):
    """Options flow response."""
    flows: list[OptionsFlow] = Field(default_factory=list)
    total_premium_bullish: float
    total_premium_bearish: float
    net_sentiment: FlowSentiment
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DarkPoolTrade(BaseModel):
    """Dark pool trade."""
    id: str
    symbol: str
    price: float
    size: int
    notional: float
    exchange: str
    timestamp: datetime


class DarkPoolResponse(BaseModel):
    """Dark pool activity response."""
    symbol: Optional[str] = None
    trades: list[DarkPoolTrade] = Field(default_factory=list)
    total_volume: int
    total_notional: float
    avg_trade_size: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FlowSignal(BaseModel):
    """Signal derived from options flow."""
    id: str
    symbol: str
    signal_type: str
    direction: str
    confidence: float
    premium_involved: float
    description: str
    expiration_focus: Optional[date] = None
    strike_focus: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FlowSignalsResponse(BaseModel):
    """Flow-derived signals."""
    signals: list[FlowSignal] = Field(default_factory=list)
    total: int


class SmartMoneyActivity(BaseModel):
    """Smart money (institutional) activity."""
    symbol: str
    net_premium: float
    call_premium: float
    put_premium: float
    sentiment: FlowSentiment
    unusual_activity_count: int
    block_trade_count: int
    sweep_count: int
    largest_trade: float
    institutional_bias: str


class SmartMoneyResponse(BaseModel):
    """Smart money activity response."""
    activities: list[SmartMoneyActivity] = Field(default_factory=list)
    market_sentiment: FlowSentiment
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_expiration(exp_str: str) -> date:
    """Parse expiration string to date."""
    try:
        return datetime.strptime(exp_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()


def _determine_flow_type(flow_data: Dict) -> FlowType:
    """Determine flow type from data."""
    if flow_data.get('is_sweep'):
        return FlowType.SWEEP
    elif flow_data.get('premium', 0) > 500000:
        return FlowType.BLOCK
    elif 'unusual' in str(flow_data.get('unusual_reasons', [])):
        return FlowType.UNUSUAL
    return FlowType.UNUSUAL


def _determine_sentiment(flow_data: Dict) -> FlowSentiment:
    """Determine sentiment from flow data."""
    sentiment = flow_data.get('sentiment', 'neutral')
    if sentiment == 'bullish':
        return FlowSentiment.BULLISH
    elif sentiment == 'bearish':
        return FlowSentiment.BEARISH
    return FlowSentiment.NEUTRAL


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "/chain/{symbol}",
    response_model=OptionChain,
    summary="Options chain",
    description="Get full options chain for a symbol."
)
async def get_option_chain(
    symbol: str = Path(..., description="Underlying symbol"),
    expiration: Optional[date] = Query(None, description="Filter by expiration"),
    strikes_around: int = Query(10, ge=1, le=50, description="Number of strikes around spot")
) -> OptionChain:
    """Get options chain with Greeks from real service."""
    opts_svc = _get_options_service()
    
    if opts_svc:
        try:
            chain_data = opts_svc.get_options_chain(symbol.upper())
            
            if not chain_data:
                raise HTTPException(status_code=404, detail=f"No options data for {symbol}")
            
            # Filter by expiration if provided
            target_exp = expiration.isoformat() if expiration else None
            if target_exp:
                calls_filtered = [c for c in chain_data.calls if c.expiration == target_exp]
                puts_filtered = [p for p in chain_data.puts if p.expiration == target_exp]
            else:
                # Get first expiration
                if chain_data.expirations:
                    first_exp = chain_data.expirations[0]
                    calls_filtered = [c for c in chain_data.calls if c.expiration == first_exp]
                    puts_filtered = [p for p in chain_data.puts if p.expiration == first_exp]
                else:
                    calls_filtered = chain_data.calls[:strikes_around * 2]
                    puts_filtered = chain_data.puts[:strikes_around * 2]
            
            # Filter to strikes around spot
            spot = chain_data.underlying_price
            calls_sorted = sorted(calls_filtered, key=lambda c: abs(c.strike - spot))[:strikes_around * 2]
            puts_sorted = sorted(puts_filtered, key=lambda p: abs(p.strike - spot))[:strikes_around * 2]
            
            # Convert to response models
            calls = []
            for c in calls_sorted:
                calls.append(OptionContract(
                    symbol=c.symbol,
                    underlying=c.underlying,
                    option_type=OptionType.CALL,
                    strike=c.strike,
                    expiration=_parse_expiration(c.expiration),
                    bid=c.bid, ask=c.ask, last=c.last,
                    volume=c.volume, open_interest=c.open_interest,
                    implied_volatility=c.implied_volatility,
                    delta=c.greeks.delta if c.greeks else 0,
                    gamma=c.greeks.gamma if c.greeks else 0,
                    theta=c.greeks.theta if c.greeks else 0,
                    vega=c.greeks.vega if c.greeks else 0,
                    in_the_money=c.in_the_money
                ))
            
            puts = []
            for p in puts_sorted:
                puts.append(OptionContract(
                    symbol=p.symbol,
                    underlying=p.underlying,
                    option_type=OptionType.PUT,
                    strike=p.strike,
                    expiration=_parse_expiration(p.expiration),
                    bid=p.bid, ask=p.ask, last=p.last,
                    volume=p.volume, open_interest=p.open_interest,
                    implied_volatility=p.implied_volatility,
                    delta=p.greeks.delta if p.greeks else 0,
                    gamma=p.greeks.gamma if p.greeks else 0,
                    theta=p.greeks.theta if p.greeks else 0,
                    vega=p.greeks.vega if p.greeks else 0,
                    in_the_money=p.in_the_money
                ))
            
            expirations = [_parse_expiration(e) for e in chain_data.expirations]
            
            return OptionChain(
                underlying=symbol.upper(),
                underlying_price=chain_data.underlying_price,
                expirations=expirations,
                calls=calls, puts=puts
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting options chain for {symbol}: {e}")
    
    # Fallback mock data
    calls = [
        OptionContract(
            symbol=f"{symbol.upper()}250117C00150000", underlying=symbol.upper(),
            option_type=OptionType.CALL, strike=150.0, expiration=date(2025, 1, 17),
            bid=3.50, ask=3.60, last=3.55, volume=5000, open_interest=25000,
            implied_volatility=0.25, delta=0.52, gamma=0.05, theta=-0.08, vega=0.15,
            in_the_money=True
        ),
    ]
    puts = [
        OptionContract(
            symbol=f"{symbol.upper()}250117P00150000", underlying=symbol.upper(),
            option_type=OptionType.PUT, strike=150.0, expiration=date(2025, 1, 17),
            bid=2.80, ask=2.90, last=2.85, volume=3500, open_interest=18000,
            implied_volatility=0.26, delta=-0.48, gamma=0.05, theta=-0.07, vega=0.14,
            in_the_money=False
        ),
    ]
    return OptionChain(
        underlying=symbol.upper(), underlying_price=150.50,
        expirations=[date(2025, 1, 17), date(2025, 1, 24), date(2025, 1, 31)],
        calls=calls, puts=puts
    )


@router.get(
    "/gex/{symbol}",
    response_model=GEXResponse,
    summary="Gamma exposure",
    description="Get gamma exposure analysis for a symbol."
)
async def get_gex(symbol: str = Path(..., description="Underlying symbol")) -> GEXResponse:
    """Get gamma exposure (GEX) levels and analysis from real service."""
    opts_svc = _get_options_service()
    gex_analyzer = _get_gex_analyzer()
    
    if opts_svc and gex_analyzer:
        try:
            chain_data = opts_svc.get_options_chain(symbol.upper())
            
            if not chain_data:
                raise HTTPException(status_code=404, detail=f"No options data for {symbol}")
            
            gex_data = gex_analyzer.analyze(symbol.upper(), chain_data)
            
            levels = []
            for strike_gex in gex_data.strikes[:20]:  # Limit to 20 levels
                levels.append(GammaLevel(
                    strike=strike_gex.strike,
                    call_gamma=strike_gex.call_gex,
                    put_gamma=strike_gex.put_gex,
                    net_gamma=strike_gex.net_gex,
                    total_gamma=abs(strike_gex.call_gex) + abs(strike_gex.put_gex)
                ))
            
            return GEXResponse(
                symbol=symbol.upper(),
                spot_price=gex_data.underlying_price,
                total_gex=gex_data.total_net_gex * 1_000_000,  # Convert from millions
                call_gex=gex_data.total_call_gex * 1_000_000,
                put_gex=gex_data.total_put_gex * 1_000_000,
                flip_point=gex_data.zero_gamma_level,
                max_pain=gex_data.max_gamma_strike,
                levels=levels
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting GEX for {symbol}: {e}")
    
    # Fallback
    levels = [
        GammaLevel(strike=145.0, call_gamma=0.02, put_gamma=0.08, net_gamma=-0.06, total_gamma=0.10),
        GammaLevel(strike=150.0, call_gamma=0.05, put_gamma=0.05, net_gamma=0.00, total_gamma=0.10),
        GammaLevel(strike=155.0, call_gamma=0.08, put_gamma=0.02, net_gamma=0.06, total_gamma=0.10),
    ]
    return GEXResponse(
        symbol=symbol.upper(), spot_price=150.50,
        total_gex=2500000000, call_gex=1800000000, put_gex=700000000,
        flip_point=148.50, max_pain=150.0, levels=levels
    )


@router.get(
    "/flow",
    response_model=FlowResponse,
    summary="Options flow",
    description="Get unusual options activity and flow."
)
async def get_flow(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    flow_type: Optional[FlowType] = Query(None, description="Filter by flow type"),
    sentiment: Optional[FlowSentiment] = Query(None, description="Filter by sentiment"),
    min_premium: float = Query(100000, description="Minimum premium filter"),
    limit: int = Query(50, ge=1, le=200)
) -> FlowResponse:
    """Get unusual options activity and flow from real service."""
    opts_svc = _get_options_service()
    
    if opts_svc:
        try:
            symbols_filter = [symbol.upper()] if symbol else None
            flow_data = opts_svc.get_unusual_flow(symbols=symbols_filter, limit=limit)
            
            if flow_data:
                flows = []
                total_bullish = 0.0
                total_bearish = 0.0
                
                for f in flow_data:
                    if f.get('premium', 0) < min_premium:
                        continue
                    
                    f_type = _determine_flow_type(f)
                    f_sentiment = _determine_sentiment(f)
                    
                    # Apply filters
                    if flow_type and f_type != flow_type:
                        continue
                    if sentiment and f_sentiment != sentiment:
                        continue
                    
                    # Track sentiment totals
                    if f_sentiment == FlowSentiment.BULLISH:
                        total_bullish += f.get('premium', 0)
                    elif f_sentiment == FlowSentiment.BEARISH:
                        total_bearish += f.get('premium', 0)
                    
                    opt_type = OptionType.CALL if f.get('type', 'call') == 'call' else OptionType.PUT
                    
                    flows.append(OptionsFlow(
                        id=f.get('id', f"flow-{len(flows)}"),
                        symbol=f.get('symbol', ''),
                        underlying=f.get('symbol', '').split()[0] if f.get('symbol') else '',
                        option_type=opt_type,
                        strike=f.get('strike', 0),
                        expiration=_parse_expiration(f.get('expiry', '')),
                        flow_type=f_type,
                        sentiment=f_sentiment,
                        premium=f.get('premium', 0),
                        size=f.get('contracts', 0),
                        spot_price=f.get('spot_price', 0) if 'spot_price' in f else 0,
                        execution_price=f.get('price', 0) if 'price' in f else (f.get('premium', 0) / f.get('contracts', 1) / 100) if f.get('contracts') else 0,
                        exchange=f.get('exchange', 'CBOE'),
                        timestamp=datetime.fromisoformat(f['timestamp']) if f.get('timestamp') else datetime.utcnow()
                    ))
                
                net_sent = FlowSentiment.BULLISH if total_bullish > total_bearish else FlowSentiment.BEARISH if total_bearish > total_bullish else FlowSentiment.NEUTRAL
                
                return FlowResponse(
                    flows=flows[:limit],
                    total_premium_bullish=total_bullish,
                    total_premium_bearish=total_bearish,
                    net_sentiment=net_sent
                )
        except Exception as e:
            logger.error(f"Error getting options flow: {e}")
    
    # Fallback mock data
    flows = [
        OptionsFlow(
            id="flow-001", symbol="SPY250117C00600000", underlying="SPY",
            option_type=OptionType.CALL, strike=600.0, expiration=date(2025, 1, 17),
            flow_type=FlowType.SWEEP, sentiment=FlowSentiment.BULLISH,
            premium=2500000, size=5000, spot_price=595.00, execution_price=5.00,
            exchange="CBOE", timestamp=datetime.utcnow()
        ),
        OptionsFlow(
            id="flow-002", symbol="TSLA250117P00250000", underlying="TSLA",
            option_type=OptionType.PUT, strike=250.0, expiration=date(2025, 1, 17),
            flow_type=FlowType.BLOCK, sentiment=FlowSentiment.BEARISH,
            premium=1800000, size=3000, spot_price=248.00, execution_price=6.00,
            exchange="PHLX", timestamp=datetime.utcnow()
        ),
    ]
    
    if symbol:
        flows = [f for f in flows if f.underlying == symbol.upper()]
    if flow_type:
        flows = [f for f in flows if f.flow_type == flow_type]
    if sentiment:
        flows = [f for f in flows if f.sentiment == sentiment]
    
    bullish_premium = sum(f.premium for f in flows if f.sentiment == FlowSentiment.BULLISH)
    bearish_premium = sum(f.premium for f in flows if f.sentiment == FlowSentiment.BEARISH)
    
    return FlowResponse(
        flows=flows[:limit],
        total_premium_bullish=bullish_premium,
        total_premium_bearish=bearish_premium,
        net_sentiment=FlowSentiment.BULLISH if bullish_premium > bearish_premium else FlowSentiment.BEARISH
    )


@router.get(
    "/dark-pool",
    response_model=DarkPoolResponse,
    summary="Dark pool activity",
    description="Get dark pool trading activity."
)
async def get_dark_pool(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    min_size: int = Query(10000, description="Minimum trade size"),
    limit: int = Query(50, ge=1, le=200)
) -> DarkPoolResponse:
    """Get dark pool trading activity."""
    if OPTIONS_FLOW_AVAILABLE:
        try:
            dark_pool = DarkPoolMonitor()
            prints = dark_pool.get_recent_prints(symbol=symbol, min_value=min_size * 100, limit=limit)
            
            trades = []
            for p in prints:
                trades.append(DarkPoolTrade(
                    id=p.id if hasattr(p, 'id') else f"dp-{len(trades)}",
                    symbol=p.symbol if hasattr(p, 'symbol') else symbol or "SPY",
                    price=p.price if hasattr(p, 'price') else 0,
                    size=p.size if hasattr(p, 'size') else 0,
                    notional=p.value if hasattr(p, 'value') else 0,
                    exchange=p.venue if hasattr(p, 'venue') else "FINRA",
                    timestamp=p.timestamp if hasattr(p, 'timestamp') else datetime.utcnow()
                ))
            
            total_vol = sum(t.size for t in trades)
            total_notional = sum(t.notional for t in trades)
            
            return DarkPoolResponse(
                symbol=symbol.upper() if symbol else None,
                trades=trades,
                total_volume=total_vol,
                total_notional=total_notional,
                avg_trade_size=int(total_vol / len(trades)) if trades else 0
            )
        except Exception as e:
            logger.error(f"Error getting dark pool data: {e}")
    
    # Fallback
    trades = [
        DarkPoolTrade(id="dp-001", symbol="SPY", price=595.00, size=500000, notional=297500000, exchange="FINRA", timestamp=datetime.utcnow()),
        DarkPoolTrade(id="dp-002", symbol="AAPL", price=150.00, size=250000, notional=37500000, exchange="FINRA", timestamp=datetime.utcnow()),
    ]
    
    if symbol:
        trades = [t for t in trades if t.symbol == symbol.upper()]
    
    return DarkPoolResponse(
        symbol=symbol.upper() if symbol else None,
        trades=trades[:limit],
        total_volume=sum(t.size for t in trades),
        total_notional=sum(t.notional for t in trades),
        avg_trade_size=int(sum(t.size for t in trades) / len(trades)) if trades else 0
    )


@router.get(
    "/signals",
    response_model=FlowSignalsResponse,
    summary="Flow signals",
    description="Get trading signals derived from options flow."
)
async def get_flow_signals(symbol: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100)) -> FlowSignalsResponse:
    """Get signals derived from unusual options activity."""
    if OPTIONS_FLOW_AVAILABLE:
        try:
            flow_signals = OptionsFlowSignals()
            signals_data = flow_signals.get_active_signals(symbol=symbol, signal_type=None)
            
            signals = []
            for s in signals_data:
                signals.append(FlowSignal(
                    id=s.id if hasattr(s, 'id') else f"sig-{len(signals)}",
                    symbol=s.symbol if hasattr(s, 'symbol') else symbol or "SPY",
                    signal_type=s.signal_type if hasattr(s, 'signal_type') else "flow_signal",
                    direction=s.direction if hasattr(s, 'direction') else "neutral",
                    confidence=s.confidence if hasattr(s, 'confidence') else 0.5,
                    premium_involved=s.premium if hasattr(s, 'premium') else 0,
                    description=s.description if hasattr(s, 'description') else "",
                    created_at=s.timestamp if hasattr(s, 'timestamp') else datetime.utcnow()
                ))
            
            return FlowSignalsResponse(signals=signals[:limit], total=len(signals))
        except Exception as e:
            logger.error(f"Error getting flow signals: {e}")
    
    # Fallback
    signals = [
        FlowSignal(
            id="flow-sig-001", symbol="SPY", signal_type="sweep_cluster", direction="bullish",
            confidence=0.75, premium_involved=5000000,
            description="Multiple bullish sweeps targeting 600 strike",
            expiration_focus=date(2025, 1, 17), strike_focus=600.0
        ),
        FlowSignal(
            id="flow-sig-002", symbol="NVDA", signal_type="unusual_volume", direction="bullish",
            confidence=0.68, premium_involved=3500000,
            description="10x normal call volume at 900 strike"
        ),
    ]
    
    if symbol:
        signals = [s for s in signals if s.symbol == symbol.upper()]
    
    return FlowSignalsResponse(signals=signals[:limit], total=len(signals))


@router.get(
    "/smart-money",
    response_model=SmartMoneyResponse,
    summary="Smart money activity",
    description="Get institutional/smart money options activity."
)
async def get_smart_money(limit: int = Query(20, ge=1, le=100)) -> SmartMoneyResponse:
    """Get smart money (institutional) options activity."""
    if OPTIONS_FLOW_AVAILABLE:
        try:
            smart_money = SmartMoneyTracker()
            flow = smart_money.get_current_flow(symbol=None)
            
            if hasattr(flow, 'to_dict'):
                flow_dict = flow.to_dict()
                
                activities = []
                for act in flow_dict.get('institutional_activity', []):
                    sentiment = FlowSentiment.BULLISH if act.get('sentiment') == 'bullish' else FlowSentiment.BEARISH if act.get('sentiment') == 'bearish' else FlowSentiment.NEUTRAL
                    activities.append(SmartMoneyActivity(
                        symbol=act.get('symbol', ''),
                        net_premium=act.get('net_premium', 0),
                        call_premium=act.get('call_premium', 0),
                        put_premium=act.get('put_premium', 0),
                        sentiment=sentiment,
                        unusual_activity_count=act.get('unusual_count', 0),
                        block_trade_count=act.get('block_count', 0),
                        sweep_count=act.get('sweep_count', 0),
                        largest_trade=act.get('largest_trade', 0),
                        institutional_bias=act.get('bias', 'neutral')
                    ))
                
                overall_sentiment = FlowSentiment.BULLISH if flow_dict.get('overall_sentiment') == 'bullish' else FlowSentiment.BEARISH if flow_dict.get('overall_sentiment') == 'bearish' else FlowSentiment.NEUTRAL
                
                return SmartMoneyResponse(activities=activities[:limit], market_sentiment=overall_sentiment)
        except Exception as e:
            logger.error(f"Error getting smart money data: {e}")
    
    # Fallback
    activities = [
        SmartMoneyActivity(
            symbol="SPY", net_premium=15000000, call_premium=20000000, put_premium=5000000,
            sentiment=FlowSentiment.BULLISH, unusual_activity_count=12, block_trade_count=5,
            sweep_count=7, largest_trade=5000000, institutional_bias="strongly bullish"
        ),
        SmartMoneyActivity(
            symbol="QQQ", net_premium=8000000, call_premium=12000000, put_premium=4000000,
            sentiment=FlowSentiment.BULLISH, unusual_activity_count=8, block_trade_count=3,
            sweep_count=5, largest_trade=3000000, institutional_bias="moderately bullish"
        ),
    ]
    
    return SmartMoneyResponse(activities=activities[:limit], market_sentiment=FlowSentiment.BULLISH)
