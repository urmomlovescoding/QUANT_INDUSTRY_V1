"""
QUANT_INDUSTRY_V1 Dashboard View - PROFESSIONAL EDITION

Modern institutional-grade dashboard with sophisticated visualizations.

Features:
- Modern metric cards with sparklines
- Professional equity curve display
- Real-time data updates
- Glass morphism effects
- Responsive layout
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
import random

from ..theme import get_theme, Spacing, FontSize, FontWeight, get_pnl_color
from ..state import get_store, get_event_bus, EventType, SignalState, PositionState
from ..components.base import StyledFrame, Card, StyledLabel, StyledButton
from ..components.indicators import (
    ConfidenceBar, DirectionIndicator, RegimeBadge,
    PnLDisplay, StatusBadge, LoadingSpinner, ProgressBar,
)
from ..components.tables import DataTable, Column, ColumnAlign, format_currency, format_percent
from ..components.charts import SparkLine, MiniBarChart, GaugeChart
from ..components.quick_actions import QuickActionsBar
from ..components.empty_states import NoSignalsState, NoPositionsState

logger = logging.getLogger(__name__)


class MetricTile(tk.Frame):
    """Modern metric display tile with optional trend indicator."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "",
        value: str = "",
        change: float = None,
        change_label: str = "",
        icon: str = None,
        accent_color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', colors.border_subtle)

        super().__init__(parent, **kwargs)

        self._title = title
        self._value = value
        self._change = change
        self._accent = accent_color or colors.accent_primary

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the tile UI."""
        theme = get_theme()
        colors = theme.colors

        # Main container with padding
        container = tk.Frame(self, bg=colors.bg_tertiary)
        container.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.SM)

        # Top row: title and optional badge
        top_row = tk.Frame(container, bg=colors.bg_tertiary)
        top_row.pack(fill=tk.X)

        self._title_label = tk.Label(
            top_row,
            text=self._title,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        self._title_label.pack(side=tk.LEFT)

        # Value with large font
        self._value_label = tk.Label(
            container,
            text=self._value,
            font=theme.get_font(FontSize.XXXL, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            anchor="w",
        )
        self._value_label.pack(fill=tk.X, pady=(Spacing.XS, 0))

        # Change indicator row
        if self._change is not None:
            change_frame = tk.Frame(container, bg=colors.bg_tertiary)
            change_frame.pack(fill=tk.X)

            change_color = colors.bullish if self._change >= 0 else colors.bearish
            arrow = "▲" if self._change >= 0 else "▼"

            self._change_label = tk.Label(
                change_frame,
                text=f"{arrow} {abs(self._change):.2f}%",
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
                fg=change_color,
                bg=colors.bg_tertiary,
            )
            self._change_label.pack(side=tk.LEFT)

        # Accent bar at bottom
        accent_bar = tk.Frame(self, bg=self._accent, height=3)
        accent_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def set_value(self, value: str, change: float = None) -> None:
        """Update the tile value."""
        theme = get_theme()
        colors = theme.colors

        self._value_label.config(text=value)

        if change is not None and hasattr(self, '_change_label'):
            self._change = change
            change_color = colors.bullish if change >= 0 else colors.bearish
            arrow = "▲" if change >= 0 else "▼"
            self._change_label.config(
                text=f"{arrow} {abs(change):.2f}%",
                fg=change_color,
            )


class QuickStatBar(tk.Frame):
    """Horizontal quick stats bar."""

    def __init__(self, parent: tk.Widget, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, **kwargs)

        self._stats = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the stats bar."""
        theme = get_theme()
        colors = theme.colors

        stats_config = [
            ("win_rate", "Win Rate", "62%", colors.bullish),
            ("profit_factor", "Profit Factor", "2.1x", colors.accent_primary),
            ("sharpe", "Sharpe", "1.85", colors.fg_primary),
            ("sortino", "Sortino", "2.42", colors.fg_primary),
            ("max_dd", "Max DD", "-8.3%", colors.bearish),
            ("trades", "Trades", "47", colors.fg_secondary),
        ]

        for stat_id, label, value, color in stats_config:
            stat_frame = tk.Frame(self, bg=colors.bg_secondary)
            stat_frame.pack(side=tk.LEFT, expand=True, fill=tk.Y, padx=Spacing.SM, pady=Spacing.XS)

            lbl = tk.Label(
                stat_frame,
                text=label,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_muted,
                bg=colors.bg_secondary,
            )
            lbl.pack()

            val_lbl = tk.Label(
                stat_frame,
                text=value,
                font=theme.get_font(FontSize.MD, FontWeight.BOLD, "data"),
                fg=color,
                bg=colors.bg_secondary,
            )
            val_lbl.pack()

            self._stats[stat_id] = val_lbl

    def set_stat(self, stat_id: str, value: str, color: str = None) -> None:
        """Update a stat value."""
        if stat_id in self._stats:
            config = {'text': value}
            if color:
                config['fg'] = color
            self._stats[stat_id].config(**config)


