"""
Polygon.io Data Provider
QUANT_INDUSTRY_V1

Real-time and historical market data from Polygon.io
"""

import os
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class PolygonConfig:
    """Polygon API configuration."""
    api_key: str = ""
    base_url: str = "https://api.polygon.io"
    ws_url: str = "wss://socket.polygon.io"
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit_per_minute: int = 100
    
    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.environ.get('POLYGON_API_KEY', '')


class PolygonProvider:
    """
    Polygon.io market data provider.
    
    Features:
    - Real-time quotes and trades
    - Historical OHLCV bars
    - Options chain data
    - Company fundamentals
    - WebSocket streaming
    """
    
    def __init__(self, config: Optional[PolygonConfig] = None):
        self.config = config or PolygonConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._request_count = 0
        self._last_reset = datetime.now()
        
    async def connect(self) -> bool:
        """Initialize HTTP session."""
        if not self.config.api_key:
            logger.error("Polygon API key not configured")
            return False
            
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        logger.info("Polygon provider connected")
        return True
        
    async def disconnect(self):
        """Close connections."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None
            
    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make API request with rate limiting."""
        if not self._session:
            raise ConnectionError("Not connected")
            
        # Rate limiting
        await self._check_rate_limit()
        
        url = f"{self.config.base_url}{endpoint}"
        params = params or {}
        params['apiKey'] = self.config.api_key
        
        for attempt in range(self.config.max_retries):
            try:
                async with self._session.get(url, params=params) as response:
                    if response.status == 429:
                        # Rate limited
                        retry_after = int(response.headers.get('Retry-After', 60))
                        logger.warning(f"Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    response.raise_for_status()
                    return await response.json()
                    
            except aiohttp.ClientError as e:
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                
        raise Exception("Max retries exceeded")
        
    async def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        now = datetime.now()
        if (now - self._last_reset).total_seconds() >= 60:
            self._request_count = 0
            self._last_reset = now
            
        if self._request_count >= self.config.rate_limit_per_minute:
            sleep_time = 60 - (now - self._last_reset).total_seconds()
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
                self._request_count = 0
                self._last_reset = datetime.now()
                
        self._request_count += 1
        
    # =========================================================================
    # Market Data
    # =========================================================================
    
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get current quote for symbol."""
        data = await self._request(f"/v2/last/trade/{symbol}")
        
        result = data.get('results', {})
        return {
            'symbol': symbol,
            'price': result.get('p', 0),
            'size': result.get('s', 0),
            'timestamp': result.get('t', 0),
            'exchange': result.get('x', ''),
            'conditions': result.get('c', [])
        }
        
    async def get_nbbo(self, symbol: str) -> Dict[str, Any]:
        """Get National Best Bid/Offer."""
        data = await self._request(f"/v2/last/nbbo/{symbol}")
        
        result = data.get('results', {})
        return {
            'symbol': symbol,
            'bid': result.get('p', 0),
            'bid_size': result.get('s', 0),
            'ask': result.get('P', 0),
            'ask_size': result.get('S', 0),
            'timestamp': result.get('t', 0)
        }
        
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Get historical OHLCV bars.
        
        Args:
            symbol: Ticker symbol
            timeframe: 'minute', 'hour', 'day', 'week', 'month'
            start: Start date
            end: End date
            limit: Max bars to return
        """
        # Map timeframe to Polygon format
        tf_map = {
            'minute': ('minute', 1),
            'hour': ('hour', 1),
            'day': ('day', 1),
            'week': ('week', 1),
            'month': ('month', 1),
            '5min': ('minute', 5),
            '15min': ('minute', 15),
            '30min': ('minute', 30),
            '4hour': ('hour', 4),
        }
        
        tf_type, multiplier = tf_map.get(timeframe, ('day', 1))
        
        # Default date range
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)
            
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': limit
        }
        
        endpoint = f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{tf_type}/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
        
        data = await self._request(endpoint, params)
        
        bars = []
        for bar in data.get('results', []):
            bars.append({
                'timestamp': datetime.fromtimestamp(bar['t'] / 1000),
                'open': bar['o'],
                'high': bar['h'],
                'low': bar['l'],
                'close': bar['c'],
                'volume': bar['v'],
                'vwap': bar.get('vw', 0),
                'transactions': bar.get('n', 0)
            })
            
        return bars
        
    async def get_trades(
        self,
        symbol: str,
        date: Optional[datetime] = None,
        limit: int = 50000
    ) -> List[Dict[str, Any]]:
        """Get historical trades."""
        if date is None:
            date = datetime.now()
            
        endpoint = f"/v2/ticks/stocks/trades/{symbol}/{date.strftime('%Y-%m-%d')}"
        params = {'limit': limit}
        
        data = await self._request(endpoint, params)
        
        trades = []
        for trade in data.get('results', []):
            trades.append({
                'timestamp': trade.get('t', 0),
                'price': trade.get('p', 0),
                'size': trade.get('s', 0),
                'exchange': trade.get('x', ''),
                'conditions': trade.get('c', [])
            })
            
        return trades
        
    async def get_quotes(
        self,
        symbol: str,
        date: Optional[datetime] = None,
        limit: int = 50000
    ) -> List[Dict[str, Any]]:
        """Get historical quotes (NBBO)."""
        if date is None:
            date = datetime.now()
            
        endpoint = f"/v2/ticks/stocks/nbbo/{symbol}/{date.strftime('%Y-%m-%d')}"
        params = {'limit': limit}
        
        data = await self._request(endpoint, params)
        
        quotes = []
        for quote in data.get('results', []):
            quotes.append({
                'timestamp': quote.get('t', 0),
                'bid': quote.get('p', 0),
                'bid_size': quote.get('s', 0),
                'ask': quote.get('P', 0),
                'ask_size': quote.get('S', 0),
                'exchange_bid': quote.get('x', ''),
                'exchange_ask': quote.get('X', '')
            })
            
        return quotes
        
    # =========================================================================
    # Reference Data
    # =========================================================================
    
    async def get_ticker_details(self, symbol: str) -> Dict[str, Any]:
        """Get company/ticker details."""
        data = await self._request(f"/v3/reference/tickers/{symbol}")
        
        result = data.get('results', {})
        return {
            'symbol': result.get('ticker', symbol),
            'name': result.get('name', ''),
            'market': result.get('market', ''),
            'locale': result.get('locale', ''),
            'type': result.get('type', ''),
            'currency': result.get('currency_name', ''),
            'active': result.get('active', False),
            'cik': result.get('cik', ''),
            'composite_figi': result.get('composite_figi', ''),
            'share_class_figi': result.get('share_class_figi', ''),
            'market_cap': result.get('market_cap', 0),
            'phone': result.get('phone_number', ''),
            'address': result.get('address', {}),
            'description': result.get('description', ''),
            'sic_code': result.get('sic_code', ''),
            'sic_description': result.get('sic_description', ''),
            'homepage': result.get('homepage_url', ''),
            'total_employees': result.get('total_employees', 0),
            'list_date': result.get('list_date', ''),
            'branding': result.get('branding', {})
        }
        
    async def search_tickers(
        self,
        query: str,
        market: str = "stocks",
        active: bool = True,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for tickers."""
        params = {
            'search': query,
            'market': market,
            'active': str(active).lower(),
            'limit': limit
        }
        
        data = await self._request("/v3/reference/tickers", params)
        
        return [
            {
                'symbol': t.get('ticker', ''),
                'name': t.get('name', ''),
                'market': t.get('market', ''),
                'type': t.get('type', ''),
                'active': t.get('active', False)
            }
            for t in data.get('results', [])
        ]
        
    async def get_market_status(self) -> Dict[str, Any]:
        """Get current market status."""
        data = await self._request("/v1/marketstatus/now")
        
        return {
            'market': data.get('market', ''),
            'server_time': data.get('serverTime', ''),
            'exchanges': data.get('exchanges', {}),
            'currencies': data.get('currencies', {})
        }
        
    # =========================================================================
    # Options
    # =========================================================================
    
    async def get_options_chain(
        self,
        underlying: str,
        expiration_date: Optional[str] = None,
        strike_price: Optional[float] = None,
        contract_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get options chain."""
        params = {
            'underlying_ticker': underlying,
            'limit': limit
        }
        
        if expiration_date:
            params['expiration_date'] = expiration_date
        if strike_price:
            params['strike_price'] = strike_price
        if contract_type:
            params['contract_type'] = contract_type
            
        data = await self._request("/v3/reference/options/contracts", params)
        
        return [
            {
                'ticker': c.get('ticker', ''),
                'underlying': c.get('underlying_ticker', ''),
                'contract_type': c.get('contract_type', ''),
                'strike': c.get('strike_price', 0),
                'expiration': c.get('expiration_date', ''),
                'shares_per_contract': c.get('shares_per_contract', 100),
                'cfi': c.get('cfi', ''),
                'exercise_style': c.get('exercise_style', '')
            }
            for c in data.get('results', [])
        ]
        
    # =========================================================================
    # WebSocket Streaming
    # =========================================================================
    
    async def stream_trades(
        self,
        symbols: List[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time trades."""
        async for msg in self._stream('T', symbols):
            yield {
                'type': 'trade',
                'symbol': msg.get('sym', ''),
                'price': msg.get('p', 0),
                'size': msg.get('s', 0),
                'timestamp': msg.get('t', 0),
                'exchange': msg.get('x', ''),
                'conditions': msg.get('c', [])
            }
            
    async def stream_quotes(
        self,
        symbols: List[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time quotes."""
        async for msg in self._stream('Q', symbols):
            yield {
                'type': 'quote',
                'symbol': msg.get('sym', ''),
                'bid': msg.get('bp', 0),
                'bid_size': msg.get('bs', 0),
                'ask': msg.get('ap', 0),
                'ask_size': msg.get('as', 0),
                'timestamp': msg.get('t', 0)
            }
            
    async def stream_bars(
        self,
        symbols: List[str],
        aggregate_type: str = "A"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time minute bars."""
        async for msg in self._stream(aggregate_type, symbols):
            yield {
                'type': 'bar',
                'symbol': msg.get('sym', ''),
                'open': msg.get('o', 0),
                'high': msg.get('h', 0),
                'low': msg.get('l', 0),
                'close': msg.get('c', 0),
                'volume': msg.get('v', 0),
                'vwap': msg.get('vw', 0),
                'timestamp': msg.get('s', 0),
                'transactions': msg.get('n', 0)
            }
            
    async def _stream(
        self,
        channel: str,
        symbols: List[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Internal streaming implementation."""
        if not self._session:
            raise ConnectionError("Not connected")
            
        url = f"{self.config.ws_url}/stocks"
        
        async with self._session.ws_connect(url) as ws:
            self._ws = ws
            
            # Authenticate
            await ws.send_json({
                "action": "auth",
                "params": self.config.api_key
            })
            
            # Wait for auth response
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if isinstance(data, list) and data[0].get('status') == 'auth_success':
                        break
                        
            # Subscribe
            subscribe_msg = {
                "action": "subscribe",
                "params": ",".join(f"{channel}.{s}" for s in symbols)
            }
            await ws.send_json(subscribe_msg)
            
            # Stream data
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('ev') == channel:
                                yield item
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break


# Convenience function
async def create_polygon_provider(api_key: Optional[str] = None) -> PolygonProvider:
    """Create and connect Polygon provider."""
    config = PolygonConfig(api_key=api_key) if api_key else PolygonConfig()
    provider = PolygonProvider(config)
    await provider.connect()
    return provider
