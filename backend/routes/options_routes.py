"""
Options Routes
==============
Endpoints for options chains, GEX analysis, and options flow.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from ._shared import (
    logger, SERVICES_AVAILABLE,
    get_data_service, get_options_service, get_gex_analyzer
)

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options/chain/{symbol}")
async def get_options_chain(
    symbol: str,
    expiration: Optional[str] = None,
    option_type: str = "ALL"
):
    """Get real options chain for a symbol"""
    symbol = symbol.upper()
    try:
        opts = get_options_service()
        chain_data = opts.get_options_chain(symbol)

        if not chain_data:
            raise HTTPException(status_code=404, detail=f"No options data for {symbol}")

        if expiration:
            calls = [c for c in chain_data.calls if c.expiration == expiration]
            puts = [p for p in chain_data.puts if p.expiration == expiration]
        else:
            expiration = chain_data.expirations[0] if chain_data.expirations else None
            calls = [c for c in chain_data.calls if c.expiration == expiration][:20]
            puts = [p for p in chain_data.puts if p.expiration == expiration][:20]

        chain = []
        if option_type in ["ALL", "CALL"]:
            for c in calls:
                chain.append({
                    "expiration": c.expiration, "strike": c.strike, "option_type": "CALL",
                    "bid": c.bid, "ask": c.ask, "iv": round(c.implied_volatility * 100, 1),
                    "delta": round(c.greeks.delta, 3) if c.greeks else 0,
                    "oi": c.open_interest, "volume": c.volume
                })
        if option_type in ["ALL", "PUT"]:
            for p in puts:
                chain.append({
                    "expiration": p.expiration, "strike": p.strike, "option_type": "PUT",
                    "bid": p.bid, "ask": p.ask, "iv": round(p.implied_volatility * 100, 1),
                    "delta": round(p.greeks.delta, 3) if p.greeks else 0,
                    "oi": p.open_interest, "volume": p.volume
                })

        return {
            "symbol": symbol,
            "underlying_price": chain_data.underlying_price,
            "expirations": chain_data.expirations,
            "chain": chain
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/gex/{symbol}")
async def get_gex_analysis(symbol: str, max_dte: int = 45):
    """Get real Gamma Exposure (GEX) analysis"""
    symbol = symbol.upper()
    try:
        opts = get_options_service()
        gex = get_gex_analyzer()

        chain_data = opts.get_options_chain(symbol)
        if not chain_data:
            raise HTTPException(status_code=404, detail=f"No options data for {symbol}")

        gex_data = gex.analyze(symbol, chain_data)

        return {
            "symbol": symbol,
            "current_price": gex_data.underlying_price,
            "data": [{"strike": s.strike, "call_gex": s.call_gex, "put_gex": s.put_gex, "total_gex": s.net_gex}
                     for s in gex_data.strikes],
            "summary": {
                "net_gex": round(gex_data.total_net_gex / 1e9, 2),
                "gex_flip_point": gex_data.zero_gamma_level,
                "max_pain": gex_data.max_gamma_strike,
                "call_wall": gex_data.call_wall,
                "put_wall": gex_data.put_wall,
                "bias": gex_data.bias
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gex/{symbol}")
async def get_gex_alias(symbol: str):
    """Alias for GEX analysis"""
    return await get_gex_analysis(symbol)


@router.get("/options/flow")
async def get_options_flow(symbols: Optional[str] = None, limit: int = 20):
    """Get unusual options flow"""
    try:
        if SERVICES_AVAILABLE:
            opts = get_options_service()
            symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
            flow_data = opts.get_unusual_flow(symbols=symbol_list, limit=limit)
            if flow_data:
                return flow_data

        return {
            "status": "unavailable",
            "flow": [],
            "_note": "Options flow requires Tradier API connection",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Options flow error: {e}")
        return []
