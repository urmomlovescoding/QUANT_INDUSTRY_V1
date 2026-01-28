"""
QUANT_INDUSTRY_V1 Chart Components

Lightweight chart widgets for inline display.

Rollback Plan: Delete this file
Tests Required: Data rendering, edge cases (empty, single point)
Failure Modes: Empty data -> show placeholder line
"""

import tkinter as tk
from typing import List, Optional, Tuple
import logging

from ..theme import get_theme, Spacing

logger = logging.getLogger(__name__)


class SparkLine(tk.Canvas):
    """
    Compact inline sparkline chart.

    Usage:
        spark = SparkLine(parent, data=[100, 102, 98, 105, 103], width=80, height=20)
        spark.set_data([...])
    """

    def __init__(
        self,
        parent: tk.Widget,
        data: List[float] = None,
        width: int = 80,
        height: int = 20,
        line_color: str = None,
        fill_color: str = None,
        show_end_point: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._line_color = line_color or colors.chart_line
        self._fill_color = fill_color
        self._show_end_point = show_end_point

        self._line_id = None
        self._fill_id = None
        self._point_id = None

        if data:
            self.set_data(data)

    def set_data(self, data: List[float]) -> None:
        """Set chart data."""
        self.delete("all")

        if not data or len(data) < 2:
            # Draw placeholder line
            self._draw_placeholder()
            return

        # Calculate points
        points = self._calculate_points(data)

        # Draw fill (optional)
        if self._fill_color:
            fill_points = points.copy()
            fill_points.insert(0, (0, self._height))
            fill_points.append((self._width, self._height))
            self._fill_id = self.create_polygon(
                fill_points,
                fill=self._fill_color,
                outline="",
            )

        # Draw line
        self._line_id = self.create_line(
            points,
            fill=self._line_color,
            width=1,
            smooth=True,
        )

        # Draw end point
        if self._show_end_point and points:
            last_x, last_y = points[-1]
            self._point_id = self.create_oval(
                last_x - 2, last_y - 2,
                last_x + 2, last_y + 2,
                fill=self._line_color,
                outline="",
            )

    def _calculate_points(self, data: List[float]) -> List[Tuple[int, int]]:
        """Calculate canvas coordinates from data."""
        if not data:
            return []

        min_val = min(data)
        max_val = max(data)
        val_range = max_val - min_val if max_val != min_val else 1

        padding = 2
        usable_width = self._width - padding * 2
        usable_height = self._height - padding * 2

        points = []
        for i, val in enumerate(data):
            x = padding + (i / (len(data) - 1)) * usable_width if len(data) > 1 else padding
            y = padding + usable_height - ((val - min_val) / val_range) * usable_height
            points.append((int(x), int(y)))

        return points

    def _draw_placeholder(self) -> None:
        """Draw placeholder for empty data."""
        theme = get_theme()
        colors = theme.colors

        mid_y = self._height // 2
        self.create_line(
            0, mid_y, self._width, mid_y,
            fill=colors.fg_muted,
            dash=(2, 2),
        )

    def set_colors(self, line_color: str = None, fill_color: str = None) -> None:
        """Update chart colors."""
        if line_color:
            self._line_color = line_color
        if fill_color:
            self._fill_color = fill_color


class MiniBarChart(tk.Canvas):
    """
    Compact bar chart for small datasets.

    Usage:
        chart = MiniBarChart(parent, data=[0.5, 0.3, -0.2, 0.8], width=60, height=20)
    """

    def __init__(
        self,
        parent: tk.Widget,
        data: List[float] = None,
        width: int = 60,
        height: int = 20,
        positive_color: str = None,
        negative_color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._positive_color = positive_color or colors.bullish
        self._negative_color = negative_color or colors.bearish

        if data:
            self.set_data(data)

    def set_data(self, data: List[float]) -> None:
        """Set chart data."""
        self.delete("all")

        if not data:
            return

        theme = get_theme()
        colors = theme.colors

        n = len(data)
        bar_width = max(2, (self._width - (n - 1)) // n)
        gap = 1

        # Find max for scaling
        max_abs = max(abs(v) for v in data) if data else 1
        if max_abs == 0:
            max_abs = 1

        mid_y = self._height // 2

        for i, val in enumerate(data):
            x = i * (bar_width + gap)
            bar_height = int((abs(val) / max_abs) * (mid_y - 2))

            if val >= 0:
                y1 = mid_y - bar_height
                y2 = mid_y
                color = self._positive_color
            else:
                y1 = mid_y
                y2 = mid_y + bar_height
                color = self._negative_color

            self.create_rectangle(
                x, y1, x + bar_width, y2,
                fill=color,
                outline="",
            )

        # Draw baseline
        self.create_line(
            0, mid_y, self._width, mid_y,
            fill=colors.border_light,
            width=1,
        )


class GaugeChart(tk.Canvas):
    """
    Semicircular gauge for single values.

    Usage:
        gauge = GaugeChart(parent, value=0.65, min_val=0, max_val=1)
    """

    def __init__(
        self,
        parent: tk.Widget,
        value: float = 0.0,
        min_val: float = 0.0,
        max_val: float = 1.0,
        size: int = 60,
        show_value: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', size)
        kwargs.setdefault('height', size // 2 + 10)

        super().__init__(parent, **kwargs)

        self._size = size
        self._min_val = min_val
        self._max_val = max_val
        self._show_value = show_value

        self._arc_bg = None
        self._arc_fg = None
        self._text_id = None

        self._draw_base()
        self.set_value(value)

    def _draw_base(self) -> None:
        """Draw gauge background."""
        theme = get_theme()
        colors = theme.colors

        padding = 4
        # Background arc
        self._arc_bg = self.create_arc(
            padding, padding,
            self._size - padding, self._size - padding,
            start=0, extent=180,
            style=tk.ARC,
            outline=colors.bg_tertiary,
            width=6,
        )

        # Value arc (initially empty)
        self._arc_fg = self.create_arc(
            padding, padding,
            self._size - padding, self._size - padding,
            start=180, extent=0,
            style=tk.ARC,
            outline=colors.accent_primary,
            width=6,
        )

        # Value text
        if self._show_value:
            self._text_id = self.create_text(
                self._size // 2, self._size // 2 - 2,
                text="0%",
                fill=colors.fg_primary,
                font=theme.get_font(10, "bold", "data"),
            )

    def set_value(self, value: float) -> None:
        """Set gauge value."""
        theme = get_theme()
        colors = theme.colors

        # Clamp value
        value = max(self._min_val, min(self._max_val, value))

        # Calculate extent
        ratio = (value - self._min_val) / (self._max_val - self._min_val) if self._max_val != self._min_val else 0
        extent = -180 * ratio  # Negative for clockwise from left

        # Update arc
        self.itemconfig(self._arc_fg, extent=extent)

        # Color based on value
        if ratio >= 0.7:
            color = colors.confidence_high
        elif ratio >= 0.4:
            color = colors.confidence_mid
        else:
            color = colors.confidence_low

        self.itemconfig(self._arc_fg, outline=color)

        # Update text
        if self._show_value:
            if self._max_val == 1.0:
                text = f"{int(value * 100)}%"
            else:
                text = f"{value:.1f}"
            self.itemconfig(self._text_id, text=text)


class HeatmapCell(tk.Frame):
    """
    Single heatmap cell for correlation matrices.

    Usage:
        cell = HeatmapCell(parent, value=0.8, show_value=True)
    """

    def __init__(
        self,
        parent: tk.Widget,
        value: float = 0.0,
        size: int = 24,
        show_value: bool = False,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Calculate background color based on value
        bg = self._value_to_color(value, colors)

        kwargs.setdefault('bg', bg)
        kwargs.setdefault('width', size)
        kwargs.setdefault('height', size)

        super().__init__(parent, **kwargs)

        self.pack_propagate(False)

        if show_value:
            # Determine text color for contrast
            fg = colors.fg_inverse if abs(value) > 0.5 else colors.fg_primary
            label = tk.Label(
                self,
                text=f"{value:.1f}",
                font=theme.get_font(8, "normal", "data"),
                fg=fg,
                bg=bg,
            )
            label.pack(expand=True)

    def _value_to_color(self, value: float, colors) -> str:
        """Convert value to heatmap color."""
        # Value should be -1 to 1
        value = max(-1, min(1, value))

        if value > 0:
            # Interpolate from neutral to bullish
            intensity = int(255 * (1 - value))
            return f"#{intensity:02x}ff{intensity:02x}"
        else:
            # Interpolate from neutral to bearish
            intensity = int(255 * (1 + value))
            return f"#ff{intensity:02x}{intensity:02x}"