class MiniEquityChart(tk.Canvas):
    """Compact equity curve for dashboard."""

    def __init__(self, parent: tk.Widget, width: int = 300, height: int = 80, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._data = []

        self.bind('<Configure>', self._on_resize)

        # Generate sample data
        self._generate_sample_data()

    def _on_resize(self, event):
        """Handle resize."""
        self._width = event.width
        self._height = event.height
        self._draw()

    def _generate_sample_data(self) -> None:
        """Generate sample equity data."""
        equity = 100000
        self._data = [equity]
        for _ in range(50):
            change = random.gauss(0.002, 0.015)
            equity = equity * (1 + change)
            self._data.append(equity)
        self._draw()

    def set_data(self, data: List[float]) -> None:
        """Set equity data."""
        self._data = data
        self._draw()

    def _draw(self) -> None:
        """Draw the equity curve."""
        self.delete("all")

        theme = get_theme()
        colors = theme.colors

        if not self._data or len(self._data) < 2:
            return

        width = self._width or 300
        height = self._height or 80

        min_val = min(self._data)
        max_val = max(self._data)
        val_range = max_val - min_val if max_val != min_val else 1

        padding = 5

        # Calculate points
        points = []
        for i, val in enumerate(self._data):
            x = padding + (i / (len(self._data) - 1)) * (width - padding * 2)
            y = padding + (height - padding * 2) - ((val - min_val) / val_range) * (height - padding * 2)
            points.append((x, y))

        # Draw gradient fill
        fill_points = [(padding, height - padding)]
        fill_points.extend(points)
        fill_points.append((width - padding, height - padding))

        flat_points = [coord for point in fill_points for coord in point]
        self.create_polygon(flat_points, fill=colors.accent_primary, outline="", stipple="gray50")

        # Draw line segments with trend colors
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]

            if self._data[i + 1] >= self._data[i]:
                color = colors.bullish
            else:
                color = colors.bearish

            self.create_line(x1, y1, x2, y2, fill=color, width=2)

        # Draw end point
        if points:
            ex, ey = points[-1]
            self.create_oval(ex - 3, ey - 3, ex + 3, ey + 3, fill=colors.accent_primary, outline=colors.fg_primary)


