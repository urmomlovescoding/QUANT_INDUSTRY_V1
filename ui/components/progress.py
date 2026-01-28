"""
QUANT_INDUSTRY_V1 Progress Indicators

Professional progress indicators, loaders, and skeleton screens.
"""

import tkinter as tk
from typing import Optional, Callable
import math
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class CircularProgress(tk.Canvas):
    """
    Circular progress indicator.

    Features:
    - Determinate and indeterminate modes
    - Customizable colors and size
    - Optional center text
    - Smooth animation
    """

    def __init__(
        self,
        parent: tk.Widget,
        size: int = 40,
        thickness: int = 4,
        value: float = 0,
        indeterminate: bool = False,
        show_text: bool = False,
        color: str = None,
        track_color: str = None,
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
        self._size = size
        self._thickness = thickness
        self._value = value
        self._indeterminate = indeterminate
        self._show_text = show_text
        self._color = color or colors.accent_primary
        self._track_color = track_color or colors.bg_tertiary

        self._angle = 0
        self._animation_id = None

        self._draw()

        if indeterminate:
            self._animate()

    def _draw(self) -> None:
        """Draw the progress indicator."""
        self.delete("all")

        size = self._size
        thickness = self._thickness
        padding = 2

        cx = size // 2
        cy = size // 2
        radius = (size - padding * 2 - thickness) // 2

        # Track
        self.create_arc(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            start=0, extent=360,
            style=tk.ARC,
            width=thickness,
            outline=self._track_color,
        )

        if self._indeterminate:
            # Animated arc
            extent = 90
            start = self._angle
            self.create_arc(
                cx - radius, cy - radius,
                cx + radius, cy + radius,
                start=start, extent=extent,
                style=tk.ARC,
                width=thickness,
                outline=self._color,
            )
        else:
            # Progress arc
            extent = -self._value * 360  # Negative for clockwise
            self.create_arc(
                cx - radius, cy - radius,
                cx + radius, cy + radius,
                start=90, extent=extent,
                style=tk.ARC,
                width=thickness,
                outline=self._color,
            )

        # Center text
        if self._show_text and not self._indeterminate:
            text = f"{int(self._value * 100)}%"
            self.create_text(
                cx, cy,
                text=text,
                font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "data"),
                fill=self._colors.fg_primary,
            )

    def _animate(self) -> None:
        """Animate indeterminate progress."""
        self._angle = (self._angle + 10) % 360
        self._draw()
        self._animation_id = self.after(30, self._animate)

    def set_value(self, value: float) -> None:
        """Set progress value (0.0 to 1.0)."""
        self._value = max(0, min(1, value))
        if not self._indeterminate:
            self._draw()

    def set_indeterminate(self, indeterminate: bool) -> None:
        """Set indeterminate mode."""
        if indeterminate and not self._indeterminate:
            self._indeterminate = True
            self._animate()
        elif not indeterminate and self._indeterminate:
            self._indeterminate = False
            if self._animation_id:
                self.after_cancel(self._animation_id)
            self._draw()

    def destroy(self) -> None:
        """Clean up."""
        if self._animation_id:
            self.after_cancel(self._animation_id)
        super().destroy()


