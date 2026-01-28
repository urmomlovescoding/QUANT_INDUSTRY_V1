"""
Tax Lot Tracking System
=======================
Institutional-grade tax lot management for optimal tax efficiency.

Features:
- Multiple cost basis methods (FIFO, LIFO, HIFO, Specific ID, Average Cost)
- Wash sale detection and adjustment
- Short-term vs long-term gains classification
- Tax-loss harvesting opportunities
- Realized/unrealized gains tracking
- Tax liability estimation
- IRS Schedule D / Form 8949 data export
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional
from collections import defaultdict
import heapq
import json

logger = logging.getLogger(__name__)


class CostBasisMethod(Enum):
    """IRS-approved cost basis methods"""
    FIFO = "fifo"           # First In, First Out
    LIFO = "lifo"           # Last In, First Out  
    HIFO = "hifo"           # Highest In, First Out (tax efficient)
    LIFO_BY_DATE = "lifo_by_date"  # LIFO within same day
    SPECIFIC_ID = "specific_id"    # Specific lot identification
    AVERAGE_COST = "average_cost"  # Average cost (mutual funds only)
    MIN_TAX = "min_tax"     # Automatic tax optimization


class GainType(Enum):
    """Tax classification of gains"""
    SHORT_TERM = "short_term"   # Held <= 1 year
    LONG_TERM = "long_term"     # Held > 1 year


@dataclass
class TaxLot:
    """Individual tax lot representing a purchase"""
    lot_id: str
    symbol: str
    quantity: Decimal
    cost_per_share: Decimal
    acquisition_date: datetime
    acquisition_type: str = "purchase"  # purchase, dividend_reinvest, transfer, gift, inheritance
    original_quantity: Decimal = None
    wash_sale_adjustment: Decimal = Decimal("0")
    wash_sale_disallowed: Decimal = Decimal("0")
    broker_lot_id: Optional[str] = None
    notes: str = ""
    
    def __post_init__(self):
        if self.original_quantity is None:
            self.original_quantity = self.quantity
        self.quantity = Decimal(str(self.quantity))
        self.cost_per_share = Decimal(str(self.cost_per_share))
        self.wash_sale_adjustment = Decimal(str(self.wash_sale_adjustment))
    
    @property
    def total_cost_basis(self) -> Decimal:
        """Total cost basis including wash sale adjustments"""
        return (self.cost_per_share * self.quantity) + self.wash_sale_adjustment
    
    @property
    def adjusted_cost_per_share(self) -> Decimal:
        """Cost per share after wash sale adjustment"""
        if self.quantity == 0:
            return Decimal("0")
        return self.total_cost_basis / self.quantity
    
    def holding_period_days(self, as_of: datetime = None) -> int:
        """Days held as of a given date"""
        as_of = as_of or datetime.now()
        return (as_of - self.acquisition_date).days
    
    def gain_type(self, sale_date: datetime) -> GainType:
        """Determine if gain is short-term or long-term"""
        days_held = (sale_date - self.acquisition_date).days
        return GainType.LONG_TERM if days_held > 365 else GainType.SHORT_TERM
    
    def to_dict(self) -> dict:
        return {
            "lot_id": self.lot_id,
            "symbol": self.symbol,
            "quantity": str(self.quantity),
            "cost_per_share": str(self.cost_per_share),
            "acquisition_date": self.acquisition_date.isoformat(),
            "acquisition_type": self.acquisition_type,
            "original_quantity": str(self.original_quantity),
            "wash_sale_adjustment": str(self.wash_sale_adjustment),
            "wash_sale_disallowed": str(self.wash_sale_disallowed),
            "broker_lot_id": self.broker_lot_id,
            "notes": self.notes,
            "total_cost_basis": str(self.total_cost_basis),
            "adjusted_cost_per_share": str(self.adjusted_cost_per_share)
        }


@dataclass
class ClosedLot:
    """Record of a closed (sold) tax lot"""
    lot_id: str
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    proceeds: Decimal
    acquisition_date: datetime
    sale_date: datetime
    gain_type: GainType
    wash_sale_disallowed: Decimal = Decimal("0")
    is_wash_sale: bool = False
    replacement_lot_id: Optional[str] = None
    
    @property
    def gross_gain(self) -> Decimal:
        """Gain before wash sale adjustment"""
        return self.proceeds - self.cost_basis
    
    @property
    def realized_gain(self) -> Decimal:
        """Net gain after wash sale disallowance"""
        return self.gross_gain + self.wash_sale_disallowed  # Disallowed is negative for losses
    
    @property
    def holding_period_days(self) -> int:
        return (self.sale_date - self.acquisition_date).days
    
    def to_form_8949(self) -> dict:
        """Export data for IRS Form 8949"""
        return {
            "description": f"{self.quantity} sh {self.symbol}",
            "date_acquired": self.acquisition_date.strftime("%m/%d/%Y"),
            "date_sold": self.sale_date.strftime("%m/%d/%Y"),
            "proceeds": str(self.proceeds.quantize(Decimal("0.01"))),
            "cost_basis": str(self.cost_basis.quantize(Decimal("0.01"))),
            "adjustment_code": "W" if self.is_wash_sale else "",
            "adjustment_amount": str(self.wash_sale_disallowed.quantize(Decimal("0.01"))) if self.is_wash_sale else "",
            "gain_or_loss": str(self.realized_gain.quantize(Decimal("0.01"))),
            "term": "short" if self.gain_type == GainType.SHORT_TERM else "long"
        }


@dataclass
class TaxLossHarvestingOpportunity:
    """Identified tax-loss harvesting opportunity"""
    symbol: str
    lot_id: str
    unrealized_loss: Decimal
    current_price: Decimal
    cost_basis: Decimal
    quantity: Decimal
    gain_type: GainType
    days_held: int
    wash_sale_risk: bool  # True if sold within last 30 days
    estimated_tax_savings: Decimal
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "lot_id": self.lot_id,
            "unrealized_loss": str(self.unrealized_loss),
            "current_price": str(self.current_price),
            "cost_basis": str(self.cost_basis),
            "quantity": str(self.quantity),
            "gain_type": self.gain_type.value,
            "days_held": self.days_held,
            "wash_sale_risk": self.wash_sale_risk,
            "estimated_tax_savings": str(self.estimated_tax_savings)
        }


class TaxLotTracker:
    """
    Comprehensive tax lot tracking system.
    
    Features:
    - Track all open and closed tax lots
    - Multiple cost basis methods
    - Automatic wash sale detection and handling
    - Tax-loss harvesting identification
    - Realized/unrealized gains reporting
    """
    
    def __init__(
        self,
        default_method: CostBasisMethod = CostBasisMethod.FIFO,
        short_term_rate: float = 0.37,  # Top marginal rate
        long_term_rate: float = 0.20,
        state_rate: float = 0.05,
        wash_sale_window_days: int = 30
    ):
        self.default_method = default_method
        self.short_term_rate = Decimal(str(short_term_rate))
        self.long_term_rate = Decimal(str(long_term_rate))
        self.state_rate = Decimal(str(state_rate))
        self.wash_sale_window = wash_sale_window_days
        
        # Storage
        self.open_lots: dict[str, list[TaxLot]] = defaultdict(list)  # symbol -> lots
        self.closed_lots: list[ClosedLot] = []
        self.lot_counter = 0
        
        # Wash sale tracking
        self.recent_sales: dict[str, list[tuple[datetime, Decimal, Decimal]]] = defaultdict(list)  # symbol -> [(date, qty, loss)]
        
        # Per-symbol cost basis method override
        self.symbol_methods: dict[str, CostBasisMethod] = {}
        
        logger.info(f"TaxLotTracker initialized with default method: {default_method.value}")
    
    def _generate_lot_id(self) -> str:
        """Generate unique lot ID"""
        self.lot_counter += 1
        return f"LOT-{self.lot_counter:08d}"
    
    def set_cost_basis_method(self, symbol: str, method: CostBasisMethod):
        """Set cost basis method for a specific symbol"""
        self.symbol_methods[symbol] = method
        logger.info(f"Set {symbol} cost basis method to {method.value}")
    
    def get_cost_basis_method(self, symbol: str) -> CostBasisMethod:
        """Get cost basis method for a symbol"""
        return self.symbol_methods.get(symbol, self.default_method)
    
    def record_purchase(
        self,
        symbol: str,
        quantity: float,
        price: float,
        date: datetime,
        acquisition_type: str = "purchase",
        broker_lot_id: str = None,
        notes: str = ""
    ) -> TaxLot:
        """
        Record a new purchase creating a tax lot.
        
        Args:
            symbol: Ticker symbol
            quantity: Number of shares
            price: Price per share
            date: Acquisition date
            acquisition_type: How acquired (purchase, dividend_reinvest, etc.)
            broker_lot_id: Broker's lot identifier for reconciliation
            notes: Additional notes
            
        Returns:
            Created TaxLot
        """
        quantity = Decimal(str(quantity))
        price = Decimal(str(price))
        
        # Check for wash sale adjustment from recent losses
        wash_adjustment = self._check_wash_sale_on_purchase(symbol, date, quantity)
        
        lot = TaxLot(
            lot_id=self._generate_lot_id(),
            symbol=symbol,
            quantity=quantity,
            cost_per_share=price,
            acquisition_date=date,
            acquisition_type=acquisition_type,
            wash_sale_adjustment=wash_adjustment,
            broker_lot_id=broker_lot_id,
            notes=notes
        )
        
        self.open_lots[symbol].append(lot)
        
        if wash_adjustment > 0:
            logger.info(
                f"Created lot {lot.lot_id}: {quantity} {symbol} @ ${price} "
                f"(wash sale adjustment: ${wash_adjustment})"
            )
        else:
            logger.info(f"Created lot {lot.lot_id}: {quantity} {symbol} @ ${price}")
        
        return lot
    
    def _check_wash_sale_on_purchase(
        self,
        symbol: str,
        purchase_date: datetime,
        quantity: Decimal
    ) -> Decimal:
        """Check if this purchase triggers wash sale from recent loss"""
        adjustment = Decimal("0")
        window_start = purchase_date - timedelta(days=self.wash_sale_window)
        
        remaining_qty = quantity
        sales_to_remove = []
        
        for i, (sale_date, sale_qty, loss_amount) in enumerate(self.recent_sales[symbol]):
            if remaining_qty <= 0:
                break
            if window_start <= sale_date <= purchase_date and loss_amount < 0:
                # This is a wash sale
                apply_qty = min(remaining_qty, sale_qty)
                apply_ratio = apply_qty / sale_qty
                disallowed = abs(loss_amount) * apply_ratio
                adjustment += disallowed
                remaining_qty -= apply_qty
                
                # Update or mark for removal
                new_qty = sale_qty - apply_qty
                if new_qty <= 0:
                    sales_to_remove.append(i)
                else:
                    self.recent_sales[symbol][i] = (
                        sale_date,
                        new_qty,
                        loss_amount * (new_qty / sale_qty)
                    )
                
                logger.warning(
                    f"Wash sale detected: ${disallowed} loss disallowed and added to cost basis"
                )
        
        # Remove fully applied sales
        for i in reversed(sales_to_remove):
            self.recent_sales[symbol].pop(i)
        
        return adjustment
    
    def record_sale(
        self,
        symbol: str,
        quantity: float,
        price: float,
        date: datetime,
        method: CostBasisMethod = None,
        specific_lot_ids: list[str] = None
    ) -> list[ClosedLot]:
        """
        Record a sale and close appropriate tax lots.
        
        Args:
            symbol: Ticker symbol
            quantity: Number of shares sold
            price: Sale price per share
            date: Sale date
            method: Cost basis method (uses symbol/default if not specified)
            specific_lot_ids: For SPECIFIC_ID method, which lots to sell
            
        Returns:
            List of closed lots
        """
        quantity = Decimal(str(quantity))
        price = Decimal(str(price))
        method = method or self.get_cost_basis_method(symbol)
        
        if symbol not in self.open_lots or not self.open_lots[symbol]:
            raise ValueError(f"No open lots for {symbol}")
        
        total_available = sum(lot.quantity for lot in self.open_lots[symbol])
        if quantity > total_available:
            raise ValueError(
                f"Insufficient shares: trying to sell {quantity} but only {total_available} available"
            )
        
        # Select lots based on method
        if method == CostBasisMethod.SPECIFIC_ID:
            if not specific_lot_ids:
                raise ValueError("SPECIFIC_ID method requires specific_lot_ids")
            lots_to_sell = self._select_specific_lots(symbol, quantity, specific_lot_ids)
        elif method == CostBasisMethod.MIN_TAX:
            lots_to_sell = self._select_min_tax_lots(symbol, quantity, price, date)
        else:
            lots_to_sell = self._select_lots_by_method(symbol, quantity, method)
        
        # Process sales
        closed = []
        for lot, sell_qty in lots_to_sell:
            closed_lot = self._close_lot(lot, sell_qty, price, date)
            closed.append(closed_lot)
        
        # Track for wash sale detection
        total_gain = sum(c.gross_gain for c in closed)
        if total_gain < 0:
            self.recent_sales[symbol].append((date, quantity, total_gain))
            # Check for wash sale against existing lots bought in window
            self._check_wash_sale_on_sale(symbol, date, closed)
        
        return closed
    
    def _select_lots_by_method(
        self,
        symbol: str,
        quantity: Decimal,
        method: CostBasisMethod
    ) -> list[tuple[TaxLot, Decimal]]:
        """Select lots based on cost basis method"""
        lots = self.open_lots[symbol].copy()
        
        if method == CostBasisMethod.FIFO:
            lots.sort(key=lambda x: x.acquisition_date)
        elif method == CostBasisMethod.LIFO:
            lots.sort(key=lambda x: x.acquisition_date, reverse=True)
        elif method == CostBasisMethod.HIFO:
            lots.sort(key=lambda x: x.adjusted_cost_per_share, reverse=True)
        elif method == CostBasisMethod.AVERAGE_COST:
            # For average cost, we treat all shares as one lot
            return self._select_average_cost(symbol, quantity)
        
        selected = []
        remaining = quantity
        
        for lot in lots:
            if remaining <= 0:
                break
            take = min(lot.quantity, remaining)
            selected.append((lot, take))
            remaining -= take
        
        return selected
    
    def _select_average_cost(
        self,
        symbol: str,
        quantity: Decimal
    ) -> list[tuple[TaxLot, Decimal]]:
        """Handle average cost method"""
        lots = self.open_lots[symbol]
        total_cost = sum(lot.total_cost_basis for lot in lots)
        total_shares = sum(lot.quantity for lot in lots)
        avg_cost = total_cost / total_shares
        
        # Proportionally reduce all lots
        selected = []
        ratio = quantity / total_shares
        remaining = quantity
        
        for lot in lots[:-1]:
            take = (lot.quantity * ratio).quantize(Decimal("0.0001"))
            take = min(take, remaining)
            if take > 0:
                # Temporarily adjust cost basis for this sale
                original_cost = lot.cost_per_share
                lot.cost_per_share = avg_cost
                selected.append((lot, take))
                lot.cost_per_share = original_cost
                remaining -= take
        
        # Last lot takes remainder
        if remaining > 0 and lots:
            lot = lots[-1]
            original_cost = lot.cost_per_share
            lot.cost_per_share = avg_cost
            selected.append((lot, remaining))
            lot.cost_per_share = original_cost
        
        return selected
    
    def _select_min_tax_lots(
        self,
        symbol: str,
        quantity: Decimal,
        sale_price: Decimal,
        sale_date: datetime
    ) -> list[tuple[TaxLot, Decimal]]:
        """Select lots to minimize tax liability"""
        lots = self.open_lots[symbol]
        
        # Score each lot by tax impact
        scored_lots = []
        for lot in lots:
            gain_per_share = sale_price - lot.adjusted_cost_per_share
            gain_type = lot.gain_type(sale_date)
            
            if gain_type == GainType.LONG_TERM:
                tax_rate = self.long_term_rate
            else:
                tax_rate = self.short_term_rate
            
            # Tax cost per share (negative means tax benefit)
            tax_impact = gain_per_share * tax_rate
            
            # Prioritize: 1) long-term losses, 2) short-term losses, 
            # 3) long-term gains, 4) short-term gains
            if gain_per_share < 0:
                # Losses - prefer short term (higher offset value)
                priority = 0 if gain_type == GainType.SHORT_TERM else 1
            else:
                # Gains - prefer long term (lower rate)
                priority = 2 if gain_type == GainType.LONG_TERM else 3
            
            scored_lots.append((priority, tax_impact, lot))
        
        # Sort by priority then by tax impact
        scored_lots.sort(key=lambda x: (x[0], x[1]))
        
        selected = []
        remaining = quantity
        
        for _, _, lot in scored_lots:
            if remaining <= 0:
                break
            take = min(lot.quantity, remaining)
            selected.append((lot, take))
            remaining -= take
        
        return selected
    
    def _select_specific_lots(
        self,
        symbol: str,
        quantity: Decimal,
        lot_ids: list[str]
    ) -> list[tuple[TaxLot, Decimal]]:
        """Select specific lots by ID"""
        lots_by_id = {lot.lot_id: lot for lot in self.open_lots[symbol]}
        
        selected = []
        remaining = quantity
        
        for lot_id in lot_ids:
            if remaining <= 0:
                break
            if lot_id not in lots_by_id:
                raise ValueError(f"Lot {lot_id} not found for {symbol}")
            lot = lots_by_id[lot_id]
            take = min(lot.quantity, remaining)
            selected.append((lot, take))
            remaining -= take
        
        if remaining > 0:
            raise ValueError(f"Specified lots insufficient: {remaining} shares remaining")
        
        return selected
    
    def _close_lot(
        self,
        lot: TaxLot,
        quantity: Decimal,
        sale_price: Decimal,
        sale_date: datetime
    ) -> ClosedLot:
        """Close (partially or fully) a tax lot"""
        # Calculate proportional cost basis
        ratio = quantity / lot.quantity
        cost_basis = lot.total_cost_basis * ratio
        proceeds = quantity * sale_price
        
        closed = ClosedLot(
            lot_id=lot.lot_id,
            symbol=lot.symbol,
            quantity=quantity,
            cost_basis=cost_basis,
            proceeds=proceeds,
            acquisition_date=lot.acquisition_date,
            sale_date=sale_date,
            gain_type=lot.gain_type(sale_date)
        )
        
        # Update or remove lot
        lot.quantity -= quantity
        lot.wash_sale_adjustment *= (1 - ratio)
        
        if lot.quantity <= Decimal("0.0001"):
            self.open_lots[lot.symbol].remove(lot)
        
        self.closed_lots.append(closed)
        
        logger.info(
            f"Closed {quantity} shares from {lot.lot_id}: "
            f"gain=${closed.realized_gain:.2f} ({closed.gain_type.value})"
        )
        
        return closed
    
    def _check_wash_sale_on_sale(
        self,
        symbol: str,
        sale_date: datetime,
        closed_lots: list[ClosedLot]
    ):
        """Check if sale triggers wash sale with recent purchases"""
        window_end = sale_date + timedelta(days=self.wash_sale_window)
        
        for lot in self.open_lots[symbol]:
            if sale_date <= lot.acquisition_date <= window_end:
                # This purchase is within wash sale window
                for closed in closed_lots:
                    if closed.gross_gain < 0 and not closed.is_wash_sale:
                        # Apply wash sale
                        disallowed = min(
                            abs(closed.gross_gain),
                            lot.quantity * abs(closed.gross_gain) / closed.quantity
                        )
                        closed.is_wash_sale = True
                        closed.wash_sale_disallowed = -disallowed  # Negative to offset loss
                        closed.replacement_lot_id = lot.lot_id
                        lot.wash_sale_adjustment += disallowed
                        
                        logger.warning(
                            f"Wash sale: ${disallowed:.2f} loss disallowed on {closed.lot_id}, "
                            f"added to {lot.lot_id} cost basis"
                        )
    
    def get_unrealized_gains(
        self,
        prices: dict[str, float],
        as_of: datetime = None
    ) -> dict:
        """
        Calculate unrealized gains for all open positions.
        
        Args:
            prices: Current prices by symbol
            as_of: Date for holding period calculation
            
        Returns:
            Unrealized gains summary
        """
        as_of = as_of or datetime.now()
        
        by_symbol = {}
        total_short_term = Decimal("0")
        total_long_term = Decimal("0")
        
        for symbol, lots in self.open_lots.items():
            if symbol not in prices:
                continue
                
            current_price = Decimal(str(prices[symbol]))
            symbol_short = Decimal("0")
            symbol_long = Decimal("0")
            symbol_cost = Decimal("0")
            symbol_value = Decimal("0")
            
            for lot in lots:
                market_value = lot.quantity * current_price
                gain = market_value - lot.total_cost_basis
                
                symbol_cost += lot.total_cost_basis
                symbol_value += market_value
                
                if lot.gain_type(as_of) == GainType.SHORT_TERM:
                    symbol_short += gain
                    total_short_term += gain
                else:
                    symbol_long += gain
                    total_long_term += gain
            
            by_symbol[symbol] = {
                "cost_basis": float(symbol_cost),
                "market_value": float(symbol_value),
                "short_term_gain": float(symbol_short),
                "long_term_gain": float(symbol_long),
                "total_gain": float(symbol_short + symbol_long)
            }
        
        return {
            "by_symbol": by_symbol,
            "total_short_term": float(total_short_term),
            "total_long_term": float(total_long_term),
            "total_unrealized": float(total_short_term + total_long_term),
            "estimated_tax": float(
                total_short_term * self.short_term_rate +
                total_long_term * self.long_term_rate
            )
        }
    
    def get_realized_gains(
        self,
        year: int = None,
        symbol: str = None
    ) -> dict:
        """
        Calculate realized gains for tax reporting.
        
        Args:
            year: Tax year (None for all)
            symbol: Filter by symbol (None for all)
            
        Returns:
            Realized gains summary
        """
        lots = self.closed_lots
        
        if year:
            lots = [l for l in lots if l.sale_date.year == year]
        if symbol:
            lots = [l for l in lots if l.symbol == symbol]
        
        short_term = Decimal("0")
        long_term = Decimal("0")
        wash_sale_adjustments = Decimal("0")
        
        for lot in lots:
            if lot.gain_type == GainType.SHORT_TERM:
                short_term += lot.realized_gain
            else:
                long_term += lot.realized_gain
            wash_sale_adjustments += lot.wash_sale_disallowed
        
        return {
            "short_term_gains": float(short_term),
            "long_term_gains": float(long_term),
            "total_realized": float(short_term + long_term),
            "wash_sale_adjustments": float(wash_sale_adjustments),
            "estimated_tax": float(
                short_term * self.short_term_rate +
                long_term * self.long_term_rate
            ),
            "transactions": len(lots)
        }
    
    def find_tax_loss_harvesting_opportunities(
        self,
        prices: dict[str, float],
        min_loss: float = 100,
        as_of: datetime = None
    ) -> list[TaxLossHarvestingOpportunity]:
        """
        Find tax-loss harvesting opportunities.
        
        Args:
            prices: Current prices by symbol
            min_loss: Minimum loss to consider
            as_of: Date for calculations
            
        Returns:
            List of harvesting opportunities
        """
        as_of = as_of or datetime.now()
        min_loss = Decimal(str(min_loss))
        opportunities = []
        
        for symbol, lots in self.open_lots.items():
            if symbol not in prices:
                continue
            
            current_price = Decimal(str(prices[symbol]))
            
            # Check for recent sales (wash sale risk)
            recent_sale = any(
                (as_of - sale_date).days <= self.wash_sale_window
                for sale_date, _, _ in self.recent_sales[symbol]
            )
            
            for lot in lots:
                unrealized = (current_price - lot.adjusted_cost_per_share) * lot.quantity
                
                if unrealized < -min_loss:
                    gain_type = lot.gain_type(as_of)
                    tax_rate = (
                        self.short_term_rate if gain_type == GainType.SHORT_TERM
                        else self.long_term_rate
                    )
                    
                    opportunities.append(TaxLossHarvestingOpportunity(
                        symbol=symbol,
                        lot_id=lot.lot_id,
                        unrealized_loss=unrealized,
                        current_price=current_price,
                        cost_basis=lot.adjusted_cost_per_share,
                        quantity=lot.quantity,
                        gain_type=gain_type,
                        days_held=lot.holding_period_days(as_of),
                        wash_sale_risk=recent_sale,
                        estimated_tax_savings=abs(unrealized) * tax_rate
                    ))
        
        # Sort by tax savings (highest first)
        opportunities.sort(key=lambda x: x.estimated_tax_savings, reverse=True)
        
        return opportunities
    
    def export_form_8949(self, year: int) -> dict:
        """
        Export data formatted for IRS Form 8949.
        
        Args:
            year: Tax year
            
        Returns:
            Form 8949 data structure
        """
        lots = [l for l in self.closed_lots if l.sale_date.year == year]
        
        # Part I: Short-term
        short_term = [
            lot.to_form_8949()
            for lot in lots
            if lot.gain_type == GainType.SHORT_TERM
        ]
        
        # Part II: Long-term
        long_term = [
            lot.to_form_8949()
            for lot in lots
            if lot.gain_type == GainType.LONG_TERM
        ]
        
        # Calculate totals
        st_proceeds = sum(Decimal(t["proceeds"]) for t in short_term)
        st_cost = sum(Decimal(t["cost_basis"]) for t in short_term)
        st_adjustment = sum(
            Decimal(t["adjustment_amount"]) if t["adjustment_amount"] else Decimal("0")
            for t in short_term
        )
        st_gain = sum(Decimal(t["gain_or_loss"]) for t in short_term)
        
        lt_proceeds = sum(Decimal(t["proceeds"]) for t in long_term)
        lt_cost = sum(Decimal(t["cost_basis"]) for t in long_term)
        lt_adjustment = sum(
            Decimal(t["adjustment_amount"]) if t["adjustment_amount"] else Decimal("0")
            for t in long_term
        )
        lt_gain = sum(Decimal(t["gain_or_loss"]) for t in long_term)
        
        return {
            "tax_year": year,
            "part_i_short_term": {
                "transactions": short_term,
                "totals": {
                    "proceeds": str(st_proceeds),
                    "cost_basis": str(st_cost),
                    "adjustments": str(st_adjustment),
                    "gain_or_loss": str(st_gain)
                }
            },
            "part_ii_long_term": {
                "transactions": long_term,
                "totals": {
                    "proceeds": str(lt_proceeds),
                    "cost_basis": str(lt_cost),
                    "adjustments": str(lt_adjustment),
                    "gain_or_loss": str(lt_gain)
                }
            },
            "schedule_d_summary": {
                "short_term_gain_loss": str(st_gain),
                "long_term_gain_loss": str(lt_gain),
                "net_gain_loss": str(st_gain + lt_gain)
            }
        }
    
    def get_position_summary(self, symbol: str, current_price: float = None) -> dict:
        """Get detailed summary for a position"""
        if symbol not in self.open_lots:
            return {"symbol": symbol, "lots": [], "total_quantity": 0}
        
        lots = self.open_lots[symbol]
        current_price = Decimal(str(current_price)) if current_price else None
        
        lot_details = []
        for lot in lots:
            detail = lot.to_dict()
            if current_price:
                market_value = lot.quantity * current_price
                unrealized = market_value - lot.total_cost_basis
                detail["market_value"] = str(market_value)
                detail["unrealized_gain"] = str(unrealized)
                detail["unrealized_pct"] = str(
                    (unrealized / lot.total_cost_basis * 100).quantize(Decimal("0.01"))
                )
            lot_details.append(detail)
        
        total_qty = sum(lot.quantity for lot in lots)
        total_cost = sum(lot.total_cost_basis for lot in lots)
        
        summary = {
            "symbol": symbol,
            "total_quantity": str(total_qty),
            "total_cost_basis": str(total_cost),
            "average_cost": str((total_cost / total_qty).quantize(Decimal("0.0001"))),
            "lots": lot_details,
            "lot_count": len(lots)
        }
        
        if current_price:
            total_value = total_qty * current_price
            summary["market_value"] = str(total_value)
            summary["unrealized_gain"] = str(total_value - total_cost)
        
        return summary
    
    def save_state(self, filepath: str):
        """Save tracker state to file"""
        state = {
            "default_method": self.default_method.value,
            "symbol_methods": {s: m.value for s, m in self.symbol_methods.items()},
            "lot_counter": self.lot_counter,
            "open_lots": {
                symbol: [lot.to_dict() for lot in lots]
                for symbol, lots in self.open_lots.items()
            },
            "closed_lots": [
                {
                    "lot_id": l.lot_id,
                    "symbol": l.symbol,
                    "quantity": str(l.quantity),
                    "cost_basis": str(l.cost_basis),
                    "proceeds": str(l.proceeds),
                    "acquisition_date": l.acquisition_date.isoformat(),
                    "sale_date": l.sale_date.isoformat(),
                    "gain_type": l.gain_type.value,
                    "wash_sale_disallowed": str(l.wash_sale_disallowed),
                    "is_wash_sale": l.is_wash_sale,
                    "replacement_lot_id": l.replacement_lot_id
                }
                for l in self.closed_lots
            ],
            "recent_sales": {
                symbol: [(d.isoformat(), str(q), str(l)) for d, q, l in sales]
                for symbol, sales in self.recent_sales.items()
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Saved tax lot state to {filepath}")
    
    @classmethod
    def load_state(cls, filepath: str) -> "TaxLotTracker":
        """Load tracker state from file"""
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        tracker = cls(
            default_method=CostBasisMethod(state["default_method"])
        )
        tracker.lot_counter = state["lot_counter"]
        tracker.symbol_methods = {
            s: CostBasisMethod(m) for s, m in state["symbol_methods"].items()
        }
        
        # Restore open lots
        for symbol, lots_data in state["open_lots"].items():
            for lot_data in lots_data:
                lot = TaxLot(
                    lot_id=lot_data["lot_id"],
                    symbol=lot_data["symbol"],
                    quantity=Decimal(lot_data["quantity"]),
                    cost_per_share=Decimal(lot_data["cost_per_share"]),
                    acquisition_date=datetime.fromisoformat(lot_data["acquisition_date"]),
                    acquisition_type=lot_data["acquisition_type"],
                    original_quantity=Decimal(lot_data["original_quantity"]),
                    wash_sale_adjustment=Decimal(lot_data["wash_sale_adjustment"]),
                    wash_sale_disallowed=Decimal(lot_data.get("wash_sale_disallowed", "0")),
                    broker_lot_id=lot_data.get("broker_lot_id"),
                    notes=lot_data.get("notes", "")
                )
                tracker.open_lots[symbol].append(lot)
        
        # Restore closed lots
        for l in state["closed_lots"]:
            closed = ClosedLot(
                lot_id=l["lot_id"],
                symbol=l["symbol"],
                quantity=Decimal(l["quantity"]),
                cost_basis=Decimal(l["cost_basis"]),
                proceeds=Decimal(l["proceeds"]),
                acquisition_date=datetime.fromisoformat(l["acquisition_date"]),
                sale_date=datetime.fromisoformat(l["sale_date"]),
                gain_type=GainType(l["gain_type"]),
                wash_sale_disallowed=Decimal(l["wash_sale_disallowed"]),
                is_wash_sale=l["is_wash_sale"],
                replacement_lot_id=l.get("replacement_lot_id")
            )
            tracker.closed_lots.append(closed)
        
        # Restore recent sales
        for symbol, sales in state["recent_sales"].items():
            tracker.recent_sales[symbol] = [
                (datetime.fromisoformat(d), Decimal(q), Decimal(l))
                for d, q, l in sales
            ]
        
        logger.info(f"Loaded tax lot state from {filepath}")
        return tracker
