"""
Broker Reconciliation System
============================
Automated reconciliation between internal records and broker statements.

Features:
- Position reconciliation (shares, cost basis)
- Transaction matching with fuzzy logic
- Cash balance verification
- Corporate action detection
- Discrepancy alerting and categorization
- Multi-broker support
- Audit trail generation
- Settlement tracking (T+1/T+2)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, Any
from collections import defaultdict
import json
import hashlib

logger = logging.getLogger(__name__)


class ReconciliationStatus(Enum):
    """Status of a reconciliation"""
    PENDING = "pending"
    MATCHED = "matched"
    PARTIAL_MATCH = "partial_match"
    DISCREPANCY = "discrepancy"
    UNMATCHED = "unmatched"
    MANUAL_OVERRIDE = "manual_override"


class DiscrepancyType(Enum):
    """Types of discrepancies"""
    POSITION_QUANTITY = "position_quantity"
    POSITION_COST_BASIS = "position_cost_basis"
    MISSING_POSITION = "missing_position"
    EXTRA_POSITION = "extra_position"
    CASH_BALANCE = "cash_balance"
    TRANSACTION_MISSING = "transaction_missing"
    TRANSACTION_EXTRA = "transaction_extra"
    TRANSACTION_AMOUNT = "transaction_amount"
    TRANSACTION_DATE = "transaction_date"
    TRANSACTION_QUANTITY = "transaction_quantity"
    SETTLEMENT_PENDING = "settlement_pending"
    CORPORATE_ACTION = "corporate_action"
    FEE_DISCREPANCY = "fee_discrepancy"
    DIVIDEND_MISSING = "dividend_missing"


class DiscrepancySeverity(Enum):
    """Severity levels"""
    INFO = "info"           # Minor, expected
    WARNING = "warning"     # Should investigate
    ERROR = "error"         # Requires action
    CRITICAL = "critical"   # Immediate attention


@dataclass
class Position:
    """Position record"""
    symbol: str
    quantity: Decimal
    cost_basis: Decimal  # Total cost basis
    market_value: Decimal
    source: str  # "internal" or broker name
    as_of_date: date
    lot_details: list[dict] = field(default_factory=list)
    
    @property
    def avg_cost(self) -> Decimal:
        if self.quantity == 0:
            return Decimal("0")
        return (self.cost_basis / self.quantity).quantize(Decimal("0.0001"))
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": str(self.quantity),
            "cost_basis": str(self.cost_basis),
            "avg_cost": str(self.avg_cost),
            "market_value": str(self.market_value),
            "source": self.source,
            "as_of_date": self.as_of_date.isoformat()
        }


@dataclass
class Transaction:
    """Transaction record"""
    transaction_id: str
    symbol: str
    transaction_type: str  # buy, sell, dividend, fee, transfer, split, etc.
    quantity: Decimal
    price: Decimal
    amount: Decimal  # Total amount (qty * price + fees)
    fees: Decimal
    trade_date: date
    settlement_date: date
    source: str
    description: str = ""
    broker_ref: str = ""
    
    @property
    def net_amount(self) -> Decimal:
        """Net amount after fees"""
        if self.transaction_type in ['buy', 'fee']:
            return -(self.amount)  # Outflow
        return self.amount  # Inflow
    
    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "symbol": self.symbol,
            "type": self.transaction_type,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "amount": str(self.amount),
            "fees": str(self.fees),
            "trade_date": self.trade_date.isoformat(),
            "settlement_date": self.settlement_date.isoformat(),
            "source": self.source,
            "description": self.description
        }
    
    def match_key(self) -> str:
        """Generate key for matching"""
        return f"{self.symbol}|{self.transaction_type}|{self.trade_date}|{abs(self.quantity):.4f}"


@dataclass
class Discrepancy:
    """Identified discrepancy"""
    discrepancy_id: str
    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity
    symbol: str
    
    internal_value: Any
    broker_value: Any
    difference: Decimal
    
    description: str
    recommendation: str
    
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolution_notes: str = ""
    
    # References
    internal_ref: str = ""
    broker_ref: str = ""
    
    def to_dict(self) -> dict:
        return {
            "discrepancy_id": self.discrepancy_id,
            "type": self.discrepancy_type.value,
            "severity": self.severity.value,
            "symbol": self.symbol,
            "internal_value": str(self.internal_value),
            "broker_value": str(self.broker_value),
            "difference": str(self.difference),
            "description": self.description,
            "recommendation": self.recommendation,
            "detected_at": self.detected_at.isoformat(),
            "resolved": self.resolved_at is not None
        }


@dataclass
class ReconciliationReport:
    """Full reconciliation report"""
    report_id: str
    broker: str
    reconciliation_date: date
    generated_at: datetime
    
    # Summary
    status: ReconciliationStatus
    positions_matched: int = 0
    positions_discrepancies: int = 0
    transactions_matched: int = 0
    transactions_discrepancies: int = 0
    cash_matched: bool = False
    
    # Details
    position_comparisons: list[dict] = field(default_factory=list)
    transaction_comparisons: list[dict] = field(default_factory=list)
    discrepancies: list[Discrepancy] = field(default_factory=list)
    
    # Balances
    internal_cash: Decimal = Decimal("0")
    broker_cash: Decimal = Decimal("0")
    internal_total_value: Decimal = Decimal("0")
    broker_total_value: Decimal = Decimal("0")
    
    # Settlement tracking
    pending_settlements: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "broker": self.broker,
            "reconciliation_date": self.reconciliation_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "status": self.status.value,
            "summary": {
                "positions_matched": self.positions_matched,
                "positions_discrepancies": self.positions_discrepancies,
                "transactions_matched": self.transactions_matched,
                "transactions_discrepancies": self.transactions_discrepancies,
                "cash_matched": self.cash_matched
            },
            "balances": {
                "internal_cash": str(self.internal_cash),
                "broker_cash": str(self.broker_cash),
                "cash_difference": str(self.broker_cash - self.internal_cash),
                "internal_total": str(self.internal_total_value),
                "broker_total": str(self.broker_total_value)
            },
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "pending_settlements": self.pending_settlements
        }


class BrokerAdapter:
    """Base class for broker-specific adapters"""
    
    def __init__(self, broker_name: str):
        self.broker_name = broker_name
    
    def get_positions(self, as_of: date) -> list[Position]:
        """Get positions from broker"""
        raise NotImplementedError
    
    def get_transactions(self, start_date: date, end_date: date) -> list[Transaction]:
        """Get transactions from broker"""
        raise NotImplementedError
    
    def get_cash_balance(self, as_of: date) -> Decimal:
        """Get cash balance from broker"""
        raise NotImplementedError
    
    def get_pending_settlements(self) -> list[dict]:
        """Get pending settlement transactions"""
        raise NotImplementedError


class MockBrokerAdapter(BrokerAdapter):
    """Mock broker adapter for testing"""
    
    def __init__(self, broker_name: str = "MockBroker"):
        super().__init__(broker_name)
        self._positions: list[Position] = []
        self._transactions: list[Transaction] = []
        self._cash: Decimal = Decimal("0")
    
    def set_positions(self, positions: list[Position]):
        self._positions = positions
    
    def set_transactions(self, transactions: list[Transaction]):
        self._transactions = transactions
    
    def set_cash(self, cash: Decimal):
        self._cash = cash
    
    def get_positions(self, as_of: date) -> list[Position]:
        return [p for p in self._positions if p.as_of_date <= as_of]
    
    def get_transactions(self, start_date: date, end_date: date) -> list[Transaction]:
        return [
            t for t in self._transactions
            if start_date <= t.trade_date <= end_date
        ]
    
    def get_cash_balance(self, as_of: date) -> Decimal:
        return self._cash
    
    def get_pending_settlements(self) -> list[dict]:
        return []


class IBKRAdapter(BrokerAdapter):
    """Interactive Brokers adapter"""
    
    def __init__(self, client_id: str = None, host: str = "127.0.0.1", port: int = 7497):
        super().__init__("IBKR")
        self.client_id = client_id
        self.host = host
        self.port = port
        self._connected = False
    
    def connect(self):
        """Connect to TWS/Gateway"""
        # Would use ib_insync or ibapi here
        logger.info(f"Connecting to IBKR at {self.host}:{self.port}")
        self._connected = True
    
    def get_positions(self, as_of: date) -> list[Position]:
        if not self._connected:
            self.connect()
        
        # Would fetch from IBKR API
        # positions = self.ib.positions()
        # return [self._convert_position(p) for p in positions]
        return []
    
    def get_transactions(self, start_date: date, end_date: date) -> list[Transaction]:
        if not self._connected:
            self.connect()
        
        # Would use flex query or executions API
        return []
    
    def get_cash_balance(self, as_of: date) -> Decimal:
        if not self._connected:
            self.connect()
        
        # Would fetch from account summary
        return Decimal("0")
    
    def get_pending_settlements(self) -> list[dict]:
        # T+1 for stocks
        return []


class AlpacaAdapter(BrokerAdapter):
    """Alpaca Markets adapter"""
    
    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        super().__init__("Alpaca")
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
    
    def get_positions(self, as_of: date) -> list[Position]:
        # Would use alpaca-trade-api
        # api = tradeapi.REST(self.api_key, self.secret_key)
        # positions = api.list_positions()
        return []
    
    def get_transactions(self, start_date: date, end_date: date) -> list[Transaction]:
        # Would fetch activities
        return []
    
    def get_cash_balance(self, as_of: date) -> Decimal:
        # Would fetch from account
        return Decimal("0")
    
    def get_pending_settlements(self) -> list[dict]:
        return []


class BrokerReconciliation:
    """
    Main reconciliation engine.
    
    Compares internal records against broker statements to identify
    and categorize discrepancies.
    """
    
    def __init__(
        self,
        tolerance_quantity: Decimal = Decimal("0.0001"),
        tolerance_amount: Decimal = Decimal("0.01"),
        tolerance_cost_basis_pct: Decimal = Decimal("0.001"),  # 0.1%
        transaction_date_tolerance_days: int = 1,
        settlement_days: int = 1  # T+1 for US equities
    ):
        self.tolerance_quantity = tolerance_quantity
        self.tolerance_amount = tolerance_amount
        self.tolerance_cost_basis_pct = tolerance_cost_basis_pct
        self.transaction_date_tolerance = transaction_date_tolerance_days
        self.settlement_days = settlement_days
        
        # Discrepancy counter
        self._discrepancy_counter = 0
        
        # Known corporate actions to exclude
        self.corporate_action_symbols: set[str] = set()
        
        logger.info("BrokerReconciliation engine initialized")
    
    def _generate_discrepancy_id(self) -> str:
        self._discrepancy_counter += 1
        return f"DISC-{datetime.now():%Y%m%d}-{self._discrepancy_counter:06d}"
    
    def reconcile_positions(
        self,
        internal_positions: list[Position],
        broker_positions: list[Position],
        as_of_date: date,
        broker_name: str
    ) -> tuple[list[dict], list[Discrepancy]]:
        """
        Reconcile position records.
        
        Returns:
            (comparisons, discrepancies)
        """
        comparisons = []
        discrepancies = []
        
        internal_by_symbol = {p.symbol: p for p in internal_positions}
        broker_by_symbol = {p.symbol: p for p in broker_positions}
        
        all_symbols = set(internal_by_symbol.keys()) | set(broker_by_symbol.keys())
        
        for symbol in all_symbols:
            internal = internal_by_symbol.get(symbol)
            broker = broker_by_symbol.get(symbol)
            
            comparison = {
                "symbol": symbol,
                "status": ReconciliationStatus.MATCHED.value,
                "internal": internal.to_dict() if internal else None,
                "broker": broker.to_dict() if broker else None,
                "differences": []
            }
            
            if not internal and broker:
                # Missing from internal records
                disc = Discrepancy(
                    discrepancy_id=self._generate_discrepancy_id(),
                    discrepancy_type=DiscrepancyType.EXTRA_POSITION,
                    severity=DiscrepancySeverity.ERROR,
                    symbol=symbol,
                    internal_value=None,
                    broker_value=broker.quantity,
                    difference=broker.quantity,
                    description=f"Position exists at {broker_name} but not in internal records",
                    recommendation="Verify if position was recently opened or if internal records need updating",
                    broker_ref=broker_name
                )
                discrepancies.append(disc)
                comparison["status"] = ReconciliationStatus.DISCREPANCY.value
                comparison["differences"].append(disc.to_dict())
                
            elif internal and not broker:
                # Missing from broker
                disc = Discrepancy(
                    discrepancy_id=self._generate_discrepancy_id(),
                    discrepancy_type=DiscrepancyType.MISSING_POSITION,
                    severity=DiscrepancySeverity.ERROR,
                    symbol=symbol,
                    internal_value=internal.quantity,
                    broker_value=None,
                    difference=-internal.quantity,
                    description=f"Position exists in internal records but not at {broker_name}",
                    recommendation="Verify if position was closed or transferred",
                    internal_ref="internal"
                )
                discrepancies.append(disc)
                comparison["status"] = ReconciliationStatus.DISCREPANCY.value
                comparison["differences"].append(disc.to_dict())
                
            elif internal and broker:
                # Both exist - compare
                qty_diff = broker.quantity - internal.quantity
                
                if abs(qty_diff) > self.tolerance_quantity:
                    disc = Discrepancy(
                        discrepancy_id=self._generate_discrepancy_id(),
                        discrepancy_type=DiscrepancyType.POSITION_QUANTITY,
                        severity=DiscrepancySeverity.ERROR if abs(qty_diff) > 1 else DiscrepancySeverity.WARNING,
                        symbol=symbol,
                        internal_value=internal.quantity,
                        broker_value=broker.quantity,
                        difference=qty_diff,
                        description=f"Quantity mismatch: internal={internal.quantity}, {broker_name}={broker.quantity}",
                        recommendation="Check for unrecorded trades, splits, or corporate actions"
                    )
                    discrepancies.append(disc)
                    comparison["status"] = ReconciliationStatus.DISCREPANCY.value
                    comparison["differences"].append(disc.to_dict())
                
                # Cost basis comparison
                if internal.quantity > 0:
                    cost_diff = broker.cost_basis - internal.cost_basis
                    cost_diff_pct = abs(cost_diff / internal.cost_basis) if internal.cost_basis != 0 else Decimal("0")
                    
                    if cost_diff_pct > self.tolerance_cost_basis_pct:
                        disc = Discrepancy(
                            discrepancy_id=self._generate_discrepancy_id(),
                            discrepancy_type=DiscrepancyType.POSITION_COST_BASIS,
                            severity=DiscrepancySeverity.WARNING,
                            symbol=symbol,
                            internal_value=internal.cost_basis,
                            broker_value=broker.cost_basis,
                            difference=cost_diff,
                            description=f"Cost basis mismatch ({cost_diff_pct:.2%}): internal=${internal.cost_basis}, {broker_name}=${broker.cost_basis}",
                            recommendation="Review lot assignments and wash sale adjustments"
                        )
                        discrepancies.append(disc)
                        if comparison["status"] == ReconciliationStatus.MATCHED.value:
                            comparison["status"] = ReconciliationStatus.PARTIAL_MATCH.value
                        comparison["differences"].append(disc.to_dict())
            
            comparisons.append(comparison)
        
        return comparisons, discrepancies
    
    def reconcile_transactions(
        self,
        internal_transactions: list[Transaction],
        broker_transactions: list[Transaction],
        start_date: date,
        end_date: date,
        broker_name: str
    ) -> tuple[list[dict], list[Discrepancy]]:
        """
        Reconcile transaction records.
        
        Uses fuzzy matching on date/symbol/quantity.
        """
        comparisons = []
        discrepancies = []
        
        # Index by match key for faster lookup
        internal_by_key = defaultdict(list)
        for t in internal_transactions:
            internal_by_key[t.match_key()].append(t)
        
        broker_matched = set()
        internal_matched = set()
        
        # First pass: exact matches
        for broker_txn in broker_transactions:
            key = broker_txn.match_key()
            
            if key in internal_by_key:
                for internal_txn in internal_by_key[key]:
                    if internal_txn.transaction_id in internal_matched:
                        continue
                    
                    # Compare amounts
                    amount_diff = abs(broker_txn.amount - internal_txn.amount)
                    
                    if amount_diff <= self.tolerance_amount:
                        # Match!
                        comparisons.append({
                            "status": ReconciliationStatus.MATCHED.value,
                            "internal": internal_txn.to_dict(),
                            "broker": broker_txn.to_dict(),
                            "differences": []
                        })
                        internal_matched.add(internal_txn.transaction_id)
                        broker_matched.add(broker_txn.transaction_id)
                        break
                    else:
                        # Partial match - amount differs
                        disc = Discrepancy(
                            discrepancy_id=self._generate_discrepancy_id(),
                            discrepancy_type=DiscrepancyType.TRANSACTION_AMOUNT,
                            severity=DiscrepancySeverity.WARNING,
                            symbol=broker_txn.symbol,
                            internal_value=internal_txn.amount,
                            broker_value=broker_txn.amount,
                            difference=broker_txn.amount - internal_txn.amount,
                            description=f"Amount mismatch on {broker_txn.trade_date}: internal=${internal_txn.amount}, {broker_name}=${broker_txn.amount}",
                            recommendation="Verify fees and execution prices",
                            internal_ref=internal_txn.transaction_id,
                            broker_ref=broker_txn.broker_ref
                        )
                        discrepancies.append(disc)
                        comparisons.append({
                            "status": ReconciliationStatus.PARTIAL_MATCH.value,
                            "internal": internal_txn.to_dict(),
                            "broker": broker_txn.to_dict(),
                            "differences": [disc.to_dict()]
                        })
                        internal_matched.add(internal_txn.transaction_id)
                        broker_matched.add(broker_txn.transaction_id)
                        break
        
        # Second pass: fuzzy date matching for unmatched
        for broker_txn in broker_transactions:
            if broker_txn.transaction_id in broker_matched:
                continue
            
            best_match = None
            best_score = 0
            
            for internal_txn in internal_transactions:
                if internal_txn.transaction_id in internal_matched:
                    continue
                
                # Same symbol and type?
                if internal_txn.symbol != broker_txn.symbol:
                    continue
                if internal_txn.transaction_type != broker_txn.transaction_type:
                    continue
                
                # Date within tolerance?
                date_diff = abs((broker_txn.trade_date - internal_txn.trade_date).days)
                if date_diff > self.transaction_date_tolerance:
                    continue
                
                # Quantity close?
                qty_diff = abs(broker_txn.quantity - internal_txn.quantity)
                if qty_diff > self.tolerance_quantity * 10:
                    continue
                
                # Score this match
                score = 100 - date_diff * 10 - float(qty_diff) * 5
                if score > best_score:
                    best_score = score
                    best_match = internal_txn
            
            if best_match:
                # Found fuzzy match
                diffs = []
                
                if best_match.trade_date != broker_txn.trade_date:
                    disc = Discrepancy(
                        discrepancy_id=self._generate_discrepancy_id(),
                        discrepancy_type=DiscrepancyType.TRANSACTION_DATE,
                        severity=DiscrepancySeverity.INFO,
                        symbol=broker_txn.symbol,
                        internal_value=best_match.trade_date,
                        broker_value=broker_txn.trade_date,
                        difference=Decimal((broker_txn.trade_date - best_match.trade_date).days),
                        description=f"Trade date differs: internal={best_match.trade_date}, {broker_name}={broker_txn.trade_date}",
                        recommendation="May be timezone or settlement date difference"
                    )
                    discrepancies.append(disc)
                    diffs.append(disc.to_dict())
                
                comparisons.append({
                    "status": ReconciliationStatus.PARTIAL_MATCH.value,
                    "internal": best_match.to_dict(),
                    "broker": broker_txn.to_dict(),
                    "differences": diffs
                })
                internal_matched.add(best_match.transaction_id)
                broker_matched.add(broker_txn.transaction_id)
            else:
                # No match found - broker has extra transaction
                disc = Discrepancy(
                    discrepancy_id=self._generate_discrepancy_id(),
                    discrepancy_type=DiscrepancyType.TRANSACTION_EXTRA,
                    severity=DiscrepancySeverity.ERROR,
                    symbol=broker_txn.symbol,
                    internal_value=None,
                    broker_value=broker_txn.amount,
                    difference=broker_txn.amount,
                    description=f"Transaction at {broker_name} not found internally: {broker_txn.transaction_type} {broker_txn.quantity} {broker_txn.symbol} on {broker_txn.trade_date}",
                    recommendation="Verify if transaction needs to be recorded",
                    broker_ref=broker_txn.broker_ref
                )
                discrepancies.append(disc)
                comparisons.append({
                    "status": ReconciliationStatus.UNMATCHED.value,
                    "internal": None,
                    "broker": broker_txn.to_dict(),
                    "differences": [disc.to_dict()]
                })
        
        # Check for internal transactions without broker match
        for internal_txn in internal_transactions:
            if internal_txn.transaction_id in internal_matched:
                continue
            
            disc = Discrepancy(
                discrepancy_id=self._generate_discrepancy_id(),
                discrepancy_type=DiscrepancyType.TRANSACTION_MISSING,
                severity=DiscrepancySeverity.ERROR,
                symbol=internal_txn.symbol,
                internal_value=internal_txn.amount,
                broker_value=None,
                difference=-internal_txn.amount,
                description=f"Internal transaction not found at {broker_name}: {internal_txn.transaction_type} {internal_txn.quantity} {internal_txn.symbol} on {internal_txn.trade_date}",
                recommendation="Verify transaction was actually executed",
                internal_ref=internal_txn.transaction_id
            )
            discrepancies.append(disc)
            comparisons.append({
                "status": ReconciliationStatus.UNMATCHED.value,
                "internal": internal_txn.to_dict(),
                "broker": None,
                "differences": [disc.to_dict()]
            })
        
        return comparisons, discrepancies
    
    def reconcile_cash(
        self,
        internal_cash: Decimal,
        broker_cash: Decimal,
        pending_settlements: list[dict],
        broker_name: str
    ) -> tuple[bool, list[Discrepancy]]:
        """
        Reconcile cash balances accounting for pending settlements.
        """
        discrepancies = []
        
        # Calculate settlement-adjusted balance
        pending_amount = sum(
            Decimal(str(s.get('amount', 0)))
            for s in pending_settlements
        )
        
        adjusted_internal = internal_cash + pending_amount
        difference = broker_cash - adjusted_internal
        
        if abs(difference) <= self.tolerance_amount:
            return True, discrepancies
        
        # Check if difference might be explained by pending
        if abs(broker_cash - internal_cash) <= self.tolerance_amount:
            # Matches without settlement adjustment - info only
            disc = Discrepancy(
                discrepancy_id=self._generate_discrepancy_id(),
                discrepancy_type=DiscrepancyType.SETTLEMENT_PENDING,
                severity=DiscrepancySeverity.INFO,
                symbol="CASH",
                internal_value=internal_cash,
                broker_value=broker_cash,
                difference=difference,
                description=f"Cash matches but {len(pending_settlements)} settlements pending",
                recommendation="Monitor settlement completion"
            )
            discrepancies.append(disc)
            return True, discrepancies
        
        # Real discrepancy
        severity = DiscrepancySeverity.WARNING
        if abs(difference) > Decimal("100"):
            severity = DiscrepancySeverity.ERROR
        if abs(difference) > Decimal("10000"):
            severity = DiscrepancySeverity.CRITICAL
        
        disc = Discrepancy(
            discrepancy_id=self._generate_discrepancy_id(),
            discrepancy_type=DiscrepancyType.CASH_BALANCE,
            severity=severity,
            symbol="CASH",
            internal_value=internal_cash,
            broker_value=broker_cash,
            difference=difference,
            description=f"Cash balance mismatch: internal=${internal_cash}, {broker_name}=${broker_cash}, adjusted=${adjusted_internal}",
            recommendation="Review recent transactions, fees, and interest payments"
        )
        discrepancies.append(disc)
        
        return False, discrepancies
    
    def run_full_reconciliation(
        self,
        internal_positions: list[Position],
        internal_transactions: list[Transaction],
        internal_cash: Decimal,
        broker_adapter: BrokerAdapter,
        reconciliation_date: date,
        transaction_lookback_days: int = 5
    ) -> ReconciliationReport:
        """
        Run complete reconciliation against a broker.
        
        Args:
            internal_positions: Internal position records
            internal_transactions: Internal transaction records
            internal_cash: Internal cash balance
            broker_adapter: Broker-specific adapter
            reconciliation_date: Date to reconcile
            transaction_lookback_days: Days of transactions to compare
            
        Returns:
            ReconciliationReport
        """
        report_id = f"REC-{reconciliation_date:%Y%m%d}-{hashlib.md5(broker_adapter.broker_name.encode()).hexdigest()[:6]}"
        
        report = ReconciliationReport(
            report_id=report_id,
            broker=broker_adapter.broker_name,
            reconciliation_date=reconciliation_date,
            generated_at=datetime.now(),
            status=ReconciliationStatus.PENDING,
            internal_cash=internal_cash
        )
        
        try:
            # Get broker data
            broker_positions = broker_adapter.get_positions(reconciliation_date)
            broker_transactions = broker_adapter.get_transactions(
                reconciliation_date - timedelta(days=transaction_lookback_days),
                reconciliation_date
            )
            broker_cash = broker_adapter.get_cash_balance(reconciliation_date)
            pending_settlements = broker_adapter.get_pending_settlements()
            
            report.broker_cash = broker_cash
            report.pending_settlements = pending_settlements
            
            # Reconcile positions
            pos_comparisons, pos_discrepancies = self.reconcile_positions(
                internal_positions,
                broker_positions,
                reconciliation_date,
                broker_adapter.broker_name
            )
            report.position_comparisons = pos_comparisons
            report.discrepancies.extend(pos_discrepancies)
            
            report.positions_matched = sum(
                1 for c in pos_comparisons
                if c["status"] == ReconciliationStatus.MATCHED.value
            )
            report.positions_discrepancies = len(pos_discrepancies)
            
            # Reconcile transactions
            txn_comparisons, txn_discrepancies = self.reconcile_transactions(
                internal_transactions,
                broker_transactions,
                reconciliation_date - timedelta(days=transaction_lookback_days),
                reconciliation_date,
                broker_adapter.broker_name
            )
            report.transaction_comparisons = txn_comparisons
            report.discrepancies.extend(txn_discrepancies)
            
            report.transactions_matched = sum(
                1 for c in txn_comparisons
                if c["status"] == ReconciliationStatus.MATCHED.value
            )
            report.transactions_discrepancies = len(txn_discrepancies)
            
            # Reconcile cash
            cash_matched, cash_discrepancies = self.reconcile_cash(
                internal_cash,
                broker_cash,
                pending_settlements,
                broker_adapter.broker_name
            )
            report.cash_matched = cash_matched
            report.discrepancies.extend(cash_discrepancies)
            
            # Calculate totals
            report.internal_total_value = internal_cash + sum(
                p.market_value for p in internal_positions
            )
            report.broker_total_value = broker_cash + sum(
                p.market_value for p in broker_positions
            )
            
            # Determine overall status
            critical_count = sum(
                1 for d in report.discrepancies
                if d.severity == DiscrepancySeverity.CRITICAL
            )
            error_count = sum(
                1 for d in report.discrepancies
                if d.severity == DiscrepancySeverity.ERROR
            )
            
            if critical_count > 0 or error_count > 3:
                report.status = ReconciliationStatus.DISCREPANCY
            elif error_count > 0 or not cash_matched:
                report.status = ReconciliationStatus.PARTIAL_MATCH
            else:
                report.status = ReconciliationStatus.MATCHED
            
            logger.info(
                f"Reconciliation {report_id} complete: {report.status.value}, "
                f"{len(report.discrepancies)} discrepancies"
            )
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            report.status = ReconciliationStatus.DISCREPANCY
            report.discrepancies.append(Discrepancy(
                discrepancy_id=self._generate_discrepancy_id(),
                discrepancy_type=DiscrepancyType.MISSING_POSITION,
                severity=DiscrepancySeverity.CRITICAL,
                symbol="SYSTEM",
                internal_value=None,
                broker_value=None,
                difference=Decimal("0"),
                description=f"Reconciliation error: {str(e)}",
                recommendation="Check broker connectivity and retry"
            ))
        
        return report
    
    def export_audit_trail(self, report: ReconciliationReport) -> str:
        """Export reconciliation report as audit trail"""
        output = []
        output.append("=" * 80)
        output.append(f"RECONCILIATION AUDIT TRAIL")
        output.append(f"Report ID: {report.report_id}")
        output.append(f"Broker: {report.broker}")
        output.append(f"Date: {report.reconciliation_date}")
        output.append(f"Generated: {report.generated_at}")
        output.append(f"Status: {report.status.value.upper()}")
        output.append("=" * 80)
        
        output.append("\n## SUMMARY")
        output.append(f"Positions Matched: {report.positions_matched}")
        output.append(f"Position Discrepancies: {report.positions_discrepancies}")
        output.append(f"Transactions Matched: {report.transactions_matched}")
        output.append(f"Transaction Discrepancies: {report.transactions_discrepancies}")
        output.append(f"Cash Matched: {'Yes' if report.cash_matched else 'No'}")
        
        output.append("\n## BALANCES")
        output.append(f"Internal Cash: ${report.internal_cash:,.2f}")
        output.append(f"Broker Cash: ${report.broker_cash:,.2f}")
        output.append(f"Difference: ${report.broker_cash - report.internal_cash:,.2f}")
        output.append(f"Internal Total: ${report.internal_total_value:,.2f}")
        output.append(f"Broker Total: ${report.broker_total_value:,.2f}")
        
        if report.discrepancies:
            output.append("\n## DISCREPANCIES")
            for disc in sorted(report.discrepancies, key=lambda d: d.severity.value, reverse=True):
                output.append(f"\n[{disc.severity.value.upper()}] {disc.discrepancy_type.value}")
                output.append(f"  ID: {disc.discrepancy_id}")
                output.append(f"  Symbol: {disc.symbol}")
                output.append(f"  Description: {disc.description}")
                output.append(f"  Internal: {disc.internal_value}")
                output.append(f"  Broker: {disc.broker_value}")
                output.append(f"  Difference: {disc.difference}")
                output.append(f"  Recommendation: {disc.recommendation}")
        
        if report.pending_settlements:
            output.append("\n## PENDING SETTLEMENTS")
            for settlement in report.pending_settlements:
                output.append(f"  - {settlement}")
        
        output.append("\n" + "=" * 80)
        output.append("END OF AUDIT TRAIL")
        output.append("=" * 80)
        
        return "\n".join(output)


class ReconciliationScheduler:
    """
    Automated reconciliation scheduler.
    
    Runs reconciliations on schedule and manages discrepancy workflows.
    """
    
    def __init__(self, reconciliation_engine: BrokerReconciliation):
        self.engine = reconciliation_engine
        self.brokers: dict[str, BrokerAdapter] = {}
        self.reports: list[ReconciliationReport] = []
        self.unresolved_discrepancies: dict[str, Discrepancy] = {}
        
        # Alert callbacks
        self.alert_callbacks: list[callable] = []
    
    def register_broker(self, name: str, adapter: BrokerAdapter):
        """Register a broker adapter"""
        self.brokers[name] = adapter
        logger.info(f"Registered broker: {name}")
    
    def add_alert_callback(self, callback: callable):
        """Add callback for discrepancy alerts"""
        self.alert_callbacks.append(callback)
    
    def run_scheduled_reconciliation(
        self,
        internal_positions: list[Position],
        internal_transactions: list[Transaction],
        internal_cash: Decimal
    ) -> list[ReconciliationReport]:
        """Run reconciliation for all registered brokers"""
        reports = []
        today = date.today()
        
        for name, adapter in self.brokers.items():
            logger.info(f"Running reconciliation for {name}")
            
            report = self.engine.run_full_reconciliation(
                internal_positions=internal_positions,
                internal_transactions=internal_transactions,
                internal_cash=internal_cash,
                broker_adapter=adapter,
                reconciliation_date=today
            )
            
            reports.append(report)
            self.reports.append(report)
            
            # Track unresolved discrepancies
            for disc in report.discrepancies:
                if disc.severity in [DiscrepancySeverity.ERROR, DiscrepancySeverity.CRITICAL]:
                    self.unresolved_discrepancies[disc.discrepancy_id] = disc
            
            # Fire alerts
            critical = [
                d for d in report.discrepancies
                if d.severity == DiscrepancySeverity.CRITICAL
            ]
            if critical:
                for callback in self.alert_callbacks:
                    try:
                        callback(report, critical)
                    except Exception as e:
                        logger.error(f"Alert callback failed: {e}")
        
        return reports
    
    def resolve_discrepancy(
        self,
        discrepancy_id: str,
        resolution_notes: str,
        resolved_by: str = "system"
    ) -> bool:
        """Mark a discrepancy as resolved"""
        if discrepancy_id in self.unresolved_discrepancies:
            disc = self.unresolved_discrepancies.pop(discrepancy_id)
            disc.resolved_at = datetime.now()
            disc.resolution_notes = f"{resolution_notes} (resolved by {resolved_by})"
            logger.info(f"Resolved discrepancy {discrepancy_id}")
            return True
        return False
    
    def get_unresolved_summary(self) -> dict:
        """Get summary of unresolved discrepancies"""
        by_severity = defaultdict(list)
        by_type = defaultdict(list)
        
        for disc in self.unresolved_discrepancies.values():
            by_severity[disc.severity.value].append(disc.discrepancy_id)
            by_type[disc.discrepancy_type.value].append(disc.discrepancy_id)
        
        return {
            "total_unresolved": len(self.unresolved_discrepancies),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "oldest": min(
                (d.detected_at for d in self.unresolved_discrepancies.values()),
                default=None
            )
        }
