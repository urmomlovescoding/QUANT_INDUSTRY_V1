"""
QUANT_INDUSTRY_V1 Advanced Chart Components

Professional-grade chart widgets with modern styling.
Inspired by Bloomberg Terminal and TradingView aesthetics.
"""

import tkinter as tk
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import math
import logging

from ..theme import (
    get_theme, Spacing, FontSize, FontWeight,
    get_pnl_color, interpolate_color,
)

logger = logging.getLogger(__name__)


@dataclass
class ChartDataPoint:
    """Single data point for charts."""
    value: float
    label: str = ""
    timestamp: float = 0.0


class EquityCurveChart(tk.Canvas):
    """
    Professional equity curve chart with gradient fill.

    Features:
    - Smooth line rendering
    - Gradient area fill
    - Grid lines
    - Value axis labels
    - Hover tooltip support
    """

    def __init__(
        self,
        parent: tk.Widget,
        data: List[float] = None,
        width: int = 400,
        height: int = 200,
        show_grid: bool = True,
        show_labels: bool = True,
        animate: bool = False,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._show_grid = show_grid
        self._show_labels = show_labels
        self._animate = animate
        self._data = data or []
        self._padding = {'top': 20, 'right': 60, 'bottom': 30, 'left': 20}

        self._tooltip_window = None
        self._hover_line = None
        self._hover_point = None

        # Bind events
        self.bind('<Motion>', self._on_mouse_move)
        self.bind('<Leave>', self._on_mouse_leave)
        self.bind('<Configure>', self._on_resize)

        if data:
            self.set_data(data)

    def _on_resize(self, event):
        """Handle resize."""
        self._width = event.width
        self._height = event.height
        if self._data:
            self.set_data(self._data)

    def set_data(self, data: List[float]) -> None:
        """Set chart data and redraw."""
        self._data = data
        self.delete("all")

        if not data or len(data) < 2:
            self._draw_empty_state()
            return

        self._draw_grid()
        self._draw_chart()
        self._draw_labels()

    def _draw_empty_state(self) -> None:
        """Draw empty state placeholder."""
        theme = get_theme()
        colors = theme.colors

        self.create_text(
            self._width // 2, self._height // 2,
            text="No data available",
            fill=colors.fg_muted,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
        )

    def _draw_grid(self) -> None:
        """Draw background grid."""
        if not self._show_grid:
            return

        theme = get_theme()
        colors = theme.colors

        chart_width = self._width - self._padding['left'] - self._padding['right']
        chart_height = self._height - self._padding['top'] - self._padding['bottom']

        # Horizontal grid lines (5 lines)
        for i in range(6):
            y = self._padding['top'] + (i * chart_height / 5)
            self.create_line(
                self._padding['left'], y,
                self._width - self._padding['right'], y,
                fill=colors.chart_grid,
                dash=(2, 4),
            )

        # Vertical grid lines (8 lines)
        for i in range(9):
            x = self._padding['left'] + (i * chart_width / 8)
            self.create_line(
                x, self._padding['top'],
                x, self._height - self._padding['bottom'],
                fill=colors.chart_grid,
                dash=(2, 4),
            )

    def _draw_chart(self) -> None:
        """Draw the equity curve."""
        theme = get_theme()
        colors = theme.colors

        if not self._data:
            return

        # Calculate bounds
        min_val = min(self._data)
        max_val = max(self._data)
        val_range = max_val - min_val if max_val != min_val else 1

        chart_width = self._width - self._padding['left'] - self._padding['right']
        chart_height = self._height - self._padding['top'] - self._padding['bottom']

        # Calculate points
        points = []
        for i, val in enumerate(self._data):
            x = self._padding['left'] + (i / (len(self._data) - 1)) * chart_width
            y = self._padding['top'] + chart_height - ((val - min_val) / val_range) * chart_height
            points.append((x, y))

        # Draw gradient fill
        fill_points = [(self._padding['left'], self._height - self._padding['bottom'])]
        fill_points.extend(points)
        fill_points.append((self._width - self._padding['right'], self._height - self._padding['bottom']))

        # Create gradient effect with multiple layers
        for layer in range(5):
            alpha_hex = format(int(255 * (0.15 - layer * 0.025)), '02x')
            layer_y_offset = layer * 2
            layer_points = []
            for px, py in fill_points:
                layer_points.append((px, min(py + layer_y_offset, self._height - self._padding['bottom'])))

            flat_points = [coord for point in layer_points for coord in point]
            self.create_polygon(
                flat_points,
                fill=colors.chart_area.rstrip('20') if colors.chart_area.endswith('20') else colors.accent_primary,
                outline="",
                stipple="gray50" if layer > 2 else "gray75" if layer > 0 else "",
            )

        # Draw the main line with gradient coloring based on trend
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]

            # Color based on direction
            if self._data[i + 1] >= self._data[i]:
                color = colors.bullish
            else:
                color = colors.bearish

            self.create_line(
                x1, y1, x2, y2,
                fill=color,
                width=2,
                smooth=False,
            )

        # Draw glow effect under the line
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]

            self.create_line(
                x1, y1 + 1, x2, y2 + 1,
                fill=colors.accent_primary,
                width=3,
                stipple="gray50",
            )

    def _draw_labels(self) -> None:
        """Draw axis labels."""
        if not self._show_labels or not self._data:
            return

        theme = get_theme()
        colors = theme.colors

        min_val = min(self._data)
        max_val = max(self._data)
        chart_height = self._height - self._padding['top'] - self._padding['bottom']

        # Y-axis labels
        for i in range(6):
            y = self._padding['top'] + (i * chart_height / 5)
            val = max_val - (i * (max_val - min_val) / 5)

            if abs(val) >= 1_000_000:
                label = f"${val/1_000_000:.1f}M"
            elif abs(val) >= 1_000:
                label = f"${val/1_000:.1f}K"
            else:
                label = f"${val:.0f}"

            self.create_text(
                self._width - self._padding['right'] + 5, y,
                text=label,
                fill=colors.fg_muted,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                anchor="w",
            )

    def _on_mouse_move(self, event):
        """Handle mouse movement for hover effects."""
        if not self._data or len(self._data) < 2:
            return

        theme = get_theme()
        colors = theme.colors

        chart_width = self._width - self._padding['left'] - self._padding['right']
        chart_height = self._height - self._padding['top'] - self._padding['bottom']

        # Calculate which data point we're hovering over
        if event.x < self._padding['left'] or event.x > self._width - self._padding['right']:
            self._hide_hover()
            return

        rel_x = event.x - self._padding['left']
        data_index = int((rel_x / chart_width) * (len(self._data) - 1))
        data_index = max(0, min(len(self._data) - 1, data_index))

        # Calculate position
        min_val = min(self._data)
        max_val = max(self._data)
        val_range = max_val - min_val if max_val != min_val else 1

        x = self._padding['left'] + (data_index / (len(self._data) - 1)) * chart_width
        val = self._data[data_index]
        y = self._padding['top'] + chart_height - ((val - min_val) / val_range) * chart_height

        # Draw hover line
        self.delete("hover")
        self.create_line(
            x, self._padding['top'], x, self._height - self._padding['bottom'],
            fill=colors.fg_muted,
            dash=(4, 2),
            tags="hover",
        )

        # Draw hover point
        self.create_oval(
            x - 4, y - 4, x + 4, y + 4,
            fill=colors.accent_primary,
            outline=colors.fg_primary,
            width=2,
            tags="hover",
        )

        # Draw value tooltip
        if abs(val) >= 1_000_000:
            label = f"${val/1_000_000:.2f}M"
        elif abs(val) >= 1_000:
            label = f"${val/1_000:.2f}K"
        else:
            label = f"${val:.2f}"

        tooltip_x = x + 10
        tooltip_y = y - 10

        # Background
        bbox = (tooltip_x, tooltip_y - 10, tooltip_x + 70, tooltip_y + 10)
        self.create_rectangle(
            bbox,
            fill=colors.bg_primary,
            outline=colors.border_light,
            tags="hover",
        )
        self.create_text(
            tooltip_x + 35, tooltip_y,
            text=label,
            fill=colors.fg_primary,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            tags="hover",
        )

    def _on_mouse_leave(self, event):
        """Handle mouse leave."""
        self._hide_hover()

    def _hide_hover(self):
        """Hide hover elements."""
        self.delete("hover")


