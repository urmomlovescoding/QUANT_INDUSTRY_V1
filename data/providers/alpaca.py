"""
Alpaca Data Provider
QUANT_INDUSTRY_V1

Real-time and historical market data from Alpaca Markets
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
class AlpacaConfig:
    """Alpaca API configuration."""
    api_key: str = ""
    api_secret: str = ""
    data_url: str = "https://data.alpaca.markets"
    stream_url: str = "wss://stream.data.alpaca.markets"
    feed: str = "iex"  # 'iex' (free) or 'sip' (paid)
    timeout: float = 30.0
    max_retries: int = 3
    
    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.environ.get('ALPACA_API_KEY', '')
        if not self.api_secret:
            self.api_secret = os.environ.get('ALPACA_API_SECRET', '')


class AlpacaProvider:
    """
    Alpaca market data provider.
    
    Features:
    - Real-time quotes, trades, bars
    - Historical data (IEX and SIP feeds)
    - Crypto data
    - News
    - WebSocket streaming
    """
    
    def __init__(self, config: Optional[AlpacaConfig] = None):
        self.config = config or AlpacaConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        
    async def connect(self) -> bool:
        """Initialize HTTP session."""
        if not self.config.api_key or not self.config.api_secret:
            logger.error("Alpaca API credentials not configured")
            return False
            
        headers = {
            'APCA-API-KEY-ID': self.config.api_key,
            'APCA-API-SECRET-KEY': self.config.api_secret
        }
        
        self._session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        logger.info("Alpaca provider connected")
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
        params: Optional[Dict[str, Any]] = None,
        version: str = "v2"
    ) -> Dict[str, Any]:
        """Make API request."""
        if not self._session:
            raise ConnectionError("Not connected")
            
        url = f"{self.config.data_url}/{version}{endpoint}"
        
        for attempt in range(self.config.max_retries):
            try:
                async with self._session.get(url, params=params) as response:
                    if response.status == 429:
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
        
    # =========================================================================
    # Stocks
    # =========================================================================
    
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get latest quote for symbol."""
        data = await self._request(f"/stocks/{symbol}/quotes/latest")
        
        quote = data.get('quote', {})
        return {
            'symbol': symbol,
            'bid': quote.get('bp', 0),
            'bid_size': quote.get('bs', 0),
            'ask': quote.get('ap', 0),
            'ask_size': quote.get('as', 0),
            'timestamp': quote.get('t', ''),
            'conditions': quote.get('c', [])
        }
        
    async def get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get latest quotes for multiple symbols."""
        params = {'symbols': ','.join(symbols)}
        data = await self._request("/stocks/quotes/latest", params)
        
        result = {}
        for symbol, quote in data.get('quotes', {}).items():
            result[symbol] = {
                'symbol': symbol,
                'bid': quote.get('bp', 0),
                'bid_size': quote.get('bs', 0),
                'ask': quote.get('ap', 0),
                'ask_size': quote.get('as', 0),
                'timestamp': quote.get('t', '')
            }
        return result
        
    async def get_trade(self, symbol: str) -> Dict[str, Any]:
        """Get latest trade for symbol."""
        data = await self._request(f"/stocks/{symbol}/trades/latest")
        
        trade = data.get('trade', {})
        return {
            'symbol': symbol,
            'price': trade.get('p', 0),
            'size': trade.get('s', 0),
            'timestamp': trade.get('t', ''),
            'exchange': trade.get('x', ''),
            'conditions': trade.get('c', [])
        }
        
    async def get_trades(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get latest trades for multiple symbols."""
        params = {'symbols': ','.join(symbols)}
        data = await self._request("/stocks/trades/latest", params)
        
        result = {}
        for symbol, trade in data.get('trades', {}).items():
            result[symbol] = {
                'symbol': symbol,
                'price': trade.get('p', 0),
                'size': trade.get('s', 0),
                'timestamp': trade.get('t', '')
            }
        return result
        
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000,
        adjustment: str = "all"
    ) -> List[Dict[str, Any]]:
        """
        Get historical bars.
        
        Args:
            symbol: Ticker symbol
            timeframe: '1Min', '5Min', '15Min', '30Min', '1Hour', '4Hour', '1Day', '1Week', '1Month'
            start: Start datetime
            end: End datetime
            limit: Max bars
            adjustment: 'raw', 'split', 'dividend', 'all'
        """
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)
            
        params = {
            'timeframe': timeframe,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'limit': limit,
            'adjustment': adjustment,
            'feed': self.config.feed
        }
        
        data = await self._request(f"/stocks/{symbol}/bars", params)
        
        bars = []
        for bar in data.get('bars', []):
            bars.append({
                'timestamp': bar.get('t', ''),
                'open': bar.get('o', 0),
                'high': bar.get('h', 0),
                'low': bar.get('l', 0),
                'close': bar.get('c', 0),
                'volume': bar.get('v', 0),
                'vwap': bar.get('vw', 0),
                'trade_count': bar.get('n', 0)
            })
            
        return bars
        
    async def get_multi_bars(
        self,
        symbols: List[str],
        timeframe: str = "1Day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get historical bars for multiple symbols."""
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)
            
        params = {
            'symbols': ','.join(symbols),
            'timeframe': timeframe,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'limit': limit,
            'feed': self.config.feed
        }
        
        data = await self._request("/stocks/bars", params)
        
        result = {}
        for symbol, bars in data.get('bars', {}).items():
            result[symbol] = [
                {
                    'timestamp': bar.get('t', ''),
                    'open': bar.get('o', 0),
                    'high': bar.get('h', 0),
                    'low': bar.get('l', 0),
                    'close': bar.get('c', 0),
                    'volume': bar.get('v', 0),
                    'vwap': bar.get('vw', 0)
                }
                for bar in bars
            ]
            
        return result
        
    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get complete snapshot for symbol."""
        data = await self._request(f"/stocks/{symbol}/snapshot")
        
        snapshot = data.get('snapshot', {})
        return {
            'symbol': symbol,
            'latest_trade': snapshot.get('latestTrade', {}),
            'latest_quote': snapshot.get('latestQuote', {}),
            'minute_bar': snapshot.get('minuteBar', {}),
            'daily_bar': snapshot.get('dailyBar', {}),
            'prev_daily_bar': snapshot.get('prevDailyBar', {})
        }
        
    async def get_snapshots(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get snapshots for multiple symbols."""
        params = {'symbols': ','.join(symbols)}
        data = await self._request("/stocks/snapshots", params)
        
        result = {}
        for symbol, snapshot in data.get('snapshots', {}).items():
            result[symbol] = {
                'symbol': symbol,
                'latest_trade': snapshot.get('latestTrade', {}),
                'latest_quote': snapshot.get('latestQuote', {}),
                'minute_bar': snapshot.get('minuteBar', {}),
                'daily_bar': snapshot.get('dailyBar', {})
            }
        return result
        
    # =========================================================================
    # Crypto
    # =========================================================================
    
    async def get_crypto_quote(self, symbol: str, exchange: str = "CBSE") -> Dict[str, Any]:
        """Get crypto quote."""
        params = {'loc': exchange}
        data = await self._request(f"/crypto/{symbol}/quotes/latest", params, version="v1beta3")
        
        quote = data.get('quote', {})
        return {
            'symbol': symbol,
            'bid': quote.get('bp', 0),
            'bid_size': quote.get('bs', 0),
            'ask': quote.get('ap', 0),
            'ask_size': quote.get('as', 0),
            'timestamp': quote.get('t', '')
        }
        
    async def get_crypto_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """Get crypto historical bars."""
        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365)
            
        params = {
            'timeframe': timeframe,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'limit': limit
        }
        
        data = await self._request(f"/crypto/{symbol}/bars", params, version="v1beta3")
        
        return [
            {
                'timestamp': bar.get('t', ''),
                'open': bar.get('o', 0),
                'high': bar.get('h', 0),
                'low': bar.get('l', 0),
                'close': bar.get('c', 0),
                'volume': bar.get('v', 0),
                'vwap': bar.get('vw', 0)
            }
            for bar in data.get('bars', [])
        ]
        
    # =========================================================================
    # News
    # =========================================================================
    
    async def get_news(
        self,
        symbols: Optional[List[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 50,
        include_content: bool = False
    ) -> List[Dict[str, Any]]:
        """Get news articles."""
        params = {'limit': limit}
        
        if symbols:
            params['symbols'] = ','.join(symbols)
        if start:
            params['start'] = start.isoformat()
        if end:
            params['end'] = end.isoformat()
        if include_content:
            params['include_content'] = 'true'
            
        data = await self._request("/news", params, version="v1beta1")
        
        return [
            {
                'id': article.get('id', ''),
                'headline': article.get('headline', ''),
                'author': article.get('author', ''),
                'created_at': article.get('created_at', ''),
                'updated_at': article.get('updated_at', ''),
                'summary': article.get('summary', ''),
                'content': article.get('content', ''),
                'url': article.get('url', ''),
                'images': article.get('images', []),
                'symbols': article.get('symbols', []),
                'source': article.get('source', '')
            }
            for article in data.get('news', [])
        ]
        
    # =========================================================================
    # WebSocket Streaming
    # =========================================================================
    
    async def stream(
        self,
        symbols: List[str],
        trades: bool = True,
        quotes: bool = True,
        bars: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream real-time market data.
        
        Args:
            symbols: List of symbols to stream
            trades: Include trades
            quotes: Include quotes
            bars: Include minute bars
        """
        if not self._session:
            raise ConnectionError("Not connected")
            
        url = f"{self.config.stream_url}/v2/{self.config.feed}"
        
        async with self._session.ws_connect(url) as ws:
            self._ws = ws
            
            # Authenticate
            auth_msg = {
                "action": "auth",
                "key": self.config.api_key,
                "secret": self.config.api_secret
            }
            await ws.send_json(auth_msg)
            
            # Wait for auth
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('T') == 'success' and item.get('msg') == 'authenticated':
                                break
                    break
                    
            # Subscribe
            subscribe_msg = {
                "action": "subscribe",
                "trades": symbols if trades else [],
                "quotes": symbols if quotes else [],
                "bars": symbols if bars else []
            }
            await ws.send_json(subscribe_msg)
            
            # Stream
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if isinstance(data, list):
                        for item in data:
                            msg_type = item.get('T')
                            
                            if msg_type == 't':  # Trade
                                yield {
                                    'type': 'trade',
                                    'symbol': item.get('S', ''),
                                    'price': item.get('p', 0),
                                    'size': item.get('s', 0),
                                    'timestamp': item.get('t', ''),
                                    'exchange': item.get('x', ''),
                                    'conditions': item.get('c', [])
                                }
                            elif msg_type == 'q':  # Quote
                                yield {
                                    'type': 'quote',
                                    'symbol': item.get('S', ''),
                                    'bid': item.get('bp', 0),
                                    'bid_size': item.get('bs', 0),
                                    'ask': item.get('ap', 0),
                                    'ask_size': item.get('as', 0),
                                    'timestamp': item.get('t', '')
                                }
                            elif msg_type == 'b':  # Bar
                                yield {
                                    'type': 'bar',
                                    'symbol': item.get('S', ''),
                                    'open': item.get('o', 0),
                                    'high': item.get('h', 0),
                                    'low': item.get('l', 0),
                                    'close': item.get('c', 0),
                                    'volume': item.get('v', 0),
                                    'vwap': item.get('vw', 0),
                                    'timestamp': item.get('t', '')
                                }
                                
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break


# Convenience function
async def create_alpaca_provider(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> AlpacaProvider:
    """Create and connect Alpaca provider."""
    config = AlpacaConfig(api_key=api_key or '', api_secret=api_secret or '')
    provider = AlpacaProvider(config)
    await provider.connect()
    return provider
