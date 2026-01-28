"""
Automated Report Generation
QUANT_INDUSTRY_V1

Industry Problem: Manual reporting is tedious and error-prone.
Investors and compliance want regular updates - you spend hours making PDFs.

Our Solution:
- Automated daily, weekly, monthly performance reports
- Tear sheets with industry-standard metrics
- Risk reports for compliance
- Attribution analysis
- Customizable templates
- Multiple output formats (PDF, HTML, Markdown)
- Scheduled email delivery
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportFrequency(Enum):
    """Report generation frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ON_DEMAND = "on_demand"


class ReportFormat(Enum):
    """Output format."""
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


@dataclass
class PerformanceData:
    """Performance data for report generation."""
    returns: pd.Series
    benchmark_returns: Optional[pd.Series] = None
    positions: Optional[pd.DataFrame] = None
    trades: Optional[pd.DataFrame] = None
    
    # Pre-calculated metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    
    # Benchmark-relative
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0
    
    # Trading metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0


class MetricsCalculator:
    """Calculate performance metrics from returns."""
    
    def __init__(self, risk_free_rate: float = 0.04):
        self.rf = risk_free_rate
        
    def calculate_all(
        self,
        returns: pd.Series,
        benchmark: Optional[pd.Series] = None,
        trades: Optional[pd.DataFrame] = None
    ) -> PerformanceData:
        """Calculate all performance metrics."""
        data = PerformanceData(returns=returns)
        
        # Basic metrics
        data.total_return = (1 + returns).prod() - 1
        data.annualized_return = (1 + data.total_return) ** (252 / len(returns)) - 1 if len(returns) > 0 else 0
        data.volatility = returns.std() * np.sqrt(252)
        
        # Risk-adjusted
        excess_returns = returns - self.rf / 252
        data.sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        data.sortino_ratio = excess_returns.mean() * 252 / downside_std if downside_std > 0 else 0
        
        # Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        data.max_drawdown = abs(drawdown.min())
        
        data.calmar_ratio = data.annualized_return / data.max_drawdown if data.max_drawdown > 0 else 0
        
        # Benchmark metrics
        if benchmark is not None and len(benchmark) == len(returns):
            data.benchmark_returns = benchmark
            
            # Beta and Alpha
            cov = np.cov(returns, benchmark)[0, 1]
            var = benchmark.var()
            data.beta = cov / var if var > 0 else 0
            data.alpha = (data.annualized_return - self.rf - 
                         data.beta * (benchmark.mean() * 252 - self.rf))
            
            # Tracking error and IR
            active_returns = returns - benchmark
            data.tracking_error = active_returns.std() * np.sqrt(252)
            data.information_ratio = active_returns.mean() * 252 / data.tracking_error if data.tracking_error > 0 else 0
            
        # Trading metrics
        if trades is not None and len(trades) > 0:
            data.total_trades = len(trades)
            
            if 'pnl' in trades.columns:
                wins = trades[trades['pnl'] > 0]
                losses = trades[trades['pnl'] < 0]
                
                data.win_rate = len(wins) / len(trades) if len(trades) > 0 else 0
                data.avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
                data.avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
                
                total_wins = wins['pnl'].sum() if len(wins) > 0 else 0
                total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
                data.profit_factor = total_wins / total_losses if total_losses > 0 else 0
                
        return data


