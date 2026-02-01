"""
QUANT_INDUSTRY_V1 Indicator Components

Visual indicators for confidence, status, direction, etc.

Rollback Plan: Delete this file
Tests Required: Visual rendering at various values
Failure Modes: Invalid value -> clamp to valid range
"""

import tkinter as tk
from typing import Optional
import logging

from ..theme import (
    get_theme, Spacing, FontSize, FontWeight,
    get_pnl_color, get_direction_color, get_confidence_color,
    get_severity_color, get_regime_color,
)

logger = logging.getLogger(__name__)


class ProgressBar(tk.Canvas):
    """
    Horizontal progress bar.

    Usage:
        bar = ProgressBar(parent, value=0.75, width=100)
        bar.set_value(0.5)
    """

    def __init__(
        self,
        parent: tk.Widget,
        value: float = 0.0,
        width: int = 100,
        height: int = 8,
        show_text: bool = False,
        color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        self._width = width
        self._height = height
        self._show_text = show_text
        self._custom_color = color

        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)

        super().__init__(parent, **kwargs)

        self._value = 0.0
        self._bg_rect = None
        self._fg_rect = None
        self._text_id = None

        self._draw()
        self.set_value(value)

    def _draw(self) -> None:
        """Draw the progress bar background."""
        theme = get_theme()
        colors = theme.colors

        # Background track
        self._bg_rect = self.create_rectangle(
            0, 0, self._width, self._height,
            fill=colors.bg_tertiary,
            outline="",
        )

        # Foreground bar
        self._fg_rect = self.create_rectangle(
            0, 0, 0, self._height,
            fill=self._custom_color or colors.accent_primary,
            outline="",
        )

        # Text (if enabled)
        if self._show_text:
            self._text_id = self.create_text(
                self._width // 2, self._height // 2,
                text="0%",
                fill=colors.fg_primary,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            )

    def set_value(self, value: float) -> None:
        """Set progress value (0.0 to 1.0)."""
        self._value = max(0.0, min(1.0, value))
        fill_width = int(self._width * self._value)

        self.coords(self._fg_rect, 0, 0, fill_width, self._height)

        if self._show_text:
            self.itemconfig(self._text_id, text=f"{int(self._value * 100)}%")

    def set_color(self, color: str) -> None:
        """Set bar color."""
        self.itemconfig(self._fg_rect, fill=color)


class ConfidenceBar(tk.Frame):
    """
    Confidence indicator with color coding.

    Usage:
        bar = ConfidenceBar(parent, confidence=0.85)
    """

    def __init__(
        self,
        parent: tk.Widget,
        confidence: float = 0.0,
        width: int = 80,
        height: int = 12,
        show_value: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._show_value = show_value

        # Canvas for bar
        self._canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            bg=colors.bg_secondary,
            highlightthickness=0,
        )
        self._canvas.pack(side=tk.LEFT)

        # Draw background
        self._bg_rect = self._canvas.create_rectangle(
            0, 0, width, height,
            fill=colors.bg_tertiary,
            outline="",
        )
        self._fg_rect = self._canvas.create_rectangle(
            0, 0, 0, height,
            fill=colors.confidence_mid,
            outline="",
        )

        # Value label
        if show_value:
            self._value_label = tk.Label(
                self,
                text="0%",
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
                fg=colors.fg_secondary,
                bg=colors.bg_secondary,
                width=4,
            )
            self._value_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

        self.set_confidence(confidence)

    def set_confidence(self, confidence: float) -> None:
        """Set confidence value (0.0 to 1.0)."""
        confidence = max(0.0, min(1.0, confidence))
        theme = get_theme()
        colors = theme.colors

        # Update bar
        fill_width = int(self._width * confidence)
        color = get_confidence_color(confidence, colors)

        self._canvas.coords(self._fg_rect, 0, 0, fill_width, self._height)
        self._canvas.itemconfig(self._fg_rect, fill=color)

        # Update label
        if self._show_value:
            self._value_label.config(
                text=f"{int(confidence * 100)}%",
                fg=color,
            )


