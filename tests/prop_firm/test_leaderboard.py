"""
Tests for Leaderboard and Gamification.
"""

import pytest
from prop_firm.leaderboard import (
    Leaderboard, BADGE_DEFINITIONS, RankTier
)


class TestRankTiers:
    """Tests for rank tier system."""
    
    def test_rank_tier_values(self):
        """Test rank tier XP thresholds."""
        assert RankTier.ROOKIE.value[1] == 0
        assert RankTier.APPRENTICE.value[1] == 500
        assert RankTier.LEGEND.value[1] == 35000
    
    def test_rank_tier_emojis(self):
        """Test rank tier emojis exist."""
        for tier in RankTier:
            assert len(tier.value[2]) > 0  # Has emoji


class TestBadgeDefinitions:
    """Tests for badge configuration."""
    
    def test_badge_structure(self):
        """Test all badges have required fields."""
        for badge in BADGE_DEFINITIONS:
            assert "name" in badge
            assert "description" in badge
            assert "icon" in badge
            assert "criteria" in badge
            assert "xp_reward" in badge
            assert "rarity" in badge
    
    def test_badge_rarities(self):
        """Test badge rarity distribution."""
        rarities = [b["rarity"] for b in BADGE_DEFINITIONS]
        assert "common" in rarities
        assert "rare" in rarities
        assert "epic" in rarities
        assert "legendary" in rarities
    
    def test_badge_xp_rewards(self):
        """Test badge XP rewards are positive."""
        for badge in BADGE_DEFINITIONS:
            assert badge["xp_reward"] > 0


class TestLeaderboard:
    """Tests for Leaderboard class."""
    
    def test_get_leaderboard_pnl(self, db_session, funded_trader, performance_metrics):
        """Test P&L leaderboard."""
        lb = Leaderboard(db_session)
        
        results = lb.get_leaderboard(category="pnl", limit=10)
        
        assert isinstance(results, list)
    
    def test_get_leaderboard_win_rate(self, db_session, funded_trader, performance_metrics):
        """Test win rate leaderboard."""
        lb = Leaderboard(db_session)
        
        results = lb.get_leaderboard(category="win_rate", limit=10)
        
        assert isinstance(results, list)
    
    def test_get_trader_profile(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test trader profile retrieval."""
        lb = Leaderboard(db_session)
        
        profile = lb.get_trader_profile(funded_trader.id)
        
        assert profile["trader"]["id"] == funded_trader.id
        assert "rank" in profile
        assert "badges" in profile
        assert "metrics" in profile
    
    def test_get_rank_tier(self, db_session):
        """Test rank tier calculation."""
        lb = Leaderboard(db_session)
        
        assert lb._get_rank_tier(0) == RankTier.ROOKIE
        assert lb._get_rank_tier(500) == RankTier.APPRENTICE
        assert lb._get_rank_tier(1500) == RankTier.TRADER
        assert lb._get_rank_tier(50000) == RankTier.LEGEND


class TestBadgeAwarding:
    """Tests for badge awarding system."""
    
    def test_check_badge_criteria_simple(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test simple badge criteria checking."""
        lb = Leaderboard(db_session)
        
        # Should have "First Trade" criteria met
        performance_metrics.total_trades = 1
        db_session.commit()
        
        criteria = {"total_trades": {"gte": 1}}
        result = lb._check_badge_criteria(criteria, performance_metrics, funded_account, funded_trader)
        
        assert result == True
    
    def test_check_badge_criteria_not_met(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test badge criteria not met."""
        lb = Leaderboard(db_session)
        
        performance_metrics.total_trades = 50
        db_session.commit()
        
        # Century Club requires 100 trades
        criteria = {"total_trades": {"gte": 100}}
        result = lb._check_badge_criteria(criteria, performance_metrics, funded_account, funded_trader)
        
        assert result == False
    
    def test_award_badges(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test badge awarding."""
        lb = Leaderboard(db_session)
        
        # Set up to earn "First Trade" badge
        funded_trader.badges = []
        performance_metrics.total_trades = 1
        db_session.commit()
        
        newly_awarded = lb.check_and_award_badges(funded_trader.id)
        
        # Should have awarded at least "First Trade"
        badge_names = [b["name"] for b in newly_awarded]
        assert "First Trade" in badge_names
    
    def test_no_duplicate_badges(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test badges aren't awarded twice."""
        lb = Leaderboard(db_session)
        
        # Already has the badge
        funded_trader.badges = ["First Trade"]
        performance_metrics.total_trades = 1
        db_session.commit()
        
        newly_awarded = lb.check_and_award_badges(funded_trader.id)
        
        # Should not re-award
        badge_names = [b["name"] for b in newly_awarded]
        assert "First Trade" not in badge_names
    
    def test_xp_awarded_with_badge(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test XP is awarded when badges are earned."""
        lb = Leaderboard(db_session)
        
        initial_xp = funded_trader.xp_points or 0
        funded_trader.badges = []
        performance_metrics.total_trades = 1
        db_session.commit()
        
        lb.check_and_award_badges(funded_trader.id)
        
        db_session.refresh(funded_trader)
        assert funded_trader.xp_points > initial_xp


class TestAchievementsProgress:
    """Tests for achievements progress tracking."""
    
    def test_get_achievements_progress(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test getting progress towards all achievements."""
        lb = Leaderboard(db_session)
        
        progress = lb.get_achievements_progress(funded_trader.id)
        
        assert len(progress) == len(BADGE_DEFINITIONS)
        for item in progress:
            assert "badge" in item
            assert "earned" in item
            assert "progress" in item
    
    def test_progress_percentage_calculation(self, db_session, funded_trader, performance_metrics, funded_account):
        """Test progress percentage is calculated correctly."""
        lb = Leaderboard(db_session)
        
        # 50 trades towards 100 = 50%
        performance_metrics.total_trades = 50
        db_session.commit()
        
        progress = lb.get_achievements_progress(funded_trader.id)
        
        century_club = next(
            p for p in progress if p["badge"]["name"] == "Century Club"
        )
        assert century_club["progress"]["total_trades"]["percentage"] == 50.0
