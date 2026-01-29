"""
Profit Split Calculator
Handles profit sharing between traders and the firm.
"""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
import logging

from .models import Trader, TraderAccount, Payout, PerformanceMetrics

logger = logging.getLogger(__name__)


class ProfitSplitCalculator:
    """
    Calculates and manages profit splits for funded traders.
    
    Features:
    - Configurable split percentages
    - Performance-based split bonuses
    - Consistency rewards
    - Scaling bonuses
    - Payout scheduling and processing
    """
    
    # Base profit splits by account tier
    BASE_SPLITS = {
        "starter": 80.0,     # Trader gets 80%
        "standard": 80.0,
        "professional": 80.0,
        "elite": 85.0,
        "master": 90.0,
    }
    
    # Bonus split adjustments
    BONUSES = {
        "consistency": 2.0,      # +2% for consistent profitability
        "scaling": 1.0,          # +1% per scale level (up to +5%)
        "longevity": 1.0,        # +1% per 6 months funded
        "top_performer": 3.0,    # +3% for top 10 monthly
    }
    
    def __init__(self, db_session):
        self.db = db_session
    
    def calculate_split(
        self,
        trader_id: int,
        gross_profit: Decimal,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Calculate profit split for a given period.
        
        Args:
            trader_id: Trader's ID
            gross_profit: Total profit for the period
            period_start: Start of profit period
            period_end: End of profit period
        
        Returns:
            Dict with split details
        """
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            raise ValueError(f"Trader {trader_id} not found")
        
        account = self.db.query(TraderAccount).filter_by(
            trader_id=trader_id, 
            is_active=True
        ).first()
        if not account:
            raise ValueError(f"No active account for trader {trader_id}")
        
        # Get base split
        base_split = trader.profit_split_percentage or 80.0
        
        # Calculate bonuses
        bonuses = self._calculate_bonuses(trader, account, period_start, period_end)
        total_bonus = sum(bonuses.values())
        
        # Final split (capped at 95%)
        final_split = min(95.0, base_split + total_bonus)
        
        # Calculate amounts
        if gross_profit <= 0:
            return {
                "gross_profit": float(gross_profit),
                "trader_split_pct": final_split,
                "trader_amount": 0,
                "firm_amount": 0,
                "base_split": base_split,
                "bonuses": bonuses,
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                }
            }
        
        trader_amount = gross_profit * Decimal(str(final_split / 100))
        trader_amount = trader_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        firm_amount = gross_profit - trader_amount
        
        return {
            "gross_profit": float(gross_profit),
            "trader_split_pct": final_split,
            "trader_amount": float(trader_amount),
            "firm_amount": float(firm_amount),
            "base_split": base_split,
            "bonuses": bonuses,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            }
        }
    
    def _calculate_bonuses(
        self,
        trader: Trader,
        account: TraderAccount,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, float]:
        """Calculate applicable bonus percentages."""
        bonuses = {}
        
        # Consistency bonus
        metrics = self.db.query(PerformanceMetrics).filter_by(trader_id=trader.id).first()
        if metrics and metrics.consistency_score and metrics.consistency_score >= 70:
            bonuses["consistency"] = self.BONUSES["consistency"]
        
        # Scaling bonus (capped at +5%)
        if account.scale_level > 1:
            scale_bonus = min(5.0, (account.scale_level - 1) * self.BONUSES["scaling"])
            bonuses["scaling"] = scale_bonus
        
        # Longevity bonus
        if account.created_at:
            months_funded = (datetime.utcnow() - account.created_at).days / 30
            if months_funded >= 6:
                longevity_bonus = min(5.0, int(months_funded / 6) * self.BONUSES["longevity"])
                bonuses["longevity"] = longevity_bonus
        
        # Top performer bonus (check monthly leaderboard)
        if metrics and metrics.monthly_rank and metrics.monthly_rank <= 10:
            bonuses["top_performer"] = self.BONUSES["top_performer"]
        
        return bonuses
    
    def create_payout_request(
        self,
        trader_id: int,
        account_id: int,
        period_start: datetime,
        period_end: datetime,
        payment_method: str = "bank_transfer"
    ) -> Payout:
        """
        Create a payout request for processing.
        """
        account = self.db.query(TraderAccount).filter_by(id=account_id).first()
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        # Calculate profit for period
        # In production, this would query actual trade history
        gross_profit = account.pending_payout or Decimal("0")
        
        if gross_profit <= 0:
            raise ValueError("No profit available for payout")
        
        # Calculate split
        split = self.calculate_split(trader_id, gross_profit, period_start, period_end)
        
        # Create payout record
        payout = Payout(
            trader_id=trader_id,
            account_id=account_id,
            gross_profit=gross_profit,
            trader_share_pct=split["trader_split_pct"],
            trader_amount=Decimal(str(split["trader_amount"])),
            firm_amount=Decimal(str(split["firm_amount"])),
            period_start=period_start,
            period_end=period_end,
            status="pending",
            payment_method=payment_method,
        )
        
        self.db.add(payout)
        
        # Clear pending payout from account
        account.pending_payout = Decimal("0")
        
        self.db.commit()
        
        logger.info(f"Created payout request {payout.id} for trader {trader_id}: ${split['trader_amount']}")
        return payout
    
    def process_payout(self, payout_id: int, payment_reference: str) -> Payout:
        """
        Mark a payout as processed (called after actual payment).
        """
        payout = self.db.query(Payout).filter_by(id=payout_id).first()
        if not payout:
            raise ValueError(f"Payout {payout_id} not found")
        
        payout.status = "completed"
        payout.payment_reference = payment_reference
        payout.processed_at = datetime.utcnow()
        payout.completed_at = datetime.utcnow()
        
        # Update trader's total payouts
        account = self.db.query(TraderAccount).filter_by(id=payout.account_id).first()
        if account:
            account.total_payouts = (account.total_payouts or Decimal("0")) + payout.trader_amount
        
        self.db.commit()
        
        logger.info(f"Processed payout {payout_id}: ${payout.trader_amount}")
        return payout
    
    def get_payout_history(
        self,
        trader_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get payout history for a trader."""
        payouts = (
            self.db.query(Payout)
            .filter_by(trader_id=trader_id)
            .order_by(Payout.requested_at.desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                "id": p.id,
                "gross_profit": float(p.gross_profit),
                "trader_share_pct": p.trader_share_pct,
                "trader_amount": float(p.trader_amount),
                "status": p.status,
                "payment_method": p.payment_method,
                "period": {
                    "start": p.period_start.isoformat(),
                    "end": p.period_end.isoformat(),
                },
                "requested_at": p.requested_at.isoformat() if p.requested_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            }
            for p in payouts
        ]
    
    def estimate_next_payout(self, account_id: int) -> Dict[str, Any]:
        """
        Estimate the next payout amount based on current performance.
        """
        account = self.db.query(TraderAccount).filter_by(id=account_id).first()
        if not account:
            return {"error": "Account not found"}
        
        pending = account.pending_payout or Decimal("0")
        
        if pending <= 0:
            return {
                "pending_profit": 0,
                "estimated_payout": 0,
                "message": "No pending profits for payout"
            }
        
        # Calculate estimated split
        period_start = datetime.utcnow() - timedelta(days=14)  # Bi-weekly
        period_end = datetime.utcnow()
        
        split = self.calculate_split(account.trader_id, pending, period_start, period_end)
        
        return {
            "pending_profit": float(pending),
            "estimated_payout": split["trader_amount"],
            "split_percentage": split["trader_split_pct"],
            "bonuses_applied": split["bonuses"],
            "next_payout_date": self._get_next_payout_date().isoformat(),
        }
    
    def _get_next_payout_date(self) -> datetime:
        """Get next bi-weekly payout date (1st and 15th of month)."""
        now = datetime.utcnow()
        if now.day < 15:
            return now.replace(day=15, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
