"""
QUANT INDUSTRY V1 - WebSocket API (v2)
======================================
Unified WebSocket stream with channel subscriptions.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum
import json
import asyncio

router = APIRouter()


# ============================================================================
# Enums
# ============================================================================

class WSChannel(str, Enum):
    """WebSocket channel types."""
    MARKET = "market"
    SIGNALS = "signals"
    POSITIONS = "positions"
    RISK = "risk"
    BRAIN = "brain"
    SYSTEM = "system"
    ORDERS = "orders"
    FLOW = "flow"  # Options flow


class WSAction(str, Enum):
    """WebSocket action types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    FILTER = "filter"
    PING = "ping"


class WSMessageType(str, Enum):
    """WebSocket message types."""
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    DATA = "data"
    ERROR = "error"
    PONG = "pong"
    CONNECTED = "connected"


# ============================================================================
# Pydantic Models
# ============================================================================

class WSSubscribeRequest(BaseModel):
    """Subscribe request."""
    action: WSAction = WSAction.SUBSCRIBE
    channels: list[WSChannel]


class WSFilterRequest(BaseModel):
    """Filter request for a channel."""
    action: WSAction = WSAction.FILTER
    channel: WSChannel
    symbols: Optional[list[str]] = None
    filters: Optional[dict[str, Any]] = None


class WSMessage(BaseModel):
    """WebSocket message format."""
    type: WSMessageType
    channel: Optional[WSChannel] = None
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class MarketUpdate(BaseModel):
    """Market data update."""
    symbol: str
    last: float
    bid: float
    ask: float
    volume: int
    change: float
    change_percent: float
    timestamp: datetime


class SignalUpdate(BaseModel):
    """Signal update."""
    signal_id: str
    symbol: str
    direction: str
    confidence: float
    entry_price: float
    status: str
    timestamp: datetime


class PositionUpdate(BaseModel):
    """Position update."""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    timestamp: datetime


class RiskUpdate(BaseModel):
    """Risk alert update."""
    alert_id: str
    severity: str
    category: str
    message: str
    timestamp: datetime


class BrainUpdate(BaseModel):
    """Brain status update."""
    status: str
    regime: str
    signals_count: int
    last_signal: Optional[datetime] = None
    timestamp: datetime