class StatusBadge(tk.Label):
    """
    Status badge with semantic coloring.

    Usage:
        badge = StatusBadge(parent, status="success", text="Active")
    """

    def __init__(
        self,
        parent: tk.Widget,
        status: str = "info",
        text: str = "",
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Get status color
        fg_color = get_severity_color(status, colors)

        # Background is slightly tinted
        bg_color = colors.bg_tertiary

        kwargs.setdefault('font', theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"))
        kwargs.setdefault('fg', fg_color)
        kwargs.setdefault('bg', bg_color)
        kwargs.setdefault('padx', Spacing.SM)
        kwargs.setdefault('pady', 2)

        super().__init__(parent, text=text, **kwargs)

        self._status = status

    def set_status(self, status: str, text: str = None) -> None:
        """Update status."""
        theme = get_theme()
        colors = theme.colors

        self._status = status
        fg_color = get_severity_color(status, colors)
        self.config(fg=fg_color)

        if text is not None:
            self.config(text=text)


class DirectionIndicator(tk.Frame):
    """
    Trading direction indicator with arrow and label.

    Usage:
        indicator = DirectionIndicator(parent, direction="LONG")
    """

    ARROWS = {
        "LONG": "\u25B2",      # ▲
        "SHORT": "\u25BC",     # ▼
        "NEUTRAL": "\u25CF",   # [*]
        "BUY": "\u25B2",
        "SELL": "\u25BC",
        "HOLD": "\u25CF",
    }

    def __init__(
        self,
        parent: tk.Widget,
        direction: str = "NEUTRAL",
        show_label: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, **kwargs)

        self._show_label = show_label

        # Arrow
        self._arrow_label = tk.Label(
            self,
            text=self.ARROWS.get(direction.upper(), self.ARROWS["NEUTRAL"]),
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "data"),
            fg=get_direction_color(direction, colors),
            bg=colors.bg_secondary,
        )
        self._arrow_label.pack(side=tk.LEFT)

        # Label
        if show_label:
            self._text_label = tk.Label(
                self,
                text=direction.upper(),
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=get_direction_color(direction, colors),
                bg=colors.bg_secondary,
            )
            self._text_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

    def set_direction(self, direction: str) -> None:
        """Update direction."""
        theme = get_theme()
        colors = theme.colors

        arrow = self.ARROWS.get(direction.upper(), self.ARROWS["NEUTRAL"])
        color = get_direction_color(direction, colors)

        self._arrow_label.config(text=arrow, fg=color)
        if self._show_label:
            self._text_label.config(text=direction.upper(), fg=color)


class RegimeBadge(tk.Label):
    """
    Market regime badge.

    Usage:
        badge = RegimeBadge(parent, regime="bull_trend", confidence=0.75)
    """

    def __init__(
        self,
        parent: tk.Widget,
        regime: str = "UNKNOWN",
        confidence: float = 0.5,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        fg_color = get_regime_color(regime, colors)

        kwargs.setdefault('font', theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"))
        kwargs.setdefault('fg', fg_color)
        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('padx', Spacing.MD)
        kwargs.setdefault('pady', Spacing.XS)

        text = f"{regime.upper().replace('_', ' ')} ({int(confidence*100)}%)"

        super().__init__(parent, text=text, **kwargs)

        self._regime = regime
        self._confidence = confidence

    def set_regime(self, regime: str, confidence: float = None) -> None:
        """Update regime."""
        theme = get_theme()
        colors = theme.colors

        self._regime = regime
        if confidence is not None:
            self._confidence = confidence

        fg_color = get_regime_color(regime, colors)
        text = f"{regime.upper().replace('_', ' ')} ({int(self._confidence*100)}%)"

        self.config(text=text, fg=fg_color)


class PnLDisplay(tk.Frame):
    """
    P&L display with color coding.

    Usage:
        pnl = PnLDisplay(parent, value=1234.56, show_percent=True, percent=-0.02)
    """

    def __init__(
        self,
        parent: tk.Widget,
        value: float = 0.0,
        show_percent: bool = False,
        percent: float = 0.0,
        prefix: str = "$",
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, **kwargs)

        self._prefix = prefix
        self._show_percent = show_percent

        # Value label
        self._value_label = tk.Label(
            self,
            text="$0.00",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_secondary,
        )
        self._value_label.pack(side=tk.LEFT)

        # Percent label
        if show_percent:
            self._percent_label = tk.Label(
                self,
                text="(0.00%)",
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
                fg=colors.fg_secondary,
                bg=colors.bg_secondary,
            )
            self._percent_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

        self.set_value(value, percent)

    def set_value(self, value: float, percent: float = None) -> None:
        """Update P&L value."""
        theme = get_theme()
        colors = theme.colors

        color = get_pnl_color(value, colors)
        sign = '+' if value >= 0 else ''

        # Format value
        if abs(value) >= 1_000_000:
            text = f"{sign}{self._prefix}{value/1_000_000:.2f}M"
        elif abs(value) >= 1_000:
            text = f"{sign}{self._prefix}{value/1_000:.2f}K"
        else:
            text = f"{sign}{self._prefix}{value:.2f}"

        self._value_label.config(text=text, fg=color)

        # Percent
        if self._show_percent and percent is not None:
            pct_sign = '+' if percent >= 0 else ''
            self._percent_label.config(
                text=f"({pct_sign}{percent*100:.2f}%)",
                fg=color,
            )


class LoadingSpinner(tk.Label):
    """
    Animated loading spinner.

    Usage:
        spinner = LoadingSpinner(parent)
        spinner.start()
        ...
        spinner.stop()
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, parent: tk.Widget, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('font', theme.get_font(FontSize.LG, FontWeight.NORMAL, "data"))
        kwargs.setdefault('fg', colors.accent_primary)
        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, text=self.FRAMES[0], **kwargs)

        self._frame_index = 0
        self._running = False
        self._after_id = None

    def start(self) -> None:
        """Start animation."""
        if not self._running:
            self._running = True
            self._animate()

    def stop(self) -> None:
        """Stop animation."""
        self._running = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def _animate(self) -> None:
        """Animate the spinner."""
        if not self._running:
            return

        self._frame_index = (self._frame_index + 1) % len(self.FRAMES)
        self.config(text=self.FRAMES[self._frame_index])
        self._after_id = self.after(100, self._animate)
