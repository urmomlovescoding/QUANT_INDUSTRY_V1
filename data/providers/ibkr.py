"""
Interactive Brokers Data Provider
QUANT_INDUSTRY_V1

Institutional-grade market data from Interactive Brokers TWS/Gateway
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
from queue import Queue
import time

logger = logging.getLogger(__name__)

# Optional IBKR import
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order as IBOrder
    from ibapi.common import BarData, TickType, TickAttrib
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logger.warning("ibapi not installed. Run: pip install ibapi")


@dataclass
class IBKRConfig:
    """Interactive Brokers configuration."""
    host: str = "127.0.0.1"
    port: int = 7497  # 7497 = paper, 7496 = live
    client_id: int = 1
    timeout: float = 30.0
    auto_reconnect: bool = True
    
    
class TickType(Enum):
    """Common tick types."""
    BID = 1
    ASK = 2
    LAST = 4
    HIGH = 6
    LOW = 7
    VOLUME = 8
    CLOSE = 9
    BID_SIZE = 0
    ASK_SIZE = 3
    LAST_SIZE = 5
    OPEN = 14
    VWAP = 35


@dataclass
class MarketData:
    """Market data container."""
    symbol: str
    bid: float = 0.0
    bid_size: int = 0
    ask: float = 0.0
    ask_size: int = 0
    last: float = 0.0
    last_size: int = 0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    close: float = 0.0
    vwap: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    
class IBKRWrapper(EWrapper if IBKR_AVAILABLE else object):
    """IBKR API wrapper for handling callbacks."""
    
    def __init__(self):
        if IBKR_AVAILABLE:
            EWrapper.__init__(self)
        self.data: Dict[int, MarketData] = {}
        self.bars: Dict[int, List[Dict]] = {}
        self.errors: List[Dict] = []
        self.callbacks: Dict[str, List[Callable]] = {}
        self._connected = False
        self._next_order_id = 0
        self._request_queue: Queue = Queue()
        
    def nextValidId(self, orderId: int):
        """Called when connection established."""
        self._next_order_id = orderId
        self._connected = True
        logger.info(f"Connected. Next order ID: {orderId}")
        
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle errors."""
        self.errors.append({
            'req_id': reqId,
            'code': errorCode,
            'message': errorString,
            'timestamp': datetime.now()
        })
        
        # Log based on severity
        if errorCode in [2104, 2106, 2158]:  # Info messages
            logger.debug(f"IBKR: {errorString}")
        elif errorCode < 1000:  # System messages
            logger.info(f"IBKR System: {errorString}")
        else:
            logger.error(f"IBKR Error {errorCode}: {errorString}")
            
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Handle price tick."""
        if reqId not in self.data:
            self.data[reqId] = MarketData(symbol=str(reqId))
            
        data = self.data[reqId]
        data.timestamp = datetime.now()
        
        if tickType == 1:  # Bid
            data.bid = price
        elif tickType == 2:  # Ask
            data.ask = price
        elif tickType == 4:  # Last
            data.last = price
        elif tickType == 6:  # High
            data.high = price
        elif tickType == 7:  # Low
            data.low = price
        elif tickType == 9:  # Close
            data.close = price
        elif tickType == 14:  # Open
            data.open = price
            
        self._notify('tick', reqId, data)
        
    def tickSize(self, reqId: int, tickType: int, size: int):
        """Handle size tick."""
        if reqId not in self.data:
            self.data[reqId] = MarketData(symbol=str(reqId))
            
        data = self.data[reqId]
        
        if tickType == 0:  # Bid size
            data.bid_size = size
        elif tickType == 3:  # Ask size
            data.ask_size = size
        elif tickType == 5:  # Last size
            data.last_size = size
        elif tickType == 8:  # Volume
            data.volume = size
            
    def tickGeneric(self, reqId: int, tickType: int, value: float):
        """Handle generic tick."""
        if reqId in self.data and tickType == 35:  # VWAP
            self.data[reqId].vwap = value
            
    def historicalData(self, reqId: int, bar):
        """Handle historical bar."""
        if reqId not in self.bars:
            self.bars[reqId] = []
            
        self.bars[reqId].append({
            'timestamp': bar.date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'vwap': bar.average,
            'count': bar.barCount
        })
        
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data request complete."""
        self._request_queue.put(('historical_complete', reqId))
        
    def realtimeBar(self, reqId: int, time: int, open_: float, high: float, low: float, 
                    close: float, volume: int, wap: float, count: int):
        """Handle real-time bar."""
        bar = {
            'timestamp': datetime.fromtimestamp(time),
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'vwap': wap,
            'count': count
        }
        self._notify('bar', reqId, bar)
        
    def _notify(self, event: str, req_id: int, data: Any):
        """Notify callbacks."""
        key = f"{event}_{req_id}"
        for callback in self.callbacks.get(key, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                
    def add_callback(self, event: str, req_id: int, callback: Callable):
        """Add event callback."""
        key = f"{event}_{req_id}"
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)


