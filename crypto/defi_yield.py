"""
DeFi Yield Optimizer Module
Automated yield farming optimization across protocols.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class Protocol(Enum):
    """Supported DeFi protocols."""
    AAVE = "aave"
    COMPOUND = "compound"
    CURVE = "curve"
    CONVEX = "convex"
    YEARN = "yearn"
    LIDO = "lido"
    ROCKET_POOL = "rocket-pool"
    MAKER = "maker"
    FRAX = "frax"
    PENDLE = "pendle"


class Chain(Enum):
    """Supported chains for DeFi."""
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    BSC = "bsc"
    AVALANCHE = "avalanche"


class RiskLevel(Enum):
    """Risk classification for DeFi strategies."""
    LOW = "low"          # Blue chip protocols, stablecoin yields
    MEDIUM = "medium"    # Established protocols, some IL risk
    HIGH = "high"        # Newer protocols, complex strategies
    DEGEN = "degen"      # High risk, high reward


@dataclass
class YieldOpportunity:
    """DeFi yield opportunity."""
    protocol: Protocol
    chain: Chain
    pool: str
    apy: Decimal
    tvl: Decimal
    risk_level: RiskLevel
    tokens: List[str] = field(default_factory=list)
    rewards: List[str] = field(default_factory=list)  # Additional reward tokens
    il_risk: bool = False  # Impermanent loss risk
    audit_status: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def risk_adjusted_apy(self) -> Decimal:
        """APY adjusted for risk level."""
        multipliers = {
            RiskLevel.LOW: Decimal("1.0"),
            RiskLevel.MEDIUM: Decimal("0.8"),
            RiskLevel.HIGH: Decimal("0.5"),
            RiskLevel.DEGEN: Decimal("0.3"),
        }
        return self.apy * multipliers.get(self.risk_level, Decimal("0.5"))


@dataclass
class GasEstimate:
    """Gas cost estimate for DeFi operation."""
    action: str
    gas_units: int
    gas_price_gwei: Decimal
    cost_eth: Decimal
    cost_usd: Decimal


class DeFiYieldOptimizer:
    """
    DeFi yield optimization and auto-rotation.
    
    Features:
    - Multi-protocol yield monitoring
    - Risk-adjusted APY ranking
    - Gas cost optimization
    - Impermanent loss calculation
    - Auto-rotation strategy
    - Position tracking
    
    Supported Strategies:
    - Stablecoin lending (lowest risk)
    - LP farming (with IL risk)
    - Liquid staking (ETH, etc.)
    - Leveraged farming (high risk)
    """
    
    # DeFiLlama API
    DEFILLAMA_API = "https://yields.llama.fi"
    
    # Risk classification by protocol
    PROTOCOL_RISK = {
        Protocol.AAVE: RiskLevel.LOW,
        Protocol.COMPOUND: RiskLevel.LOW,
        Protocol.CURVE: RiskLevel.MEDIUM,
        Protocol.CONVEX: RiskLevel.MEDIUM,
        Protocol.YEARN: RiskLevel.MEDIUM,
        Protocol.LIDO: RiskLevel.LOW,
        Protocol.ROCKET_POOL: RiskLevel.LOW,
        Protocol.MAKER: RiskLevel.LOW,
        Protocol.FRAX: RiskLevel.MEDIUM,
        Protocol.PENDLE: RiskLevel.HIGH,
    }
    
    def __init__(
        self,
        min_tvl: Decimal = Decimal("10000000"),  # $10M minimum TVL
        min_apy: Decimal = Decimal("1.0"),  # 1% minimum APY
        max_risk: RiskLevel = RiskLevel.MEDIUM
    ):
        self.min_tvl = min_tvl
        self.min_apy = min_apy
        self.max_risk = max_risk
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._opportunities: List[YieldOpportunity] = []
        self._positions: Dict[str, Dict[str, Any]] = {}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_risk_level(self, pool_data: Dict) -> RiskLevel:
        """Determine risk level from pool data."""
        project = pool_data.get("project", "").lower()
        
        # Check if it's a known protocol
        for protocol, risk in self.PROTOCOL_RISK.items():
            if protocol.value in project:
                return risk
        
        # Check other risk factors
        tvl = Decimal(str(pool_data.get("tvlUsd", 0)))
        apy = Decimal(str(pool_data.get("apy", 0)))
        
        # High APY with low TVL = risky
        if apy > 50 and tvl < 1000000:
            return RiskLevel.DEGEN
        elif apy > 30:
            return RiskLevel.HIGH
        elif pool_data.get("ilRisk", False):
            return RiskLevel.MEDIUM
        
        return RiskLevel.MEDIUM
    
    async def fetch_yield_opportunities(
        self,
        chain: Optional[Chain] = None,
        protocol: Optional[Protocol] = None
    ) -> List[YieldOpportunity]:
        """
        Fetch yield opportunities from DeFiLlama.
        
        Args:
            chain: Filter by chain
            protocol: Filter by protocol
        
        Returns:
            List of yield opportunities
        """
        session = await self._get_session()
        
        try:
            url = f"{self.DEFILLAMA_API}/pools"
            async with session.get(url) as response:
                data = await response.json()
            
            opportunities = []
            
            for pool in data.get("data", []):
                tvl = Decimal(str(pool.get("tvlUsd", 0)))
                apy = Decimal(str(pool.get("apy") or 0))
                
                # Apply filters
                if tvl < self.min_tvl:
                    continue
                if apy < self.min_apy:
                    continue
                
                pool_chain = pool.get("chain", "").lower()
                if chain and pool_chain != chain.value:
                    continue
                
                pool_project = pool.get("project", "").lower()
                if protocol and protocol.value not in pool_project:
                    continue
                
                risk_level = self._get_risk_level(pool)
                
                # Filter by max risk
                risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.DEGEN]
                if risk_order.index(risk_level) > risk_order.index(self.max_risk):
                    continue
                
                # Map to Protocol enum if possible
                protocol_enum = None
                for p in Protocol:
                    if p.value in pool_project:
                        protocol_enum = p
                        break
                
                if not protocol_enum:
                    continue  # Skip unknown protocols
                
                # Map to Chain enum if possible
                chain_enum = None
                for c in Chain:
                    if c.value == pool_chain:
                        chain_enum = c
                        break
                
                if not chain_enum:
                    chain_enum = Chain.ETHEREUM
                
                opp = YieldOpportunity(
                    protocol=protocol_enum,
                    chain=chain_enum,
                    pool=pool.get("symbol", "Unknown"),
                    apy=apy,
                    tvl=tvl,
                    risk_level=risk_level,
                    tokens=pool.get("underlyingTokens", []),
                    il_risk=pool.get("ilRisk", False),
                )
                
                opportunities.append(opp)
            
            # Sort by risk-adjusted APY
            opportunities.sort(key=lambda x: x.risk_adjusted_apy, reverse=True)
            
            # Cache
            self._opportunities = opportunities
            
            logger.info(f"Found {len(opportunities)} yield opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error fetching yield opportunities: {e}")
            return []
    
    def get_top_opportunities(
        self,
        limit: int = 10,
        stablecoins_only: bool = False
    ) -> List[YieldOpportunity]:
        """
        Get top yield opportunities.
        
        Args:
            limit: Maximum results
            stablecoins_only: Filter for stablecoin pools only
        
        Returns:
            Top opportunities sorted by risk-adjusted APY
        """
        opps = self._opportunities
        
        if stablecoins_only:
            stablecoin_symbols = ["USDC", "USDT", "DAI", "FRAX", "LUSD", "GUSD"]
            opps = [
                o for o in opps
                if any(s in o.pool.upper() for s in stablecoin_symbols)
            ]
        
        return opps[:limit]
    
    def calculate_impermanent_loss(
        self,
        price_change_pct: float,
        is_50_50: bool = True
    ) -> float:
        """
        Calculate impermanent loss for LP position.
        
        Args:
            price_change_pct: Price change percentage (e.g., 50 for 50% increase)
            is_50_50: True for 50/50 pools, False for other ratios
        
        Returns:
            IL as percentage (e.g., 5.72 for 5.72% loss)
        """
        if not is_50_50:
            return 0.0  # Would need pool weights for other ratios
        
        price_ratio = 1 + (price_change_pct / 100)
        
        # IL formula for 50/50 pool
        il = 2 * (price_ratio ** 0.5) / (1 + price_ratio) - 1
        
        return abs(il) * 100
    
    def calculate_net_apy(
        self,
        base_apy: Decimal,
        expected_il: float,
        gas_cost_usd: Decimal,
        position_size_usd: Decimal,
        hold_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate net APY after costs and IL.
        
        Args:
            base_apy: Gross APY percentage
            expected_il: Expected impermanent loss percentage
            gas_cost_usd: Total gas costs (entry + exit)
            position_size_usd: Position size
            hold_days: Expected hold period
        
        Returns:
            Net APY analysis
        """
        # Annualized yield
        annual_yield = position_size_usd * (base_apy / 100)
        
        # Pro-rated yield for hold period
        period_yield = annual_yield * Decimal(hold_days) / Decimal(365)
        
        # IL cost
        il_cost = position_size_usd * Decimal(str(expected_il / 100))
        
        # Net profit
        net_profit = period_yield - il_cost - gas_cost_usd
        
        # Annualized net APY
        net_apy = (net_profit / position_size_usd) * Decimal(365) / Decimal(hold_days) * 100
        
        return {
            "gross_apy": float(base_apy),
            "expected_il_pct": expected_il,
            "il_cost_usd": float(il_cost),
            "gas_cost_usd": float(gas_cost_usd),
            "period_yield_usd": float(period_yield),
            "net_profit_usd": float(net_profit),
            "net_apy": float(net_apy),
            "break_even_days": int(gas_cost_usd / (annual_yield / 365)) if annual_yield > 0 else 999,
            "profitable": net_profit > 0
        }
    
    def get_rotation_recommendation(
        self,
        current_positions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations for position rotation.
        
        Args:
            current_positions: List of current positions with APY
        
        Returns:
            Rotation recommendations
        """
        recommendations = []
        
        if not self._opportunities:
            return [{"message": "Fetch opportunities first"}]
        
        for position in current_positions:
            current_apy = Decimal(str(position.get("apy", 0)))
            current_protocol = position.get("protocol", "")
            
            # Find better opportunities
            better = [
                o for o in self._opportunities
                if o.risk_adjusted_apy > current_apy * Decimal("1.2")  # 20% better
                and o.protocol.value != current_protocol
            ]
            
            if better:
                best = better[0]
                
                recommendations.append({
                    "action": "ROTATE",
                    "from": {
                        "protocol": current_protocol,
                        "pool": position.get("pool"),
                        "apy": float(current_apy)
                    },
                    "to": {
                        "protocol": best.protocol.value,
                        "pool": best.pool,
                        "apy": float(best.apy),
                        "risk_adjusted_apy": float(best.risk_adjusted_apy)
                    },
                    "improvement_pct": float((best.apy - current_apy) / current_apy * 100),
                    "reason": f"Better risk-adjusted yield available on {best.protocol.value}"
                })
        
        return recommendations
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of yield landscape."""
        if not self._opportunities:
            return {"message": "No data. Fetch opportunities first."}
        
        by_chain = {}
        by_protocol = {}
        by_risk = {}
        
        for opp in self._opportunities:
            # By chain
            chain_key = opp.chain.value
            if chain_key not in by_chain:
                by_chain[chain_key] = {"count": 0, "avg_apy": Decimal("0")}
            by_chain[chain_key]["count"] += 1
            by_chain[chain_key]["avg_apy"] += opp.apy
            
            # By protocol
            proto_key = opp.protocol.value
            if proto_key not in by_protocol:
                by_protocol[proto_key] = {"count": 0, "avg_apy": Decimal("0")}
            by_protocol[proto_key]["count"] += 1
            by_protocol[proto_key]["avg_apy"] += opp.apy
            
            # By risk
            risk_key = opp.risk_level.value
            if risk_key not in by_risk:
                by_risk[risk_key] = {"count": 0, "avg_apy": Decimal("0")}
            by_risk[risk_key]["count"] += 1
            by_risk[risk_key]["avg_apy"] += opp.apy
        
        # Calculate averages
        for d in [by_chain, by_protocol, by_risk]:
            for k, v in d.items():
                if v["count"] > 0:
                    v["avg_apy"] = float(v["avg_apy"] / v["count"])
        
        return {
            "total_opportunities": len(self._opportunities),
            "top_apy": float(self._opportunities[0].apy) if self._opportunities else 0,
            "by_chain": by_chain,
            "by_protocol": by_protocol,
            "by_risk": by_risk,
            "timestamp": datetime.utcnow().isoformat()
        }
