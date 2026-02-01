"""
Subscription and Billing Models
===============================
Models for Stripe integration and usage tracking.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date,
    ForeignKey, Text, Index, JSON, Numeric, Enum as SQLEnum,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle states."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"


class SubscriptionPlan:
    """
    Subscription plan definitions with limits.

    Not a database model - static configuration.
    """
    FREE = {
        "id": "free",
        "name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
        "limits": {
            "strategies": 1,
            "portfolios": 1,
            "api_calls_per_day": 100,
            "signals_per_day": 50,
            "historical_data_days": 30,
            "live_trading": False,
            "sso_enabled": False,
            "audit_logs": False,
            "dedicated_support": False,
            "max_users": 1,
        }
    }

    PRO = {
        "id": "pro",
        "name": "Pro",
        "price_monthly": 99,
        "price_yearly": 990,
        "stripe_price_id_monthly": "price_pro_monthly",  # Set from env
        "stripe_price_id_yearly": "price_pro_yearly",
        "limits": {
            "strategies": 10,
            "portfolios": 5,
            "api_calls_per_day": 10000,
            "signals_per_day": 1000,
            "historical_data_days": 365,
            "live_trading": True,
            "sso_enabled": False,
            "audit_logs": True,
            "dedicated_support": False,
            "max_users": 5,
        }
    }

    ENTERPRISE = {
        "id": "enterprise",
        "name": "Enterprise",
        "price_monthly": None,  # Custom pricing
        "price_yearly": None,
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
        "limits": {
            "strategies": -1,  # Unlimited
            "portfolios": -1,
            "api_calls_per_day": -1,
            "signals_per_day": -1,
            "historical_data_days": -1,
            "live_trading": True,
            "sso_enabled": True,
            "audit_logs": True,
            "dedicated_support": True,
            "max_users": -1,
        }
    }

    @classmethod
    def get_plan(cls, plan_id: str) -> Optional[Dict]:
        """Get plan configuration by ID."""
        plans = {
            "free": cls.FREE,
            "pro": cls.PRO,
            "enterprise": cls.ENTERPRISE,
        }
        return plans.get(plan_id)

    @classmethod
    def get_limit(cls, plan_id: str, limit_name: str) -> Optional[int]:
        """Get a specific limit for a plan."""
        plan = cls.get_plan(plan_id)
        if plan:
            return plan["limits"].get(limit_name)
        return None


class Subscription(Base):
    """
    Subscription record linked to Stripe.

    Tracks the current subscription state for billing.
    """
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Plan
    plan_id = Column(String(50), nullable=False, default="free")
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)

    # Billing cycle
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))

    # Stripe integration
    stripe_subscription_id = Column(String(255), unique=True)
    stripe_price_id = Column(String(255))
    stripe_customer_id = Column(String(255))

    # Trial
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))

    # Quantity (for seat-based pricing)
    quantity = Column(Integer, default=1)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    organization = relationship("Organization", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription {self.organization_id} ({self.plan_id}, {self.status.value})>"

    @property
    def is_active(self) -> bool:
        """Check if subscription allows service access."""
        return self.status in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE  # Grace period
        ]

    @property
    def limits(self) -> Dict[str, int]:
        """Get current plan limits."""
        plan = SubscriptionPlan.get_plan(self.plan_id)
        if plan:
            return plan["limits"]
        return SubscriptionPlan.FREE["limits"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "limits": self.limits,
        }


class UsageRecord(Base):
    """
    Daily usage tracking for metered billing.

    Records API calls, signals generated, etc. per organization per day.
    """
    __tablename__ = "usage_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False
    )

    # Metric identification
    metric_type = Column(String(50), nullable=False)  # api_calls, signals, trades
    recorded_date = Column(Date, nullable=False)

    # Usage count
    quantity = Column(Integer, nullable=False, default=0)

    # Billing period (for invoicing)
    billing_period_start = Column(Date)
    billing_period_end = Column(Date)

    # Stripe metering
    stripe_usage_record_id = Column(String(255))
    reported_to_stripe = Column(Boolean, default=False)
    reported_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            'organization_id', 'metric_type', 'recorded_date',
            name='uix_usage_org_metric_date'
        ),
        Index('ix_usage_org_date', 'organization_id', 'recorded_date'),
    )

    def __repr__(self):
        return f"<UsageRecord {self.organization_id} {self.metric_type}={self.quantity} ({self.recorded_date})>"


class Invoice(Base):
    """
    Invoice records from Stripe.

    Stored for reference and compliance.
    """
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Stripe reference
    stripe_invoice_id = Column(String(255), unique=True, nullable=False)

    # Invoice details
    number = Column(String(100))
    status = Column(String(50))  # draft, open, paid, void, uncollectible
    currency = Column(String(3), default="usd")

    # Amounts (in cents)
    subtotal = Column(Integer)
    tax = Column(Integer, default=0)
    total = Column(Integer)
    amount_paid = Column(Integer, default=0)
    amount_due = Column(Integer)

    # Dates
    period_start = Column(DateTime(timezone=True))
    period_end = Column(DateTime(timezone=True))
    due_date = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))

    # PDF
    invoice_pdf = Column(Text)  # URL to Stripe-hosted PDF
    hosted_invoice_url = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Invoice {self.number} ${self.total/100:.2f} ({self.status})>"


class PaymentMethod(Base):
    """
    Stored payment methods from Stripe.
    """
    __tablename__ = "payment_methods"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Stripe reference
    stripe_payment_method_id = Column(String(255), unique=True, nullable=False)

    # Card details (non-sensitive, from Stripe)
    type = Column(String(50))  # card, bank_account
    brand = Column(String(50))  # visa, mastercard, amex
    last4 = Column(String(4))
    exp_month = Column(Integer)
    exp_year = Column(Integer)

    # Status
    is_default = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<PaymentMethod {self.brand} ****{self.last4}>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "brand": self.brand,
            "last4": self.last4,
            "exp_month": self.exp_month,
            "exp_year": self.exp_year,
            "is_default": self.is_default,
        }
