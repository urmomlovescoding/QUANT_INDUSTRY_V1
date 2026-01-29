"""
CEX-DEX Arbitrage Detection
===========================
Identifies arbitrage between centralized and decentralized exchanges.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import logging
from collections import defaultdict

from .price_feeds import Exchange, ExchangePrice, AssetType

logger = logging.getLogger(__name__)


class DexProtocol(Enum):
    """DEX protocols."""
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    SUSHISWAP = "sushiswap"
    CURVE = "curve"
    BALANCER = "balancer"
    PANCAKESWAP = "pancakeswap"
    QUICKSWAP = "quickswap"
    TRADERJOE = "traderjoe"
    CAMELOT = "camelot"


class Chain(Enum):
    """Blockchain networks."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    BASE = "base"
    SOLANA = "solana"


@dataclass
class DexQuote:
    """Quote from a DEX."""
    protocol: DexProtocol
    chain: Chain
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    price: float  # amount_out / amount_in
    price_impact: float  # Percentage
    
    # Pool info
    pool_address: str = ""
    pool_fee: float = 0.003  # 0.3% default
    liquidity: float = 0.0
    
    # Gas
    estimated_gas: int = 0
    gas_price_gwei: float = 0.0
    gas_cost_usd: float = 0.0
    
    # Timing
    timestamp: datetime = field(default_factory=datetime.now)
    block_number: int = 0
    
    @property
    def effective_price(self) -> float:
        """Price including gas costs."""
        if self.amount_in > 0:
            total_cost = self.amount_in + self.gas_cost_usd
            return self.amount_out / total_cost
        return self.price
    
    @property
    def is_stale(self) -> bool:
        return (datetime.now() - self.timestamp).total_seconds() > 15
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "chain": self.chain.value,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in": self.amount_in,
            "amount_out": self.amount_out,
            "price": self.price,
            "price_impact": self.price_impact,
            "gas_cost_usd": self.gas_cost_usd,
            "effective_price": self.effective_price,
        }


@dataclass
class CexDexOpportunity:
    """Arbitrage opportunity between CEX and DEX."""
    id: str
    detected_at: datetime
    
    # Asset
    symbol: str
    base_token: str
    quote_token: str
    
    # CEX side
    cex_exchange: Exchange
    cex_side: str  # "buy" or "sell"
    cex_price: float
    cex_size: float
    
    # DEX side
    dex_protocol: DexProtocol
    dex_chain: Chain
    dex_side: str  # "buy" or "sell"
    dex_price: float
    dex_size: float
    dex_quote: Optional[DexQuote] = None
    
    # Profit
    price_diff_pct: float = 0.0
    gross_profit_pct: float = 0.0
    net_profit_pct: float = 0.0
    profit_usd: float = 0.0
    
    # Costs
    cex_fees: float = 0.0
    dex_fees: float = 0.0
    gas_cost: float = 0.0
    bridge_cost: float = 0.0  # If cross-chain
    slippage_estimate: float = 0.0
    
    # Constraints
    max_size: float = 0.0
    
    # Risk
    execution_time_estimate: float = 0.0  # seconds
    mev_risk: float = 0.0  # 0-1, risk of MEV extraction
    reorg_risk: float = 0.0  # 0-1, risk of blockchain reorg
    
    # Status
    confidence: float = 0.0
    expires_at: Optional[datetime] = None
    
    @property
    def direction(self) -> str:
        """Which way is the arb."""
        if self.cex_side == "buy":
            return "cex_to_dex"  # Buy on CEX, sell on DEX
        return "dex_to_cex"  # Buy on DEX, sell on CEX
    
    @property
    def is_valid(self) -> bool:
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return self.net_profit_pct > 0
    
    @property
    def total_cost_pct(self) -> float:
        return self.gross_profit_pct - self.net_profit_pct
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "detected_at": self.detected_at.isoformat(),
            "symbol": self.symbol,
            "direction": self.direction,
            "cex_exchange": self.cex_exchange.value,
            "cex_price": self.cex_price,
            "dex_protocol": self.dex_protocol.value,
            "dex_chain": self.dex_chain.value,
            "dex_price": self.dex_price,
            "price_diff_pct": self.price_diff_pct,
            "gross_profit_pct": self.gross_profit_pct,
            "net_profit_pct": self.net_profit_pct,
            "profit_usd": self.profit_usd,
            "max_size": self.max_size,
            "gas_cost": self.gas_cost,
            "confidence": self.confidence,
        }