class CandlestickChart(tk.Canvas):
    """
    Professional candlestick chart for OHLC data.

    Features:
    - Proper candlestick rendering
    - Volume subplot
    - Crosshair cursor
    - Price axis
    """

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 400,
        height: int = 250,
        show_volume: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._show_volume = show_volume
        self._data = []  # List of (open, high, low, close, volume) tuples

        self._padding = {'top': 20, 'right': 60, 'bottom': 30, 'left': 10}
        self._volume_height = 40 if show_volume else 0

        self.bind('<Configure>', self._on_resize)

    def _on_resize(self, event):
        """Handle resize."""
        self._width = event.width
        self._height = event.height
        if self._data:
            self.set_data(self._data)

    def set_data(self, data: List[Tuple[float, float, float, float, float]]) -> None:
        """Set OHLCV data and redraw."""
        self._data = data
        self.delete("all")

        if not data:
            return

        self._draw_grid()
        self._draw_candles()
        if self._show_volume:
            self._draw_volume()
        self._draw_labels()

    def _draw_grid(self) -> None:
        """Draw background grid."""
        theme = get_theme()
        colors = theme.colors

        chart_width = self._width - self._padding['left'] - self._padding['right']
        chart_height = self._height - self._padding['top'] - self._padding['bottom'] - self._volume_height

        # Horizontal lines
        for i in range(5):
            y = self._padding['top'] + (i * chart_height / 4)
            self.create_line(
                self._padding['left'], y,
                self._width - self._padding['right'], y,
                fill=colors.chart_grid,
                dash=(2, 4),
            )

    def _draw_candles(self) -> None:
        """Draw candlesticks."""
        theme = get_theme()
        colors = theme.colors

        if not self._data:
            return

        # Calculate bounds
        all_highs = [d[1] for d in self._data]
        all_lows = [d[2] for d in self._data]
        min_price = min(all_lows)
        max_price = max(all_highs)
        price_range = max_price - min_price if max_price != min_price else 1

        chart_width = self._width - self._padding['left'] - self._padding['right']
        chart_height = self._height - self._padding['top'] - self._padding['bottom'] - self._volume_height

        n_candles = len(self._data)
        candle_width = max(3, (chart_width / n_candles) * 0.8)
        gap = (chart_width / n_candles) * 0.2

        for i, (open_p, high, low, close) in enumerate([(d[0], d[1], d[2], d[3]) for d in self._data]):
            x = self._padding['left'] + i * (candle_width + gap) + candle_width / 2

            # Calculate y positions
            y_high = self._padding['top'] + chart_height - ((high - min_price) / price_range) * chart_height
            y_low = self._padding['top'] + chart_height - ((low - min_price) / price_range) * chart_height
            y_open = self._padding['top'] + chart_height - ((open_p - min_price) / price_range) * chart_height
            y_close = self._padding['top'] + chart_height - ((close - min_price) / price_range) * chart_height

            is_bullish = close >= open_p
            color = colors.chart_candle_up if is_bullish else colors.chart_candle_down

            # Draw wick
            self.create_line(
                x, y_high, x, y_low,
                fill=colors.chart_wick,
                width=1,
            )

            # Draw body
            body_top = min(y_open, y_close)
            body_bottom = max(y_open, y_close)
            body_height = max(1, body_bottom - body_top)

            self.create_rectangle(
                x - candle_width / 2, body_top,
                x + candle_width / 2, body_top + body_height,
                fill=color if is_bullish else "",
                outline=color,
                width=1,
            )

    def _draw_volume(self) -> None:
        """Draw volume bars."""
        theme = get_theme()
        colors = theme.colors

        if not self._data:
            return

        volumes = [d[4] for d in self._data]
        max_vol = max(volumes) if volumes else 1

        chart_width = self._width - self._padding['left'] - self._padding['right']
        vol_top = self._height - self._padding['bottom'] - self._volume_height
        vol_height = self._volume_height - 5

        n_bars = len(self._data)
        bar_width = max(3, (chart_width / n_bars) * 0.8)
        gap = (chart_width / n_bars) * 0.2

        for i, (open_p, _, _, close, vol) in enumerate(self._data):
            x = self._padding['left'] + i * (bar_width + gap)
            h = (vol / max_vol) * vol_height if max_vol > 0 else 0

            is_bullish = close >= open_p
            color = colors.chart_candle_up if is_bullish else colors.chart_candle_down

            self.create_rectangle(
                x, vol_top + vol_height - h,
                x + bar_width, vol_top + vol_height,
                fill=color,
                outline="",
                stipple="gray50",
            )

    def _draw_labels(self) -> None:
        """Draw price axis labels."""
        theme = get_theme()
        colors = theme.colors

        if not self._data:
            return

        all_highs = [d[1] for d in self._data]
        all_lows = [d[2] for d in self._data]
        min_price = min(all_lows)
        max_price = max(all_highs)

        chart_height = self._height - self._padding['top'] - self._padding['bottom'] - self._volume_height

        for i in range(5):
            y = self._padding['top'] + (i * chart_height / 4)
            price = max_price - (i * (max_price - min_price) / 4)

            self.create_text(
                self._width - self._padding['right'] + 5, y,
                text=f"${price:.2f}",
                fill=colors.fg_muted,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                anchor="w",
            )