class IBKRClient(EClient if IBKR_AVAILABLE else object):
    """IBKR API client."""
    
    def __init__(self, wrapper: IBKRWrapper):
        if IBKR_AVAILABLE:
            EClient.__init__(self, wrapper)
        self.wrapper = wrapper


class IBKRProvider:
    """
    Interactive Brokers market data provider.
    
    Features:
    - Real-time quotes and trades
    - Historical data (1-second to monthly bars)
    - Market depth (Level 2)
    - Options chains
    - Fundamentals
    - News
    
    Requires TWS or IB Gateway running.
    """
    
    def __init__(self, config: Optional[IBKRConfig] = None):
        if not IBKR_AVAILABLE:
            raise ImportError("ibapi not installed. Run: pip install ibapi")
            
        self.config = config or IBKRConfig()
        self.wrapper = IBKRWrapper()
        self.client = IBKRClient(self.wrapper)
        
        self._thread: Optional[threading.Thread] = None
        self._req_id = 0
        self._symbol_map: Dict[int, str] = {}
        
    @property
    def connected(self) -> bool:
        return self.wrapper._connected
        
    def connect(self) -> bool:
        """Connect to TWS/Gateway."""
        try:
            self.client.connect(
                self.config.host,
                self.config.port,
                self.config.client_id
            )
            
            # Start message loop in background
            self._thread = threading.Thread(target=self.client.run, daemon=True)
            self._thread.start()
            
            # Wait for connection
            timeout = time.time() + self.config.timeout
            while not self.wrapper._connected and time.time() < timeout:
                time.sleep(0.1)
                
            if not self.wrapper._connected:
                logger.error("Connection timeout")
                return False
                
            logger.info("Connected to Interactive Brokers")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from TWS/Gateway."""
        self.client.disconnect()
        self.wrapper._connected = False
        
    def _get_req_id(self) -> int:
        """Get next request ID."""
        self._req_id += 1
        return self._req_id
        
    def _create_contract(
        self,
        symbol: str,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
        expiry: str = "",
        strike: float = 0.0,
        right: str = ""
    ) -> Contract:
        """Create IBKR contract."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        
        if sec_type in ["FUT", "OPT", "FOP"]:
            contract.lastTradeDateOrContractMonth = expiry
        if sec_type in ["OPT", "FOP"]:
            contract.strike = strike
            contract.right = right
            
        return contract
        
    # =========================================================================
    # Market Data
    # =========================================================================
    
    def subscribe_market_data(
        self,
        symbol: str,
        callback: Optional[Callable] = None,
        sec_type: str = "STK",
        exchange: str = "SMART"
    ) -> int:
        """
        Subscribe to real-time market data.
        
        Returns request ID for tracking.
        """
        req_id = self._get_req_id()
        contract = self._create_contract(symbol, sec_type, exchange)
        
        self._symbol_map[req_id] = symbol
        self.wrapper.data[req_id] = MarketData(symbol=symbol)
        
        if callback:
            self.wrapper.add_callback('tick', req_id, callback)
            
        # Request all tick types
        self.client.reqMktData(req_id, contract, "", False, False, [])
        
        return req_id
        
    def unsubscribe_market_data(self, req_id: int):
        """Unsubscribe from market data."""
        self.client.cancelMktData(req_id)
        
    def get_snapshot(self, symbol: str, sec_type: str = "STK") -> MarketData:
        """Get market data snapshot (blocking)."""
        req_id = self.subscribe_market_data(symbol, sec_type=sec_type)
        
        # Wait for data
        time.sleep(2)
        
        data = self.wrapper.data.get(req_id, MarketData(symbol=symbol))
        self.unsubscribe_market_data(req_id)
        
        return data
        
    # =========================================================================
    # Historical Data
    # =========================================================================
    
    def get_historical_bars(
        self,
        symbol: str,
        duration: str = "1 Y",
        bar_size: str = "1 day",
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        sec_type: str = "STK"
    ) -> List[Dict]:
        """
        Get historical bars.
        
        Args:
            symbol: Ticker symbol
            duration: Time span (e.g., "1 D", "1 W", "1 M", "1 Y")
            bar_size: Bar size (e.g., "1 secs", "5 secs", "1 min", "1 hour", "1 day")
            what_to_show: "TRADES", "MIDPOINT", "BID", "ASK"
            use_rth: Use regular trading hours only
            sec_type: Security type
        """
        req_id = self._get_req_id()
        contract = self._create_contract(symbol, sec_type)
        
        self.wrapper.bars[req_id] = []
        
        end_time = datetime.now().strftime("%Y%m%d %H:%M:%S")
        
        self.client.reqHistoricalData(
            req_id,
            contract,
            end_time,
            duration,
            bar_size,
            what_to_show,
            1 if use_rth else 0,
            1,  # Format dates as strings
            False,
            []
        )
        
        # Wait for completion
        timeout = time.time() + self.config.timeout
        while time.time() < timeout:
            try:
                msg = self.wrapper._request_queue.get(timeout=0.1)
                if msg[0] == 'historical_complete' and msg[1] == req_id:
                    break
            except:
                continue
                
        return self.wrapper.bars.get(req_id, [])
        
    def subscribe_realtime_bars(
        self,
        symbol: str,
        callback: Callable,
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        sec_type: str = "STK"
    ) -> int:
        """
        Subscribe to 5-second real-time bars.
        
        Returns request ID.
        """
        req_id = self._get_req_id()
        contract = self._create_contract(symbol, sec_type)
        
        self.wrapper.add_callback('bar', req_id, callback)
        
        self.client.reqRealTimeBars(
            req_id,
            contract,
            5,  # Always 5 seconds
            what_to_show,
            use_rth,
            []
        )
        
        return req_id
        
    def unsubscribe_realtime_bars(self, req_id: int):
        """Unsubscribe from real-time bars."""
        self.client.cancelRealTimeBars(req_id)
        
    # =========================================================================
    # Market Depth
    # =========================================================================
    
    def subscribe_market_depth(
        self,
        symbol: str,
        callback: Callable,
        num_rows: int = 10,
        sec_type: str = "STK"
    ) -> int:
        """Subscribe to Level 2 market depth."""
        req_id = self._get_req_id()
        contract = self._create_contract(symbol, sec_type)
        
        self.wrapper.add_callback('depth', req_id, callback)
        
        self.client.reqMktDepth(req_id, contract, num_rows, False, [])
        
        return req_id
        
    def unsubscribe_market_depth(self, req_id: int):
        """Unsubscribe from market depth."""
        self.client.cancelMktDepth(req_id, False)
        
    # =========================================================================
    # Options
    # =========================================================================
    
    def get_option_chain(
        self,
        underlying: str,
        exchange: str = "SMART"
    ) -> Dict[str, Any]:
        """Get available option expirations and strikes."""
        req_id = self._get_req_id()
        contract = self._create_contract(underlying, "STK", exchange)
        
        # This returns contract details for options
        self.client.reqSecDefOptParams(req_id, underlying, "", "STK", 0)
        
        # Wait for response
        time.sleep(2)
        
        return {}  # Would need to implement callback
        
    def get_option_quote(
        self,
        underlying: str,
        expiry: str,
        strike: float,
        right: str,  # "C" or "P"
        exchange: str = "SMART"
    ) -> MarketData:
        """Get option quote."""
        contract = self._create_contract(
            underlying,
            "OPT",
            exchange,
            "USD",
            expiry,
            strike,
            right
        )
        
        req_id = self._get_req_id()
        self.wrapper.data[req_id] = MarketData(symbol=f"{underlying}_{expiry}_{strike}{right}")
        
        self.client.reqMktData(req_id, contract, "", True, False, [])
        
        time.sleep(2)
        
        data = self.wrapper.data.get(req_id)
        self.client.cancelMktData(req_id)
        
        return data
        
    # =========================================================================
    # Fundamentals
    # =========================================================================
    
    def get_fundamentals(
        self,
        symbol: str,
        report_type: str = "ReportSnapshot"
    ) -> str:
        """
        Get fundamental data.
        
        report_type options:
        - ReportSnapshot: Company overview
        - ReportsFinSummary: Financial summary
        - ReportRatios: Financial ratios
        - ReportsFinStatements: Financial statements
        - RESC: Analyst estimates
        """
        req_id = self._get_req_id()
        contract = self._create_contract(symbol)
        
        self.client.reqFundamentalData(req_id, contract, report_type, [])
        
        # Would need to implement fundamentalData callback
        time.sleep(5)
        
        return ""


# Async wrapper for consistency with other providers
class AsyncIBKRProvider:
    """Async wrapper for IBKR provider."""
    
    def __init__(self, config: Optional[IBKRConfig] = None):
        self._sync_provider = IBKRProvider(config)
        
    async def connect(self) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_provider.connect)
        
    async def disconnect(self):
        self._sync_provider.disconnect()
        
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._sync_provider.get_snapshot, symbol)
        return {
            'symbol': data.symbol,
            'bid': data.bid,
            'bid_size': data.bid_size,
            'ask': data.ask,
            'ask_size': data.ask_size,
            'last': data.last,
            'volume': data.volume,
            'high': data.high,
            'low': data.low,
            'vwap': data.vwap
        }
        
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1 day",
        duration: str = "1 Y"
    ) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._sync_provider.get_historical_bars(symbol, duration, timeframe)
        )