@dataclass
class CexDexConfig:
    """Configuration for CEX-DEX arbitrage."""
    # Profit thresholds
    min_price_diff_pct: float = 0.5  # 0.5% minimum spread
    min_net_profit_pct: float = 0.2
    min_profit_usd: float = 20.0
    
    # Fees
    cex_taker_fee: float = 0.001  # 0.1%
    dex_swap_fee: float = 0.003  # 0.3%
    
    # Gas estimates (in USD)
    gas_estimates: Dict[Chain, float] = field(default_factory=lambda: {
        Chain.ETHEREUM: 15.0,
        Chain.BSC: 0.5,
        Chain.POLYGON: 0.1,
        Chain.ARBITRUM: 0.5,
        Chain.OPTIMISM: 0.3,
        Chain.AVALANCHE: 0.5,
        Chain.BASE: 0.2,
    })
    
    # Bridge costs
    bridge_costs: Dict[Tuple[Chain, Chain], float] = field(default_factory=dict)
    
    # Size constraints
    min_size_usd: float = 100.0
    max_size_usd: float = 50_000.0
    
    # Timing
    opportunity_ttl_seconds: float = 10.0
    
    # Risk thresholds
    max_price_impact_pct: float = 1.0
    max_mev_risk: float = 0.3


class CexDexArbDetector:
    """
    Detects arbitrage between CEX and DEX.
    
    Monitors:
    - CEX prices (Binance, Coinbase, etc.)
    - DEX quotes (Uniswap, Sushi, etc.)
    - Gas prices
    - Liquidity depth
    """
    
    def __init__(self, config: Optional[CexDexConfig] = None):
        self.config = config or CexDexConfig()
        
        # Price data
        self._cex_prices: Dict[str, Dict[Exchange, ExchangePrice]] = defaultdict(dict)
        self._dex_quotes: Dict[str, Dict[DexProtocol, DexQuote]] = defaultdict(dict)
        
        # Gas prices by chain
        self._gas_prices: Dict[Chain, float] = {}
        
        # Opportunities
        self._opportunities: Dict[str, CexDexOpportunity] = {}
        self._opp_counter = 0
        
    def update_cex_price(self, price: ExchangePrice):
        """Update CEX price."""
        self._cex_prices[price.symbol][price.exchange] = price
        
    def update_dex_quote(self, quote: DexQuote):
        """Update DEX quote."""
        symbol = f"{quote.token_in}/{quote.token_out}"
        self._dex_quotes[symbol][quote.protocol] = quote
        
    def update_gas_price(self, chain: Chain, gwei: float):
        """Update gas price for chain."""
        self._gas_prices[chain] = gwei
        
    def scan(self, symbol: str) -> List[CexDexOpportunity]:
        """Scan for CEX-DEX opportunities for symbol."""
        opportunities = []
        
        cex_prices = self._cex_prices.get(symbol, {})
        dex_quotes = self._dex_quotes.get(symbol, {})
        
        if not cex_prices or not dex_quotes:
            return opportunities
            
        for cex_exchange, cex_price in cex_prices.items():
            if cex_price.is_stale:
                continue
                
            for dex_protocol, dex_quote in dex_quotes.items():
                if dex_quote.is_stale:
                    continue
                    
                # Check both directions
                
                # Direction 1: Buy on CEX (at ask), sell on DEX
                opp1 = self._check_opportunity(
                    symbol=symbol,
                    cex_exchange=cex_exchange,
                    cex_price=cex_price.ask,
                    cex_size=cex_price.ask_size,
                    cex_side="buy",
                    dex_protocol=dex_protocol,
                    dex_quote=dex_quote,
                    dex_price=dex_quote.price,
                    dex_side="sell",
                )
                if opp1:
                    opportunities.append(opp1)
                    
                # Direction 2: Buy on DEX, sell on CEX (at bid)
                opp2 = self._check_opportunity(
                    symbol=symbol,
                    cex_exchange=cex_exchange,
                    cex_price=cex_price.bid,
                    cex_size=cex_price.bid_size,
                    cex_side="sell",
                    dex_protocol=dex_protocol,
                    dex_quote=dex_quote,
                    dex_price=dex_quote.price,
                    dex_side="buy",
                )
                if opp2:
                    opportunities.append(opp2)
                    
        # Store valid opportunities
        for opp in opportunities:
            if opp.is_valid:
                self._opportunities[opp.id] = opp
                
        self._cleanup_expired()
        return opportunities
    
    def _check_opportunity(
        self,
        symbol: str,
        cex_exchange: Exchange,
        cex_price: float,
        cex_size: float,
        cex_side: str,
        dex_protocol: DexProtocol,
        dex_quote: DexQuote,
        dex_price: float,
        dex_side: str,
    ) -> Optional[CexDexOpportunity]:
        """Check if there's a profitable opportunity."""
        # Calculate price difference
        if cex_side == "buy":
            # Buy CEX (pay cex_price), sell DEX (receive dex_price)
            buy_price = cex_price
            sell_price = dex_price
        else:
            # Buy DEX (pay dex_price), sell CEX (receive cex_price)
            buy_price = dex_price
            sell_price = cex_price
            
        if sell_price <= buy_price:
            return None
            
        price_diff_pct = (sell_price - buy_price) / buy_price * 100
        
        if price_diff_pct < self.config.min_price_diff_pct:
            return None
            
        # Check price impact
        if dex_quote.price_impact > self.config.max_price_impact_pct:
            return None
            
        # Calculate max size
        max_size = min(
            cex_size * cex_price,
            dex_quote.liquidity * 0.1,  # Max 10% of pool
            self.config.max_size_usd,
        )
        
        if max_size < self.config.min_size_usd:
            return None
            
        # Calculate costs
        cex_fees = max_size * self.config.cex_taker_fee
        dex_fees = max_size * self.config.dex_swap_fee
        gas_cost = self.config.gas_estimates.get(dex_quote.chain, 5.0)
        
        # Slippage estimate
        slippage = dex_quote.price_impact / 100 * max_size
        
        total_cost = cex_fees + dex_fees + gas_cost + slippage
        gross_profit = price_diff_pct / 100 * max_size
        net_profit = gross_profit - total_cost
        net_profit_pct = (net_profit / max_size) * 100
        
        if net_profit_pct < self.config.min_net_profit_pct:
            return None
            
        if net_profit < self.config.min_profit_usd:
            return None
            
        # Estimate MEV risk
        mev_risk = self._estimate_mev_risk(dex_quote.chain, max_size)
        
        if mev_risk > self.config.max_mev_risk:
            return None
            
        self._opp_counter += 1
        
        # Parse symbol
        parts = symbol.split("/") if "/" in symbol else [symbol[:3], symbol[3:]]
        base_token = parts[0] if parts else symbol
        quote_token = parts[1] if len(parts) > 1 else "USD"
        
        return CexDexOpportunity(
            id=f"CXD-{self._opp_counter:08d}",
            detected_at=datetime.now(),
            symbol=symbol,
            base_token=base_token,
            quote_token=quote_token,
            cex_exchange=cex_exchange,
            cex_side=cex_side,
            cex_price=cex_price,
            cex_size=cex_size,
            dex_protocol=dex_protocol,
            dex_chain=dex_quote.chain,
            dex_side=dex_side,
            dex_price=dex_price,
            dex_size=dex_quote.amount_out,
            dex_quote=dex_quote,
            price_diff_pct=price_diff_pct,
            gross_profit_pct=price_diff_pct,
            net_profit_pct=net_profit_pct,
            profit_usd=net_profit,
            cex_fees=cex_fees,
            dex_fees=dex_fees,
            gas_cost=gas_cost,
            slippage_estimate=slippage,
            max_size=max_size,
            mev_risk=mev_risk,
            confidence=self._calculate_confidence(net_profit_pct, mev_risk),
            expires_at=datetime.now() + timedelta(seconds=self.config.opportunity_ttl_seconds),
        )
    
    def _estimate_mev_risk(self, chain: Chain, size_usd: float) -> float:
        """Estimate MEV extraction risk."""
        # Higher risk on Ethereum mainnet
        chain_risk = {
            Chain.ETHEREUM: 0.4,
            Chain.BSC: 0.2,
            Chain.POLYGON: 0.15,
            Chain.ARBITRUM: 0.1,
            Chain.OPTIMISM: 0.1,
            Chain.AVALANCHE: 0.15,
            Chain.BASE: 0.1,
        }.get(chain, 0.2)
        
        # Larger sizes more attractive to MEV
        size_risk = min(0.3, size_usd / 100_000)
        
        return min(1.0, chain_risk + size_risk)
    
    def _calculate_confidence(
        self,
        net_profit_pct: float,
        mev_risk: float,
    ) -> float:
        """Calculate opportunity confidence."""
        profit_score = min(1.0, net_profit_pct / 1.0)  # Max at 1%
        risk_score = 1 - mev_risk
        return profit_score * 0.6 + risk_score * 0.4
    
    def _cleanup_expired(self):
        """Remove expired opportunities."""
        now = datetime.now()
        expired = [
            opp_id for opp_id, opp in self._opportunities.items()
            if opp.expires_at and now > opp.expires_at
        ]
        for opp_id in expired:
            del self._opportunities[opp_id]
    
    def get_opportunities(
        self,
        min_profit_pct: float = 0.0,
        chain: Optional[Chain] = None,
    ) -> List[CexDexOpportunity]:
        """Get active opportunities."""
        opps = [
            opp for opp in self._opportunities.values()
            if opp.is_valid
            and opp.net_profit_pct >= min_profit_pct
            and (chain is None or opp.dex_chain == chain)
        ]
        opps.sort(key=lambda x: x.net_profit_pct, reverse=True)
        return opps
    
    def scan_all_symbols(self) -> List[CexDexOpportunity]:
        """Scan all tracked symbols."""
        all_opps = []
        
        symbols = set(self._cex_prices.keys()) | set(self._dex_quotes.keys())
        for symbol in symbols:
            opps = self.scan(symbol)
            all_opps.extend(opps)
            
        all_opps.sort(key=lambda x: x.net_profit_pct, reverse=True)
        return all_opps


