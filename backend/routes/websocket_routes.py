"""
WebSocket Routes
================
Real-time WebSocket endpoints for market data, signals, and system status.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ._shared import (
    logger, SERVICES_AVAILABLE, PROPFIRM_BRAIN_V6_AVAILABLE,
    MARKET_DATA, refresh_market_data, get_data_service
)

router = APIRouter(tags=["websocket"])


# ============== CONNECTION MANAGER ==============

class AdvancedConnectionManager:
    """WebSocket connection manager with channel subscriptions."""
    
    def __init__(self):
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.channel_subscribers: Dict[str, set] = {
            "market": set(), "signals": set(), "trades": set(),
            "brain": set(), "system": set(), "flow": set()
        }
        self.connection_counter = 0

    def generate_connection_id(self) -> str:
        self.connection_counter += 1
        return f"conn_{self.connection_counter}_{datetime.now().strftime('%H%M%S')}"

    async def connect(self, websocket: WebSocket, channels: List[str] = None) -> str:
        await websocket.accept()
        connection_id = self.generate_connection_id()
        channels = channels or ["market"]
        
        self.connections[connection_id] = {
            "websocket": websocket,
            "channels": set(channels),
            "connected_at": datetime.now(),
            "message_count": 0
        }

        for channel in channels:
            if channel in self.channel_subscribers:
                self.channel_subscribers[channel].add(connection_id)

        logger.info(f"WebSocket connected: {connection_id}")
        return connection_id

    def disconnect(self, connection_id: str):
        if connection_id in self.connections:
            for channel in self.connections[connection_id]["channels"]:
                if channel in self.channel_subscribers:
                    self.channel_subscribers[channel].discard(connection_id)
            del self.connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")

    async def send_to_connection(self, connection_id: str, message: Dict):
        if connection_id in self.connections:
            try:
                await self.connections[connection_id]["websocket"].send_text(json.dumps(message))
                self.connections[connection_id]["message_count"] += 1
            except Exception:
                self.disconnect(connection_id)

    async def broadcast_to_channel(self, channel: str, message: Dict):
        if channel not in self.channel_subscribers:
            return
        message["channel"] = channel
        message["timestamp"] = datetime.now().isoformat()
        
        disconnected = []
        for connection_id in self.channel_subscribers[channel].copy():
            if connection_id in self.connections:
                try:
                    await self.connections[connection_id]["websocket"].send_text(json.dumps(message))
                except Exception:
                    disconnected.append(connection_id)
        
        for conn_id in disconnected:
            self.disconnect(conn_id)

    def get_stats(self) -> Dict:
        return {
            "total_connections": len(self.connections),
            "channel_counts": {ch: len(subs) for ch, subs in self.channel_subscribers.items()}
        }


ws_manager = AdvancedConnectionManager()


# ============== DATA ENGINE ==============

class RealTimeDataEngine:
    """Engine for generating real-time data using live sources."""
    
    def __init__(self):
        self.signal_history: List[Dict] = []
        self.trade_history: List[Dict] = []
        self._data_service = None
        self._quote_cache = {}

    def _get_data_service(self):
        if self._data_service is None:
            self._data_service = get_data_service()
        return self._data_service

    def generate_market_tick(self, symbol: str, base_price: float) -> Dict:
        try:
            ds = self._get_data_service()
            quote = ds.get_quote(symbol)
            if quote:
                return {
                    "symbol": symbol,
                    "price": quote.price,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "volume": quote.volume,
                    "change": quote.change,
                    "change_pct": quote.change_pct,
                    "source": quote.source,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.debug(f"WebSocket quote fetch failed: {e}")

        return {
            "symbol": symbol,
            "price": base_price,
            "source": "unavailable",
            "is_stale": True,
            "timestamp": datetime.now().isoformat()
        }

    def generate_brain_update(self) -> Dict:
        try:
            if PROPFIRM_BRAIN_V6_AVAILABLE:
                from brain.propfirm_brain_v6 import get_propfirm_brain_v6
                brain = get_propfirm_brain_v6()
                status = brain.get_status()
                return {
                    "type": "brain_update",
                    "is_trained": status.get("is_trained", False),
                    "total_trades": status.get("total_trades", 0),
                    "timestamp": datetime.now().isoformat()
                }
        except Exception:
            pass
        return {"type": "brain_update", "data_status": "UNAVAILABLE"}

    def generate_system_health(self) -> Dict:
        try:
            import psutil
            return {
                "type": "system_health",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "active_connections": len(ws_manager.connections),
                "timestamp": datetime.now().isoformat()
            }
        except ImportError:
            return {"type": "system_health", "error": "psutil not available"}


data_engine = RealTimeDataEngine()


# ============== WEBSOCKET ENDPOINTS ==============

async def _handle_unified_websocket(websocket: WebSocket):
    """
    Internal handler for unified WebSocket connections.
    Supports multiple channel subscriptions and heartbeat.
    """
    connection_id = await ws_manager.connect(websocket, ["market"])

    try:
        await ws_manager.send_to_connection(connection_id, {
            "type": "connected",
            "connection_id": connection_id,
            "available_channels": list(ws_manager.channel_subscribers.keys())
        })

        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                data = json.loads(message)

                # Handle subscription requests
                # Supports both formats:
                # - { action: 'subscribe', channels: [...] }
                # - { type: 'subscribe', channel: '...' } (legacy frontend format)
                if data.get("action") == "subscribe" or data.get("type") == "subscribe":
                    channels = data.get("channels", [])
                    # Support single channel format
                    if data.get("channel"):
                        channels.append(data.get("channel"))

                    for channel in channels:
                        if channel in ws_manager.channel_subscribers:
                            ws_manager.connections[connection_id]["channels"].add(channel)
                            ws_manager.channel_subscribers[channel].add(connection_id)

                    await ws_manager.send_to_connection(connection_id, {
                        "type": "subscribed",
                        "channels": list(ws_manager.connections[connection_id]["channels"])
                    })

                # Handle ping/heartbeat
                elif data.get("action") == "ping" or data.get("type") == "heartbeat":
                    await ws_manager.send_to_connection(connection_id, {"type": "pong"})

            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id)


@router.websocket("/ws/unified")
async def websocket_unified(websocket: WebSocket):
    """Unified WebSocket supporting multiple channel subscriptions."""
    await _handle_unified_websocket(websocket)


@router.websocket("/ws/connect")
async def websocket_connect(websocket: WebSocket):
    """
    Alias for /ws/unified for frontend compatibility.
    The frontend may try to connect to /ws/connect by default.
    """
    await _handle_unified_websocket(websocket)


@router.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    """WebSocket for real-time market data."""
    connection_id = await ws_manager.connect(websocket, ["market"])
    last_refresh = datetime.now()

    try:
        while True:
            if connection_id not in ws_manager.connections:
                break

            if (datetime.now() - last_refresh).total_seconds() >= 10:
                refresh_market_data()
                last_refresh = datetime.now()

            tickers = []
            for symbol, data in MARKET_DATA.items():
                tickers.append({
                    "symbol": symbol,
                    "price": data.get("price", 0),
                    "change": data.get("change", 0),
                    "change_pct": data.get("change_pct", 0),
                    "source": data.get("source", "live"),
                    "timestamp": datetime.now().isoformat()
                })

            try:
                await websocket.send_json({
                    "type": "market_update",
                    "data": tickers,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception:
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(connection_id)


@router.websocket("/ws/brain")
async def websocket_brain(websocket: WebSocket):
    """WebSocket for brain status and metrics."""
    connection_id = await ws_manager.connect(websocket, ["brain"])

    try:
        while True:
            brain_update = data_engine.generate_brain_update()
            await ws_manager.send_to_connection(connection_id, brain_update)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id)


@router.websocket("/ws/system")
async def websocket_system(websocket: WebSocket):
    """WebSocket for system health monitoring."""
    connection_id = await ws_manager.connect(websocket, ["system"])

    try:
        while True:
            health = data_engine.generate_system_health()
            await ws_manager.send_to_connection(connection_id, health)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id)


# ============== MANAGEMENT ENDPOINTS ==============

@router.get("/api/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics"""
    return ws_manager.get_stats()