class DonutChart(tk.Canvas):
    """
    Donut/pie chart for allocation displays.

    Features:
    - Smooth arc rendering
    - Center label
    - Legend support
    - Hover effects
    """

    def __init__(
        self,
        parent: tk.Widget,
        size: int = 150,
        thickness: int = 25,
        show_center_label: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', size)
        kwargs.setdefault('height', size)

        super().__init__(parent, **kwargs)

        self._size = size
        self._thickness = thickness
        self._show_center_label = show_center_label
        self._data = []  # List of (label, value, color) tuples
        self._center_text_id = None

    def set_data(self, data: List[Tuple[str, float, str]]) -> None:
        """Set chart data: [(label, value, color), ...]"""
        self._data = data
        self.delete("all")

        if not data:
            return

        self._draw_donut()
        if self._show_center_label:
            self._draw_center_label()

    def _draw_donut(self) -> None:
        """Draw the donut segments."""
        theme = get_theme()
        colors = theme.colors

        total = sum(d[1] for d in self._data)
        if total == 0:
            return

        padding = 10
        outer_radius = (self._size - padding * 2) / 2
        inner_radius = outer_radius - self._thickness

        center_x = self._size / 2
        center_y = self._size / 2

        start_angle = 90  # Start from top

        for label, value, color in self._data:
            extent = (value / total) * 360

            # Draw outer arc
            self.create_arc(
                padding, padding,
                self._size - padding, self._size - padding,
                start=start_angle,
                extent=-extent,
                style=tk.PIESLICE,
                fill=color,
                outline=colors.bg_elevated,
                width=2,
            )

            start_angle -= extent

        # Draw inner circle to create donut effect
        inner_padding = padding + self._thickness
        self.create_oval(
            inner_padding, inner_padding,
            self._size - inner_padding, self._size - inner_padding,
            fill=colors.bg_elevated,
            outline="",
        )

    def _draw_center_label(self) -> None:
        """Draw center label."""
        theme = get_theme()
        colors = theme.colors

        total = sum(d[1] for d in self._data)

        self._center_text_id = self.create_text(
            self._size / 2, self._size / 2,
            text=f"${total:,.0f}",
            fill=colors.fg_primary,
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "data"),
        )


