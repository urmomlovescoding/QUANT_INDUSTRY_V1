"""
Tax Lot Tracking API Routes
===========================
REST API for tax lot management and reporting.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

from accounting.tax_lot_tracker import (
    TaxLotTracker,
    CostBasisMethod,
    GainType
)


router = APIRouter(prefix="/tax", tags=["tax"])

# Global tracker instance (in production, use dependency injection)
_tracker: Optional[TaxLotTracker] = None


def get_tracker() -> TaxLotTracker:
    global _tracker
    if _tracker is None:
        _tracker = TaxLotTracker()
    return _tracker


# Request/Response Models

class PurchaseRequest(BaseModel):
    symbol: str
    quantity: float
    price: float
    date: datetime
    acquisition_type: str = "purchase"
    broker_lot_id: Optional[str] = None
    notes: str = ""


class SaleRequest(BaseModel):
    symbol: str
    quantity: float
    price: float
    date: datetime
    method: Optional[str] = None  # fifo, lifo, hifo, specific_id, min_tax
    specific_lot_ids: Optional[list[str]] = None


class SetMethodRequest(BaseModel):
    symbol: str
    method: str  # fifo, lifo, hifo, average_cost, min_tax


class UnrealizedGainsRequest(BaseModel):
    prices: dict[str, float]


# Routes

@router.post("/purchase")
async def record_purchase(request: PurchaseRequest):
    """Record a new purchase creating a tax lot"""
    tracker = get_tracker()
    
    try:
        lot = tracker.record_purchase(
            symbol=request.symbol,
            quantity=request.quantity,
            price=request.price,
            date=request.date,
            acquisition_type=request.acquisition_type,
            broker_lot_id=request.broker_lot_id,
            notes=request.notes
        )
        
        return {
            "status": "success",
            "lot": lot.to_dict()
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sale")
async def record_sale(request: SaleRequest):
    """Record a sale closing tax lots"""
    tracker = get_tracker()
    
    try:
        method = None
        if request.method:
            method = CostBasisMethod(request.method)
        
        closed = tracker.record_sale(
            symbol=request.symbol,
            quantity=request.quantity,
            price=request.price,
            date=request.date,
            method=method,
            specific_lot_ids=request.specific_lot_ids
        )
        
        return {
            "status": "success",
            "closed_lots": [
                {
                    "lot_id": c.lot_id,
                    "symbol": c.symbol,
                    "quantity": str(c.quantity),
                    "cost_basis": str(c.cost_basis),
                    "proceeds": str(c.proceeds),
                    "gain": str(c.realized_gain),
                    "gain_type": c.gain_type.value,
                    "holding_days": c.holding_period_days,
                    "is_wash_sale": c.is_wash_sale
                }
                for c in closed
            ],
            "total_gain": str(sum(c.realized_gain for c in closed))
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(symbol: Optional[str] = None):
    """Get all open positions"""
    tracker = get_tracker()
    
    if symbol:
        summary = tracker.get_position_summary(symbol)
        return {"positions": [summary] if summary["lots"] else []}
    
    positions = []
    for sym, lots in tracker.open_lots.items():
        if lots:
            positions.append(tracker.get_position_summary(sym))
    
    return {"positions": positions}


@router.get("/positions/{symbol}")
async def get_position(symbol: str, current_price: Optional[float] = None):
    """Get detailed position for a symbol"""
    tracker = get_tracker()
    
    summary = tracker.get_position_summary(symbol, current_price)
    if not summary["lots"]:
        raise HTTPException(status_code=404, detail=f"No position for {symbol}")
    
    return summary


@router.post("/unrealized-gains")
async def get_unrealized_gains(request: UnrealizedGainsRequest):
    """Calculate unrealized gains with current prices"""
    tracker = get_tracker()
    
    gains = tracker.get_unrealized_gains(request.prices)
    return gains


@router.get("/realized-gains")
async def get_realized_gains(
    year: Optional[int] = None,
    symbol: Optional[str] = None
):
    """Get realized gains summary"""
    tracker = get_tracker()
    
    gains = tracker.get_realized_gains(year=year, symbol=symbol)
    return gains


@router.post("/tax-loss-harvesting")
async def find_harvesting_opportunities(
    request: UnrealizedGainsRequest,
    min_loss: float = 100
):
    """Find tax-loss harvesting opportunities"""
    tracker = get_tracker()
    
    opportunities = tracker.find_tax_loss_harvesting_opportunities(
        prices=request.prices,
        min_loss=min_loss
    )
    
    return {
        "opportunities": [o.to_dict() for o in opportunities],
        "total_potential_savings": str(sum(o.estimated_tax_savings for o in opportunities))
    }


@router.get("/form-8949/{year}")
async def export_form_8949(year: int):
    """Export IRS Form 8949 data"""
    tracker = get_tracker()
    
    form_data = tracker.export_form_8949(year)
    return form_data


@router.post("/cost-basis-method")
async def set_cost_basis_method(request: SetMethodRequest):
    """Set cost basis method for a symbol"""
    tracker = get_tracker()
    
    try:
        method = CostBasisMethod(request.method)
        tracker.set_cost_basis_method(request.symbol, method)
        
        return {
            "status": "success",
            "symbol": request.symbol,
            "method": method.value
        }
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method. Choose from: {[m.value for m in CostBasisMethod]}"
        )


@router.get("/cost-basis-method/{symbol}")
async def get_cost_basis_method(symbol: str):
    """Get cost basis method for a symbol"""
    tracker = get_tracker()
    
    method = tracker.get_cost_basis_method(symbol)
    return {
        "symbol": symbol,
        "method": method.value,
        "is_default": symbol not in tracker.symbol_methods
    }


@router.get("/closed-lots")
async def get_closed_lots(
    year: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = 100
):
    """Get closed lot history"""
    tracker = get_tracker()
    
    lots = tracker.closed_lots
    
    if year:
        lots = [l for l in lots if l.sale_date.year == year]
    if symbol:
        lots = [l for l in lots if l.symbol == symbol]
    
    lots = sorted(lots, key=lambda l: l.sale_date, reverse=True)[:limit]
    
    return {
        "closed_lots": [
            {
                "lot_id": l.lot_id,
                "symbol": l.symbol,
                "quantity": str(l.quantity),
                "cost_basis": str(l.cost_basis),
                "proceeds": str(l.proceeds),
                "gross_gain": str(l.gross_gain),
                "realized_gain": str(l.realized_gain),
                "gain_type": l.gain_type.value,
                "acquisition_date": l.acquisition_date.isoformat(),
                "sale_date": l.sale_date.isoformat(),
                "holding_days": l.holding_period_days,
                "is_wash_sale": l.is_wash_sale,
                "wash_sale_disallowed": str(l.wash_sale_disallowed)
            }
            for l in lots
        ],
        "count": len(lots)
    }


@router.post("/save")
async def save_state(filepath: str = "tax_lots.json"):
    """Save tracker state to file"""
    tracker = get_tracker()
    
    try:
        tracker.save_state(filepath)
        return {"status": "success", "filepath": filepath}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_state(filepath: str = "tax_lots.json"):
    """Load tracker state from file"""
    global _tracker
    
    try:
        _tracker = TaxLotTracker.load_state(filepath)
        return {
            "status": "success",
            "filepath": filepath,
            "open_positions": len(_tracker.open_lots),
            "closed_lots": len(_tracker.closed_lots)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_tax_summary(year: Optional[int] = None):
    """Get comprehensive tax summary"""
    tracker = get_tracker()
    
    year = year or datetime.now().year
    
    realized = tracker.get_realized_gains(year=year)
    form_data = tracker.export_form_8949(year)
    
    return {
        "year": year,
        "realized_gains": realized,
        "form_8949_summary": form_data["schedule_d_summary"],
        "open_positions": len([
            sym for sym, lots in tracker.open_lots.items() if lots
        ]),
        "total_closed_lots": len([
            l for l in tracker.closed_lots if l.sale_date.year == year
        ])
    }