class DexAggregator:
    """
    Aggregates quotes from multiple DEX protocols.
    """
    
    def __init__(self):
        self._quotes: Dict[str, List[DexQuote]] = defaultdict(list)
        
    def add_quote(self, quote: DexQuote):
        """Add quote from a DEX."""
        symbol = f"{quote.token_in}/{quote.token_out}"
        self._quotes[symbol].append(quote)
        
        # Keep only recent quotes per protocol
        self._quotes[symbol] = [
            q for q in self._quotes[symbol]
            if not q.is_stale
        ][-50:]  # Max 50 quotes per symbol
        
    def get_best_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        chain: Optional[Chain] = None,
    ) -> Optional[DexQuote]:
        """Get best quote for trade."""
        symbol = f"{token_in}/{token_out}"
        quotes = self._quotes.get(symbol, [])
        
        if chain:
            quotes = [q for q in quotes if q.chain == chain]
            
        # Filter by amount (need sufficient liquidity)
        quotes = [
            q for q in quotes
            if q.liquidity >= amount_in * 10  # 10x buffer
            and not q.is_stale
        ]
        
        if not quotes:
            return None
            
        # Best = highest output for given input
        return max(quotes, key=lambda q: q.effective_price)
    
    def get_all_quotes(
        self,
        token_in: str,
        token_out: str,
    ) -> List[DexQuote]:
        """Get all quotes for pair."""
        symbol = f"{token_in}/{token_out}"
        return [q for q in self._quotes.get(symbol, []) if not q.is_stale]
