"""
AI Trading Coach
Personalized coaching and performance improvement using ML/LLM.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class CoachingInsightType:
    """Types of coaching insights."""
    RISK_WARNING = "risk_warning"
    PATTERN_DETECTED = "pattern_detected"
    IMPROVEMENT_TIP = "improvement_tip"
    CONGRATULATION = "congratulation"
    STRATEGY_SUGGESTION = "strategy_suggestion"
    BEHAVIOR_ANALYSIS = "behavior_analysis"


class AICoach:
    """
    AI-powered trading coach providing personalized insights and recommendations.
    
    Features:
    - Pattern detection in trading behavior
    - Personalized improvement suggestions
    - Risk behavior analysis
    - Emotional trading detection
    - Strategy optimization tips
    - Performance milestone celebrations
    
    Differentiator: No other prop firm has AI coaching built-in!
    """
    
    def __init__(self, db_session, llm_client=None):
        self.db = db_session
        self.llm = llm_client  # Optional LLM for advanced insights
        
        # Trading pattern rules (rule-based analysis)
        self.patterns = self._load_pattern_rules()
    
    def _load_pattern_rules(self) -> List[Dict]:
        """Load pattern detection rules."""
        return [
            {
                "id": "revenge_trading",
                "name": "Revenge Trading Detected",
                "type": CoachingInsightType.RISK_WARNING,
                "condition": lambda stats: (
                    stats.get("consecutive_losses", 0) >= 3 and
                    stats.get("position_size_increase_after_loss", False)
                ),
                "message": "[WARN]️ Warning: You may be revenge trading. After {consecutive_losses} consecutive losses, your position sizes have increased. This is a dangerous pattern. Consider taking a break.",
                "recommendation": "Take at least a 30-minute break after 3 consecutive losses. Reset your mental state before the next trade."
            },
            {
                "id": "overtrading",
                "name": "Overtrading Pattern",
                "type": CoachingInsightType.PATTERN_DETECTED,
                "condition": lambda stats: stats.get("trades_today", 0) > stats.get("avg_daily_trades", 5) * 2,
                "message": "[CHART] You've made {trades_today} trades today, which is {multiplier}x your average. Quality over quantity!",
                "recommendation": "Set a maximum daily trade limit. More trades don't equal more profits - focus on high-quality setups."
            },
            {
                "id": "early_exit",
                "name": "Premature Exit Pattern",
                "type": CoachingInsightType.BEHAVIOR_ANALYSIS,
                "condition": lambda stats: (
                    stats.get("avg_winner_hold_time", 0) < stats.get("avg_loser_hold_time", 0) * 0.5
                ),
                "message": "🏃 You're cutting winners short! Your average winning trade is held {winner_time}min vs {loser_time}min for losers.",
                "recommendation": "Let your winners run. Consider using trailing stops instead of fixed take-profits."
            },
            {
                "id": "no_stop_loss",
                "name": "Missing Stop Loss",
                "type": CoachingInsightType.RISK_WARNING,
                "condition": lambda stats: stats.get("trades_without_stop", 0) > 0,
                "message": "🚨 {trades_without_stop} of your recent trades had no stop loss. This is extremely risky!",
                "recommendation": "Always use stop losses. Define your risk before entering any trade."
            },
            {
                "id": "time_of_day",
                "name": "Time Performance Pattern",
                "type": CoachingInsightType.PATTERN_DETECTED,
                "condition": lambda stats: stats.get("best_hour_pnl", 0) > stats.get("worst_hour_pnl", 0) * 3,
                "message": "[ALARM] Your performance varies significantly by time. Best: {best_hour} ({best_pnl}). Worst: {worst_hour} ({worst_pnl}).",
                "recommendation": "Consider focusing on your peak performance hours and avoiding your worst periods."
            },
            {
                "id": "win_streak",
                "name": "Winning Streak",
                "type": CoachingInsightType.CONGRATULATION,
                "condition": lambda stats: stats.get("current_win_streak", 0) >= 5,
                "message": "🔥 Amazing! You're on a {current_win_streak} trade winning streak! Keep it up!",
                "recommendation": "Stay disciplined - don't let success lead to overconfidence. Stick to your strategy."
            },
            {
                "id": "improving_win_rate",
                "name": "Win Rate Improving",
                "type": CoachingInsightType.CONGRATULATION,
                "condition": lambda stats: (
                    stats.get("recent_win_rate", 0) > stats.get("overall_win_rate", 0) + 10
                ),
                "message": "[UP] Your recent win rate ({recent_win_rate}%) is significantly better than your overall ({overall_win_rate}%)!",
                "recommendation": "Great progress! Document what you're doing differently - it's clearly working."
            },
            {
                "id": "risk_reward_improving",
                "name": "R:R Ratio Improving",
                "type": CoachingInsightType.IMPROVEMENT_TIP,
                "condition": lambda stats: stats.get("recent_rr", 0) > stats.get("overall_rr", 0) * 1.2,
                "message": "💪 Your recent risk-reward ratio ({recent_rr}) is better than your average ({overall_rr}).",
                "recommendation": "You're improving at picking better setups. Keep refining your entry criteria."
            },
            {
                "id": "friday_curse",
                "name": "Friday Performance Issue",
                "type": CoachingInsightType.PATTERN_DETECTED,
                "condition": lambda stats: (
                    stats.get("friday_pnl", 0) < 0 and
                    abs(stats.get("friday_pnl", 0)) > stats.get("avg_daily_pnl", 0) * 2
                ),
                "message": "📅 Your Friday trading tends to be problematic (avg P&L: ${friday_pnl}). Weekend pressure?",
                "recommendation": "Consider reducing position sizes or skipping Fridays. Weekend risk management may be affecting your decisions."
            },
            {
                "id": "concentration_risk",
                "name": "Symbol Concentration",
                "type": CoachingInsightType.RISK_WARNING,
                "condition": lambda stats: stats.get("top_symbol_pct", 0) > 80,
                "message": "[WARN]️ {top_symbol_pct}% of your trades are in {top_symbol}. Diversification could reduce risk.",
                "recommendation": "Consider expanding to other correlated instruments. Over-concentration increases event risk."
            },
        ]
    
    def analyze_trading_behavior(self, trader_id: int) -> List[Dict[str, Any]]:
        """
        Analyze a trader's behavior and generate insights.
        
        Returns:
            List of coaching insights
        """
        from .models import Trader, PropTrade, PerformanceMetrics, TraderAccount
        
        # Gather trading statistics
        stats = self._gather_trading_stats(trader_id)
        
        insights = []
        
        # Check each pattern
        for pattern in self.patterns:
            try:
                if pattern["condition"](stats):
                    insight = {
                        "id": pattern["id"],
                        "type": pattern["type"],
                        "title": pattern["name"],
                        "message": self._format_message(pattern["message"], stats),
                        "recommendation": pattern["recommendation"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "priority": self._get_priority(pattern["type"]),
                    }
                    insights.append(insight)
            except Exception as e:
                logger.warning(f"Error checking pattern {pattern['id']}: {e}")
        
        # Sort by priority
        insights.sort(key=lambda x: x["priority"], reverse=True)
        
        return insights
    
    def _gather_trading_stats(self, trader_id: int) -> Dict[str, Any]:
        """Gather comprehensive trading statistics for analysis."""
        from .models import PropTrade, PerformanceMetrics
        
        metrics = self.db.query(PerformanceMetrics).filter_by(trader_id=trader_id).first()
        
        # Get recent trades
        recent_trades = (
            self.db.query(PropTrade)
            .filter_by(trader_id=trader_id)
            .filter(PropTrade.entry_time >= datetime.utcnow() - timedelta(days=30))
            .order_by(PropTrade.entry_time.desc())
            .limit(100)
            .all()
        )
        
        if not recent_trades:
            return {}
        
        # Calculate statistics
        stats = {
            "total_trades": len(recent_trades),
            "trades_today": sum(1 for t in recent_trades if t.entry_time.date() == datetime.utcnow().date()),
            "avg_daily_trades": len(recent_trades) / 30,
        }
        
        # Win/loss analysis
        wins = [t for t in recent_trades if t.realized_pnl and t.realized_pnl > 0]
        losses = [t for t in recent_trades if t.realized_pnl and t.realized_pnl < 0]
        
        stats["recent_win_rate"] = (len(wins) / len(recent_trades) * 100) if recent_trades else 0
        stats["overall_win_rate"] = metrics.win_rate if metrics else 0
        
        # Consecutive losses detection
        consecutive_losses = 0
        for trade in recent_trades:
            if trade.realized_pnl and trade.realized_pnl < 0:
                consecutive_losses += 1
            else:
                break
        stats["consecutive_losses"] = consecutive_losses
        
        # Position size analysis after losses
        if consecutive_losses >= 3 and len(recent_trades) > consecutive_losses:
            last_loss_size = recent_trades[consecutive_losses - 1].quantity
            next_trade_size = recent_trades[consecutive_losses].quantity if len(recent_trades) > consecutive_losses else 0
            stats["position_size_increase_after_loss"] = next_trade_size > last_loss_size * 1.5
        
        # Hold time analysis
        winning_trades = [t for t in recent_trades if t.realized_pnl and t.realized_pnl > 0 and t.exit_time]
        losing_trades = [t for t in recent_trades if t.realized_pnl and t.realized_pnl < 0 and t.exit_time]
        
        if winning_trades:
            avg_winner_time = sum((t.exit_time - t.entry_time).total_seconds() / 60 for t in winning_trades) / len(winning_trades)
            stats["avg_winner_hold_time"] = avg_winner_time
            stats["winner_time"] = f"{avg_winner_time:.0f}"
        
        if losing_trades:
            avg_loser_time = sum((t.exit_time - t.entry_time).total_seconds() / 60 for t in losing_trades) / len(losing_trades)
            stats["avg_loser_hold_time"] = avg_loser_time
            stats["loser_time"] = f"{avg_loser_time:.0f}"
        
        # Stop loss usage
        trades_without_stop = sum(1 for t in recent_trades if not t.stop_loss)
        stats["trades_without_stop"] = trades_without_stop
        
        # Current win streak
        current_streak = 0
        for trade in recent_trades:
            if trade.realized_pnl and trade.realized_pnl > 0:
                current_streak += 1
            else:
                break
        stats["current_win_streak"] = current_streak
        
        # Risk-reward analysis
        if wins and losses:
            avg_win = sum(float(t.realized_pnl) for t in wins) / len(wins)
            avg_loss = abs(sum(float(t.realized_pnl) for t in losses) / len(losses))
            stats["recent_rr"] = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0
            stats["overall_rr"] = round(
                (metrics.avg_win / abs(metrics.avg_loss)) if metrics and metrics.avg_win and metrics.avg_loss else 0, 2
            )
        
        # Symbol concentration
        symbols = {}
        for t in recent_trades:
            symbols[t.symbol] = symbols.get(t.symbol, 0) + 1
        if symbols:
            top_symbol = max(symbols, key=symbols.get)
            stats["top_symbol"] = top_symbol
            stats["top_symbol_pct"] = round(symbols[top_symbol] / len(recent_trades) * 100, 1)
        
        # Add metrics data
        if metrics:
            stats["max_win_streak"] = metrics.max_win_streak
            stats["max_loss_streak"] = metrics.max_loss_streak
            stats["sharpe_ratio"] = metrics.sharpe_ratio
            stats["profit_factor"] = metrics.profit_factor
        
        return stats
    
    def _format_message(self, template: str, stats: Dict) -> str:
        """Format message template with stats."""
        try:
            return template.format(**stats)
        except KeyError:
            return template
    
    def _get_priority(self, insight_type: str) -> int:
        """Get priority score for insight type."""
        priorities = {
            CoachingInsightType.RISK_WARNING: 100,
            CoachingInsightType.PATTERN_DETECTED: 70,
            CoachingInsightType.BEHAVIOR_ANALYSIS: 60,
            CoachingInsightType.IMPROVEMENT_TIP: 50,
            CoachingInsightType.STRATEGY_SUGGESTION: 40,
            CoachingInsightType.CONGRATULATION: 30,
        }
        return priorities.get(insight_type, 50)
    
    async def get_ai_coaching_response(
        self,
        trader_id: int,
        question: str
    ) -> Dict[str, Any]:
        """
        Get AI-generated coaching response using LLM.
        
        For personalized advice beyond rule-based patterns.
        """
        if not self.llm:
            return {
                "response": "AI coaching is not configured. Please contact support.",
                "source": "error"
            }
        
        # Gather context
        stats = self._gather_trading_stats(trader_id)
        insights = self.analyze_trading_behavior(trader_id)
        
        # Build context for LLM
        context = f"""
