"""
QUANT_INDUSTRY_V1 Portfolio Summary Panel

Professional portfolio overview with key metrics and mini charts.
"""

import tkinter as tk
from typing import Dict, Any, Optional, List
import logging
import math

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class PortfolioSummary(tk.Frame):
    """
    Portfolio summary panel with key metrics.

    Features:
    - Total value with change
    - P&L breakdown (realized/unrealized)
    - Allocation donut chart
    - Performance sparkline
    """

    def __init__(
        self,
        parent: tk.Widget,
        portfolio_value: float = 100000,
        daily_change: float = 0,
        daily_change_pct: float = 0,
        unrealized_pnl: float = 0,
        realized_pnl: float = 0,
        buying_power: float = 0,
        positions_count: int = 0,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme

        # Data
        self._portfolio_value = portfolio_value
        self._daily_change = daily_change
        self._daily_change_pct = daily_change_pct
        self._unrealized_pnl = unrealized_pnl
        self._realized_pnl = realized_pnl
        self._buying_power = buying_power
        self._positions_count = positions_count

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the portfolio summary UI."""
        colors = self._colors
        theme = self._theme

        # Header
        header = tk.Frame(self, bg=colors.bg_elevated)
        header.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        title = tk.Label(
            header,
            text="Portfolio Overview",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        )
        title.pack(side=tk.LEFT)

        # Main value
        value_frame = tk.Frame(self, bg=colors.bg_elevated)
        value_frame.pack(fill=tk.X, padx=Spacing.MD)

        value_label = tk.Label(
            value_frame,
            text=f"${self._portfolio_value:,.2f}",
            font=theme.get_font(FontSize.TITLE, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        )
        value_label.pack(anchor="w")

        # Daily change
        change_frame = tk.Frame(value_frame, bg=colors.bg_elevated)
        change_frame.pack(anchor="w")

        change_color = colors.bullish if self._daily_change >= 0 else colors.bearish
        change_sign = "+" if self._daily_change >= 0 else ""
        arrow = "▲" if self._daily_change >= 0 else "▼"

        change_label = tk.Label(
            change_frame,
            text=f"{arrow} {change_sign}${abs(self._daily_change):,.2f} ({change_sign}{self._daily_change_pct:.2f}%)",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=change_color,
            bg=colors.bg_elevated,
        )
        change_label.pack(side=tk.LEFT)

        tk.Label(
            change_frame,
            text=" Today",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        # Divider
        divider = tk.Frame(self, bg=colors.border, height=1)
        divider.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        # Metrics grid
        metrics_frame = tk.Frame(self, bg=colors.bg_elevated)
        metrics_frame.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.XS)

        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.columnconfigure(1, weight=1)

        # Unrealized P&L
        self._create_metric(
            metrics_frame, 0, 0,
            "Unrealized P&L",
            f"${self._unrealized_pnl:+,.2f}",
            colors.bullish if self._unrealized_pnl >= 0 else colors.bearish
        )

        # Realized P&L
        self._create_metric(
            metrics_frame, 0, 1,
            "Realized P&L",
            f"${self._realized_pnl:+,.2f}",
            colors.bullish if self._realized_pnl >= 0 else colors.bearish
        )

        # Buying Power
        self._create_metric(
            metrics_frame, 1, 0,
            "Buying Power",
            f"${self._buying_power:,.2f}",
            colors.fg_primary
        )

        # Positions
        self._create_metric(
            metrics_frame, 1, 1,
            "Open Positions",
            str(self._positions_count),
            colors.fg_primary
        )

        # Mini allocation chart
        chart_frame = tk.Frame(self, bg=colors.bg_elevated)
        chart_frame.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        tk.Label(
            chart_frame,
            text="ALLOCATION",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        self._allocation_chart = AllocationBar(
            chart_frame,
            allocations=[
                ("Stocks", 0.60, colors.accent_primary),
                ("Options", 0.25, colors.accent_secondary),
                ("Cash", 0.15, colors.fg_muted),
            ]
        )
        self._allocation_chart.pack(fill=tk.X, pady=Spacing.XS)

    def _create_metric(
        self,
        parent: tk.Frame,
        row: int,
        col: int,
        label: str,
        value: str,
        value_color: str
    ) -> None:
        """Create a metric display."""
        colors = self._colors
        theme = self._theme

        frame = tk.Frame(parent, bg=colors.bg_elevated)
        frame.grid(row=row, column=col, sticky="w", pady=Spacing.XS)

        tk.Label(
            frame,
            text=label,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        tk.Label(
            frame,
            text=value,
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "data"),
            fg=value_color,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

    def update_data(
        self,
        portfolio_value: float = None,
        daily_change: float = None,
        daily_change_pct: float = None,
        unrealized_pnl: float = None,
        realized_pnl: float = None,
        buying_power: float = None,
        positions_count: int = None,
    ) -> None:
        """Update portfolio data."""
        if portfolio_value is not None:
            self._portfolio_value = portfolio_value
        if daily_change is not None:
            self._daily_change = daily_change
        if daily_change_pct is not None:
            self._daily_change_pct = daily_change_pct
        if unrealized_pnl is not None:
            self._unrealized_pnl = unrealized_pnl
        if realized_pnl is not None:
            self._realized_pnl = realized_pnl
        if buying_power is not None:
            self._buying_power = buying_power
        if positions_count is not None:
            self._positions_count = positions_count

        # Rebuild UI
        for widget in self.winfo_children():
            widget.destroy()
        self._setup_ui()


class AllocationBar(tk.Canvas):
    """Horizontal allocation bar chart."""

    def __init__(
        self,
        parent: tk.Widget,
        allocations: List[tuple] = None,
        height: int = 24,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        super().__init__(
            parent,
            height=height,
            bg=colors.bg_elevated,
            highlightthickness=0,
            **kwargs
        )

        self._colors = colors
        self._theme = theme
        self._allocations = allocations or []
        self._height = height

        self.bind('<Configure>', self._on_configure)

    def _on_configure(self, event) -> None:
        """Redraw on resize."""
        self._draw()

    def _draw(self) -> None:
        """Draw the allocation bar."""
        self.delete("all")

        width = self.winfo_width()
        height = self._height

        if width <= 1:
            return

        bar_height = 8
        y = (height - bar_height) // 2

        # Draw segments
        x = 0
        for name, pct, color in self._allocations:
            seg_width = int(width * pct)
            if seg_width > 0:
                self.create_rectangle(
                    x, y, x + seg_width, y + bar_height,
                    fill=color, outline=""
                )
                x += seg_width

        # Draw labels below
        x = 0
        for name, pct, color in self._allocations:
            seg_width = int(width * pct)
            if seg_width > 30:  # Only show label if segment is wide enough
                self.create_text(
                    x + seg_width // 2, y + bar_height + 8,
                    text=f"{name} {pct*100:.0f}%",
                    font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                    fill=self._colors.fg_muted,
                    anchor="n"
                )
            x += seg_width


class MiniDonutChart(tk.Canvas):
    """Compact donut chart for allocation display."""

    def __init__(
        self,
        parent: tk.Widget,
        segments: List[tuple] = None,
        size: int = 60,
        thickness: int = 10,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        super().__init__(
            parent,
            width=size,
            height=size,
            bg=colors.bg_elevated,
            highlightthickness=0,
            **kwargs
        )

        self._colors = colors
        self._theme = theme
        self._segments = segments or []
        self._size = size
        self._thickness = thickness

        self._draw()

    def _draw(self) -> None:
        """Draw the donut chart."""
        self.delete("all")

        size = self._size
        thickness = self._thickness
        padding = 2

        outer_r = (size - padding * 2) // 2
        inner_r = outer_r - thickness

        cx = size // 2
        cy = size // 2

        # Draw segments
        start_angle = 90  # Start from top
        for name, pct, color in self._segments:
            extent = -pct * 360  # Negative for clockwise

            # Draw arc
            self.create_arc(
                cx - outer_r, cy - outer_r,
                cx + outer_r, cy + outer_r,
                start=start_angle, extent=extent,
                fill=color, outline=""
            )

            start_angle += extent

        # Draw inner circle to create donut
        self.create_oval(
            cx - inner_r, cy - inner_r,
            cx + inner_r, cy + inner_r,
            fill=self._colors.bg_elevated, outline=""
        )

    def set_segments(self, segments: List[tuple]) -> None:
        """Update donut segments."""
        self._segments = segments
        self._draw()


class PerformanceRow(tk.Frame):
    """Single performance metric row with label, value, and change."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        change: float = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme

        # Label
        tk.Label(
            self,
            text=label,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
            width=15,
            anchor="w",
        ).pack(side=tk.LEFT)

        # Value
        tk.Label(
            self,
            text=value,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT, padx=Spacing.SM)

        # Change indicator
        if change is not None:
            change_color = colors.bullish if change >= 0 else colors.bearish
            change_sign = "+" if change >= 0 else ""
            arrow = "▲" if change >= 0 else "▼"

            tk.Label(
                self,
                text=f"{arrow} {change_sign}{change:.2f}%",
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                fg=change_color,
                bg=colors.bg_elevated,
            ).pack(side=tk.RIGHT)


class PortfolioCard(tk.Frame):
    """
    Compact portfolio card for dashboard display.

    Shows key metrics in a single card format.
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "Portfolio",
        value: float = 0,
        change: float = 0,
        change_pct: float = 0,
        subtitle: str = None,
        icon: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme

        # Container with padding
        inner = tk.Frame(self, bg=colors.bg_elevated)
        inner.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.SM)

        # Top row: Icon and title
        top = tk.Frame(inner, bg=colors.bg_elevated)
        top.pack(fill=tk.X)

        if icon:
            tk.Label(
                top,
                text=icon,
                font=theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
                fg=colors.accent_primary,
                bg=colors.bg_elevated,
            ).pack(side=tk.LEFT)

        tk.Label(
            top,
            text=title,
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT, padx=(Spacing.XS if icon else 0, 0))

        # Value
        tk.Label(
            inner,
            text=f"${value:,.2f}",
            font=theme.get_font(FontSize.HEADING, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
            anchor="w",
        ).pack(fill=tk.X)

        # Change
        change_frame = tk.Frame(inner, bg=colors.bg_elevated)
        change_frame.pack(fill=tk.X)

        change_color = colors.bullish if change >= 0 else colors.bearish
        change_sign = "+" if change >= 0 else ""
        arrow = "▲" if change >= 0 else "▼"

        tk.Label(
            change_frame,
            text=f"{arrow} {change_sign}${abs(change):,.2f} ({change_sign}{change_pct:.2f}%)",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
            fg=change_color,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        # Subtitle
        if subtitle:
            tk.Label(
                inner,
                text=subtitle,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_muted,
                bg=colors.bg_elevated,
                anchor="w",
            ).pack(fill=tk.X, pady=(Spacing.XS, 0))
