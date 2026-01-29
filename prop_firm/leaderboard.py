"""
Leaderboard System
Gamification and competitive rankings for prop traders.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from .models import Trader, PerformanceMetrics, Badge, TraderAccount

logger = logging.getLogger(__name__)


class RankTier(Enum):
    """Trader rank tiers based on XP."""
    ROOKIE = ("Rookie", 0, "🌱")
    APPRENTICE = ("Apprentice", 500, "📚")
    TRADER = ("Trader", 1500, "📊")
    SKILLED = ("Skilled", 3500, "⭐")
    EXPERT = ("Expert", 7000, "💎")
    MASTER = ("Master", 12000, "🏆")
    ELITE = ("Elite", 20000, "👑")
    LEGEND = ("Legend", 35000, "🔥")


# Badge definitions
BADGE_DEFINITIONS = [
    {
        "name": "First Trade",
        "description": "Completed your first trade",
        "icon": "🎯",
        "criteria": {"total_trades": {"gte": 1}},
        "xp_reward": 50,
        "rarity": "common"
    },
    {
        "name": "Century Club",
        "description": "Completed 100 trades",
        "icon": "💯",
        "criteria": {"total_trades": {"gte": 100}},
        "xp_reward": 200,
        "rarity": "common"
    },
    {
        "name": "Sharpshooter",
        "description": "Achieved 60%+ win rate over 50+ trades",
        "icon": "🎯",
        "criteria": {"win_rate": {"gte": 60}, "total_trades": {"gte": 50}},
        "xp_reward": 500,
        "rarity": "rare"
    },
    {
        "name": "Consistent",
        "description": "Profitable for 10 consecutive trading days",
        "icon": "📈",
        "criteria": {"profitable_streak": {"gte": 10}},
        "xp_reward": 750,
        "rarity": "rare"
    },
    {
        "name": "Risk Manager",
        "description": "Maintained <3% max drawdown for a month",
        "icon": "🛡️",
        "criteria": {"max_drawdown": {"lte": 3}, "trading_days": {"gte": 20}},
        "xp_reward": 1000,
        "rarity": "epic"
    },
    {
        "name": "Sharp Mind",
        "description": "Achieved Sharpe Ratio > 2.0",
        "icon": "🧠",
        "criteria": {"sharpe_ratio": {"gte": 2.0}},
        "xp_reward": 1500,
        "rarity": "epic"
    },
    {
        "name": "Money Maker",
        "description": "Earned $10,000+ in payouts",
        "icon": "💰",
        "criteria": {"total_payouts": {"gte": 10000}},
        "xp_reward": 2000,
        "rarity": "epic"
    },
    {
        "name": "Top 10",
        "description": "Reached top 10 on monthly leaderboard",
        "icon": "🏅",
        "criteria": {"monthly_rank": {"lte": 10}},
        "xp_reward": 2500,
        "rarity": "legendary"
    },
    {
        "name": "Champion",
        "description": "Reached #1 on monthly leaderboard",
        "icon": "🥇",
        "criteria": {"monthly_rank": {"eq": 1}},
        "xp_reward": 5000,
        "rarity": "legendary"
    },
    {
        "name": "Scale Master",
        "description": "Scaled your account 5 times",
        "icon": "📈",
        "criteria": {"scale_level": {"gte": 5}},
        "xp_reward": 3000,
        "rarity": "legendary"
    },
]


class Leaderboard:
    """
    Manages trader rankings, badges, and gamification.
    
    Features:
    - Global and monthly leaderboards
    - Multiple ranking categories
    - Badge system with achievements
    - XP and rank progression
    - Challenge streaks
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def get_leaderboard(
        self,
        category: str = "pnl",
        period: str = "monthly",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard rankings.
        
        Args:
            category: Ranking category (pnl, win_rate, sharpe, consistency)
            period: Time period (daily, weekly, monthly, all_time)
            limit: Number of results
        
        Returns:
            List of ranked traders
        """
        # Get all traders with metrics
        query = (
            self.db.query(Trader, PerformanceMetrics)
            .join(PerformanceMetrics, Trader.id == PerformanceMetrics.trader_id)
            .filter(Trader.status == "funded")
        )
        
        # Order by category
        if category == "pnl":
            query = query.order_by(PerformanceMetrics.total_pnl.desc())
        elif category == "win_rate":
            query = query.filter(PerformanceMetrics.total_trades >= 20)
            query = query.order_by(PerformanceMetrics.win_rate.desc())
        elif category == "sharpe":
            query = query.filter(PerformanceMetrics.total_trades >= 20)
            query = query.order_by(PerformanceMetrics.sharpe_ratio.desc().nullslast())
        elif category == "consistency":
            query = query.order_by(PerformanceMetrics.consistency_score.desc().nullslast())
        elif category == "profit_factor":
            query = query.filter(PerformanceMetrics.total_trades >= 20)
            query = query.order_by(PerformanceMetrics.profit_factor.desc().nullslast())
        
        results = query.limit(limit).all()
        
        leaderboard = []
        for rank, (trader, metrics) in enumerate(results, 1):
            leaderboard.append({
                "rank": rank,
                "trader": {
                    "id": trader.id,
                    "username": trader.username,
                    "rank_tier": trader.rank,
                    "badges_count": len(trader.badges or []),
                },
                "metrics": {
                    "total_pnl": float(metrics.total_pnl or 0),
                    "win_rate": metrics.win_rate,
                    "sharpe_ratio": metrics.sharpe_ratio,
                    "profit_factor": metrics.profit_factor,
                    "consistency_score": metrics.consistency_score,
                    "total_trades": metrics.total_trades,
                },
                "category_value": self._get_category_value(metrics, category),
            })
        
        return leaderboard
    
    def _get_category_value(self, metrics: PerformanceMetrics, category: str) -> Any:
        """Get the primary value for ranking category."""
        mapping = {
            "pnl": float(metrics.total_pnl or 0),
            "win_rate": metrics.win_rate,
            "sharpe": metrics.sharpe_ratio,
            "consistency": metrics.consistency_score,
            "profit_factor": metrics.profit_factor,
        }
        return mapping.get(category, 0)
    
    def update_rankings(self):
        """
        Update all trader rankings.
        Called periodically (e.g., hourly).
        """
        # Get all funded traders with metrics
        results = (
            self.db.query(PerformanceMetrics)
            .join(Trader, Trader.id == PerformanceMetrics.trader_id)
            .filter(Trader.status == "funded")
            .order_by(PerformanceMetrics.total_pnl.desc())
            .all()
        )
        
        # Update global ranks
        for rank, metrics in enumerate(results, 1):
            metrics.global_rank = rank
        
        # Update monthly ranks (based on monthly P&L)
        # In production, this would filter by current month's performance
        for rank, metrics in enumerate(results, 1):
            metrics.monthly_rank = rank
        
        self.db.commit()
        logger.info(f"Updated rankings for {len(results)} traders")
    
    def check_and_award_badges(self, trader_id: int) -> List[Dict[str, Any]]:
        """
        Check and award any earned badges to a trader.
        
        Returns:
            List of newly awarded badges
        """
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return []
        
        metrics = self.db.query(PerformanceMetrics).filter_by(trader_id=trader_id).first()
        account = self.db.query(TraderAccount).filter_by(trader_id=trader_id, is_active=True).first()
        
        current_badges = set(trader.badges or [])
        newly_awarded = []
        
        for badge_def in BADGE_DEFINITIONS:
            if badge_def["name"] in current_badges:
                continue  # Already has this badge
            
            if self._check_badge_criteria(badge_def["criteria"], metrics, account, trader):
                # Award badge
                current_badges.add(badge_def["name"])
                trader.xp_points = (trader.xp_points or 0) + badge_def["xp_reward"]
                
                newly_awarded.append({
                    "name": badge_def["name"],
                    "description": badge_def["description"],
                    "icon": badge_def["icon"],
                    "xp_reward": badge_def["xp_reward"],
                    "rarity": badge_def["rarity"],
                })
                
                logger.info(f"Awarded badge '{badge_def['name']}' to trader {trader_id}")
        
        if newly_awarded:
            trader.badges = list(current_badges)
            
            # Update rank tier based on XP
            trader.rank = self._get_rank_tier(trader.xp_points).value[0]
            
            self.db.commit()
        
        return newly_awarded
    
    def _check_badge_criteria(
        self,
        criteria: Dict,
        metrics: Optional[PerformanceMetrics],
        account: Optional[TraderAccount],
        trader: Trader
    ) -> bool:
        """Check if a trader meets badge criteria."""
        if not metrics:
            return False
        
        for field, conditions in criteria.items():
            # Get field value
            if hasattr(metrics, field):
                value = getattr(metrics, field)
            elif account and hasattr(account, field):
                value = getattr(account, field)
            elif hasattr(trader, field):
                value = getattr(trader, field)
            else:
                continue
            
            if value is None:
                return False
            
            # Check conditions
            for op, threshold in conditions.items():
                if op == "gte" and not (value >= threshold):
                    return False
                elif op == "lte" and not (value <= threshold):
                    return False
                elif op == "eq" and not (value == threshold):
                    return False
                elif op == "gt" and not (value > threshold):
                    return False
                elif op == "lt" and not (value < threshold):
                    return False
        
        return True
    
    def _get_rank_tier(self, xp: int) -> RankTier:
        """Determine rank tier based on XP."""
        for tier in reversed(RankTier):
            if xp >= tier.value[1]:
                return tier
        return RankTier.ROOKIE
    
    def get_trader_profile(self, trader_id: int) -> Dict[str, Any]:
        """Get full trader profile with rankings and badges."""
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return {"error": "Trader not found"}
        
        metrics = self.db.query(PerformanceMetrics).filter_by(trader_id=trader_id).first()
        account = self.db.query(TraderAccount).filter_by(trader_id=trader_id, is_active=True).first()
        
        # Get rank tier info
        xp = trader.xp_points or 0
        current_tier = self._get_rank_tier(xp)
        next_tier = None
        xp_to_next = 0
        
        for tier in RankTier:
            if tier.value[1] > xp:
                next_tier = tier
                xp_to_next = tier.value[1] - xp
                break
        
        return {
            "trader": {
                "id": trader.id,
                "username": trader.username,
                "full_name": trader.full_name,
                "status": trader.status.value if trader.status else None,
                "member_since": trader.created_at.isoformat() if trader.created_at else None,
            },
            "rank": {
                "tier": current_tier.value[0],
                "emoji": current_tier.value[2],
                "xp": xp,
                "next_tier": next_tier.value[0] if next_tier else None,
                "xp_to_next": xp_to_next,
            },
            "badges": [
                next(
                    (b for b in BADGE_DEFINITIONS if b["name"] == badge_name),
                    {"name": badge_name}
                )
                for badge_name in (trader.badges or [])
            ],
            "rankings": {
                "global_rank": metrics.global_rank if metrics else None,
                "monthly_rank": metrics.monthly_rank if metrics else None,
            },
            "metrics": {
                "total_pnl": float(metrics.total_pnl or 0) if metrics else 0,
                "win_rate": metrics.win_rate if metrics else 0,
                "total_trades": metrics.total_trades if metrics else 0,
                "sharpe_ratio": metrics.sharpe_ratio if metrics else None,
                "profit_factor": metrics.profit_factor if metrics else None,
                "max_drawdown": metrics.max_drawdown if metrics else None,
                "consistency_score": metrics.consistency_score if metrics else None,
            },
            "account": {
                "balance": float(account.current_balance) if account else None,
                "scale_level": account.scale_level if account else None,
                "total_payouts": float(account.total_payouts or 0) if account else 0,
            } if account else None,
        }
    
    def get_achievements_progress(self, trader_id: int) -> List[Dict[str, Any]]:
        """Get progress towards all badges."""
        trader = self.db.query(Trader).filter_by(id=trader_id).first()
        if not trader:
            return []
        
        metrics = self.db.query(PerformanceMetrics).filter_by(trader_id=trader_id).first()
        account = self.db.query(TraderAccount).filter_by(trader_id=trader_id, is_active=True).first()
        
        current_badges = set(trader.badges or [])
        progress = []
        
        for badge_def in BADGE_DEFINITIONS:
            is_earned = badge_def["name"] in current_badges
            badge_progress = self._calculate_badge_progress(
                badge_def["criteria"], metrics, account, trader
            )
            
            progress.append({
                "badge": badge_def,
                "earned": is_earned,
                "progress": badge_progress,
            })
        
        return progress
    
    def _calculate_badge_progress(
        self,
        criteria: Dict,
        metrics: Optional[PerformanceMetrics],
        account: Optional[TraderAccount],
        trader: Trader
    ) -> Dict[str, Any]:
        """Calculate progress towards badge criteria."""
        progress = {}
        
        for field, conditions in criteria.items():
            if hasattr(metrics, field):
                value = getattr(metrics, field) if metrics else 0
            elif account and hasattr(account, field):
                value = getattr(account, field) if account else 0
            else:
                value = 0
            
            value = value or 0
            
            for op, threshold in conditions.items():
                if op in ("gte", "gt"):
                    pct = min(100, (value / threshold) * 100) if threshold else 100
                    progress[field] = {
                        "current": value,
                        "target": threshold,
                        "percentage": pct,
                    }
                elif op in ("lte", "lt"):
                    # For "less than" criteria, invert logic
                    pct = 100 if value <= threshold else max(0, ((threshold / value) * 100) if value else 100)
                    progress[field] = {
                        "current": value,
                        "target": threshold,
                        "percentage": pct,
                    }
        
        return progress
