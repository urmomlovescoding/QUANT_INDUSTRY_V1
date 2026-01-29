"""
Challenge Engine
Manages trading challenges, evaluations, and progression.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import logging

from .models import (
    Trader, Challenge, Evaluation, TraderAccount, PropTrade,
    ChallengePhase, ChallengeResult, AccountStatus
)

logger = logging.getLogger(__name__)


class ChallengeType(Enum):
    """Predefined challenge configurations."""
    STARTER_10K = "starter_10k"
    STANDARD_25K = "standard_25k"
    PROFESSIONAL_50K = "professional_50k"
    ELITE_100K = "elite_100k"
    MASTER_200K = "master_200k"


# Challenge configurations
CHALLENGE_CONFIGS = {
    ChallengeType.STARTER_10K: {
        "name": "Starter $10K Challenge",
        "starting_balance": Decimal("10000"),
        "fee": Decimal("99"),
        "phase_1": {
            "profit_target_pct": 8.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 30,
        },
        "phase_2": {
            "profit_target_pct": 5.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 60,
        },
        "profit_split": 80.0,
    },
    ChallengeType.STANDARD_25K: {
        "name": "Standard $25K Challenge",
        "starting_balance": Decimal("25000"),
        "fee": Decimal("199"),
        "phase_1": {
            "profit_target_pct": 8.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 30,
        },
        "phase_2": {
            "profit_target_pct": 5.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 60,
        },
        "profit_split": 80.0,
    },
    ChallengeType.PROFESSIONAL_50K: {
        "name": "Professional $50K Challenge",
        "starting_balance": Decimal("50000"),
        "fee": Decimal("299"),
        "phase_1": {
            "profit_target_pct": 8.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 30,
        },
        "phase_2": {
            "profit_target_pct": 5.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 60,
        },
        "profit_split": 80.0,
    },
    ChallengeType.ELITE_100K: {
        "name": "Elite $100K Challenge",
        "starting_balance": Decimal("100000"),
        "fee": Decimal("499"),
        "phase_1": {
            "profit_target_pct": 10.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 30,
        },
        "phase_2": {
            "profit_target_pct": 5.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 60,
        },
        "profit_split": 85.0,  # Higher split for elite
    },
    ChallengeType.MASTER_200K: {
        "name": "Master $200K Challenge",
        "starting_balance": Decimal("200000"),
        "fee": Decimal("999"),
        "phase_1": {
            "profit_target_pct": 10.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 30,
        },
        "phase_2": {
            "profit_target_pct": 5.0,
            "max_daily_drawdown_pct": 5.0,
            "max_total_drawdown_pct": 10.0,
            "min_trading_days": 5,
            "max_trading_days": 60,
        },
        "profit_split": 90.0,  # Highest split for master
    },
}


class ChallengeEngine:
    """
    Manages the lifecycle of trading challenges.
    
    Features:
    - Create and configure challenges
    - Track progress and metrics
    - Handle phase transitions
    - Determine pass/fail conditions
    - Provision funded accounts
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def create_challenge(
        self,
        trader_id: int,
        challenge_type: ChallengeType,
        custom_config: Optional[Dict] = None
    ) -> Challenge:
        """
        Create a new challenge for a trader.
        
        Args:
            trader_id: The trader's ID
            challenge_type: Predefined challenge type
            custom_config: Optional overrides for challenge parameters
        
        Returns:
            Created Challenge object
        """
        config = CHALLENGE_CONFIGS[challenge_type].copy()
        if custom_config:
            config.update(custom_config)
        
        phase_config = config["phase_1"]
        starting_balance = config["starting_balance"]
        
        challenge = Challenge(
            trader_id=trader_id,
            name=config["name"],
            phase=ChallengePhase.PHASE_1,
            starting_balance=starting_balance,
            current_balance=starting_balance,
            peak_balance=starting_balance,
            profit_target_pct=phase_config["profit_target_pct"],
            profit_target_amount=starting_balance * Decimal(str(phase_config["profit_target_pct"] / 100)),
            max_daily_drawdown_pct=phase_config["max_daily_drawdown_pct"],
            max_total_drawdown_pct=phase_config["max_total_drawdown_pct"],
            max_daily_drawdown_amount=starting_balance * Decimal(str(phase_config["max_daily_drawdown_pct"] / 100)),
            max_total_drawdown_amount=starting_balance * Decimal(str(phase_config["max_total_drawdown_pct"] / 100)),
            min_trading_days=phase_config["min_trading_days"],
            max_trading_days=phase_config["max_trading_days"],
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=phase_config["max_trading_days"]),
            fee_paid=config["fee"],
            result=ChallengeResult.PENDING
        )
        
        self.db.add(challenge)
        self.db.commit()
        
        logger.info(f"Created challenge {challenge.id} for trader {trader_id}: {config['name']}")
        return challenge
    
    def update_challenge_metrics(
        self,
        challenge_id: int,
        current_balance: Decimal,
        daily_pnl: Decimal
    ) -> Tuple[Challenge, Dict[str, Any]]:
        """
        Update challenge metrics after trading activity.
        
        Args:
            challenge_id: Challenge ID
            current_balance: Current account balance
            daily_pnl: Today's P&L
        
        Returns:
            Tuple of (updated Challenge, status dict with any alerts)
        """
        challenge = self.db.query(Challenge).filter_by(id=challenge_id).first()
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")
        
        alerts = []
        
        # Update balances
        challenge.current_balance = current_balance
        challenge.daily_pnl = daily_pnl
        
        # Update peak balance (high-water mark)
        if current_balance > challenge.peak_balance:
            challenge.peak_balance = current_balance
        
        # Calculate P&L
        challenge.current_pnl = current_balance - challenge.starting_balance
        challenge.current_pnl_pct = float(challenge.current_pnl / challenge.starting_balance * 100)
        
        # Calculate drawdown from peak
        drawdown = challenge.peak_balance - current_balance
        challenge.current_drawdown = drawdown
        challenge.current_drawdown_pct = float(drawdown / challenge.peak_balance * 100)
        
        # Calculate daily drawdown
        if daily_pnl < 0:
            challenge.daily_drawdown = abs(daily_pnl)
        else:
            challenge.daily_drawdown = Decimal("0")
        
        # Check for rule violations
        status = self._check_challenge_status(challenge)
        
        self.db.commit()
        
        return challenge, status
    
    def _check_challenge_status(self, challenge: Challenge) -> Dict[str, Any]:
        """Check if challenge has passed, failed, or needs attention."""
        status = {
            "passed": False,
            "failed": False,
            "alerts": [],
            "progress_pct": 0,
        }
        
        # Check for failure conditions
        if challenge.current_drawdown_pct >= challenge.max_total_drawdown_pct:
            challenge.result = ChallengeResult.FAILED
            challenge.failed_reason = "Maximum total drawdown exceeded"
            challenge.completed_at = datetime.utcnow()
            status["failed"] = True
            status["alerts"].append({
                "type": "failure",
                "message": f"Challenge failed: {challenge.failed_reason}"
            })
            return status
        
        if challenge.daily_drawdown >= challenge.max_daily_drawdown_amount:
            challenge.result = ChallengeResult.FAILED
            challenge.failed_reason = "Maximum daily drawdown exceeded"
            challenge.completed_at = datetime.utcnow()
            status["failed"] = True
            status["alerts"].append({
                "type": "failure",
                "message": f"Challenge failed: {challenge.failed_reason}"
            })
            return status
        
        # Check for time expiry
        if datetime.utcnow() > challenge.end_date:
            if not challenge.profit_target_reached:
                challenge.result = ChallengeResult.EXPIRED
                challenge.failed_reason = "Challenge period expired without reaching profit target"
                challenge.completed_at = datetime.utcnow()
                status["failed"] = True
                status["alerts"].append({
                    "type": "failure",
                    "message": f"Challenge failed: {challenge.failed_reason}"
                })
                return status
        
        # Check for passing conditions
        if (challenge.profit_target_reached and 
            challenge.trading_days_completed >= challenge.min_trading_days):
            challenge.result = ChallengeResult.PASSED
            challenge.completed_at = datetime.utcnow()
            status["passed"] = True
            status["alerts"].append({
                "type": "success",
                "message": f"Congratulations! Challenge {challenge.phase.value} passed!"
            })
        
        # Calculate progress
        if challenge.profit_target_pct > 0:
            status["progress_pct"] = min(100, (challenge.current_pnl_pct / challenge.profit_target_pct) * 100)
        
        # Warning alerts
        drawdown_warning_threshold = 0.7  # 70% of max
        if challenge.current_drawdown_pct >= challenge.max_total_drawdown_pct * drawdown_warning_threshold:
            status["alerts"].append({
                "type": "warning",
                "message": f"Warning: Approaching maximum drawdown ({challenge.current_drawdown_pct:.1f}%)"
            })
        
        days_remaining = challenge.days_remaining
        if days_remaining <= 5 and not challenge.profit_target_reached:
            status["alerts"].append({
                "type": "warning",
                "message": f"Warning: Only {days_remaining} days remaining to reach profit target"
            })
        
        return status
    
    def advance_to_phase_2(self, challenge_id: int) -> Challenge:
        """
        Advance a passed Phase 1 challenge to Phase 2.
        """
        challenge = self.db.query(Challenge).filter_by(id=challenge_id).first()
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")
        
        if challenge.result != ChallengeResult.PASSED:
            raise ValueError("Challenge must be passed to advance to Phase 2")
        
        if challenge.phase != ChallengePhase.PHASE_1:
            raise ValueError("Challenge must be in Phase 1 to advance")
        
        # Get Phase 2 config
        challenge_type = self._get_challenge_type(challenge)
        config = CHALLENGE_CONFIGS[challenge_type]["phase_2"]
        
        # Create Phase 2 challenge
        phase_2 = Challenge(
            trader_id=challenge.trader_id,
            name=f"{challenge.name} - Phase 2",
            phase=ChallengePhase.PHASE_2,
            starting_balance=challenge.starting_balance,  # Reset to original
            current_balance=challenge.starting_balance,
            peak_balance=challenge.starting_balance,
            profit_target_pct=config["profit_target_pct"],
            profit_target_amount=challenge.starting_balance * Decimal(str(config["profit_target_pct"] / 100)),
            max_daily_drawdown_pct=config["max_daily_drawdown_pct"],
            max_total_drawdown_pct=config["max_total_drawdown_pct"],
            max_daily_drawdown_amount=challenge.starting_balance * Decimal(str(config["max_daily_drawdown_pct"] / 100)),
            max_total_drawdown_amount=challenge.starting_balance * Decimal(str(config["max_total_drawdown_pct"] / 100)),
            min_trading_days=config["min_trading_days"],
            max_trading_days=config["max_trading_days"],
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=config["max_trading_days"]),
            result=ChallengeResult.PENDING
        )
        
        self.db.add(phase_2)
        self.db.commit()
        
        logger.info(f"Advanced trader {challenge.trader_id} to Phase 2 (challenge {phase_2.id})")
        return phase_2
    
    def provision_funded_account(self, challenge_id: int) -> TraderAccount:
        """
        Provision a funded account after passing Phase 2.
        """
        challenge = self.db.query(Challenge).filter_by(id=challenge_id).first()
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")
        
        if challenge.result != ChallengeResult.PASSED:
            raise ValueError("Challenge must be passed to provision funded account")
        
        if challenge.phase != ChallengePhase.PHASE_2:
            raise ValueError("Must pass Phase 2 to get funded account")
        
        # Get profit split from config
        challenge_type = self._get_challenge_type(challenge)
        profit_split = CHALLENGE_CONFIGS[challenge_type]["profit_split"]
        
        # Update trader's profit split
        trader = self.db.query(Trader).filter_by(id=challenge.trader_id).first()
        trader.profit_split_percentage = profit_split
        trader.status = AccountStatus.FUNDED
        
        # Create funded account
        import uuid
        account = TraderAccount(
            trader_id=challenge.trader_id,
            challenge_id=challenge_id,
            account_number=f"QI-{uuid.uuid4().hex[:8].upper()}",
            account_type="funded",
            initial_balance=challenge.starting_balance,
            current_balance=challenge.starting_balance,
            buying_power=challenge.starting_balance,
            max_daily_loss=challenge.max_daily_drawdown_amount,
            max_total_drawdown=challenge.max_total_drawdown_amount,
            next_scale_target=challenge.starting_balance * Decimal("1.10"),  # 10% to scale
            is_active=True
        )
        
        self.db.add(account)
        self.db.commit()
        
        logger.info(f"Provisioned funded account {account.account_number} for trader {challenge.trader_id}")
        return account
    
    def _get_challenge_type(self, challenge: Challenge) -> ChallengeType:
        """Determine challenge type from balance."""
        balance = float(challenge.starting_balance)
        if balance <= 10000:
            return ChallengeType.STARTER_10K
        elif balance <= 25000:
            return ChallengeType.STANDARD_25K
        elif balance <= 50000:
            return ChallengeType.PROFESSIONAL_50K
        elif balance <= 100000:
            return ChallengeType.ELITE_100K
        else:
            return ChallengeType.MASTER_200K
    
    def record_trading_day(self, challenge_id: int, evaluation: Dict[str, Any]) -> Evaluation:
        """
        Record a daily evaluation snapshot.
        """
        challenge = self.db.query(Challenge).filter_by(id=challenge_id).first()
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")
        
        eval_record = Evaluation(
            challenge_id=challenge_id,
            trader_id=challenge.trader_id,
            evaluation_date=evaluation.get("date", datetime.utcnow()),
            start_balance=evaluation.get("start_balance", challenge.starting_balance),
            end_balance=evaluation.get("end_balance", challenge.current_balance),
            daily_pnl=evaluation.get("daily_pnl", 0),
            daily_pnl_pct=evaluation.get("daily_pnl_pct", 0),
            cumulative_pnl=evaluation.get("cumulative_pnl", challenge.current_pnl),
            cumulative_pnl_pct=evaluation.get("cumulative_pnl_pct", challenge.current_pnl_pct),
            trades_count=evaluation.get("trades_count", 0),
            winning_trades=evaluation.get("winning_trades", 0),
            losing_trades=evaluation.get("losing_trades", 0),
            win_rate=evaluation.get("win_rate", 0),
            sharpe_ratio=evaluation.get("sharpe_ratio"),
            profit_factor=evaluation.get("profit_factor"),
            is_trading_day=evaluation.get("is_trading_day", True)
        )
        
        if eval_record.is_trading_day:
            challenge.trading_days_completed += 1
        
        self.db.add(eval_record)
        self.db.commit()
        
        return eval_record
    
    def get_challenge_summary(self, challenge_id: int) -> Dict[str, Any]:
        """Get comprehensive challenge summary for dashboard."""
        challenge = self.db.query(Challenge).filter_by(id=challenge_id).first()
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")
        
        return {
            "id": challenge.id,
            "name": challenge.name,
            "phase": challenge.phase.value,
            "result": challenge.result.value,
            "balance": {
                "starting": float(challenge.starting_balance),
                "current": float(challenge.current_balance),
                "peak": float(challenge.peak_balance),
            },
            "pnl": {
                "amount": float(challenge.current_pnl),
                "percentage": challenge.current_pnl_pct,
            },
            "targets": {
                "profit_target_pct": challenge.profit_target_pct,
                "profit_target_amount": float(challenge.profit_target_amount),
                "progress_pct": min(100, (challenge.current_pnl_pct / challenge.profit_target_pct) * 100) if challenge.profit_target_pct else 0,
            },
            "drawdown": {
                "current": float(challenge.current_drawdown),
                "current_pct": challenge.current_drawdown_pct,
                "max_allowed_pct": challenge.max_total_drawdown_pct,
                "daily": float(challenge.daily_drawdown),
                "max_daily_allowed": float(challenge.max_daily_drawdown_amount),
            },
            "trading_days": {
                "completed": challenge.trading_days_completed,
                "minimum": challenge.min_trading_days,
                "remaining": challenge.days_remaining,
            },
            "dates": {
                "start": challenge.start_date.isoformat(),
                "end": challenge.end_date.isoformat(),
            }
        }