class DashboardView(tk.Frame):
    """
    Professional dashboard view.

    Layout:
    ┌─────────────────────────────────────────────────────────────┐
    │  Status Bar (regime, time, health, mode)                     │
    ├─────────────────────────────────────────────────────────────┤
    │  Metric Tiles Row                                            │
    │  [Equity] [Day P&L] [Total P&L] [Exposure] [Cash]            │
    ├─────────────────────────────────────────────────────────────┤
    │  Quick Stats Bar                                             │
    ├───────────────────────────┬─────────────────────────────────┤
    │  Active Signals           │  Open Positions                  │
    │  (with confidence bars)   │  (with P&L highlighting)         │
    ├───────────────────────────┼─────────────────────────────────┤
    │  Mini Equity Chart        │  Recent Alerts                   │
    └───────────────────────────┴─────────────────────────────────┘
    """

    def __init__(self, parent: tk.Widget, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_primary)

        super().__init__(parent, **kwargs)

        self._store = get_store()
        self._event_bus = get_event_bus()

        self._setup_ui()
        self._bind_events()
        self._refresh_data()

    def _setup_ui(self) -> None:
        """Setup dashboard UI."""
        theme = get_theme()
        colors = theme.colors

        # Configure grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)
        self.rowconfigure(5, weight=1)

        # Row 0: Status bar
        self._status_bar = self._create_status_bar()
        self._status_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=Spacing.MD, pady=(Spacing.SM, Spacing.XS))

        # Row 1: Quick Actions Bar
        self._actions_bar = self._create_actions_bar()
        self._actions_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=Spacing.MD, pady=Spacing.XS)

        # Row 2: Metric tiles
        self._metrics_row = self._create_metrics_row()
        self._metrics_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=Spacing.MD, pady=Spacing.XS)

        # Row 3: Quick stats bar
        self._stats_bar = QuickStatBar(self)
        self._stats_bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=Spacing.MD, pady=Spacing.XS)

        # Row 4: Signals and Positions
        self._signals_card = self._create_signals_card()
        self._signals_card.grid(row=4, column=0, sticky="nsew", padx=(Spacing.MD, Spacing.XS), pady=Spacing.XS)

        self._positions_card = self._create_positions_card()
        self._positions_card.grid(row=4, column=1, sticky="nsew", padx=(Spacing.XS, Spacing.MD), pady=Spacing.XS)

        # Row 5: Mini chart and alerts
        self._chart_card = self._create_chart_card()
        self._chart_card.grid(row=5, column=0, sticky="nsew", padx=(Spacing.MD, Spacing.XS), pady=(Spacing.XS, Spacing.MD))

        self._alerts_card = self._create_alerts_card()
        self._alerts_card.grid(row=5, column=1, sticky="nsew", padx=(Spacing.XS, Spacing.MD), pady=(Spacing.XS, Spacing.MD))

    def _create_status_bar(self) -> tk.Frame:
        """Create status bar."""
        theme = get_theme()
        colors = theme.colors

        frame = tk.Frame(self, bg=colors.bg_secondary, height=40)
        frame.pack_propagate(False)

        inner = tk.Frame(frame, bg=colors.bg_secondary)
        inner.pack(fill=tk.BOTH, expand=True, padx=Spacing.SM, pady=Spacing.XS)

        # Left section: Regime
        left = tk.Frame(inner, bg=colors.bg_secondary)
        left.pack(side=tk.LEFT, fill=tk.Y)

        self._regime_badge = RegimeBadge(left, regime="ANALYZING", confidence=0.5)
        self._regime_badge.pack(side=tk.LEFT, padx=(0, Spacing.MD))

        # Center: Time with live indicator
        center = tk.Frame(inner, bg=colors.bg_secondary)
        center.pack(side=tk.LEFT, expand=True)

        # Live indicator dot
        live_dot = tk.Label(
            center,
            text="[*]",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.bullish,
            bg=colors.bg_secondary,
        )
        live_dot.pack(side=tk.LEFT)

        self._time_label = tk.Label(
            center,
            text=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
            fg=colors.fg_secondary,
            bg=colors.bg_secondary,
        )
        self._time_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

        # Right section: Health and mode
        right = tk.Frame(inner, bg=colors.bg_secondary)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self._health_badge = StatusBadge(right, status="success", text="HEALTHY")
        self._health_badge.pack(side=tk.RIGHT, padx=(Spacing.SM, 0))

        mode = self._store.get('mode', 'paper')
        mode_colors = {'paper': 'warning', 'live': 'success', 'backtest': 'info'}
        self._mode_badge = StatusBadge(right, status=mode_colors.get(mode, 'info'), text=mode.upper())
        self._mode_badge.pack(side=tk.RIGHT, padx=(Spacing.SM, 0))

        # System status
        self._sys_label = tk.Label(
            right,
            text="SYS OK",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.success,
            bg=colors.bg_secondary,
        )
        self._sys_label.pack(side=tk.RIGHT, padx=(0, Spacing.SM))

        # Start time update
        self._update_time()

        return frame

    def _update_time(self) -> None:
        """Update time display."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self._time_label.config(text=now)
        self.after(1000, self._update_time)

    def _create_actions_bar(self) -> tk.Frame:
        """Create quick actions bar."""
        theme = get_theme()
        colors = theme.colors

        actions = [
            ("Execute Signals", "▶", "success", self._execute_all_signals, "Execute all active signals"),
            ("Close All", "[FAIL]", "danger", self._close_all_positions, "Close all open positions"),
            ("Refresh", "↻", "default", self._refresh_data, "Refresh market data"),
            ("New Trade", "+", "primary", self._new_trade, "Open trade entry form"),
        ]

        return QuickActionsBar(self, actions=actions)

    def _execute_all_signals(self) -> None:
        """Execute all active signals."""
        from ..components.toast import toast_info
        toast_info("Executing all signals...", title="Trade Execution")

    def _close_all_positions(self) -> None:
        """Close all open positions."""
        from ..components.toast import toast_warning
        toast_warning("Closing all positions...", title="Position Management")

    def _new_trade(self) -> None:
        """Open trade entry form."""
        from ..components.toast import toast_info
        toast_info("Use Ctrl+N to open trade entry", title="New Trade")

    def _create_metrics_row(self) -> tk.Frame:
        """Create metrics row with tiles."""
        theme = get_theme()
        colors = theme.colors

        frame = tk.Frame(self, bg=colors.bg_primary)

        # Configure columns
        for i in range(5):
            frame.columnconfigure(i, weight=1)

        # Equity tile
        self._equity_tile = MetricTile(
            frame,
            title="PORTFOLIO VALUE",
            value="$100,000.00",
            change=2.45,
            accent_color=colors.accent_primary,
        )
        self._equity_tile.grid(row=0, column=0, sticky="nsew", padx=(0, Spacing.XS))

        # Day P&L tile
        self._day_pnl_tile = MetricTile(
            frame,
            title="DAY P&L",
            value="+$1,234.56",
            change=1.23,
            accent_color=colors.bullish,
        )
        self._day_pnl_tile.grid(row=0, column=1, sticky="nsew", padx=Spacing.XS)

        # Total P&L tile
        self._total_pnl_tile = MetricTile(
            frame,
            title="TOTAL P&L",
            value="+$24,567.89",
            change=24.57,
            accent_color=colors.bullish,
        )
        self._total_pnl_tile.grid(row=0, column=2, sticky="nsew", padx=Spacing.XS)

        # Exposure tile
        self._exposure_tile = MetricTile(
            frame,
            title="NET EXPOSURE",
            value="45.2%",
            change=None,
            accent_color=colors.accent_secondary,
        )
        self._exposure_tile.grid(row=0, column=3, sticky="nsew", padx=Spacing.XS)

        # Cash tile
        self._cash_tile = MetricTile(
            frame,
            title="CASH AVAILABLE",
            value="$54,800.00",
            change=None,
            accent_color=colors.fg_muted,
        )
        self._cash_tile.grid(row=0, column=4, sticky="nsew", padx=(Spacing.XS, 0))

        return frame

    def _create_signals_card(self) -> Card:
        """Create signals panel."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Active Signals", padding="tight")

        # Table columns with enhanced styling
        columns = [
            Column("symbol", "Symbol", width=70, align=ColumnAlign.LEFT),
            Column("direction", "Direction", width=60, align=ColumnAlign.CENTER,
                   color_fn=lambda d: colors.bullish if d == "LONG" else colors.bearish if d == "SHORT" else colors.neutral),
            Column("confidence", "Conf", width=55, align=ColumnAlign.CENTER,
                   formatter=lambda v: f"{int(v*100)}%" if v else "-"),
            Column("entry_price", "Entry", width=65, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}" if v else "-"),
            Column("expected_return", "E[R]", width=55, align=ColumnAlign.RIGHT,
                   formatter=format_percent,
                   color_fn=lambda v: colors.bullish if v > 0 else colors.bearish if v < 0 else colors.fg_secondary),
        ]

        self._signals_table = DataTable(
            card.content,
            columns=columns,
            row_height=28,
            selectable=True,
        )
        self._signals_table.pack(fill=tk.BOTH, expand=True)

        return card

    def _create_positions_card(self) -> Card:
        """Create positions panel."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Open Positions", padding="tight")

        columns = [
            Column("symbol", "Symbol", width=70, align=ColumnAlign.LEFT),
            Column("side", "Side", width=55, align=ColumnAlign.CENTER,
                   color_fn=lambda s: colors.bullish if s == "long" else colors.bearish),
            Column("qty", "Qty", width=50, align=ColumnAlign.RIGHT),
            Column("entry_price", "Entry", width=65, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}"),
            Column("current_price", "Current", width=65, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}"),
            Column("unrealized_pnl", "P&L", width=80, align=ColumnAlign.RIGHT,
                   formatter=format_currency,
                   color_fn=lambda v: colors.bullish if v > 0 else colors.bearish if v < 0 else colors.fg_secondary),
        ]

        self._positions_table = DataTable(
            card.content,
            columns=columns,
            row_height=28,
            selectable=True,
        )
        self._positions_table.pack(fill=tk.BOTH, expand=True)

        return card

    def _create_chart_card(self) -> Card:
        """Create mini equity chart card."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Equity Curve (24h)", padding="tight")

        self._mini_chart = MiniEquityChart(card.content, width=300, height=100)
        self._mini_chart.pack(fill=tk.BOTH, expand=True)

        return card

    def _create_alerts_card(self) -> Card:
        """Create alerts panel."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Recent Alerts", padding="tight")

        self._alerts_frame = tk.Frame(card.content, bg=colors.bg_elevated)
        self._alerts_frame.pack(fill=tk.BOTH, expand=True)

        # Sample alerts
        sample_alerts = [
            ("info", "System initialized successfully", "2m ago"),
            ("success", "Position SPY opened: LONG 100 @ $450.25", "5m ago"),
            ("warning", "High volatility detected in QQQ", "12m ago"),
        ]

        for severity, message, time_ago in sample_alerts:
            self._add_alert(severity, message, time_ago)

        return card

    def _add_alert(self, severity: str, message: str, time_str: str) -> None:
        """Add an alert to the alerts frame."""
        theme = get_theme()
        colors = theme.colors

        alert_frame = tk.Frame(self._alerts_frame, bg=colors.bg_elevated)
        alert_frame.pack(fill=tk.X, pady=(0, Spacing.XS))

        # Severity indicator
        severity_colors = {
            'info': colors.info,
            'success': colors.success,
            'warning': colors.warning,
            'error': colors.error,
        }
        indicator = tk.Label(
            alert_frame,
            text="[*]",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=severity_colors.get(severity, colors.fg_muted),
            bg=colors.bg_elevated,
        )
        indicator.pack(side=tk.LEFT, padx=(0, Spacing.XS))

        # Message
        msg_label = tk.Label(
            alert_frame,
            text=message,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
            anchor="w",
        )
        msg_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Time
        time_label = tk.Label(
            alert_frame,
            text=time_str,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        )
        time_label.pack(side=tk.RIGHT)

    def _bind_events(self) -> None:
        """Bind to state events."""
        self._event_bus.subscribe(EventType.SIGNALS_UPDATED, self._on_signals_updated)
        self._event_bus.subscribe(EventType.POSITIONS_UPDATED, self._on_positions_updated)
        self._event_bus.subscribe(EventType.PORTFOLIO_UPDATED, self._on_portfolio_updated)
        self._event_bus.subscribe(EventType.REGIME_CHANGED, self._on_regime_changed)
        self._event_bus.subscribe(EventType.HEALTH_UPDATED, self._on_health_updated)
        self._event_bus.subscribe(EventType.NOTIFICATION, self._on_notification)

    def _refresh_data(self) -> None:
        """Refresh all data from state."""
        theme = get_theme()
        colors = theme.colors
        state = self._store.state

        # Update signals
        signals_data = [
            {
                'symbol': sig.symbol,
                'direction': sig.direction,
                'confidence': sig.confidence,
                'entry_price': sig.entry_price,
                'expected_return': sig.expected_return,
            }
            for sig in state.signals.values()
        ]
        self._signals_table.set_data(signals_data)

        # Update positions
        positions_data = [
            {
                'symbol': pos.symbol,
                'side': pos.side,
                'qty': pos.qty,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'unrealized_pnl': pos.unrealized_pnl,
            }
            for pos in state.positions.values()
        ]
        self._positions_table.set_data(positions_data)

        # Update portfolio metrics
        portfolio = state.portfolio
        self._equity_tile.set_value(
            f"${portfolio.equity:,.2f}",
            portfolio.total_return_pct * 100 if portfolio.equity > 0 else 0
        )

        day_pnl_sign = '+' if portfolio.day_pnl >= 0 else ''
        day_pnl_color = colors.bullish if portfolio.day_pnl >= 0 else colors.bearish
        self._day_pnl_tile.set_value(
            f"{day_pnl_sign}${abs(portfolio.day_pnl):,.2f}",
            portfolio.day_pnl / portfolio.equity * 100 if portfolio.equity > 0 else 0
        )

        total_pnl_sign = '+' if portfolio.total_pnl >= 0 else ''
        self._total_pnl_tile.set_value(
            f"{total_pnl_sign}${abs(portfolio.total_pnl):,.2f}",
            portfolio.total_return_pct * 100
        )

        self._exposure_tile.set_value(f"{portfolio.net_exposure * 100:.1f}%")
        self._cash_tile.set_value(f"${portfolio.cash:,.2f}")

        # Update regime
        market = state.market
        self._regime_badge.set_regime(market.regime, market.regime_confidence)

        # Update health
        health = state.health
        status_map = {'healthy': 'success', 'degraded': 'warning', 'unhealthy': 'error'}
        self._health_badge.set_status(status_map.get(health.status, 'info'), health.status.upper())

    def _on_signals_updated(self, event) -> None:
        """Handle signals update."""
        self.after(0, self._refresh_data)

    def _on_positions_updated(self, event) -> None:
        """Handle positions update."""
        self.after(0, self._refresh_data)

    def _on_portfolio_updated(self, event) -> None:
        """Handle portfolio update."""
        self.after(0, self._refresh_data)

    def _on_regime_changed(self, event) -> None:
        """Handle regime change."""
        self.after(0, self._refresh_data)

    def _on_health_updated(self, event) -> None:
        """Handle health update."""
        self.after(0, self._refresh_data)

    def _on_notification(self, event) -> None:
        """Handle notification."""
        pass

    def destroy(self) -> None:
        """Clean up on destroy."""
        self._event_bus.unsubscribe(EventType.SIGNALS_UPDATED, self._on_signals_updated)
        self._event_bus.unsubscribe(EventType.POSITIONS_UPDATED, self._on_positions_updated)
        self._event_bus.unsubscribe(EventType.PORTFOLIO_UPDATED, self._on_portfolio_updated)
        self._event_bus.unsubscribe(EventType.REGIME_CHANGED, self._on_regime_changed)
        self._event_bus.unsubscribe(EventType.HEALTH_UPDATED, self._on_health_updated)
        self._event_bus.unsubscribe(EventType.NOTIFICATION, self._on_notification)
        super().destroy()
