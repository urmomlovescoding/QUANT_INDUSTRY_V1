"""
QUANT_INDUSTRY_V1 Right Rail Panel

Quick stats, active signals, and risk meters panel.
"""

import tkinter as tk
from typing import Optional, List, Dict, Any
import logging
import math

from ..theme import get_theme, Spacing, FontSize, FontWeight
from .base import Card

logger = logging.getLogger(__name__)


class QuickStat(tk.Frame):
    """Compact stat display for right rail."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        change: Optional[str] = None,
        positive: Optional[bool] = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme

        # Label
        lbl = tk.Label(
            self,
            text=label,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
        )
        lbl.pack(anchor="w")

        # Value row
        value_frame = tk.Frame(self, bg=colors.bg_secondary)
        value_frame.pack(anchor="w", fill=tk.X)

        self._value_label = tk.Label(
            value_frame,
            text=value,
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_secondary,
        )
        self._value_label.pack(side=tk.LEFT)

        # Change indicator
        if change:
            change_color = colors.bullish if positive else colors.bearish if positive is False else colors.fg_muted
            self._change_label = tk.Label(
                value_frame,
                text=change,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                fg=change_color,
                bg=colors.bg_secondary,
            )
            self._change_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

    def update_value(self, value: str, change: str = None, positive: bool = None) -> None:
        """Update the displayed value."""
        self._value_label.config(text=value)
        if hasattr(self, '_change_label') and change:
            change_color = self._colors.bullish if positive else self._colors.bearish if positive is False else self._colors.fg_muted
            self._change_label.config(text=change, fg=change_color)


class RiskMeter(tk.Canvas):
    """Visual risk level indicator."""

    def __init__(
        self,
        parent: tk.Widget,
        value: float = 0,  # 0-100
        label: str = "Risk",
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('width', 120)
        kwargs.setdefault('height', 60)
        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('highlightthickness', 0)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._value = value
        self._label = label
        self._width = kwargs.get('width', 120)
        self._height = kwargs.get('height', 60)

        self._draw()

    def _draw(self) -> None:
        """Draw the meter."""
        self.delete("all")

        cx = self._width / 2
        cy = self._height - 10

        # Arc background
        radius = min(cx - 5, cy - 10)
        start_angle = 180
        extent = 180

        # Background arc
        self.create_arc(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            start=start_angle, extent=extent,
            outline=self._colors.bg_tertiary,
            width=8,
            style=tk.ARC,
        )

        # Determine color based on value
        if self._value < 33:
            color = self._colors.bullish
        elif self._value < 66:
            color = self._colors.warning
        else:
            color = self._colors.bearish

        # Value arc
        value_extent = (self._value / 100) * extent
        if value_extent > 0:
            self.create_arc(
                cx - radius, cy - radius,
                cx + radius, cy + radius,
                start=start_angle, extent=value_extent,
                outline=color,
                width=8,
                style=tk.ARC,
            )

        # Needle
        needle_angle = math.radians(180 - (self._value / 100) * 180)
        needle_length = radius - 15
        nx = cx + needle_length * math.cos(needle_angle)
        ny = cy - needle_length * math.sin(needle_angle)

        self.create_line(
            cx, cy, nx, ny,
            fill=self._colors.fg_primary,
            width=2,
        )

        # Center dot
        self.create_oval(
            cx - 4, cy - 4, cx + 4, cy + 4,
            fill=self._colors.fg_primary,
            outline="",
        )

        # Value text
        self.create_text(
            cx, cy - radius - 15,
            text=f"{self._value:.0f}%",
            font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fill=self._colors.fg_primary,
        )

        # Label
        self.create_text(
            cx, self._height - 2,
            text=self._label,
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fill=self._colors.fg_muted,
        )

    def set_value(self, value: float) -> None:
        """Update the meter value."""
        self._value = max(0, min(100, value))
        self._draw()


class SignalItem(tk.Frame):
    """Active signal display for right rail."""

    def __init__(
        self,
        parent: tk.Widget,
        symbol: str,
        direction: str,  # "LONG" or "SHORT"
        confidence: float,
        time_ago: str,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        super().__init__(parent, **kwargs)

        # Direction indicator
        dir_color = colors.bullish if direction == "LONG" else colors.bearish
        dir_text = "▲" if direction == "LONG" else "▼"

        dir_label = tk.Label(
            self,
            text=dir_text,
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "data"),
            fg=dir_color,
            bg=colors.bg_secondary,
        )
        dir_label.pack(side=tk.LEFT, padx=(0, Spacing.XS))

        # Info frame
        info = tk.Frame(self, bg=colors.bg_secondary)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Symbol
        sym_label = tk.Label(
            info,
            text=symbol,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_secondary,
        )
        sym_label.pack(anchor="w")

        # Time
        time_label = tk.Label(
            info,
            text=time_ago,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
        )
        time_label.pack(anchor="w")

        # Confidence bar
        conf_frame = tk.Frame(self, bg=colors.bg_secondary)
        conf_frame.pack(side=tk.RIGHT)

        conf_label = tk.Label(
            conf_frame,
            text=f"{confidence:.0%}",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_secondary,
            bg=colors.bg_secondary,
        )
        conf_label.pack()


class RightRail(tk.Frame):
    """
    Right rail panel with quick stats, signals, and risk meters.

    Layout:
    ┌─────────────────┐
    │ Quick Stats     │
    ├─────────────────┤
    │ Risk Meters     │
    ├─────────────────┤
    │ Active Signals  │
    ├─────────────────┤
    │ Market Status   │
    └─────────────────┘
    """

    def __init__(self, parent: tk.Widget, width: int = 200, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        super().__init__(parent, width=width, **kwargs)

        self._colors = colors
        self._theme = theme
        self._width = width

        self.pack_propagate(False)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the right rail UI."""
        # Scrollable container
        canvas = tk.Canvas(
            self,
            bg=self._colors.bg_secondary,
            highlightthickness=0,
            width=self._width - 2,
        )
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            self,
            orient=tk.VERTICAL,
            command=canvas.yview,
            width=8,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas.configure(yscrollcommand=scrollbar.set)

        # Inner content
        content = tk.Frame(canvas, bg=self._colors.bg_secondary)
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")

        content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # === Quick Stats Section ===
        stats_header = tk.Label(
            content,
            text="QUICK STATS",
            font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
            anchor="w",
        )
        stats_header.pack(fill=tk.X, padx=Spacing.SM, pady=(Spacing.MD, Spacing.XS))

        # Stats
        self._stats = {}
        stats_data = [
            ("pnl", "Today's P&L", "$0.00", "+0.00%", True),
            ("positions", "Open Positions", "0", None, None),
            ("win_rate", "Win Rate", "0%", None, None),
            ("sharpe", "Sharpe (30d)", "0.00", None, None),
        ]

        for key, label, value, change, positive in stats_data:
            stat = QuickStat(content, label, value, change, positive)
            stat.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)
            self._stats[key] = stat

        # Separator
        sep1 = tk.Frame(content, bg=self._colors.border_light, height=1)
        sep1.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.MD)

        # === Risk Meters Section ===
        risk_header = tk.Label(
            content,
            text="RISK EXPOSURE",
            font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
            anchor="w",
        )
        risk_header.pack(fill=tk.X, padx=Spacing.SM, pady=(0, Spacing.XS))

        # Risk meters row
        meters_frame = tk.Frame(content, bg=self._colors.bg_secondary)
        meters_frame.pack(fill=tk.X, padx=Spacing.XS)

        self._portfolio_risk = RiskMeter(meters_frame, value=35, label="Portfolio")
        self._portfolio_risk.pack(side=tk.LEFT, padx=2)

        self._drawdown_risk = RiskMeter(meters_frame, value=15, label="Drawdown")
        self._drawdown_risk.pack(side=tk.LEFT, padx=2)

        # Separator
        sep2 = tk.Frame(content, bg=self._colors.border_light, height=1)
        sep2.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.MD)

        # === Active Signals Section ===
        signals_header = tk.Label(
            content,
            text="ACTIVE SIGNALS",
            font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
            anchor="w",
        )
        signals_header.pack(fill=tk.X, padx=Spacing.SM, pady=(0, Spacing.XS))

        self._signals_frame = tk.Frame(content, bg=self._colors.bg_secondary)
        self._signals_frame.pack(fill=tk.X, padx=Spacing.SM)

        # Sample signals
        sample_signals = [
            ("AAPL", "LONG", 0.85, "2m ago"),
            ("TSLA", "SHORT", 0.72, "5m ago"),
            ("MSFT", "LONG", 0.68, "12m ago"),
        ]

        for symbol, direction, confidence, time_ago in sample_signals:
            signal = SignalItem(
                self._signals_frame,
                symbol, direction, confidence, time_ago
            )
            signal.pack(fill=tk.X, pady=2)

        # Separator
        sep3 = tk.Frame(content, bg=self._colors.border_light, height=1)
        sep3.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.MD)

        # === Market Status Section ===
        market_header = tk.Label(
            content,
            text="MARKET STATUS",
            font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
            anchor="w",
        )
        market_header.pack(fill=tk.X, padx=Spacing.SM, pady=(0, Spacing.XS))

        # Market status indicator
        status_frame = tk.Frame(content, bg=self._colors.bg_secondary)
        status_frame.pack(fill=tk.X, padx=Spacing.SM)

        # Status dot
        self._market_dot = tk.Canvas(
            status_frame,
            width=10,
            height=10,
            bg=self._colors.bg_secondary,
            highlightthickness=0,
        )
        self._market_dot.pack(side=tk.LEFT, padx=(0, Spacing.XS))
        self._market_dot.create_oval(2, 2, 8, 8, fill=self._colors.bullish, outline="")

        self._market_status = tk.Label(
            status_frame,
            text="Market Open",
            font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_primary,
            bg=self._colors.bg_secondary,
        )
        self._market_status.pack(side=tk.LEFT)

        # Time info
        time_frame = tk.Frame(content, bg=self._colors.bg_secondary)
        time_frame.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        session_label = tk.Label(
            time_frame,
            text="Regular Session",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
        )
        session_label.pack(anchor="w")

        # VIX indicator
        vix_frame = tk.Frame(content, bg=self._colors.bg_secondary)
        vix_frame.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        vix_label = tk.Label(
            vix_frame,
            text="VIX:",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
        )
        vix_label.pack(side=tk.LEFT)

        self._vix_value = tk.Label(
            vix_frame,
            text="18.45",
            font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=self._colors.fg_primary,
            bg=self._colors.bg_secondary,
        )
        self._vix_value.pack(side=tk.LEFT, padx=Spacing.XS)

        self._vix_change = tk.Label(
            vix_frame,
            text="-2.3%",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=self._colors.bullish,
            bg=self._colors.bg_secondary,
        )
        self._vix_change.pack(side=tk.LEFT)

    def update_stats(self, stats: Dict[str, Any]) -> None:
        """Update quick stats."""
        for key, data in stats.items():
            if key in self._stats:
                self._stats[key].update_value(
                    data.get('value', ''),
                    data.get('change'),
                    data.get('positive'),
                )

    def update_risk(self, portfolio: float, drawdown: float) -> None:
        """Update risk meters."""
        self._portfolio_risk.set_value(portfolio)
        self._drawdown_risk.set_value(drawdown)

    def set_market_status(self, is_open: bool, status_text: str) -> None:
        """Update market status."""
        color = self._colors.bullish if is_open else self._colors.fg_muted
        self._market_dot.delete("all")
        self._market_dot.create_oval(2, 2, 8, 8, fill=color, outline="")
        self._market_status.config(text=status_text)