class LinearProgress(tk.Canvas):
    """
    Linear progress bar.

    Features:
    - Determinate and indeterminate modes
    - Customizable height and colors
    - Rounded corners
    - Smooth animation
    """

    def __init__(
        self,
        parent: tk.Widget,
        height: int = 4,
        value: float = 0,
        indeterminate: bool = False,
        color: str = None,
        track_color: str = None,
        rounded: bool = True,
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
        self._height = height
        self._value = value
        self._indeterminate = indeterminate
        self._color = color or colors.accent_primary
        self._track_color = track_color or colors.bg_tertiary
        self._rounded = rounded

        self._position = 0
        self._animation_id = None

        self.bind('<Configure>', lambda e: self._draw())

        if indeterminate:
            self._animate()

    def _draw(self) -> None:
        """Draw the progress bar."""
        self.delete("all")

        width = self.winfo_width()
        height = self._height

        if width <= 1:
            return

        radius = height // 2 if self._rounded else 0

        # Track
        self._draw_rounded_rect(0, 0, width, height, radius, self._track_color)

        if self._indeterminate:
            # Animated segment
            seg_width = width // 3
            x = int(self._position * (width + seg_width)) - seg_width
            self._draw_rounded_rect(max(0, x), 0, min(width, x + seg_width), height, radius, self._color)
        else:
            # Progress bar
            progress_width = int(width * self._value)
            if progress_width > 0:
                self._draw_rounded_rect(0, 0, progress_width, height, radius, self._color)

    def _draw_rounded_rect(
        self, x1: int, y1: int, x2: int, y2: int, radius: int, fill: str
    ) -> None:
        """Draw a rounded rectangle."""
        if radius == 0:
            self.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
        else:
            # Simple rectangle for small sizes
            self.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")

    def _animate(self) -> None:
        """Animate indeterminate progress."""
        self._position = (self._position + 0.02) % 1.5
        self._draw()
        self._animation_id = self.after(20, self._animate)

    def set_value(self, value: float) -> None:
        """Set progress value (0.0 to 1.0)."""
        self._value = max(0, min(1, value))
        if not self._indeterminate:
            self._draw()

    def set_indeterminate(self, indeterminate: bool) -> None:
        """Set indeterminate mode."""
        if indeterminate and not self._indeterminate:
            self._indeterminate = True
            self._animate()
        elif not indeterminate and self._indeterminate:
            self._indeterminate = False
            if self._animation_id:
                self.after_cancel(self._animation_id)
            self._draw()

    def destroy(self) -> None:
        """Clean up."""
        if self._animation_id:
            self.after_cancel(self._animation_id)
        super().destroy()


class SkeletonLoader(tk.Frame):
    """
    Skeleton loading placeholder.

    Creates animated placeholder elements while content loads.
    """

    def __init__(
        self,
        parent: tk.Widget,
        lines: int = 3,
        line_height: int = 16,
        avatar: bool = False,
        avatar_size: int = 40,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._lines = lines
        self._line_height = line_height
        self._avatar = avatar
        self._avatar_size = avatar_size

        self._shimmer_position = 0
        self._animation_id = None

        self._setup_ui()
        self._animate()

    def _setup_ui(self) -> None:
        """Build the skeleton UI."""
        colors = self._colors

        content = tk.Frame(self, bg=colors.bg_elevated)
        content.pack(fill=tk.BOTH, expand=True, padx=Spacing.SM, pady=Spacing.SM)

        if self._avatar:
            # Avatar + lines layout
            left = tk.Frame(content, bg=colors.bg_elevated)
            left.pack(side=tk.LEFT, padx=(0, Spacing.MD))

            self._avatar_canvas = tk.Canvas(
                left,
                width=self._avatar_size,
                height=self._avatar_size,
                bg=colors.bg_elevated,
                highlightthickness=0,
            )
            self._avatar_canvas.pack()

            right = tk.Frame(content, bg=colors.bg_elevated)
            right.pack(side=tk.LEFT, fill=tk.X, expand=True)
            lines_parent = right
        else:
            lines_parent = content

        # Lines
        self._line_canvases = []
        widths = [1.0, 0.8, 0.6]  # Varying line widths

        for i in range(self._lines):
            width_ratio = widths[i % len(widths)]
            canvas = tk.Canvas(
                lines_parent,
                height=self._line_height,
                bg=colors.bg_elevated,
                highlightthickness=0,
            )
            canvas.pack(fill=tk.X, pady=2)
            canvas.width_ratio = width_ratio
            self._line_canvases.append(canvas)

        # Bind resize
        for canvas in self._line_canvases:
            canvas.bind('<Configure>', lambda e: self._draw())

    def _draw(self) -> None:
        """Draw skeleton elements."""
        colors = self._colors
        base_color = colors.bg_tertiary
        shimmer_color = colors.bg_secondary

        # Avatar
        if self._avatar:
            self._avatar_canvas.delete("all")
            size = self._avatar_size
            self._avatar_canvas.create_oval(
                2, 2, size - 2, size - 2,
                fill=base_color, outline=""
            )

        # Lines
        for canvas in self._line_canvases:
            canvas.delete("all")
            width = canvas.winfo_width()
            height = self._line_height

            if width <= 1:
                continue

            line_width = int(width * canvas.width_ratio)

            # Base rectangle
            canvas.create_rectangle(
                0, 4, line_width, height - 4,
                fill=base_color, outline=""
            )

            # Shimmer effect
            shimmer_width = 100
            shimmer_x = int(self._shimmer_position * (line_width + shimmer_width)) - shimmer_width

            if 0 <= shimmer_x < line_width:
                # Gradient effect simulation
                for i in range(shimmer_width):
                    alpha = 1 - abs(i - shimmer_width // 2) / (shimmer_width // 2)
                    if shimmer_x + i < line_width:
                        # Simple line for shimmer
                        canvas.create_line(
                            shimmer_x + i, 4,
                            shimmer_x + i, height - 4,
                            fill=shimmer_color,
                        )

    def _animate(self) -> None:
        """Animate shimmer effect."""
        self._shimmer_position = (self._shimmer_position + 0.03) % 1.5
        self._draw()
        self._animation_id = self.after(30, self._animate)

    def destroy(self) -> None:
        """Clean up."""
        if self._animation_id:
            self.after_cancel(self._animation_id)
        super().destroy()


class PulsingDot(tk.Canvas):
    """
    Simple pulsing dot indicator.

    Shows activity/loading state with a pulsing animation.
    """

    def __init__(
        self,
        parent: tk.Widget,
        size: int = 12,
        color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        super().__init__(
            parent,
            width=size,
            height=size,
            bg=kwargs.get('bg', colors.bg_elevated),
            highlightthickness=0,
        )

        self._colors = colors
        self._size = size
        self._color = color or colors.accent_primary
        self._scale = 1.0
        self._growing = True
        self._animation_id = None

        self._draw()
        self._animate()

    def _draw(self) -> None:
        """Draw the dot."""
        self.delete("all")

        size = self._size
        cx = size // 2
        cy = size // 2

        scaled_size = int((size // 2 - 2) * self._scale)
        self.create_oval(
            cx - scaled_size, cy - scaled_size,
            cx + scaled_size, cy + scaled_size,
            fill=self._color, outline=""
        )

    def _animate(self) -> None:
        """Animate pulse."""
        if self._growing:
            self._scale += 0.05
            if self._scale >= 1.0:
                self._growing = False
        else:
            self._scale -= 0.05
            if self._scale <= 0.5:
                self._growing = True

        self._draw()
        self._animation_id = self.after(50, self._animate)

    def destroy(self) -> None:
        """Clean up."""
        if self._animation_id:
            self.after_cancel(self._animation_id)
        super().destroy()


class DotsLoader(tk.Frame):
    """
    Three dots loading animation.
    """

    def __init__(
        self,
        parent: tk.Widget,
        dot_size: int = 8,
        spacing: int = 4,
        color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._dot_size = dot_size
        self._spacing = spacing
        self._color = color or colors.accent_primary

        self._dots = []
        self._current_dot = 0
        self._animation_id = None

        self._setup_ui()
        self._animate()

    def _setup_ui(self) -> None:
        """Build the dots UI."""
        for i in range(3):
            canvas = tk.Canvas(
                self,
                width=self._dot_size,
                height=self._dot_size,
                bg=self['bg'],
                highlightthickness=0,
            )
            canvas.pack(side=tk.LEFT, padx=self._spacing // 2)
            self._dots.append(canvas)

        self._draw()

    def _draw(self) -> None:
        """Draw the dots."""
        for i, canvas in enumerate(self._dots):
            canvas.delete("all")
            size = self._dot_size

            # Active dot is fully opaque, others are faded
            if i == self._current_dot:
                color = self._color
            else:
                color = self._colors.bg_tertiary

            canvas.create_oval(
                2, 2, size - 2, size - 2,
                fill=color, outline=""
            )

    def _animate(self) -> None:
        """Animate dots."""
        self._current_dot = (self._current_dot + 1) % 3
        self._draw()
        self._animation_id = self.after(300, self._animate)

    def destroy(self) -> None:
        """Clean up."""
        if self._animation_id:
            self.after_cancel(self._animation_id)
        super().destroy()


class LoadingOverlay(tk.Frame):
    """
    Full overlay loading indicator.

    Covers parent widget with semi-transparent overlay and spinner.
    """

    def __init__(
        self,
        parent: tk.Widget,
        message: str = "Loading...",
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_primary)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._message = message

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the overlay UI."""
        colors = self._colors
        theme = self._theme

        # Center container
        center = tk.Frame(self, bg=colors.bg_elevated)
        center.place(relx=0.5, rely=0.5, anchor="center")

        inner = tk.Frame(center, bg=colors.bg_elevated)
        inner.pack(padx=Spacing.XL, pady=Spacing.LG)

        # Spinner
        self._spinner = CircularProgress(
            inner,
            size=48,
            thickness=4,
            indeterminate=True,
        )
        self._spinner.pack(pady=Spacing.MD)

        # Message
        tk.Label(
            inner,
            text=self._message,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
        ).pack()

    def set_message(self, message: str) -> None:
        """Update loading message."""
        self._message = message
        # Rebuild UI
        for widget in self.winfo_children():
            widget.destroy()
        self._setup_ui()

    def destroy(self) -> None:
        """Clean up."""
        if hasattr(self, '_spinner'):
            self._spinner.destroy()
        super().destroy()


class ProgressWithLabel(tk.Frame):
    """
    Progress bar with label and percentage text.
    """

    def __init__(
        self,
        parent: tk.Widget,
        label: str = "",
        value: float = 0,
        show_percent: bool = True,
        color: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._label = label
        self._value = value
        self._show_percent = show_percent
        self._color = color

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the progress UI."""
        colors = self._colors
        theme = self._theme

        # Label row
        label_row = tk.Frame(self, bg=colors.bg_elevated)
        label_row.pack(fill=tk.X)

        tk.Label(
            label_row,
            text=self._label,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        if self._show_percent:
            self._percent_label = tk.Label(
                label_row,
                text=f"{int(self._value * 100)}%",
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
                fg=colors.fg_primary,
                bg=colors.bg_elevated,
            )
            self._percent_label.pack(side=tk.RIGHT)

        # Progress bar
        self._progress = LinearProgress(
            self,
            height=6,
            value=self._value,
            color=self._color,
        )
        self._progress.pack(fill=tk.X, pady=(Spacing.XS, 0))

    def set_value(self, value: float) -> None:
        """Update progress value."""
        self._value = max(0, min(1, value))
        self._progress.set_value(self._value)
        if self._show_percent:
            self._percent_label.config(text=f"{int(self._value * 100)}%")

    def set_label(self, label: str) -> None:
        """Update label text."""
        self._label = label
        # Rebuild to update
        for widget in self.winfo_children():
            widget.destroy()
        self._setup_ui()
