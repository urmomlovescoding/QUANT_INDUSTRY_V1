"""
Broker Reconciliation API Routes
================================
REST API for reconciliation management and reporting.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from reconciliation.broker_reconciliation import (
    BrokerReconciliation,
    ReconciliationScheduler,
    Position,
    Transaction,
    MockBrokerAdapter,
    AlpacaAdapter,
    IBKRAdapter,
    ReconciliationStatus,
    DiscrepancySeverity
)


router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

# Global instances (use dependency injection in production)
_engine: Optional[BrokerReconciliation] = None
_scheduler: Optional[ReconciliationScheduler] = None


def get_engine() -> BrokerReconciliation:
    global _engine
    if _engine is None:
        _engine = BrokerReconciliation()
    return _engine


def get_scheduler() -> ReconciliationScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ReconciliationScheduler(get_engine())
    return _scheduler


# Request/Response Models

class PositionData(BaseModel):
    symbol: str
    quantity: float
    cost_basis: float
    market_value: float


class TransactionData(BaseModel):
    transaction_id: str
    symbol: str
    transaction_type: str
    quantity: float
    price: float
    amount: float
    fees: float
    trade_date: date
    settlement_date: date
    description: str = ""


class ReconciliationRequest(BaseModel):
    broker: str
    reconciliation_date: Optional[date] = None
    positions: list[PositionData]
    transactions: list[TransactionData] = []
    cash_balance: float
    transaction_lookback_days: int = 5


class RegisterBrokerRequest(BaseModel):
    broker_name: str
    broker_type: str  # mock, alpaca, ibkr
    config: dict = {}


class ResolveDiscrepancyRequest(BaseModel):
    discrepancy_id: str
    resolution_notes: str
    resolved_by: str = "user"


# Routes

@router.post("/run")
async def run_reconciliation(request: ReconciliationRequest):
    """Run reconciliation against broker data"""
    engine = get_engine()
    scheduler = get_scheduler()
    
    recon_date = request.reconciliation_date or date.today()
    
    # Convert request data to internal formats
    internal_positions = [
        Position(
            symbol=p.symbol,
            quantity=Decimal(str(p.quantity)),
            cost_basis=Decimal(str(p.cost_basis)),
            market_value=Decimal(str(p.market_value)),
            source="internal",
            as_of_date=recon_date
        )
        for p in request.positions
    ]
    
    internal_transactions = [
        Transaction(
            transaction_id=t.transaction_id,
            symbol=t.symbol,
            transaction_type=t.transaction_type,
            quantity=Decimal(str(t.quantity)),
            price=Decimal(str(t.price)),
            amount=Decimal(str(t.amount)),
            fees=Decimal(str(t.fees)),
            trade_date=t.trade_date,
            settlement_date=t.settlement_date,
            source="internal",
            description=t.description
        )
        for t in request.transactions
    ]
    
    # Get or create broker adapter
    if request.broker not in scheduler.brokers:
        # Create mock adapter with provided data
        adapter = MockBrokerAdapter(request.broker)
        scheduler.register_broker(request.broker, adapter)
    
    adapter = scheduler.brokers[request.broker]
    
    # Run reconciliation
    report = engine.run_full_reconciliation(
        internal_positions=internal_positions,
        internal_transactions=internal_transactions,
        internal_cash=Decimal(str(request.cash_balance)),
        broker_adapter=adapter,
        reconciliation_date=recon_date,
        transaction_lookback_days=request.transaction_lookback_days
    )
    
    return report.to_dict()


@router.post("/broker/register")
async def register_broker(request: RegisterBrokerRequest):
    """Register a broker adapter"""
    scheduler = get_scheduler()
    
    if request.broker_type == "mock":
        adapter = MockBrokerAdapter(request.broker_name)
    elif request.broker_type == "alpaca":
        adapter = AlpacaAdapter(
            api_key=request.config.get("api_key"),
            secret_key=request.config.get("secret_key"),
            paper=request.config.get("paper", True)
        )
    elif request.broker_type == "ibkr":
        adapter = IBKRAdapter(
            client_id=request.config.get("client_id"),
            host=request.config.get("host", "127.0.0.1"),
            port=request.config.get("port", 7497)
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown broker type: {request.broker_type}"
        )
    
    scheduler.register_broker(request.broker_name, adapter)
    
    return {
        "status": "success",
        "broker": request.broker_name,
        "type": request.broker_type
    }


@router.get("/brokers")
async def list_brokers():
    """List registered brokers"""
    scheduler = get_scheduler()
    
    return {
        "brokers": [
            {
                "name": name,
                "type": adapter.__class__.__name__
            }
            for name, adapter in scheduler.brokers.items()
        ]
    }


@router.get("/reports")
async def list_reports(
    broker: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """List reconciliation reports"""
    scheduler = get_scheduler()
    
    reports = scheduler.reports
    
    if broker:
        reports = [r for r in reports if r.broker == broker]
    if status:
        reports = [r for r in reports if r.status.value == status]
    
    reports = sorted(reports, key=lambda r: r.generated_at, reverse=True)[:limit]
    
    return {
        "reports": [
            {
                "report_id": r.report_id,
                "broker": r.broker,
                "date": r.reconciliation_date.isoformat(),
                "status": r.status.value,
                "discrepancy_count": len(r.discrepancies),
                "generated_at": r.generated_at.isoformat()
            }
            for r in reports
        ]
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get detailed reconciliation report"""
    scheduler = get_scheduler()
    
    for report in scheduler.reports:
        if report.report_id == report_id:
            return report.to_dict()
    
    raise HTTPException(status_code=404, detail="Report not found")