class MetricCard(tk.Frame):
    """
    Modern metric display card with optional sparkline.

    Features:
    - Large value display
    - Change indicator
    - Optional mini chart
    - Subtle animations
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str = "",
        value: str = "",
        change: float = None,
        sparkline_data: List[float] = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', colors.border_subtle)

        super().__init__(parent, **kwargs)

        self._title = title
        self._value = value
        self._change = change

        self._setup_ui()

        if sparkline_data:
            self.set_sparkline(sparkline_data)

    def _setup_ui(self) -> None:
        """Setup the card UI."""
        theme = get_theme()
        colors = theme.colors

        # Title
        self._title_label = tk.Label(
            self,
            text=self._title,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        )
        self._title_label.pack(anchor="w", padx=Spacing.MD, pady=(Spacing.SM, 0))

        # Value row
        value_frame = tk.Frame(self, bg=colors.bg_elevated)
        value_frame.pack(fill=tk.X, padx=Spacing.MD)

        self._value_label = tk.Label(
            value_frame,
            text=self._value,
            font=theme.get_font(FontSize.XXL, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        )
        self._value_label.pack(side=tk.LEFT)

        # Change indicator
        if self._change is not None:
            change_color = colors.bullish if self._change >= 0 else colors.bearish
            arrow = "▲" if self._change >= 0 else "▼"
            change_text = f"{arrow} {abs(self._change):.2f}%"

            self._change_label = tk.Label(
                value_frame,
                text=change_text,
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
                fg=change_color,
                bg=colors.bg_elevated,
            )
            self._change_label.pack(side=tk.LEFT, padx=(Spacing.SM, 0))

        # Sparkline canvas
        self._sparkline_canvas = tk.Canvas(
            self,
            width=120,
            height=30,
            bg=colors.bg_elevated,
            highlightthickness=0,
        )
        self._sparkline_canvas.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

    def set_sparkline(self, data: List[float]) -> None:
        """Set sparkline data."""
        theme = get_theme()
        colors = theme.colors

        self._sparkline_canvas.delete("all")

        if not data or len(data) < 2:
            return

        width = self._sparkline_canvas.winfo_width() or 120
        height = 30

        min_val = min(data)
        max_val = max(data)
        val_range = max_val - min_val if max_val != min_val else 1

        points = []
        for i, val in enumerate(data):
            x = (i / (len(data) - 1)) * width
            y = height - 5 - ((val - min_val) / val_range) * (height - 10)
            points.append((x, y))

        # Determine trend color
        trend_color = colors.bullish if data[-1] >= data[0] else colors.bearish

        # Draw line
        for i in range(len(points) - 1):
            self._sparkline_canvas.create_line(
                points[i][0], points[i][1],
                points[i + 1][0], points[i + 1][1],
                fill=trend_color,
                width=2,
            )

    def set_value(self, value: str, change: float = None) -> None:
        """Update the displayed value."""
        theme = get_theme()
        colors = theme.colors

        self._value_label.config(text=value)

        if change is not None and hasattr(self, '_change_label'):
            change_color = colors.bullish if change >= 0 else colors.bearish
            arrow = "▲" if change >= 0 else "▼"
            self._change_label.config(
                text=f"{arrow} {abs(change):.2f}%",
                fg=change_color,
            )


class HorizontalBarChart(tk.Canvas):
    """
    Horizontal bar chart for factor exposures and comparisons.

    Features:
    - Centered zero line
    - Value labels
    - Color coding by sign
    """

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 300,
        height: int = 200,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._data = []  # List of (label, value) tuples

        self.bind('<Configure>', self._on_resize)

    def _on_resize(self, event):
        """Handle resize."""
        self._width = event.width
        self._height = event.height
        if self._data:
            self.set_data(self._data)

    def set_data(self, data: List[Tuple[str, float]]) -> None:
        """Set chart data: [(label, value), ...]"""
        self._data = data
        self.delete("all")

        if not data:
            return

        self._draw_chart()

    def _draw_chart(self) -> None:
        """Draw the horizontal bar chart."""
        theme = get_theme()
        colors = theme.colors

        if not self._data:
            return

        padding = {'left': 80, 'right': 50, 'top': 15, 'bottom': 15}
        chart_width = self._width - padding['left'] - padding['right']
        chart_height = self._height - padding['top'] - padding['bottom']

        n_bars = len(self._data)
        bar_height = min(25, (chart_height - (n_bars - 1) * 5) / n_bars)
        gap = 5

        max_abs = max(abs(v) for _, v in self._data) if self._data else 1
        if max_abs == 0:
            max_abs = 1

        center_x = padding['left'] + chart_width / 2

        # Draw center line
        self.create_line(
            center_x, padding['top'],
            center_x, self._height - padding['bottom'],
            fill=colors.fg_muted,
            dash=(2, 2),
        )

        for i, (label, value) in enumerate(self._data):
            y = padding['top'] + i * (bar_height + gap)

            # Draw label
            self.create_text(
                padding['left'] - 5, y + bar_height / 2,
                text=label,
                fill=colors.fg_secondary,
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                anchor="e",
            )

            # Draw bar
            bar_width = (abs(value) / max_abs) * (chart_width / 2)
            color = colors.bullish if value >= 0 else colors.bearish

            if value >= 0:
                x1 = center_x
                x2 = center_x + bar_width
            else:
                x1 = center_x - bar_width
                x2 = center_x

            self.create_rectangle(
                x1, y + 2,
                x2, y + bar_height - 2,
                fill=color,
                outline="",
            )

            # Draw value label
            value_x = x2 + 5 if value >= 0 else x1 - 5
            anchor = "w" if value >= 0 else "e"

            self.create_text(
                value_x, y + bar_height / 2,
                text=f"{value:+.2f}",
                fill=colors.fg_primary,
                font=theme.get_font(FontSize.XS, FontWeight.BOLD, "data"),
                anchor=anchor,
            )