You are an expert trading coach for a prop trading firm. A trader is asking for advice.

Trader Statistics (Last 30 Days):
- Total Trades: {stats.get('total_trades', 'N/A')}
- Win Rate: {stats.get('recent_win_rate', 'N/A')}%
- Risk/Reward Ratio: {stats.get('recent_rr', 'N/A')}
- Current Win Streak: {stats.get('current_win_streak', 0)}
- Sharpe Ratio: {stats.get('sharpe_ratio', 'N/A')}

Recent Patterns Detected:
{json.dumps([i['title'] for i in insights], indent=2)}

Trader's Question: {question}

Provide specific, actionable advice based on their actual data. Be encouraging but honest.
"""
        
        try:
            response = await self.llm.generate(
                prompt=context,
                max_tokens=500,
                temperature=0.7
            )
            
            return {
                "response": response,
                "source": "ai",
                "context_used": {
                    "stats": stats,
                    "patterns_detected": len(insights),
                }
            }
        except Exception as e:
            logger.error(f"LLM coaching error: {e}")
            return {
                "response": "Unable to generate AI response. Please try again later.",
                "source": "error"
            }
    
    def get_daily_briefing(self, trader_id: int) -> Dict[str, Any]:
        """
        Generate a daily coaching briefing for the trader.
        Sent via notification each morning.
        """
        stats = self._gather_trading_stats(trader_id)
        insights = self.analyze_trading_behavior(trader_id)
        
        # Get yesterday's performance
        from .models import Evaluation
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        yesterday_eval = (
            self.db.query(Evaluation)
            .filter(Evaluation.trader_id == trader_id)
            .filter(Evaluation.evaluation_date >= yesterday)
            .first()
        )
        
        briefing = {
            "date": datetime.utcnow().date().isoformat(),
            "greeting": self._get_greeting(stats),
            "yesterday_summary": None,
            "key_insights": insights[:3],  # Top 3 insights
            "focus_for_today": self._get_daily_focus(stats, insights),
            "motivation": self._get_motivation_quote(),
        }
        
        if yesterday_eval:
            briefing["yesterday_summary"] = {
                "pnl": float(yesterday_eval.daily_pnl),
                "trades": yesterday_eval.trades_count,
                "win_rate": yesterday_eval.win_rate,
            }
        
        return briefing
    
    def _get_greeting(self, stats: Dict) -> str:
        """Generate personalized greeting."""
        win_streak = stats.get("current_win_streak", 0)
        if win_streak >= 5:
            return "🔥 You're on fire! Keep up the amazing work!"
        elif win_streak >= 3:
            return "[UP] Great momentum! Let's keep it going today."
        elif stats.get("consecutive_losses", 0) >= 3:
            return "💪 Fresh day, fresh start. You've got this!"
        else:
            return "Good morning! Ready to execute your plan?"
    
    def _get_daily_focus(self, stats: Dict, insights: List) -> str:
        """Generate focus area for today."""
        risk_warnings = [i for i in insights if i["type"] == CoachingInsightType.RISK_WARNING]
        
        if risk_warnings:
            return f"[WARN]️ Focus on {risk_warnings[0]['title'].lower()} - it's impacting your performance."
        elif stats.get("recent_win_rate", 0) > 60:
            return "[OK] You're executing well. Stay disciplined and trust your process."
        else:
            return "[TARGET] Focus on quality setups today. Fewer but better trades."
    
    def _get_motivation_quote(self) -> str:
        """Get a random trading motivation quote."""
        quotes = [
            "The goal of a successful trader is to make the best trades. Money is secondary. - Alexander Elder",
            "In trading, the impossible happens about twice a year. - Henri M. Simoes",
            "The market is a device for transferring money from the impatient to the patient. - Warren Buffett",
            "Risk comes from not knowing what you're doing. - Warren Buffett",
            "The trend is your friend until the end when it bends. - Ed Seykota",
            "Cut your losses and let your profits run. - David Ricardo",
            "The most important rule of trading is to play great defense, not offense. - Paul Tudor Jones",
            "Confidence is not 'I will profit on this trade.' Confidence is 'I will be fine if I don't profit.' - Yvan Byeajee",
        ]
        import random
        return random.choice(quotes)
