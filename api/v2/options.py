"""
V2 Options Router
=================
Options chain, GEX, flow analysis.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()


class OptionContract(BaseModel):
    """Option contract details."""
    expiration: str
    strike: float
    option_type: str  # call, put
    bid: float
    ask: float
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    oi: int
    volume: int


class GEXLevel(BaseModel):
    """GEX level."""
    strike: float
    gex: float


class GEXData(BaseModel):
    """Gamma Exposure data."""
    symbol: str
    total_gex: float
    call_gex: float
    put_gex: float
    key_levels: List[GEXLevel]
    flip_point: float


class OptionsFlow(BaseModel):
    """Options flow entry."""
    id: str
    symbol: str
    type: str  # call, put
    side: str  # buy, sell
    sentiment: str  # bullish, bearish
    strike: float
    expiry: str
    premium: float
    contracts: int
    is_unusual: bool
    is_sweep: bool
    timestamp: str


class DarkPoolData(BaseModel):
    """Dark pool activity."""
    symbol: str
    short_volume: int
    short_pct: float
    dark_pool_volume: int
    dark_pool_pct: float
    timestamp: str


class FlowSignal(BaseModel):
    """Flow-derived signal."""
    symbol: str
    direction: str
    confidence: float
    flow_type: str  # unusual, sweep, block
    details: str


class SmartMoneyActivity(BaseModel):
    """Smart money/institutional activity."""
    symbol: str
    activity_type: str
    size: float
    sentiment: str
    timestamp: str


@router.get("/chain/{symbol}", response_model=List[OptionContract])
async def get_options_chain(
    symbol: str,
    expiration: Optional[str] = Query(None, description="Specific expiration date"),
    option_type: str = Query("ALL", description="ALL, CALL, or PUT")
):
    """
    Get options chain for a symbol.
    
    Args:
        symbol: Ticker symbol
        expiration: Optional specific expiration
        option_type: Filter by call/put
        
    Returns:
        List of option contracts
    """
    contracts = [
        OptionContract(
            expiration="2026-02-21",
            strike=700.0,
            option_type="call",
            bid=5.50,
            ask=5.60,
            iv=0.20,
            delta=0.45,
            gamma=0.02,
            theta=-0.05,
            vega=0.15,
            oi=10000,
            volume=5000
        ),
        OptionContract(
            expiration="2026-02-21",
            strike=700.0,
            option_type="put",
            bid=4.50,
            ask=4.60,
            iv=0.22,
            delta=-0.40,
            gamma=0.02,
            theta=-0.04,
            vega=0.14,
            oi=8000,
            volume=3000
        )
    ]
    if option_type != "ALL":
        contracts = [c for c in contracts if c.option_type == option_type.lower()]
    return contracts


@router.get("/gex/{symbol}", response_model=GEXData)
async def get_gex(symbol: str):
    """
    Get Gamma Exposure (GEX) data.
    
    Returns total GEX, key levels, and flip point.
    """
    return GEXData(
        symbol=symbol.upper(),
        total_gex=500000000.0,
        call_gex=800000000.0,
        put_gex=-300000000.0,
        key_levels=[
            GEXLevel(strike=700.0, gex=150000000.0),
            GEXLevel(strike=690.0, gex=100000000.0),
            GEXLevel(strike=710.0, gex=80000000.0)
        ],
        flip_point=695.0
    )


@router.get("/flow", response_model=List[OptionsFlow])
async def get_options_flow(
    unusual: bool = Query(False, description="Filter unusual activity only"),
    sweep: bool = Query(False, description="Filter sweeps only"),
    smart_money: bool = Query(False, description="Filter smart money only")
):
    """
    Get options flow data.
    
    Args:
        unusual: Filter for unusual activity
        sweep: Filter for sweeps
        smart_money: Filter for institutional activity
        
    Returns:
        List of flow entries
    """
    flows = [
        OptionsFlow(
            id="flow_001",
            symbol="SPY",
            type="call",
            side="buy",
            sentiment="bullish",
            strike=700.0,
            expiry="2026-02-21",
            premium=250000.0,
            contracts=500,
            is_unusual=True,
            is_sweep=True,
            timestamp=datetime.utcnow().isoformat()
        )
    ]
    if unusual:
        flows = [f for f in flows if f.is_unusual]
    if sweep:
        flows = [f for f in flows if f.is_sweep]
    return flows


@router.get("/dark-pool", response_model=List[DarkPoolData])
async def get_dark_pool():
    """Get dark pool activity."""
    return [
        DarkPoolData(
            symbol="SPY",
            short_volume=50000000,
            short_pct=0.35,
            dark_pool_volume=80000000,
            dark_pool_pct=0.45,
            timestamp=datetime.utcnow().isoformat()
        )
    ]


@router.get("/signals", response_model=List[FlowSignal])
async def get_flow_signals():
    """Get flow-derived trading signals."""
    return [
        FlowSignal(
            symbol="SPY",
            direction="LONG",
            confidence=0.75,
            flow_type="unusual",
            details="Large call sweep at 700 strike"
        )
    ]


@router.get("/smart-money", response_model=List[SmartMoneyActivity])
async def get_smart_money():
    """Get smart money/institutional activity."""
    return [
        SmartMoneyActivity(
            symbol="SPY",
            activity_type="block_trade",
            size=500000.0,
            sentiment="bullish",
            timestamp=datetime.utcnow().isoformat()
        )
    ]
