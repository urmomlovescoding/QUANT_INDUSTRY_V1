"""
WebSocket Routes - FastAPI WebSocket Endpoints
QUANT_INDUSTRY_V1
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
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

# SECURITY: Input validation for WebSocket messages
_VALID_SYMBOL = re.compile(r'^[A-Za-z0-9.\-/^]{1,10}$')
_VALID_CHANNELS = {c.value for c in ChannelType}
_MAX_SYMBOLS = 50  # Maximum symbols per subscription


def _validate_ws_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize WebSocket message.

    Raises:
        ValueError: If message is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Message must be a JSON object")

    msg_type = data.get('type')
    if not isinstance(msg_type, str) or msg_type not in ('subscribe', 'unsubscribe', 'ping', 'pong'):
        raise ValueError(f"Invalid message type: {msg_type}")

    # Validate channel if present
    channel = data.get('channel')
    if channel is not None:
        if not isinstance(channel, str) or channel not in _VALID_CHANNELS:
            raise ValueError(f"Invalid channel: {channel}")

    # Validate symbols if present
    symbols = data.get('symbols', [])
    if symbols:
        if not isinstance(symbols, list):
            raise ValueError("symbols must be a list")
        if len(symbols) > _MAX_SYMBOLS:
            raise ValueError(f"Too many symbols (max {_MAX_SYMBOLS})")
        for sym in symbols:
            if not isinstance(sym, str) or not _VALID_SYMBOL.match(sym):
                raise ValueError(f"Invalid symbol: {sym}")

    # Validate filters if present
    filters = data.get('filters', {})
    if filters and not isinstance(filters, dict):
        raise ValueError("filters must be an object")

    return data


def _validate_symbol_param(symbol: str) -> str:
    """Validate URL symbol parameter."""
    if not symbol or not _VALID_SYMBOL.match(symbol):
        raise ValueError(f"Invalid symbol: {symbol}")
    return symbol.upper()


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
                # SECURITY: Validate message before processing
                validated_data = _validate_ws_message(data)
                await manager.handle_message(client_id, validated_data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    'type': 'error',
                    'error': 'Invalid JSON'
                })
            except ValueError as e:
                await websocket.send_json({
                    'type': 'error',
                    'error': str(e)
                })

    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception:
        await manager.disconnect(client_id)


@router.websocket("/market/{symbol}")
async def market_data_stream(websocket: WebSocket, symbol: str):
    """
    Direct WebSocket endpoint for single symbol market data.
    Simpler alternative to main endpoint for single-symbol streaming.
    """
    manager = get_ws_manager()

    # SECURITY: Validate symbol parameter
    try:
        symbol = _validate_symbol_param(symbol)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid symbol")
        return

    try:
        client_id = await manager.connect(websocket)

        # Auto-subscribe to market data for this symbol
        await manager.handle_message(client_id, {
            'type': 'subscribe',
            'channel': ChannelType.MARKET_DATA.value,
            'symbols': [symbol]
        })

        while True:
            try:
                data = await websocket.receive_json()
                validated_data = _validate_ws_message(data)
                await manager.handle_message(client_id, validated_data)
            except (json.JSONDecodeError, ValueError):
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
