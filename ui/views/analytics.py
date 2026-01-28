"""
QUANT_INDUSTRY_V1 Advanced Analytics View - PROFESSIONAL EDITION

Professional analytics dashboard with sophisticated visualizations.

Features:
- Performance attribution
- Factor exposures
- Risk decomposition
- Correlation matrices
- Modern professional styling
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
import random
import math

from ..theme import get_theme, Spacing, FontSize, FontWeight, get_pnl_color, get_grade_color
from ..state import get_store, get_event_bus
from ..components.base import StyledFrame, Card, StyledLabel

logger = logging.getLogger(__name__)


class MetricDisplay(tk.Frame):
    """Compact metric display with label and value."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        super().__init__(parent, **kwargs)

        self._label = tk.Label(
            self,
            text=label,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
        )
        self._label.pack()

        self._value = tk.Label(
            self,
            text=value,
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "data"),
            fg=color or colors.fg_primary,
            bg=colors.bg_secondary,
        )
        self._value.pack()

    def set_value(self, value: str, color: str = None) -> None:
        """Update the value."""
        config = {'text': value}
        if color:
            config['fg'] = color
        self._value.config(**config)


class GradeDisplay(tk.Frame):
    """Letter grade display with color coding."""

    def __init__(
        self,
        parent: tk.Widget,
        label: str,
        grade: str = "B+",
        score: float = 82.5,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', colors.border_subtle)
        super().__init__(parent, **kwargs)

        container = tk.Frame(self, bg=colors.bg_tertiary)
        container.pack(fill=tk.BOTH, expand=True, padx=Spacing.SM, pady=Spacing.XS)

        # Label
        self._label = tk.Label(
            container,
            text=label,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        self._label.pack(side=tk.LEFT)

        # Score
        self._score_label = tk.Label(
            container,
            text=f"{score:.1f}",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
        )
        self._score_label.pack(side=tk.RIGHT, padx=(Spacing.SM, 0))

        # Grade
        grade_color = get_grade_color(grade, colors)
        self._grade_label = tk.Label(
            container,
            text=grade,
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "data"),
            fg=grade_color,
            bg=colors.bg_tertiary,
        )
        self._grade_label.pack(side=tk.RIGHT)

    def set_grade(self, grade: str, score: float) -> None:
        """Update grade and score."""
        theme = get_theme()
        colors = theme.colors

        self._grade_label.config(text=grade, fg=get_grade_color(grade, colors))
        self._score_label.config(text=f"{score:.1f}")


class AnalyticsView(tk.Frame):
    """
    Advanced analytics and performance attribution view.

    Layout:
    +---------------------------------------------------------+
    |  Summary Metrics Row                                     |
    +---------------------------------------------------------+
    |  Grade Cards (System, Returns, Risk, etc.)               |
    +---------------------------+-----------------------------+
    |  Equity Curve             |  Drawdown Analysis          |
    +---------------------------+-----------------------------+
    |  Return Distribution      |  Factor Exposures           |
    +---------------------------+-----------------------------+
    |  Risk Decomposition Table                               |
    +---------------------------------------------------------+
    """

    def __init__(self, parent: tk.Widget, **kwargs):
        theme = get_theme()
        colors = theme.colors
        kwargs.setdefault('bg', colors.bg_primary)

        super().__init__(parent, **kwargs)

        self._store = get_store()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup UI components."""
        theme = get_theme()
        colors = theme.colors

        # Configure grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=1)

        # Row 0: Summary metrics
        self._summary = self._create_summary()
        self._summary.grid(row=0, column=0, columnspan=2, sticky="ew",
                          padx=Spacing.MD, pady=Spacing.SM)

        # Row 1: Grade cards
        self._grades = self._create_grade_cards()
        self._grades.grid(row=1, column=0, columnspan=2, sticky="ew",
                         padx=Spacing.MD, pady=Spacing.XS)

        # Row 2: Equity curve and Drawdown
        self._equity_card = self._create_equity_card()
        self._equity_card.grid(row=2, column=0, sticky="nsew",
                              padx=(Spacing.MD, Spacing.XS), pady=Spacing.XS)

        self._drawdown_card = self._create_drawdown_card()
        self._drawdown_card.grid(row=2, column=1, sticky="nsew",
                                padx=(Spacing.XS, Spacing.MD), pady=Spacing.XS)

        # Row 3: Distribution and Factors
        self._dist_card = self._create_distribution_card()
        self._dist_card.grid(row=3, column=0, sticky="nsew",
                            padx=(Spacing.MD, Spacing.XS), pady=Spacing.XS)

        self._factor_card = self._create_factor_card()
        self._factor_card.grid(row=3, column=1, sticky="nsew",
                              padx=(Spacing.XS, Spacing.MD), pady=Spacing.XS)

        # Row 4: Risk decomposition
        self._risk_card = self._create_risk_card()
        self._risk_card.grid(row=4, column=0, columnspan=2, sticky="nsew",
                            padx=Spacing.MD, pady=(Spacing.XS, Spacing.MD))

    def _create_summary(self) -> tk.Frame:
        """Create summary metrics row."""
        theme = get_theme()
        colors = theme.colors

        frame = tk.Frame(self, bg=colors.bg_secondary, height=60)
        frame.pack_propagate(False)

        inner = tk.Frame(frame, bg=colors.bg_secondary)
        inner.pack(fill=tk.BOTH, expand=True, padx=Spacing.SM, pady=Spacing.XS)

        metrics = [
            ("Total Return", "+24.5%", colors.bullish),
            ("Sharpe Ratio", "1.85", colors.fg_primary),
            ("Sortino Ratio", "2.42", colors.fg_primary),
            ("Max Drawdown", "-8.3%", colors.bearish),
            ("Win Rate", "62%", colors.bullish),
            ("Profit Factor", "2.1x", colors.fg_primary),
            ("Calmar Ratio", "2.95", colors.accent_primary),
            ("Beta", "0.35", colors.fg_secondary),
        ]

        for label, value, color in metrics:
            MetricDisplay(inner, label, value, color).pack(
                side=tk.LEFT, expand=True, fill=tk.Y, padx=Spacing.XS
            )

        return frame

    def _create_grade_cards(self) -> tk.Frame:
        """Create grade display cards."""
        theme = get_theme()
        colors = theme.colors

        frame = tk.Frame(self, bg=colors.bg_primary)

        grades = [
            ("Overall", "A-", 85.6),
            ("Returns", "B+", 82.3),
            ("Risk-Adjusted", "A", 91.2),
            ("Consistency", "B", 78.5),
            ("Drawdown", "A-", 86.0),
            ("Model Perf", "B+", 81.4),
            ("Execution", "A", 90.5),
            ("Risk Mgmt", "B+", 83.2),
        ]

        for i, (label, grade, score) in enumerate(grades):
            frame.columnconfigure(i, weight=1)
            GradeDisplay(frame, label, grade, score).grid(
                row=0, column=i, sticky="ew", padx=Spacing.XS if i > 0 else 0
            )

        return frame

    def _create_equity_card(self) -> Card:
        """Create equity curve visualization."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Equity Curve", padding="tight")

        self._equity_canvas = tk.Canvas(
            card.content, bg=colors.bg_elevated,
            height=180, highlightthickness=0
        )
        self._equity_canvas.pack(fill=tk.BOTH, expand=True)
        self._equity_canvas.bind('<Configure>', lambda e: self._draw_equity_curve())

        self.after(100, self._draw_equity_curve)

        return card

    def _draw_equity_curve(self) -> None:
        """Draw equity curve with modern styling."""
        theme = get_theme()
        colors = theme.colors

        canvas = self._equity_canvas
        canvas.delete("all")

        width = canvas.winfo_width() or 400
        height = canvas.winfo_height() or 180

        # Generate sample data
        n_points = 100
        equity = [100000]
        random.seed(42)  # Consistent display
        for _ in range(n_points - 1):
            change = random.gauss(0.002, 0.018)
            equity.append(equity[-1] * (1 + change))

        # Normalize
        min_eq = min(equity)
        max_eq = max(equity)
        range_eq = max_eq - min_eq or 1

        padding = {'top': 15, 'right': 50, 'bottom': 25, 'left': 15}
        chart_width = width - padding['left'] - padding['right']
        chart_height = height - padding['top'] - padding['bottom']

        # Draw grid
        for i in range(5):
            y = padding['top'] + (i * chart_height / 4)
            canvas.create_line(
                padding['left'], y, width - padding['right'], y,
                fill=colors.chart_grid, dash=(2, 4)
            )

        # Calculate points
        points = []
        for i, e in enumerate(equity):
            x = padding['left'] + (i / (n_points - 1)) * chart_width
            y = padding['top'] + chart_height - ((e - min_eq) / range_eq) * chart_height
            points.append((x, y))

        # Draw gradient fill
        fill_points = [(padding['left'], height - padding['bottom'])]
        fill_points.extend(points)
        fill_points.append((width - padding['right'], height - padding['bottom']))
        flat_points = [coord for point in fill_points for coord in point]
        canvas.create_polygon(flat_points, fill=colors.accent_primary, outline="", stipple="gray50")

        # Draw line with trend coloring
        for i in range(len(points) - 1):
            color = colors.bullish if equity[i + 1] >= equity[i] else colors.bearish
            canvas.create_line(
                points[i][0], points[i][1],
                points[i + 1][0], points[i + 1][1],
                fill=color, width=2
            )

        # Y-axis labels
        for i in range(5):
            y = padding['top'] + (i * chart_height / 4)
            val = max_eq - (i * (max_eq - min_eq) / 4)
            label = f"${val/1000:.0f}K"
            canvas.create_text(
                width - padding['right'] + 5, y,
                text=label, fill=colors.fg_muted,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                anchor="w"
            )

    def _create_drawdown_card(self) -> Card:
        """Create drawdown analysis visualization."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Drawdown Analysis", padding="tight")

        self._drawdown_canvas = tk.Canvas(
            card.content, bg=colors.bg_elevated,
            height=180, highlightthickness=0
        )
        self._drawdown_canvas.pack(fill=tk.BOTH, expand=True)
        self._drawdown_canvas.bind('<Configure>', lambda e: self._draw_drawdown())

        self.after(100, self._draw_drawdown)

        return card

    def _draw_drawdown(self) -> None:
        """Draw drawdown chart with modern styling."""
        theme = get_theme()
        colors = theme.colors

        canvas = self._drawdown_canvas
        canvas.delete("all")

        width = canvas.winfo_width() or 400
        height = canvas.winfo_height() or 180

        # Generate sample drawdown data
        n_points = 100
        drawdown = []
        current_dd = 0
        random.seed(43)
        for _ in range(n_points):
            change = random.gauss(0, 0.008)
            current_dd = min(0, max(-0.15, current_dd + change))
            if random.random() > 0.97:
                current_dd = current_dd * 0.3
            drawdown.append(current_dd)

        padding = {'top': 15, 'right': 50, 'bottom': 25, 'left': 15}
        chart_width = width - padding['left'] - padding['right']
        chart_height = height - padding['top'] - padding['bottom']

        max_dd = 0.20  # Scale to 20%

        # Draw filled area
        points = [(padding['left'], padding['top'])]
        for i, dd in enumerate(drawdown):
            x = padding['left'] + (i / (n_points - 1)) * chart_width
            y = padding['top'] + (abs(dd) / max_dd) * chart_height
            points.append((x, y))
        points.append((width - padding['right'], padding['top']))

        flat_points = [coord for point in points for coord in point]
        canvas.create_polygon(flat_points, fill=colors.bearish, outline="", stipple="gray50")

        # Draw line
        line_points = points[1:-1]
        for i in range(len(line_points) - 1):
            canvas.create_line(
                line_points[i][0], line_points[i][1],
                line_points[i + 1][0], line_points[i + 1][1],
                fill=colors.bearish, width=2
            )

        # Zero line
        canvas.create_line(
            padding['left'], padding['top'],
            width - padding['right'], padding['top'],
            fill=colors.fg_muted, dash=(4, 2)
        )

        # Labels
        for i, pct in enumerate([0, -5, -10, -15, -20]):
            y = padding['top'] + (abs(pct) / 20) * chart_height
            canvas.create_text(
                width - padding['right'] + 5, y,
                text=f"{pct}%", fill=colors.fg_muted,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                anchor="w"
            )

    def _create_distribution_card(self) -> Card:
        """Create return distribution histogram."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Return Distribution", padding="tight")

        self._dist_canvas = tk.Canvas(
            card.content, bg=colors.bg_elevated,
            height=180, highlightthickness=0
        )
        self._dist_canvas.pack(fill=tk.BOTH, expand=True)
        self._dist_canvas.bind('<Configure>', lambda e: self._draw_distribution())

        self.after(100, self._draw_distribution)

        return card

    def _draw_distribution(self) -> None:
        """Draw return distribution histogram."""
        theme = get_theme()
        colors = theme.colors

        canvas = self._dist_canvas
        canvas.delete("all")

        width = canvas.winfo_width() or 400
        height = canvas.winfo_height() or 180

        # Generate sample returns
        random.seed(44)
        returns = [random.gauss(0.001, 0.02) for _ in range(500)]

        # Create histogram bins
        n_bins = 25
        min_ret = min(returns)
        max_ret = max(returns)
        bin_width = (max_ret - min_ret) / n_bins

        bins = [0] * n_bins
        for r in returns:
            bin_idx = min(int((r - min_ret) / bin_width), n_bins - 1)
            bins[bin_idx] += 1

        max_count = max(bins)

        padding = {'top': 15, 'right': 15, 'bottom': 30, 'left': 15}
        chart_width = width - padding['left'] - padding['right']
        chart_height = height - padding['top'] - padding['bottom']
        bar_width = chart_width / n_bins

        # Draw bars
        for i, count in enumerate(bins):
            x = padding['left'] + i * bar_width
            bar_height = (count / max_count) * chart_height if max_count > 0 else 0

            bin_center = min_ret + (i + 0.5) * bin_width
            color = colors.bullish if bin_center > 0 else colors.bearish

            canvas.create_rectangle(
                x + 1, height - padding['bottom'] - bar_height,
                x + bar_width - 1, height - padding['bottom'],
                fill=color, outline=""
            )

        # Draw zero line
        zero_x = padding['left'] + ((0 - min_ret) / (max_ret - min_ret)) * chart_width
        canvas.create_line(
            zero_x, padding['top'],
            zero_x, height - padding['bottom'],
            fill=colors.fg_primary, dash=(4, 2), width=2
        )

        # X-axis labels
        for pct in [-4, -2, 0, 2, 4]:
            x = padding['left'] + ((pct / 100 - min_ret) / (max_ret - min_ret)) * chart_width
            if padding['left'] < x < width - padding['right']:
                canvas.create_text(
                    x, height - padding['bottom'] + 10,
                    text=f"{pct}%", fill=colors.fg_muted,
                    font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data")
                )

    def _create_factor_card(self) -> Card:
        """Create factor exposure chart."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Factor Exposures", padding="tight")

        self._factor_canvas = tk.Canvas(
            card.content, bg=colors.bg_elevated,
            height=180, highlightthickness=0
        )
        self._factor_canvas.pack(fill=tk.BOTH, expand=True)
        self._factor_canvas.bind('<Configure>', lambda e: self._draw_factors())

        self.after(100, self._draw_factors)

        return card

    def _draw_factors(self) -> None:
        """Draw factor exposure bars."""
        theme = get_theme()
        colors = theme.colors

        canvas = self._factor_canvas
        canvas.delete("all")

        width = canvas.winfo_width() or 400
        height = canvas.winfo_height() or 180

        factors = [
            ("Market", 0.35),
            ("Size", -0.15),
            ("Value", 0.22),
            ("Momentum", 0.45),
            ("Volatility", -0.28),
            ("Quality", 0.18),
        ]

        padding = {'left': 75, 'right': 50, 'top': 10, 'bottom': 10}
        chart_width = width - padding['left'] - padding['right']
        bar_height = 18
        spacing = 8

        max_exposure = max(abs(e) for _, e in factors)

        for i, (name, exposure) in enumerate(factors):
            y = padding['top'] + i * (bar_height + spacing)

            # Label
            canvas.create_text(
                padding['left'] - 8, y + bar_height / 2,
                text=name, fill=colors.fg_secondary,
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                anchor="e"
            )

            # Zero line position
            zero_x = padding['left'] + chart_width / 2

            # Bar
            bar_length = (exposure / max_exposure) * (chart_width / 2)
            color = colors.bullish if exposure > 0 else colors.bearish

            if exposure > 0:
                canvas.create_rectangle(
                    zero_x, y,
                    zero_x + bar_length, y + bar_height,
                    fill=color, outline=""
                )
            else:
                canvas.create_rectangle(
                    zero_x + bar_length, y,
                    zero_x, y + bar_height,
                    fill=color, outline=""
                )

            # Value label
            val_x = zero_x + bar_length + (8 if exposure > 0 else -8)
            anchor = "w" if exposure > 0 else "e"
            canvas.create_text(
                val_x, y + bar_height / 2,
                text=f"{exposure:+.2f}",
                fill=colors.fg_primary,
                font=theme.get_font(FontSize.XS, FontWeight.BOLD, "data"),
                anchor=anchor
            )

        # Zero line
        zero_x = padding['left'] + chart_width / 2
        canvas.create_line(
            zero_x, padding['top'] - 5,
            zero_x, height - padding['bottom'] + 5,
            fill=colors.fg_muted, dash=(2, 2)
        )

    def _create_risk_card(self) -> Card:
        """Create risk decomposition view."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Risk Decomposition", padding="normal")

        # Create table with style
        style = ttk.Style()
        style.configure(
            "Analytics.Treeview",
            background=colors.bg_elevated,
            foreground=colors.fg_primary,
            fieldbackground=colors.bg_elevated,
            rowheight=28,
        )
        style.configure(
            "Analytics.Treeview.Heading",
            background=colors.bg_tertiary,
            foreground=colors.fg_secondary,
        )

        columns = ("component", "contribution", "marginal", "pct")
        tree = ttk.Treeview(
            card.content, columns=columns, show="headings",
            height=6, style="Analytics.Treeview"
        )

        tree.heading("component", text="Component")
        tree.heading("contribution", text="Risk Contrib")
        tree.heading("marginal", text="Marginal VaR")
        tree.heading("pct", text="% of Total")

        tree.column("component", width=150)
        tree.column("contribution", width=100)
        tree.column("marginal", width=100)
        tree.column("pct", width=80)

        risk_data = [
            ("Equity (SPY)", "$1,250", "$0.85", "35%"),
            ("Fixed Income (TLT)", "$450", "$0.32", "12%"),
            ("Momentum Factor", "$890", "$0.65", "25%"),
            ("Value Factor", "$520", "$0.42", "15%"),
            ("Volatility", "$380", "$0.28", "11%"),
            ("Residual", "$85", "$0.05", "2%"),
        ]

        for row in risk_data:
            tree.insert("", "end", values=row)

        tree.pack(fill=tk.BOTH, expand=True)

        return card

    def refresh(self, data: Dict[str, Any] = None) -> None:
        """Refresh analytics with new data."""
        self.after(50, self._draw_equity_curve)
        self.after(50, self._draw_drawdown)
        self.after(50, self._draw_distribution)
        self.after(50, self._draw_factors)