@router.get("/reports/{report_id}/audit")
async def get_audit_trail(report_id: str):
    """Get audit trail for a report"""
    engine = get_engine()
    scheduler = get_scheduler()
    
    for report in scheduler.reports:
        if report.report_id == report_id:
            audit = engine.export_audit_trail(report)
            return {"audit_trail": audit}
    
    raise HTTPException(status_code=404, detail="Report not found")


@router.get("/discrepancies")
async def list_discrepancies(
    severity: Optional[str] = None,
    unresolved_only: bool = True,
    limit: int = 100
):
    """List discrepancies"""
    scheduler = get_scheduler()
    
    if unresolved_only:
        discrepancies = list(scheduler.unresolved_discrepancies.values())
    else:
        discrepancies = []
        for report in scheduler.reports:
            discrepancies.extend(report.discrepancies)
    
    if severity:
        discrepancies = [
            d for d in discrepancies
            if d.severity.value == severity
        ]
    
    discrepancies = sorted(
        discrepancies,
        key=lambda d: (d.severity.value, d.detected_at),
        reverse=True
    )[:limit]
    
    return {
        "discrepancies": [d.to_dict() for d in discrepancies],
        "count": len(discrepancies)
    }


@router.post("/discrepancies/resolve")
async def resolve_discrepancy(request: ResolveDiscrepancyRequest):
    """Resolve a discrepancy"""
    scheduler = get_scheduler()
    
    result = scheduler.resolve_discrepancy(
        discrepancy_id=request.discrepancy_id,
        resolution_notes=request.resolution_notes,
        resolved_by=request.resolved_by
    )
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Discrepancy not found or already resolved"
        )
    
    return {"status": "resolved", "discrepancy_id": request.discrepancy_id}


@router.get("/discrepancies/summary")
async def get_discrepancy_summary():
    """Get summary of unresolved discrepancies"""
    scheduler = get_scheduler()
    
    return scheduler.get_unresolved_summary()


@router.post("/schedule/run")
async def run_scheduled_reconciliation(
    background_tasks: BackgroundTasks,
    positions: list[PositionData],
    transactions: list[TransactionData] = [],
    cash_balance: float = 0
):
    """Run reconciliation for all registered brokers"""
    scheduler = get_scheduler()
    
    if not scheduler.brokers:
        raise HTTPException(
            status_code=400,
            detail="No brokers registered"
        )
    
    internal_positions = [
        Position(
            symbol=p.symbol,
            quantity=Decimal(str(p.quantity)),
            cost_basis=Decimal(str(p.cost_basis)),
            market_value=Decimal(str(p.market_value)),
            source="internal",
            as_of_date=date.today()
        )
        for p in positions
    ]
    
    internal_transactions = [
        Transaction(
            transaction_id=t.transaction_id,
            symbol=t.symbol,
            transaction_type=t.transaction_type,
            quantity=Decimal(str(t.quantity)),
            price=Decimal(str(t.price)),
            amount=Decimal(str(t.amount)),
            fees=Decimal(str(t.fees)),
            trade_date=t.trade_date,
            settlement_date=t.settlement_date,
            source="internal",
            description=t.description
        )
        for t in transactions
    ]
    
    reports = scheduler.run_scheduled_reconciliation(
        internal_positions=internal_positions,
        internal_transactions=internal_transactions,
        internal_cash=Decimal(str(cash_balance))
    )
    
    return {
        "status": "completed",
        "reports": [
            {
                "report_id": r.report_id,
                "broker": r.broker,
                "status": r.status.value,
                "discrepancies": len(r.discrepancies)
            }
            for r in reports
        ]
    }


@router.get("/config")
async def get_config():
    """Get reconciliation engine configuration"""
    engine = get_engine()
    
    return {
        "tolerance_quantity": str(engine.tolerance_quantity),
        "tolerance_amount": str(engine.tolerance_amount),
        "tolerance_cost_basis_pct": str(engine.tolerance_cost_basis_pct),
        "transaction_date_tolerance_days": engine.transaction_date_tolerance,
        "settlement_days": engine.settlement_days
    }


@router.post("/config")
async def update_config(
    tolerance_quantity: Optional[float] = None,
    tolerance_amount: Optional[float] = None,
    tolerance_cost_basis_pct: Optional[float] = None,
    transaction_date_tolerance_days: Optional[int] = None
):
    """Update reconciliation engine configuration"""
    engine = get_engine()
    
    if tolerance_quantity is not None:
        engine.tolerance_quantity = Decimal(str(tolerance_quantity))
    if tolerance_amount is not None:
        engine.tolerance_amount = Decimal(str(tolerance_amount))
    if tolerance_cost_basis_pct is not None:
        engine.tolerance_cost_basis_pct = Decimal(str(tolerance_cost_basis_pct))
    if transaction_date_tolerance_days is not None:
        engine.transaction_date_tolerance = transaction_date_tolerance_days
    
    return {"status": "updated", "config": await get_config()}


@router.get("/health")
async def health_check():
    """Check reconciliation service health"""
    scheduler = get_scheduler()
    
    return {
        "status": "healthy",
        "registered_brokers": len(scheduler.brokers),
        "total_reports": len(scheduler.reports),
        "unresolved_discrepancies": len(scheduler.unresolved_discrepancies)
    }
