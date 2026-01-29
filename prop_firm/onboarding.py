"""
Trader Onboarding
Handles new trader registration, KYC, and challenge enrollment.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
import logging
import hashlib
import secrets
import re

from .models import Trader, Challenge, AccountStatus
from .challenge_engine import ChallengeEngine, ChallengeType

logger = logging.getLogger(__name__)


class TraderOnboarding:
    """
    Manages the trader onboarding process.
    
    Features:
    - Registration with validation
    - KYC document handling
    - Referral code processing
    - Challenge enrollment
    - Welcome flow
    """
    
    def __init__(self, db_session):
        self.db = db_session
        self.challenge_engine = ChallengeEngine(db_session)
    
    def register_trader(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str,
        country: str,
        phone: Optional[str] = None,
        timezone: str = "UTC",
        referral_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new trader.
        
        Returns:
            Dict with trader info and next steps
        """
        # Validate inputs
        errors = self._validate_registration(email, username, password)
        if errors:
            return {"success": False, "errors": errors}
        
        # Check for existing email/username
        existing = self.db.query(Trader).filter(
            (Trader.email == email.lower()) | (Trader.username == username.lower())
        ).first()
        
        if existing:
            if existing.email == email.lower():
                return {"success": False, "errors": ["Email already registered"]}
            else:
                return {"success": False, "errors": ["Username already taken"]}
        
        # Handle referral
        referred_by_id = None
        if referral_code:
            referrer = self.db.query(Trader).filter_by(referral_code=referral_code).first()
            if referrer:
                referred_by_id = referrer.id
        
        # Create trader
        trader = Trader(
            email=email.lower(),
            username=username.lower(),
            full_name=full_name,
            phone=phone,
            country=country,
            timezone=timezone,
            password_hash=self._hash_password(password),
            status=AccountStatus.PENDING,
            referral_code=self._generate_referral_code(username),
            referred_by=referred_by_id,
        )
        
        self.db.add(trader)
        self.db.commit()
        
        logger.info(f"Registered new trader: {username} ({email})")
        
        return {
            "success": True,
            "trader": {
                "id": trader.id,
                "username": trader.username,
                "email": trader.email,
                "referral_code": trader.referral_code,
            },
            "next_steps": [
                "Complete KYC verification",
                "Choose a challenge to start trading",
            ]
        }
    
    def _validate_registration(
        self,
        email: str,
        username: str,
        password: str
    ) -> list:
        """Validate registration inputs."""
        errors = []
        
        # Email validation
        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_pattern, email):
            errors.append("Invalid email format")
        
        # Username validation
        if len(username) < 3 or len(username) > 20:
            errors.append("Username must be 3-20 characters")
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append("Username can only contain letters, numbers, and underscores")
        
        # Password validation
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', password):
            errors.append("Password must contain at least one number")
        
        return errors
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256((password + salt).encode())
        return f"{salt}:{hash_obj.hexdigest()}"
    
    def _generate_referral_code(self, username: str) -> str:
        """Generate unique referral code."""
        random_suffix = secrets.token_hex(3).upper()
        return f"{username[:4].upper()}{random_suffix}"
    
    def verify_password(self, trader: Trader, password: str) -> bool:
        """Verify password against stored hash."""
        if not trader.password_hash or ':' not in trader.password_hash:
            return False
        salt, stored_hash = trader.password_hash.split(':')
        hash_obj = hashlib.sha256((password + salt).encode())
        return hash_obj.hexdigest() == stored_hash
    
    def submit_kyc(
        self,
        trader_id: int,
        document_type: str,
        document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit KYC documents for verification.
        
        Args:
            trader_id: Trader's ID
            document_type: Type of document (passport, drivers_license, id_card)
            document_data: Document info and file references
        
        Returns:
            KYC submission status
        """
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return {"success": False, "error": "Trader not found"}
        
        # Store document reference (in production, integrate with KYC provider)
        kyc_docs = trader.kyc_documents or {}
        kyc_docs[document_type] = {
            "submitted_at": datetime.utcnow().isoformat(),
            "status": "pending_review",
            **document_data
        }
        trader.kyc_documents = kyc_docs
        
        self.db.commit()
        
        logger.info(f"KYC document submitted for trader {trader_id}: {document_type}")
        
        return {
            "success": True,
            "status": "pending_review",
            "message": "Documents submitted successfully. Review typically takes 24-48 hours."
        }
    
    def approve_kyc(self, trader_id: int) -> Dict[str, Any]:
        """Approve KYC for a trader (admin function)."""
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return {"success": False, "error": "Trader not found"}
        
        trader.kyc_verified = True
        trader.status = AccountStatus.EVALUATION
        
        self.db.commit()
        
        logger.info(f"KYC approved for trader {trader_id}")
        
        return {
            "success": True,
            "status": trader.status.value,
            "message": "KYC approved! You can now enroll in a challenge."
        }
    
    def enroll_challenge(
        self,
        trader_id: int,
        challenge_type: str,
        payment_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Enroll a trader in a challenge.
        
        Args:
            trader_id: Trader's ID
            challenge_type: Challenge type identifier
            payment_info: Payment details for challenge fee
        
        Returns:
            Enrollment result with challenge details
        """
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return {"success": False, "error": "Trader not found"}
        
        if not trader.kyc_verified:
            return {"success": False, "error": "KYC verification required before enrollment"}
        
        # Map string to ChallengeType enum
        try:
            challenge_type_enum = ChallengeType[challenge_type.upper()]
        except KeyError:
            return {"success": False, "error": f"Invalid challenge type: {challenge_type}"}
        
        # Process payment (in production, integrate with payment provider)
        # For now, assume payment is successful
        payment_successful = True
        
        if not payment_successful:
            return {"success": False, "error": "Payment failed"}
        
        # Create challenge
        challenge = self.challenge_engine.create_challenge(
            trader_id=trader_id,
            challenge_type=challenge_type_enum
        )
        
        # Update trader status
        trader.status = AccountStatus.EVALUATION
        self.db.commit()
        
        logger.info(f"Trader {trader_id} enrolled in {challenge_type}: challenge {challenge.id}")
        
        return {
            "success": True,
            "challenge": {
                "id": challenge.id,
                "name": challenge.name,
                "starting_balance": float(challenge.starting_balance),
                "profit_target": challenge.profit_target_pct,
                "max_drawdown": challenge.max_total_drawdown_pct,
                "start_date": challenge.start_date.isoformat(),
                "end_date": challenge.end_date.isoformat(),
            },
            "next_steps": [
                "Connect your trading platform",
                "Review the challenge rules",
                "Start trading when you're ready",
            ]
        }
    
    def get_available_challenges(self) -> List[Dict[str, Any]]:
        """Get list of available challenges for enrollment."""
        from .challenge_engine import CHALLENGE_CONFIGS
        
        challenges = []
        for challenge_type, config in CHALLENGE_CONFIGS.items():
            challenges.append({
                "id": challenge_type.value,
                "name": config["name"],
                "starting_balance": float(config["starting_balance"]),
                "fee": float(config["fee"]),
                "phase_1": {
                    "profit_target": config["phase_1"]["profit_target_pct"],
                    "max_daily_drawdown": config["phase_1"]["max_daily_drawdown_pct"],
                    "max_total_drawdown": config["phase_1"]["max_total_drawdown_pct"],
                    "min_trading_days": config["phase_1"]["min_trading_days"],
                    "max_trading_days": config["phase_1"]["max_trading_days"],
                },
                "phase_2": {
                    "profit_target": config["phase_2"]["profit_target_pct"],
                    "max_daily_drawdown": config["phase_2"]["max_daily_drawdown_pct"],
                    "max_total_drawdown": config["phase_2"]["max_total_drawdown_pct"],
                    "min_trading_days": config["phase_2"]["min_trading_days"],
                    "max_trading_days": config["phase_2"]["max_trading_days"],
                },
                "profit_split": config["profit_split"],
            })
        
        return challenges
    
    def get_onboarding_status(self, trader_id: int) -> Dict[str, Any]:
        """Get current onboarding status for a trader."""
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return {"error": "Trader not found"}
        
        # Get active challenges
        active_challenges = (
            self.db.query(Challenge)
            .filter_by(trader_id=trader_id)
            .filter(Challenge.result == "pending")
            .all()
        )
        
        return {
            "trader": {
                "id": trader.id,
                "username": trader.username,
                "status": trader.status.value,
            },
            "steps": {
                "registration": {"completed": True},
                "kyc_verified": {"completed": trader.kyc_verified},
                "challenge_enrolled": {"completed": len(active_challenges) > 0},
            },
            "active_challenges": [
                {
                    "id": c.id,
                    "name": c.name,
                    "phase": c.phase.value,
                }
                for c in active_challenges
            ],
            "next_action": self._get_next_action(trader, active_challenges),
        }
    
    def _get_next_action(
        self,
        trader: Trader,
        active_challenges: list
    ) -> Dict[str, str]:
        """Determine the next action for the trader."""
        if not trader.kyc_verified:
            return {
                "action": "submit_kyc",
                "message": "Submit KYC documents to continue"
            }
        elif len(active_challenges) == 0:
            return {
                "action": "enroll_challenge",
                "message": "Choose a challenge to start your trading journey"
            }
        else:
            return {
                "action": "trade",
                "message": "Start trading to pass your challenge!"
            }
