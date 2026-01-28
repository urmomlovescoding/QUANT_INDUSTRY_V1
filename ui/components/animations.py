"""
QUANT_INDUSTRY_V1 Animation Utilities

Smooth animations and transitions for professional UI polish.
"""

import tkinter as tk
from typing import Callable, Optional, Any
import math
import logging

from ..theme import get_theme

logger = logging.getLogger(__name__)


class EasingFunctions:
    """Common easing functions for smooth animations."""

    @staticmethod
    def linear(t: float) -> float:
        """Linear (no easing)."""
        return t

    @staticmethod
    def ease_in_quad(t: float) -> float:
        """Ease in quadratic."""
        return t * t

    @staticmethod
    def ease_out_quad(t: float) -> float:
        """Ease out quadratic."""
        return t * (2 - t)

    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        """Ease in-out quadratic."""
        if t < 0.5:
            return 2 * t * t
        return -1 + (4 - 2 * t) * t

    @staticmethod
    def ease_out_cubic(t: float) -> float:
        """Ease out cubic."""
        t = t - 1
        return t * t * t + 1

    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        """Ease in-out cubic."""
        if t < 0.5:
            return 4 * t * t * t
        return (t - 1) * (2 * t - 2) * (2 * t - 2) + 1

    @staticmethod
    def ease_out_elastic(t: float) -> float:
        """Ease out elastic (bounce)."""
        if t == 0 or t == 1:
            return t
        p = 0.3
        return pow(2, -10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1


class Animator:
    """
    Utility class for animating widget properties.

    Usage:
        animator = Animator(widget)
        animator.animate_property('width', start=0, end=100, duration=300)
    """

    def __init__(self, widget: tk.Widget):
        self.widget = widget
        self._animations = {}
        self._animation_id = 0

    def animate_value(
        self,
        start: float,
        end: float,
        duration: int,
        callback: Callable[[float], None],
        easing: Callable[[float], float] = None,
        on_complete: Callable[[], None] = None,
    ) -> int:
        """
        Animate a value over time.

        Args:
            start: Starting value
            end: Ending value
            duration: Duration in milliseconds
            callback: Called each frame with current value
            easing: Easing function (default: ease_out_quad)
            on_complete: Called when animation completes

        Returns:
            Animation ID for cancellation
        """
        easing = easing or EasingFunctions.ease_out_quad

        self._animation_id += 1
        anim_id = self._animation_id

        frame_interval = 16  # ~60fps
        total_frames = max(1, duration // frame_interval)
        current_frame = [0]

        def animate():
            if anim_id not in self._animations:
                return  # Cancelled

            progress = min(1.0, current_frame[0] / total_frames)
            eased = easing(progress)
            current_value = start + (end - start) * eased

            callback(current_value)

            current_frame[0] += 1

            if progress < 1.0:
                self.widget.after(frame_interval, animate)
            else:
                del self._animations[anim_id]
                if on_complete:
                    on_complete()

        self._animations[anim_id] = True
        animate()

        return anim_id

    def cancel(self, anim_id: int) -> None:
        """Cancel an animation."""
        if anim_id in self._animations:
            del self._animations[anim_id]

    def cancel_all(self) -> None:
        """Cancel all animations."""
        self._animations.clear()


class FadeIn(tk.Frame):
    """Frame that fades in when shown."""

    def __init__(self, parent: tk.Widget, duration: int = 200, **kwargs):
        super().__init__(parent, **kwargs)

        self._duration = duration
        self._animator = Animator(self)
        self._opacity = 0

        # Start invisible
        self.configure(highlightthickness=0)

    def show(self) -> None:
        """Fade in the frame."""
        theme = get_theme()
        colors = theme.colors

        # Animate by gradually changing background alpha simulation
        def update(value):
            # Tkinter doesn't support true opacity, but we can simulate
            # by interpolating background colors
            self._opacity = value

        self._animator.animate_value(
            0, 1, self._duration, update,
            easing=EasingFunctions.ease_out_quad
        )


class PulsingIndicator(tk.Canvas):
    """Animated pulsing indicator."""

    def __init__(
        self,
        parent: tk.Widget,
        size: int = 12,
        color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('width', size)
        kwargs.setdefault('height', size)
        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('highlightthickness', 0)

        super().__init__(parent, **kwargs)

        self._size = size
        self._color = color or colors.bullish
        self._running = False
        self._phase = 0

        self._draw()

    def _draw(self) -> None:
        """Draw the indicator."""
        self.delete("all")

        center = self._size / 2
        base_radius = self._size / 4

        # Pulsing effect
        pulse = 0.3 * math.sin(self._phase)
        radius = base_radius * (1 + pulse)

        self.create_oval(
            center - radius, center - radius,
            center + radius, center + radius,
            fill=self._color, outline=""
        )

        # Glow effect
        glow_radius = radius * 1.5
        self.create_oval(
            center - glow_radius, center - glow_radius,
            center + glow_radius, center + glow_radius,
            fill="", outline=self._color, width=1,
            stipple="gray50"
        )

    def start(self) -> None:
        """Start pulsing animation."""
        if not self._running:
            self._running = True
            self._animate()

    def stop(self) -> None:
        """Stop pulsing animation."""
        self._running = False

    def _animate(self) -> None:
        """Animation loop."""
        if not self._running:
            return

        self._phase += 0.15
        self._draw()

        self.after(33, self._animate)  # ~30fps


class CountUpLabel(tk.Label):
    """Label that animates number counting up."""

    def __init__(
        self,
        parent: tk.Widget,
        value: float = 0,
        format_str: str = "{:.2f}",
        duration: int = 500,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('font', theme.get_font(14, "bold", "data"))
        kwargs.setdefault('fg', colors.fg_primary)
        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, text=format_str.format(value), **kwargs)

        self._value = value
        self._format_str = format_str
        self._duration = duration
        self._animator = Animator(self)

    def set_value(self, value: float, animate: bool = True) -> None:
        """Set value with optional animation."""
        if not animate:
            self._value = value
            self.config(text=self._format_str.format(value))
            return

        start = self._value
        self._value = value

        def update(current):
            self.config(text=self._format_str.format(current))

        self._animator.animate_value(
            start, value, self._duration, update,
            easing=EasingFunctions.ease_out_cubic
        )


class ProgressAnimator(tk.Canvas):
    """Animated progress bar."""

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 200,
        height: int = 8,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)
        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('highlightthickness', 0)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._value = 0
        self._target = 0
        self._animator = Animator(self)

        # Background
        self._bg_rect = self.create_rectangle(
            0, 0, width, height,
            fill=colors.bg_tertiary, outline=""
        )

        # Foreground
        self._fg_rect = self.create_rectangle(
            0, 0, 0, height,
            fill=colors.accent_primary, outline=""
        )

    def set_progress(self, value: float, animate: bool = True) -> None:
        """Set progress value (0-1) with optional animation."""
        value = max(0, min(1, value))
        self._target = value

        if not animate:
            self._value = value
            self._update_bar()
            return

        def update(current):
            self._value = current
            self._update_bar()

        self._animator.animate_value(
            self._value, value, 300, update,
            easing=EasingFunctions.ease_out_quad
        )

    def _update_bar(self) -> None:
        """Update the progress bar width."""
        fill_width = int(self._width * self._value)
        self.coords(self._fg_rect, 0, 0, fill_width, self._height)


class TypewriterLabel(tk.Label):
    """Label that displays text with typewriter effect."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "",
        chars_per_second: int = 30,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('font', theme.get_font(11, "normal", "ui"))
        kwargs.setdefault('fg', colors.fg_primary)
        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('anchor', 'w')

        super().__init__(parent, text="", **kwargs)

        self._full_text = text
        self._current_index = 0
        self._interval = 1000 // chars_per_second

        if text:
            self._type_next()

    def _type_next(self) -> None:
        """Type next character."""
        if self._current_index < len(self._full_text):
            self._current_index += 1
            self.config(text=self._full_text[:self._current_index])
            self.after(self._interval, self._type_next)

    def set_text(self, text: str) -> None:
        """Set new text with typewriter effect."""
        self._full_text = text
        self._current_index = 0
        self._type_next()


class ShimmerEffect(tk.Canvas):
    """Loading shimmer effect placeholder."""

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 200,
        height: int = 20,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('width', width)
        kwargs.setdefault('height', height)
        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('highlightthickness', 0)

        super().__init__(parent, **kwargs)

        self._width = width
        self._height = height
        self._position = -width // 3
        self._running = False

        self._draw()

    def _draw(self) -> None:
        """Draw shimmer effect."""
        self.delete("all")

        theme = get_theme()
        colors = theme.colors

        # Base
        self.create_rectangle(
            0, 0, self._width, self._height,
            fill=colors.bg_tertiary, outline=""
        )

        # Shimmer highlight
        shimmer_width = self._width // 3
        self.create_rectangle(
            self._position, 0,
            self._position + shimmer_width, self._height,
            fill=colors.bg_hover, outline="",
            stipple="gray50"
        )

    def start(self) -> None:
        """Start shimmer animation."""
        if not self._running:
            self._running = True
            self._animate()

    def stop(self) -> None:
        """Stop shimmer animation."""
        self._running = False

    def _animate(self) -> None:
        """Animation loop."""
        if not self._running:
            return

        self._position += 5
        if self._position > self._width:
            self._position = -self._width // 3

        self._draw()
        self.after(33, self._animate)