class SystemUpdate(BaseModel):
    """System status update."""
    cpu_percent: float
    memory_percent: float
    active_connections: int
    timestamp: datetime


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[WSChannel]] = {}
        self.filters: dict[str, dict[WSChannel, dict]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        self.filters[client_id] = {}
        
        # Send connected message
        await self.send_message(client_id, WSMessage(
            type=WSMessageType.CONNECTED,
            data={"client_id": client_id, "available_channels": [c.value for c in WSChannel]}
        ))
    
    def disconnect(self, client_id: str):
        """Remove a connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.subscriptions:
            del self.subscriptions[client_id]
        if client_id in self.filters:
            del self.filters[client_id]
    
    async def subscribe(self, client_id: str, channels: list[WSChannel]):
        """Subscribe to channels."""
        if client_id in self.subscriptions:
            for channel in channels:
                self.subscriptions[client_id].add(channel)
            
            await self.send_message(client_id, WSMessage(
                type=WSMessageType.SUBSCRIBED,
                data={"channels": [c.value for c in channels]}
            ))
    
    async def unsubscribe(self, client_id: str, channels: list[WSChannel]):
        """Unsubscribe from channels."""
        if client_id in self.subscriptions:
            for channel in channels:
                self.subscriptions[client_id].discard(channel)
            
            await self.send_message(client_id, WSMessage(
                type=WSMessageType.UNSUBSCRIBED,
                data={"channels": [c.value for c in channels]}
            ))
    
    async def set_filter(self, client_id: str, channel: WSChannel, filters: dict):
        """Set filters for a channel."""
        if client_id in self.filters:
            self.filters[client_id][channel] = filters
    
    async def send_message(self, client_id: str, message: WSMessage):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message.model_dump(mode='json'))
    
    async def broadcast_to_channel(self, channel: WSChannel, data: Any):
        """Broadcast data to all subscribers of a channel."""
        message = WSMessage(
            type=WSMessageType.DATA,
            channel=channel,
            data=data
        )
        
        for client_id, channels in self.subscriptions.items():
            if channel in channels:
                # Apply filters if any
                if self._should_send(client_id, channel, data):
                    await self.send_message(client_id, message)
    
    def _should_send(self, client_id: str, channel: WSChannel, data: Any) -> bool:
        """Check if data should be sent based on filters."""
        if client_id not in self.filters:
            return True
        
        channel_filters = self.filters[client_id].get(channel, {})
        if not channel_filters:
            return True
        
        # Apply symbol filter
        symbols = channel_filters.get("symbols")
        if symbols and hasattr(data, "symbol"):
            if data.symbol not in symbols:
                return False
        
        return True


# Global connection manager
manager = ConnectionManager()


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/stream")
async def websocket_stream(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None)
):
    """
    Unified WebSocket stream endpoint.
    
    Connect and subscribe to channels:
    - market: Real-time market data
    - signals: Trading signals from brain
    - positions: Position updates
    - risk: Risk alerts
    - brain: Brain status updates
    - system: System status
    - orders: Order status updates
    - flow: Options flow
    
    Message format:
    
    Subscribe:
    ```json
    {"action": "subscribe", "channels": ["market", "signals"]}
    ```
    
    Filter:
    ```json
    {"action": "filter", "channel": "market", "symbols": ["SPY", "QQQ"]}
    ```
    
    Ping:
    ```json
    {"action": "ping"}
    ```
    """
    # Generate client ID if not provided
    if not client_id:
        import uuid
        client_id = str(uuid.uuid4())[:8]
    
    await manager.connect(websocket, client_id)
    
    try:
        # Start background tasks for demo data
        demo_task = asyncio.create_task(send_demo_data(client_id))
        
        while True:
            # Receive and process messages
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                
                if action == "subscribe":
                    channels = [WSChannel(c) for c in message.get("channels", [])]
                    await manager.subscribe(client_id, channels)
                
                elif action == "unsubscribe":
                    channels = [WSChannel(c) for c in message.get("channels", [])]
                    await manager.unsubscribe(client_id, channels)
                
                elif action == "filter":
                    channel = WSChannel(message.get("channel"))
                    filters = {
                        "symbols": message.get("symbols"),
                        **message.get("filters", {})
                    }
                    await manager.set_filter(client_id, channel, filters)
                
                elif action == "ping":
                    await manager.send_message(client_id, WSMessage(
                        type=WSMessageType.PONG,
                        data={"timestamp": datetime.utcnow().isoformat()}
                    ))
                
                else:
                    await manager.send_message(client_id, WSMessage(
                        type=WSMessageType.ERROR,
                        error=f"Unknown action: {action}"
                    ))
            
            except json.JSONDecodeError:
                await manager.send_message(client_id, WSMessage(
                    type=WSMessageType.ERROR,
                    error="Invalid JSON"
                ))
            except ValueError as e:
                await manager.send_message(client_id, WSMessage(
                    type=WSMessageType.ERROR,
                    error=str(e)
                ))
    
    except WebSocketDisconnect:
        demo_task.cancel()
        manager.disconnect(client_id)
    except Exception as e:
        demo_task.cancel()
        manager.disconnect(client_id)


async def send_demo_data(client_id: str):
    """Send demo data for subscribed channels."""
    import random
    
    while True:
        try:
            await asyncio.sleep(1)  # Update every second
            
            if client_id not in manager.subscriptions:
                break
            
            subscriptions = manager.subscriptions[client_id]
            
            # Market updates
            if WSChannel.MARKET in subscriptions:
                for symbol in ["SPY", "QQQ", "AAPL"]:
                    base_price = {"SPY": 595.0, "QQQ": 510.0, "AAPL": 152.0}[symbol]
                    update = MarketUpdate(
                        symbol=symbol,
                        last=base_price + random.uniform(-0.5, 0.5),
                        bid=base_price - 0.02,
                        ask=base_price + 0.02,
                        volume=random.randint(1000000, 5000000),
                        change=random.uniform(-2, 2),
                        change_percent=random.uniform(-0.5, 0.5),
                        timestamp=datetime.utcnow()
                    )
                    await manager.broadcast_to_channel(WSChannel.MARKET, update.model_dump(mode='json'))
            
            # System updates (every 5 seconds)
            if WSChannel.SYSTEM in subscriptions:
                update = SystemUpdate(
                    cpu_percent=random.uniform(20, 60),
                    memory_percent=random.uniform(40, 70),
                    active_connections=len(manager.active_connections),
                    timestamp=datetime.utcnow()
                )
                await manager.broadcast_to_channel(WSChannel.SYSTEM, update.model_dump(mode='json'))
        
        except asyncio.CancelledError:
            break
        except Exception:
            pass


# ============================================================================
# REST Endpoints for WebSocket Info
# ============================================================================

@router.get(
    "/info",
    summary="WebSocket info",
    description="Get WebSocket connection information."
)
async def get_ws_info() -> dict:
    """
    Get WebSocket endpoint information.
    """
    return {
        "endpoint": "/ws/v2/stream",
        "protocol": "wss",
        "available_channels": [c.value for c in WSChannel],
        "message_format": {
            "subscribe": {"action": "subscribe", "channels": ["market", "signals"]},
            "unsubscribe": {"action": "unsubscribe", "channels": ["market"]},
            "filter": {"action": "filter", "channel": "market", "symbols": ["SPY"]},
            "ping": {"action": "ping"}
        },
        "active_connections": len(manager.active_connections)
    }


@router.get(
    "/channels",
    summary="List channels",
    description="Get available WebSocket channels."
)
async def list_channels() -> dict:
    """
    List available WebSocket channels and their descriptions.
    """
    return {
        "channels": {
            "market": "Real-time market quotes and trades",
            "signals": "Trading signals from ML brain",
            "positions": "Position updates and P&L",
            "risk": "Risk alerts and warnings",
            "brain": "ML brain status and regime changes",
            "system": "System health and metrics",
            "orders": "Order status updates",
            "flow": "Unusual options flow"
        }
    }
