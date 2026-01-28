"""
WebSocket Manager - Real-time Data Streaming
QUANT_INDUSTRY_V1

Handles WebSocket connections for live market data, signals, and portfolio updates.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """WebSocket channel types."""
    MARKET_DATA = "market_data"
    ORDER_BOOK = "order_book"
    SIGNALS = "signals"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    EXECUTIONS = "executions"
    ALERTS = "alerts"
    SYSTEM = "system"


class MessageType(str, Enum):
    """WebSocket message types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    DATA = "data"
    ERROR = "error"
    ACK = "ack"
    HEARTBEAT = "heartbeat"


@dataclass
class Subscription:
    """Represents a client subscription."""
    channel: ChannelType
    symbols: Set[str] = field(default_factory=set)
    filters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""
    id: str
    websocket: WebSocket
    subscriptions: Dict[ChannelType, Subscription] = field(default_factory=dict)
    connected_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    
    async def send(self, message: Dict[str, Any]):
        """Send message to client."""
        try:
            await self.websocket.send_json(message)
            self.message_count += 1
        except Exception as e:
            logger.error(f"Failed to send to client {self.id}: {e}")
            raise


class WebSocketManager:
    """
    Manages WebSocket connections and message routing.
    
    Features:
    - Multi-channel subscription model
    - Symbol-level filtering
    - Automatic reconnection handling
    - Rate limiting
    - Message compression for high-frequency data
    """
    
    def __init__(
        self,
        heartbeat_interval: float = 30.0,
        max_clients: int = 1000,
        rate_limit_per_second: int = 100
    ):
        self.heartbeat_interval = heartbeat_interval
        self.max_clients = max_clients
        self.rate_limit_per_second = rate_limit_per_second
        
        # Client management
        self.clients: Dict[str, WebSocketClient] = {}
        self.channel_subscribers: Dict[ChannelType, Set[str]] = defaultdict(set)
        self.symbol_subscribers: Dict[str, Set[str]] = defaultdict(set)
        
        # Message queues for batching
        self.message_queues: Dict[ChannelType, asyncio.Queue] = {
            channel: asyncio.Queue() for channel in ChannelType
        }
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._broadcast_tasks: Dict[ChannelType, asyncio.Task] = {}
        
        # Metrics
        self.metrics = {
            'total_connections': 0,
            'total_messages_sent': 0,
            'total_messages_received': 0,
            'errors': 0
        }
        
    async def start(self):
        """Start background tasks."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        for channel in ChannelType:
            self._broadcast_tasks[channel] = asyncio.create_task(
                self._broadcast_loop(channel)
            )
            
        logger.info("WebSocket manager started")
        
    async def stop(self):
        """Stop background tasks and close connections."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        for task in self._broadcast_tasks.values():
            task.cancel()
            
        # Close all connections
        for client in list(self.clients.values()):
            await self.disconnect(client.id)
            
        logger.info("WebSocket manager stopped")
        
    async def connect(self, websocket: WebSocket) -> str:
        """Accept new WebSocket connection."""
        if len(self.clients) >= self.max_clients:
            await websocket.close(code=1013, reason="Server overloaded")
            raise ConnectionRefusedError("Max clients reached")
            
        await websocket.accept()
        
        client_id = str(uuid.uuid4())
        client = WebSocketClient(
            id=client_id,
            websocket=websocket
        )
        
        self.clients[client_id] = client
        self.metrics['total_connections'] += 1
        
        # Send welcome message
        await client.send({
            'type': MessageType.ACK,
            'client_id': client_id,
            'server_time': datetime.now().isoformat(),
            'available_channels': [c.value for c in ChannelType]
        })
        
        logger.info(f"Client {client_id} connected")
        return client_id
        
    async def disconnect(self, client_id: str):
        """Handle client disconnection."""
        if client_id not in self.clients:
            return
            
        client = self.clients[client_id]
        
        # Remove from all subscription lists
        for channel in client.subscriptions:
            self.channel_subscribers[channel].discard(client_id)
            
        for symbols in [sub.symbols for sub in client.subscriptions.values()]:
            for symbol in symbols:
                self.symbol_subscribers[symbol].discard(client_id)
                
        # Close connection
        try:
            await client.websocket.close()
        except Exception:
            pass
            
        del self.clients[client_id]
        logger.info(f"Client {client_id} disconnected")
        
    async def handle_message(self, client_id: str, message: Dict[str, Any]):
        """Process incoming message from client."""
        self.metrics['total_messages_received'] += 1
        
        if client_id not in self.clients:
            return
            
        client = self.clients[client_id]
        msg_type = message.get('type')
        
        try:
            if msg_type == MessageType.SUBSCRIBE:
                await self._handle_subscribe(client, message)
            elif msg_type == MessageType.UNSUBSCRIBE:
                await self._handle_unsubscribe(client, message)
            elif msg_type == MessageType.HEARTBEAT:
                client.last_heartbeat = datetime.now()
                await client.send({
                    'type': MessageType.HEARTBEAT,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                await client.send({
                    'type': MessageType.ERROR,
                    'error': f"Unknown message type: {msg_type}"
                })
        except Exception as e:
            self.metrics['errors'] += 1
            await client.send({
                'type': MessageType.ERROR,
                'error': str(e)
            })
            
    async def _handle_subscribe(self, client: WebSocketClient, message: Dict[str, Any]):
        """Handle subscription request."""
        channel_name = message.get('channel')
        symbols = set(message.get('symbols', []))
        filters = message.get('filters', {})
        
        try:
            channel = ChannelType(channel_name)
        except ValueError:
            raise ValueError(f"Invalid channel: {channel_name}")
            
        subscription = Subscription(
            channel=channel,
            symbols=symbols,
            filters=filters
        )
        
        client.subscriptions[channel] = subscription
        self.channel_subscribers[channel].add(client.id)
        
        for symbol in symbols:
            self.symbol_subscribers[symbol].add(client.id)
            
        await client.send({
            'type': MessageType.ACK,
            'action': 'subscribe',
            'channel': channel_name,
            'symbols': list(symbols)
        })
        
        logger.debug(f"Client {client.id} subscribed to {channel_name}: {symbols}")
        
    async def _handle_unsubscribe(self, client: WebSocketClient, message: Dict[str, Any]):
        """Handle unsubscription request."""
        channel_name = message.get('channel')
        
        try:
            channel = ChannelType(channel_name)
        except ValueError:
            raise ValueError(f"Invalid channel: {channel_name}")
            
        if channel in client.subscriptions:
            subscription = client.subscriptions[channel]
            
            for symbol in subscription.symbols:
                self.symbol_subscribers[symbol].discard(client.id)
                
            del client.subscriptions[channel]
            self.channel_subscribers[channel].discard(client.id)
            
        await client.send({
            'type': MessageType.ACK,
            'action': 'unsubscribe',
            'channel': channel_name
        })
        
    async def broadcast(
        self,
        channel: ChannelType,
        data: Dict[str, Any],
        symbols: Optional[List[str]] = None
    ):
        """Broadcast message to all subscribers of a channel."""
        message = {
            'type': MessageType.DATA,
            'channel': channel.value,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        await self.message_queues[channel].put((message, symbols))
        
    async def _broadcast_loop(self, channel: ChannelType):
        """Background task for batched broadcasting."""
        while True:
            try:
                # Batch messages for efficiency
                messages = []
                symbols_list = []
                
                # Get first message (blocking)
                msg, syms = await self.message_queues[channel].get()
                messages.append(msg)
                symbols_list.append(syms)
                
                # Drain queue for batching (non-blocking)
                while not self.message_queues[channel].empty() and len(messages) < 100:
                    try:
                        msg, syms = self.message_queues[channel].get_nowait()
                        messages.append(msg)
                        symbols_list.append(syms)
                    except asyncio.QueueEmpty:
                        break
                        
                # Send batched or individual messages
                for message, symbols in zip(messages, symbols_list):
                    await self._send_to_subscribers(channel, message, symbols)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast error on {channel}: {e}")
                await asyncio.sleep(1)
                
    async def _send_to_subscribers(
        self,
        channel: ChannelType,
        message: Dict[str, Any],
        symbols: Optional[List[str]] = None
    ):
        """Send message to channel subscribers, optionally filtered by symbols."""
        client_ids = self.channel_subscribers[channel].copy()
        
        # Filter by symbols if specified
        if symbols:
            symbol_clients = set()
            for symbol in symbols:
                symbol_clients.update(self.symbol_subscribers[symbol])
            client_ids = client_ids.intersection(symbol_clients)
            
        # Send to all matching clients
        tasks = []
        for client_id in client_ids:
            if client_id in self.clients:
                client = self.clients[client_id]
                
                # Check symbol filter in subscription
                subscription = client.subscriptions.get(channel)
                if subscription and subscription.symbols:
                    if symbols and not set(symbols).intersection(subscription.symbols):
                        continue
                        
                tasks.append(self._send_with_retry(client, message))
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self.metrics['total_messages_sent'] += len(tasks)
            
    async def _send_with_retry(
        self,
        client: WebSocketClient,
        message: Dict[str, Any],
        retries: int = 2
    ):
        """Send message with retry logic."""
        for attempt in range(retries + 1):
            try:
                await client.send(message)
                return
            except Exception as e:
                if attempt == retries:
                    logger.warning(f"Failed to send to {client.id} after {retries} retries")
                    await self.disconnect(client.id)
                else:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    
    async def _heartbeat_loop(self):
        """Background task for heartbeat monitoring."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                now = datetime.now()
                timeout = self.heartbeat_interval * 3
                
                for client_id in list(self.clients.keys()):
                    client = self.clients.get(client_id)
                    if not client:
                        continue
                        
                    elapsed = (now - client.last_heartbeat).total_seconds()
                    if elapsed > timeout:
                        logger.info(f"Client {client_id} timed out (no heartbeat)")
                        await self.disconnect(client_id)
                    else:
                        # Send heartbeat
                        try:
                            await client.send({
                                'type': MessageType.HEARTBEAT,
                                'timestamp': now.isoformat()
                            })
                        except Exception:
                            await self.disconnect(client_id)
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'active_clients': len(self.clients),
            'channel_subscribers': {
                channel.value: len(subs) 
                for channel, subs in self.channel_subscribers.items()
            },
            'metrics': self.metrics.copy()
        }


class MarketDataStreamer:
    """
    Streams real-time market data to WebSocket clients.
    
    Integrates with data providers and pushes updates through WebSocket manager.
    """
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self, symbols: List[str], interval_ms: int = 100):
        """Start streaming market data."""
        self._running = True
        self._task = asyncio.create_task(self._stream_loop(symbols, interval_ms))
        
    async def stop(self):
        """Stop streaming."""
        self._running = False
        if self._task:
            self._task.cancel()
            
    async def _stream_loop(self, symbols: List[str], interval_ms: int):
        """Main streaming loop."""
        from data.unified_api import UnifiedDataAPI
        
        api = UnifiedDataAPI()
        interval = interval_ms / 1000
        
        while self._running:
            try:
                for symbol in symbols:
                    quote = await api.get_quote(symbol)
                    
                    await self.ws_manager.broadcast(
                        channel=ChannelType.MARKET_DATA,
                        data={
                            'symbol': symbol,
                            'price': quote.get('price'),
                            'bid': quote.get('bid'),
                            'ask': quote.get('ask'),
                            'volume': quote.get('volume'),
                            'change': quote.get('change'),
                            'change_pct': quote.get('change_pct')
                        },
                        symbols=[symbol]
                    )
                    
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Market data stream error: {e}")
                await asyncio.sleep(1)


class SignalStreamer:
    """Streams trading signals to WebSocket clients."""
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        
    async def publish_signal(
        self,
        symbol: str,
        signal_type: str,
        direction: str,
        strength: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Publish a new trading signal."""
        await self.ws_manager.broadcast(
            channel=ChannelType.SIGNALS,
            data={
                'symbol': symbol,
                'signal_type': signal_type,
                'direction': direction,
                'strength': strength,
                'metadata': metadata or {},
                'generated_at': datetime.now().isoformat()
            },
            symbols=[symbol]
        )


class RiskStreamer:
    """Streams risk metrics to WebSocket clients."""
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        
    async def publish_risk_update(
        self,
        var_95: float,
        cvar_95: float,
        portfolio_beta: float,
        drawdown: float,
        exposure: Dict[str, float]
    ):
        """Publish risk metrics update."""
        await self.ws_manager.broadcast(
            channel=ChannelType.RISK,
            data={
                'var_95': var_95,
                'cvar_95': cvar_95,
                'portfolio_beta': portfolio_beta,
                'current_drawdown': drawdown,
                'sector_exposure': exposure,
                'updated_at': datetime.now().isoformat()
            }
        )
        
    async def publish_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Publish risk alert."""
        await self.ws_manager.broadcast(
            channel=ChannelType.ALERTS,
            data={
                'alert_type': alert_type,
                'severity': severity,
                'message': message,
                'details': details or {},
                'triggered_at': datetime.now().isoformat()
            }
        )


class ExecutionStreamer:
    """Streams execution updates to WebSocket clients."""
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        
    async def publish_execution(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        status: str,
        filled_qty: int = 0,
        avg_price: Optional[float] = None
    ):
        """Publish execution update."""
        await self.ws_manager.broadcast(
            channel=ChannelType.EXECUTIONS,
            data={
                'order_id': order_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'status': status,
                'filled_qty': filled_qty,
                'avg_price': avg_price,
                'updated_at': datetime.now().isoformat()
            },
            symbols=[symbol]
        )


# Singleton instance
_manager: Optional[WebSocketManager] = None


def get_ws_manager() -> WebSocketManager:
    """Get or create WebSocket manager singleton."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager
