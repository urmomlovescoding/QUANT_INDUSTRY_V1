"""
WebSocket Routes - FastAPI WebSocket Endpoints
QUANT_INDUSTRY_V1
"""

import asyncio
import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import JSONResponse

from .manager import (
    get_ws_manager, 
    WebSocketManager,
    ChannelType,
    MarketDataStreamer,
    SignalStreamer,
    RiskStreamer,
    ExecutionStreamer
)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time data streaming.
    
    Protocol:
    1. Connect to this endpoint
    2. Receive welcome message with client_id and available channels
    3. Send subscription messages to subscribe to channels
    4. Receive real-time data updates
    
    Subscription message format:
    {
        "type": "subscribe",
        "channel": "market_data",
        "symbols": ["AAPL", "GOOGL"]
    }
    
    Unsubscription message format:
    {
        "type": "unsubscribe",
        "channel": "market_data"
    }
    """
    manager = get_ws_manager()
    
    try:
        client_id = await manager.connect(websocket)
        
        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    'type': 'error',
                    'error': 'Invalid JSON'
                })
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        await manager.disconnect(client_id)


@router.websocket("/market/{symbol}")
async def market_data_stream(websocket: WebSocket, symbol: str):
    """
    Direct WebSocket endpoint for single symbol market data.
    Simpler alternative to main endpoint for single-symbol streaming.
    """
    manager = get_ws_manager()
    
    try:
        client_id = await manager.connect(websocket)
        
        # Auto-subscribe to market data for this symbol
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.MARKET_DATA.value,
            'symbols': [symbol.upper()]
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


@router.websocket("/orderbook/{symbol}")
async def orderbook_stream(websocket: WebSocket, symbol: str):
    """Direct WebSocket endpoint for order book updates."""
    manager = get_ws_manager()
    
    try:
        client_id = await manager.connect(websocket)
        
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.ORDER_BOOK.value,
            'symbols': [symbol.upper()]
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


@router.websocket("/signals")
async def signals_stream(websocket: WebSocket):
    """Direct WebSocket endpoint for trading signals."""
    manager = get_ws_manager()
    
    try:
        client_id = await manager.connect(websocket)
        
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.SIGNALS.value
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


@router.websocket("/risk")
async def risk_stream(websocket: WebSocket):
    """Direct WebSocket endpoint for risk metrics."""
    manager = get_ws_manager()
    
    try:
        client_id = await manager.connect(websocket)
        
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.RISK.value
        })
        
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.ALERTS.value
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


@router.websocket("/executions")
async def executions_stream(websocket: WebSocket):
    """Direct WebSocket endpoint for execution updates."""
    manager = get_ws_manager()
    
    try:
        client_id = await manager.connect(websocket)
        
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.EXECUTIONS.value
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        await manager.disconnect(client_id)


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket manager statistics."""
    manager = get_ws_manager()
    return manager.get_stats()


@router.get("/channels")
async def list_channels():
    """List available WebSocket channels."""
    return {
        'channels': [
            {
                'name': channel.value,
                'description': _get_channel_description(channel)
            }
            for channel in ChannelType
        ]
    }


def _get_channel_description(channel: ChannelType) -> str:
    """Get description for a channel."""
    descriptions = {
        ChannelType.MARKET_DATA: "Real-time price quotes, bid/ask, volume",
        ChannelType.ORDER_BOOK: "Level 2 order book updates",
        ChannelType.SIGNALS: "Trading signals from alpha models",
        ChannelType.PORTFOLIO: "Portfolio position and P&L updates",
        ChannelType.RISK: "Risk metrics (VaR, exposure, drawdown)",
        ChannelType.EXECUTIONS: "Order execution status updates",
        ChannelType.ALERTS: "Risk alerts and system notifications",
        ChannelType.SYSTEM: "System status and health updates"
    }
    return descriptions.get(channel, "")
