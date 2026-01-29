"""
Prop Firm API Routes
RESTful endpoints for prop trading management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

router = APIRouter(prefix="/prop-firm", tags=["prop-firm"])


# ============== Pydantic Models ==============

class TraderRegistration(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    country: str
    phone: Optional[str] = None
    timezone: str = "UTC"
    referral_code: Optional[str] = None


class TraderLogin(BaseModel):
    email: EmailStr
    password: str


class KYCSubmission(BaseModel):
    document_type: str = Field(..., description="passport, drivers_license, id_card")
    document_data: Dict[str, Any]


class ChallengeEnrollment(BaseModel):
    challenge_type: str = Field(..., description="e.g., ELITE_100K")
    payment_method: Optional[str] = "card"


class TradeUpdate(BaseModel):
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class BalanceUpdate(BaseModel):
    current_balance: float
    daily_pnl: float


class PayoutRequest(BaseModel):
    payment_method: str = "bank_transfer"


class CoachingQuestion(BaseModel):
    question: str


# ============== Onboarding Endpoints ==============

@router.post("/register")
async def register_trader(data: TraderRegistration, db=Depends(get_db)):
    """Register a new trader."""
    from prop_firm import TraderOnboarding
    
    onboarding = TraderOnboarding(db)
    result = onboarding.register_trader(
        email=data.email,
        username=data.username,
        password=data.password,
        full_name=data.full_name,
        country=data.country,
        phone=data.phone,
        timezone=data.timezone,
        referral_code=data.referral_code
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.post("/login")
async def login_trader(data: TraderLogin, db=Depends(get_db)):
    """Authenticate trader and return token."""
    from prop_firm.models import Trader
    from prop_firm import TraderOnboarding
    
    trader = db.query(Trader).filter_by(email=data.email.lower()).first()
    if not trader:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    onboarding = TraderOnboarding(db)
    if not onboarding.verify_password(trader, data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    trader.last_login = datetime.utcnow()
    db.commit()
    
    # In production, generate JWT token here
    return {
        "success": True,
        "trader": {
            "id": trader.id,
            "username": trader.username,
            "status": trader.status.value,
        },
        "token": f"token_{trader.id}"  # Placeholder
    }


@router.get("/challenges/available")
async def get_available_challenges(db=Depends(get_db)):
    """Get list of available challenges for enrollment."""
    from prop_firm import TraderOnboarding
    
    onboarding = TraderOnboarding(db)
    return {"challenges": onboarding.get_available_challenges()}


@router.post("/kyc/{trader_id}")
async def submit_kyc(trader_id: int, data: KYCSubmission, db=Depends(get_db)):
    """Submit KYC documents."""
    from prop_firm import TraderOnboarding
    
    onboarding = TraderOnboarding(db)
    result = onboarding.submit_kyc(
        trader_id=trader_id,
        document_type=data.document_type,
        document_data=data.document_data
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/challenges/enroll/{trader_id}")
async def enroll_challenge(trader_id: int, data: ChallengeEnrollment, db=Depends(get_db)):
    """Enroll in a trading challenge."""
    from prop_firm import TraderOnboarding
    
    onboarding = TraderOnboarding(db)
    result = onboarding.enroll_challenge(
        trader_id=trader_id,
        challenge_type=data.challenge_type,
        payment_info={"method": data.payment_method}
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/onboarding/status/{trader_id}")
async def get_onboarding_status(trader_id: int, db=Depends(get_db)):
    """Get onboarding progress for a trader."""
    from prop_firm import TraderOnboarding
    
    onboarding = TraderOnboarding(db)
    return onboarding.get_onboarding_status(trader_id)


# ============== Challenge Endpoints ==============

@router.get("/challenges/{challenge_id}")
async def get_challenge_details(challenge_id: int, db=Depends(get_db)):
    """Get challenge details and progress."""
    from prop_firm import ChallengeEngine
    
    engine = ChallengeEngine(db)
    return engine.get_challenge_summary(challenge_id)


@router.post("/challenges/{challenge_id}/update")
async def update_challenge_metrics(challenge_id: int, data: BalanceUpdate, db=Depends(get_db)):
    """Update challenge metrics (called by trading system)."""
    from prop_firm import ChallengeEngine
    
    engine = ChallengeEngine(db)
    challenge, status = engine.update_challenge_metrics(
        challenge_id=challenge_id,
        current_balance=Decimal(str(data.current_balance)),
        daily_pnl=Decimal(str(data.daily_pnl))
    )
    
    return {
        "challenge_id": challenge.id,
        "result": challenge.result.value,
        "status": status
    }


@router.get("/challenges/{challenge_id}/evaluations")
async def get_challenge_evaluations(challenge_id: int, db=Depends(get_db)):
    """Get daily evaluations for a challenge."""
    from prop_firm.models import Evaluation
    
    evaluations = (
        db.query(Evaluation)
        .filter_by(challenge_id=challenge_id)
        .order_by(Evaluation.evaluation_date.desc())
        .all()
    )
    
    return {
        "evaluations": [
            {
                "date": e.evaluation_date.isoformat(),
                "daily_pnl": float(e.daily_pnl),
                "cumulative_pnl": float(e.cumulative_pnl),
                "trades_count": e.trades_count,
                "win_rate": e.win_rate,
            }
            for e in evaluations
        ]
    }


# ============== Risk Management Endpoints ==============

@router.post("/risk/pre-trade-check")
async def pre_trade_check(
    account_id: int,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    db=Depends(get_db)
):
    """Pre-trade risk validation."""
    from prop_firm import PropFirmRiskManager
    
    risk_mgr = PropFirmRiskManager(db)
    approved, details = risk_mgr.check_pre_trade_risk(
        account_id=account_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price
    )
    
    return {"approved": approved, "details": details}


@router.get("/risk/limits/{account_id}")
async def get_dynamic_limits(account_id: int, db=Depends(get_db)):
    """Get current dynamic position limits."""
    from prop_firm import PropFirmRiskManager
    
    risk_mgr = PropFirmRiskManager(db)
    return risk_mgr.get_dynamic_position_limits(account_id)


@router.post("/risk/emergency-flatten/{account_id}")
async def emergency_flatten(account_id: int, reason: str, db=Depends(get_db)):
    """Emergency flatten all positions."""
    from prop_firm import PropFirmRiskManager
    
    risk_mgr = PropFirmRiskManager(db)
    return risk_mgr.emergency_flatten(account_id, reason)


# ============== Profit Split Endpoints ==============

@router.get("/payouts/estimate/{account_id}")
async def estimate_payout(account_id: int, db=Depends(get_db)):
    """Estimate next payout amount."""
    from prop_firm import ProfitSplitCalculator
    
    calculator = ProfitSplitCalculator(db)
    return calculator.estimate_next_payout(account_id)


@router.post("/payouts/request/{trader_id}/{account_id}")
async def request_payout(
    trader_id: int,
    account_id: int,
    data: PayoutRequest,
    db=Depends(get_db)
):
    """Request a profit payout."""
    from prop_firm import ProfitSplitCalculator
    from datetime import timedelta
    
    calculator = ProfitSplitCalculator(db)
    
    # Use bi-weekly period
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=14)
    
    try:
        payout = calculator.create_payout_request(
            trader_id=trader_id,
            account_id=account_id,
            period_start=period_start,
            period_end=period_end,
            payment_method=data.payment_method
        )
        return {
            "success": True,
            "payout_id": payout.id,
            "amount": float(payout.trader_amount),
            "status": payout.status
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payouts/history/{trader_id}")
async def get_payout_history(trader_id: int, limit: int = 10, db=Depends(get_db)):
    """Get payout history."""
    from prop_firm import ProfitSplitCalculator
    
    calculator = ProfitSplitCalculator(db)
    return {"payouts": calculator.get_payout_history(trader_id, limit)}


# ============== Leaderboard Endpoints ==============

@router.get("/leaderboard")
async def get_leaderboard(
    category: str = "pnl",
    period: str = "monthly",
    limit: int = 100,
    db=Depends(get_db)
):
    """Get trader leaderboard."""
    from prop_firm import Leaderboard
    
    lb = Leaderboard(db)
    return {"leaderboard": lb.get_leaderboard(category, period, limit)}


@router.get("/profile/{trader_id}")
async def get_trader_profile(trader_id: int, db=Depends(get_db)):
    """Get full trader profile with rankings and badges."""
    from prop_firm import Leaderboard
    
    lb = Leaderboard(db)
    return lb.get_trader_profile(trader_id)


@router.get("/achievements/{trader_id}")
async def get_achievements_progress(trader_id: int, db=Depends(get_db)):
    """Get progress towards all achievements."""
    from prop_firm import Leaderboard
    
    lb = Leaderboard(db)
    return {"achievements": lb.get_achievements_progress(trader_id)}


@router.post("/badges/check/{trader_id}")
async def check_and_award_badges(trader_id: int, db=Depends(get_db)):
    """Check and award any earned badges."""
    from prop_firm import Leaderboard
    
    lb = Leaderboard(db)
    newly_awarded = lb.check_and_award_badges(trader_id)
    return {"newly_awarded": newly_awarded}


# ============== AI Coaching Endpoints ==============

@router.get("/coaching/insights/{trader_id}")
async def get_coaching_insights(trader_id: int, db=Depends(get_db)):
    """Get AI-generated coaching insights."""
    from prop_firm import AICoach
    
    coach = AICoach(db)
    return {"insights": coach.analyze_trading_behavior(trader_id)}


@router.get("/coaching/briefing/{trader_id}")
async def get_daily_briefing(trader_id: int, db=Depends(get_db)):
    """Get daily coaching briefing."""
    from prop_firm import AICoach
    
    coach = AICoach(db)
    return coach.get_daily_briefing(trader_id)


@router.post("/coaching/ask/{trader_id}")
async def ask_coach(trader_id: int, data: CoachingQuestion, db=Depends(get_db)):
    """Ask the AI coach a question."""
    from prop_firm import AICoach
    
    coach = AICoach(db)
    # Note: This requires async LLM client
    # For now, return rule-based insights
    insights = coach.analyze_trading_behavior(trader_id)
    
    return {
        "question": data.question,
        "response": "AI coaching coming soon! Here are your current insights:",
        "insights": insights[:3]
    }


# ============== Admin Endpoints ==============

@router.post("/admin/kyc/approve/{trader_id}")
async def admin_approve_kyc(trader_id: int, db=Depends(get_db)):
    """Approve KYC for a trader (admin only)."""
    from prop_firm import TraderOnboarding
    
    # In production, add admin authentication
    onboarding = TraderOnboarding(db)
    return onboarding.approve_kyc(trader_id)


@router.post("/admin/rankings/update")
async def admin_update_rankings(db=Depends(get_db)):
    """Update all trader rankings (admin only)."""
    from prop_firm import Leaderboard
    
    lb = Leaderboard(db)
    lb.update_rankings()
    return {"success": True, "message": "Rankings updated"}


# ============== Dependency ==============

def get_db():
    """Database session dependency - implement based on your setup."""
    # This should return your SQLAlchemy session
    # Example:
    # from database import SessionLocal
    # db = SessionLocal()
    # try:
    #     yield db
    # finally:
    #     db.close()
    pass