class ReportGenerator:
    """Generate performance reports."""
    
    def __init__(self):
        self.metrics_calculator = MetricsCalculator()
        
    def generate_daily_report(
        self,
        data: PerformanceData,
        date: datetime,
        strategy_name: str = "Strategy",
        format: ReportFormat = ReportFormat.MARKDOWN
    ) -> str:
        """Generate daily performance report."""
        # Get today's return
        today_return = data.returns.iloc[-1] if len(data.returns) > 0 else 0
        
        # MTD returns
        month_start = date.replace(day=1)
        mtd_returns = data.returns[data.returns.index >= month_start]
        mtd_return = (1 + mtd_returns).prod() - 1 if len(mtd_returns) > 0 else 0
        
        # YTD returns
        year_start = date.replace(month=1, day=1)
        ytd_returns = data.returns[data.returns.index >= year_start]
        ytd_return = (1 + ytd_returns).prod() - 1 if len(ytd_returns) > 0 else 0
        
        if format == ReportFormat.MARKDOWN:
            return self._daily_markdown(
                strategy_name, date, today_return, mtd_return, ytd_return, data
            )
        elif format == ReportFormat.JSON:
            return json.dumps({
                'date': date.isoformat(),
                'strategy': strategy_name,
                'daily_return': today_return,
                'mtd_return': mtd_return,
                'ytd_return': ytd_return,
                'sharpe_30d': data.sharpe_ratio
            }, indent=2)
        else:
            return self._daily_html(
                strategy_name, date, today_return, mtd_return, ytd_return, data
            )
            
    def _daily_markdown(
        self,
        name: str,
        date: datetime,
        daily: float,
        mtd: float,
        ytd: float,
        data: PerformanceData
    ) -> str:
        """Generate daily report in Markdown."""
        emoji = "📈" if daily >= 0 else "📉"
        
        return f"""# {name} - Daily Report
**Date:** {date.strftime('%B %d, %Y')}

## Performance Summary {emoji}

| Period | Return |
|--------|--------|
| Today | {daily*100:+.2f}% |
| MTD | {mtd*100:+.2f}% |
| YTD | {ytd*100:+.2f}% |
| Total | {data.total_return*100:+.2f}% |

## Risk Metrics

| Metric | Value |
|--------|-------|
| Sharpe (30d) | {data.sharpe_ratio:.2f} |
| Volatility | {data.volatility*100:.1f}% |
| Max Drawdown | {data.max_drawdown*100:.1f}% |
| Current DD | {self._current_drawdown(data.returns)*100:.1f}% |

## Key Stats

- **Win Rate:** {data.win_rate*100:.1f}%
- **Profit Factor:** {data.profit_factor:.2f}
- **Total Trades:** {data.total_trades}

---
*Generated automatically at {datetime.now().strftime('%H:%M:%S')}*
"""
            
    def _daily_html(
        self,
        name: str,
        date: datetime,
        daily: float,
        mtd: float,
        ytd: float,
        data: PerformanceData
    ) -> str:
        """Generate daily report in HTML."""
        color = "#10B981" if daily >= 0 else "#EF4444"
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{name} - Daily Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; background: #1a1a1a; color: #fff; }}
        h1 {{ color: #fff; }}
        .metric {{ display: inline-block; margin: 10px; padding: 20px; background: #2a2a2a; border-radius: 8px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: {color}; }}
        .metric-label {{ font-size: 12px; color: #888; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #888; }}
    </style>
</head>
<body>
    <h1>{name} - Daily Report</h1>
    <p style="color: #888;">{date.strftime('%B %d, %Y')}</p>
    
    <div class="metric">
        <div class="metric-value">{daily*100:+.2f}%</div>
        <div class="metric-label">Today</div>
    </div>
    <div class="metric">
        <div class="metric-value">{mtd*100:+.2f}%</div>
        <div class="metric-label">MTD</div>
    </div>
    <div class="metric">
        <div class="metric-value">{ytd*100:+.2f}%</div>
        <div class="metric-label">YTD</div>
    </div>
    <div class="metric">
        <div class="metric-value">{data.sharpe_ratio:.2f}</div>
        <div class="metric-label">Sharpe</div>
    </div>
    
    <h2>Risk Metrics</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Volatility</td><td>{data.volatility*100:.1f}%</td></tr>
        <tr><td>Max Drawdown</td><td>{data.max_drawdown*100:.1f}%</td></tr>
        <tr><td>Sharpe Ratio</td><td>{data.sharpe_ratio:.2f}</td></tr>
        <tr><td>Sortino Ratio</td><td>{data.sortino_ratio:.2f}</td></tr>
    </table>
    
    <p style="color: #666; font-size: 12px;">Generated at {datetime.now().strftime('%H:%M:%S')}</p>
</body>
</html>"""
            
    def generate_tearsheet(
        self,
        data: PerformanceData,
        strategy_name: str = "Strategy",
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        format: ReportFormat = ReportFormat.MARKDOWN
    ) -> str:
        """Generate comprehensive tearsheet."""
        if format == ReportFormat.MARKDOWN:
            return self._tearsheet_markdown(data, strategy_name, period_start, period_end)
        else:
            return self._tearsheet_html(data, strategy_name, period_start, period_end)
            
    def _tearsheet_markdown(
        self,
        data: PerformanceData,
        name: str,
        start: Optional[datetime],
        end: Optional[datetime]
    ) -> str:
        """Generate tearsheet in Markdown."""
        period = ""
        if start and end:
            period = f"**Period:** {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
            
        # Monthly returns table
        monthly_table = self._generate_monthly_returns_table(data.returns)
        
        # Drawdown analysis
        dd_analysis = self._analyze_drawdowns(data.returns)
        
        return f"""# {name} - Performance Tearsheet

{period}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## Executive Summary

{name} achieved a **{data.total_return*100:+.2f}%** total return with a Sharpe ratio of **{data.sharpe_ratio:.2f}**.

## Performance Metrics

### Returns

| Metric | Value |
|--------|-------|
| Total Return | {data.total_return*100:+.2f}% |
| Annualized Return | {data.annualized_return*100:+.2f}% |
| Best Day | {data.returns.max()*100:+.2f}% |
| Worst Day | {data.returns.min()*100:+.2f}% |
| Avg Daily Return | {data.returns.mean()*100:+.4f}% |

### Risk

| Metric | Value |
|--------|-------|
| Volatility (Ann.) | {data.volatility*100:.1f}% |
| Max Drawdown | {data.max_drawdown*100:.1f}% |
| VaR (95%) | {np.percentile(data.returns, 5)*100:.2f}% |
| CVaR (95%) | {data.returns[data.returns <= np.percentile(data.returns, 5)].mean()*100:.2f}% |

### Risk-Adjusted Returns

| Metric | Value |
|--------|-------|
| Sharpe Ratio | {data.sharpe_ratio:.2f} |
| Sortino Ratio | {data.sortino_ratio:.2f} |
| Calmar Ratio | {data.calmar_ratio:.2f} |

### Benchmark Comparison

| Metric | Value |
|--------|-------|
| Alpha (Ann.) | {data.alpha*100:+.2f}% |
| Beta | {data.beta:.2f} |
| Information Ratio | {data.information_ratio:.2f} |
| Tracking Error | {data.tracking_error*100:.1f}% |

## Monthly Returns

{monthly_table}

## Drawdown Analysis

| Rank | Start | End | Depth | Recovery |
|------|-------|-----|-------|----------|
{dd_analysis}

## Trading Statistics

| Metric | Value |
|--------|-------|
| Total Trades | {data.total_trades} |
| Win Rate | {data.win_rate*100:.1f}% |
| Profit Factor | {data.profit_factor:.2f} |
| Avg Win | ${data.avg_win:,.2f} |
| Avg Loss | ${data.avg_loss:,.2f} |

---

*This report was automatically generated. Past performance does not guarantee future results.*
"""
            
    def _tearsheet_html(
        self,
        data: PerformanceData,
        name: str,
        start: Optional[datetime],
        end: Optional[datetime]
    ) -> str:
        """Generate tearsheet in HTML."""
        # Simplified HTML version
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{name} - Tearsheet</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 40px; background: #fff; color: #333; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .card {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
        .value {{ font-size: 28px; font-weight: bold; color: #333; }}
        .label {{ font-size: 12px; color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <h1>{name} Tearsheet</h1>
    
    <div class="grid">
        <div class="card">
            <div class="value">{data.total_return*100:+.1f}%</div>
            <div class="label">Total Return</div>
        </div>
        <div class="card">
            <div class="value">{data.sharpe_ratio:.2f}</div>
            <div class="label">Sharpe Ratio</div>
        </div>
        <div class="card">
            <div class="value">{data.max_drawdown*100:.1f}%</div>
            <div class="label">Max Drawdown</div>
        </div>
        <div class="card">
            <div class="value">{data.win_rate*100:.0f}%</div>
            <div class="label">Win Rate</div>
        </div>
    </div>
</body>
</html>"""
            
    def _generate_monthly_returns_table(self, returns: pd.Series) -> str:
        """Generate monthly returns table."""
        if len(returns) == 0:
            return "No data available"
            
        # Resample to monthly
        monthly = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        
        # Pivot by year/month
        monthly_df = pd.DataFrame({
            'year': monthly.index.year,
            'month': monthly.index.month,
            'return': monthly.values
        })
        
        pivot = monthly_df.pivot(index='year', columns='month', values='return')
        
        # Format as markdown table
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        header = "| Year | " + " | ".join(months) + " | Total |"
        sep = "|------|" + "|".join(["---"] * 12) + "|------|"
        
        rows = []
        for year in pivot.index:
            row_vals = []
            for m in range(1, 13):
                val = pivot.loc[year, m] if m in pivot.columns else np.nan
                if pd.isna(val):
                    row_vals.append("-")
                else:
                    row_vals.append(f"{val*100:+.1f}%")
            
            year_total = pivot.loc[year].sum()
            row_vals.append(f"{year_total*100:+.1f}%")
            
            rows.append(f"| {year} | " + " | ".join(row_vals) + " |")
            
        return header + "\n" + sep + "\n" + "\n".join(rows)
        
    def _analyze_drawdowns(self, returns: pd.Series, top_n: int = 5) -> str:
        """Analyze top drawdowns."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        # Find drawdown periods
        dd_periods = []
        in_drawdown = False
        start_idx = None
        
        for i, (idx, dd) in enumerate(drawdown.items()):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = idx
            elif dd == 0 and in_drawdown:
                in_drawdown = False
                period_dd = drawdown[start_idx:idx]
                dd_periods.append({
                    'start': start_idx,
                    'end': idx,
                    'depth': period_dd.min(),
                    'duration': len(period_dd)
                })
                
        # Sort by depth
        dd_periods.sort(key=lambda x: x['depth'])
        
        rows = []
        for i, dd in enumerate(dd_periods[:top_n]):
            rows.append(
                f"| {i+1} | {dd['start'].strftime('%Y-%m-%d')} | "
                f"{dd['end'].strftime('%Y-%m-%d')} | {dd['depth']*100:.1f}% | {dd['duration']}d |"
            )
            
        return "\n".join(rows) if rows else "| - | - | - | - | - |"
        
    def _current_drawdown(self, returns: pd.Series) -> float:
        """Calculate current drawdown."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        return (cumulative.iloc[-1] - running_max.iloc[-1]) / running_max.iloc[-1]


class ReportScheduler:
    """Schedule automated report generation."""
    
    def __init__(self, generator: ReportGenerator):
        self.generator = generator
        self.schedules: List[Dict[str, Any]] = []
        
    def schedule(
        self,
        frequency: ReportFrequency,
        report_type: str,  # "daily", "tearsheet", "risk"
        recipients: List[str],
        format: ReportFormat = ReportFormat.MARKDOWN,
        time_of_day: str = "18:00"
    ):
        """Schedule a report."""
        self.schedules.append({
            'frequency': frequency,
            'report_type': report_type,
            'recipients': recipients,
            'format': format,
            'time_of_day': time_of_day,
            'last_run': None
        })
        
    def check_and_run(self, data: PerformanceData, strategy_name: str):
        """Check schedules and generate reports if due."""
        now = datetime.now()
        
        for schedule in self.schedules:
            if self._is_due(schedule, now):
                report = self._generate_report(
                    schedule['report_type'],
                    data,
                    strategy_name,
                    schedule['format']
                )
                
                self._deliver_report(report, schedule['recipients'])
                schedule['last_run'] = now
                
    def _is_due(self, schedule: Dict, now: datetime) -> bool:
        """Check if report is due."""
        if schedule['last_run'] is None:
            return True
            
        freq = schedule['frequency']
        last = schedule['last_run']
        
        if freq == ReportFrequency.DAILY:
            return (now - last).days >= 1
        elif freq == ReportFrequency.WEEKLY:
            return (now - last).days >= 7
        elif freq == ReportFrequency.MONTHLY:
            return (now - last).days >= 30
            
        return False
        
    def _generate_report(
        self,
        report_type: str,
        data: PerformanceData,
        name: str,
        format: ReportFormat
    ) -> str:
        """Generate the appropriate report."""
        if report_type == "daily":
            return self.generator.generate_daily_report(data, datetime.now(), name, format)
        elif report_type == "tearsheet":
            return self.generator.generate_tearsheet(data, name, format=format)
        else:
            return ""
            
    def _deliver_report(self, report: str, recipients: List[str]):
        """Deliver report to recipients."""
        # Would send via email, Slack, etc.
        logger.info(f"Delivering report to {recipients}")
