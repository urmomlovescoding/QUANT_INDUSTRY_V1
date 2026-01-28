"""
QUANT_INDUSTRY_V1 Base UI Components

Core styled widgets built on Tkinter.

Rollback Plan: Delete this file
Tests Required: Visual inspection, theme switching
Failure Modes: Missing font -> fallback to system font
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Tuple, Any
import logging

from ..theme import (
    get_theme, ThemeConfig, Spacing, FontSize, FontWeight,
    get_pnl_color, get_direction_color,
)

logger = logging.getLogger(__name__)


class StyledFrame(tk.Frame):
    """
    Themed frame with consistent styling.

    Usage:
        frame = StyledFrame(parent, padding="normal")
        frame.pack(fill=tk.BOTH, expand=True)
    """

    PADDING_PRESETS = {
        "none": (0, 0),
        "tight": (Spacing.XS, Spacing.SM),
        "normal": (Spacing.SM, Spacing.MD),
        "relaxed": (Spacing.MD, Spacing.LG),
        "section": (Spacing.LG, Spacing.XL),
    }

    def __init__(
        self,
        parent: tk.Widget,
        padding: str = "normal",
        bg: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Resolve padding
        if isinstance(padding, str):
            pad_y, pad_x = self.PADDING_PRESETS.get(padding, self.PADDING_PRESETS["normal"])
        elif isinstance(padding, tuple):
            pad_y, pad_x = padding
        else:
            pad_y = pad_x = padding

        # Apply styling
        kwargs.setdefault('bg', bg or colors.bg_primary)
        kwargs.setdefault('padx', pad_x)
        kwargs.setdefault('pady', pad_y)

        super().__init__(parent, **kwargs)


class Card(tk.Frame):
    """
    Elevated card container with optional title.

    Usage:
        card = Card(parent, title="Portfolio")
        content_frame = card.content
        label = tk.Label(content_frame, text="Hello")
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str = None,
        padding: str = "normal",
        elevated: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Card background
        bg = colors.bg_elevated if elevated else colors.bg_secondary
        kwargs.setdefault('bg', bg)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', colors.border_light)

        super().__init__(parent, **kwargs)

        # Resolve padding
        if isinstance(padding, str):
            pad_presets = StyledFrame.PADDING_PRESETS
            pad_y, pad_x = pad_presets.get(padding, pad_presets["normal"])
        else:
            pad_y = pad_x = padding

        # Title header
        self._title_frame = None
        self._title_label = None
        if title:
            self._title_frame = tk.Frame(self, bg=bg)
            self._title_frame.pack(fill=tk.X, padx=pad_x, pady=(pad_y, 0))

            self._title_label = tk.Label(
                self._title_frame,
                text=title,
                font=theme.get_font(FontSize.SUBTITLE, FontWeight.BOLD, "ui"),
                fg=colors.fg_primary,
                bg=bg,
                anchor="w",
            )
            self._title_label.pack(side=tk.LEFT)

            # Separator
            sep = tk.Frame(self, bg=colors.border_light, height=1)
            sep.pack(fill=tk.X, padx=pad_x, pady=(Spacing.SM, 0))

        # Content area
        self.content = tk.Frame(self, bg=bg, padx=pad_x, pady=pad_y)
        self.content.pack(fill=tk.BOTH, expand=True)

    def set_title(self, title: str) -> None:
        """Update card title."""
        if self._title_label:
            self._title_label.config(text=title)


class StyledLabel(tk.Label):
    """
    Themed label with preset styles.

    Usage:
        label = StyledLabel(parent, text="Hello", style="title")
        label = StyledLabel(parent, text="$100", style="pnl", value=100)
    """

    STYLE_PRESETS = {
        "body": {"size": FontSize.MD, "weight": FontWeight.NORMAL},
        "caption": {"size": FontSize.CAPTION, "weight": FontWeight.NORMAL, "muted": True},
        "title": {"size": FontSize.TITLE, "weight": FontWeight.BOLD},
        "heading": {"size": FontSize.HEADING, "weight": FontWeight.BOLD},
        "subtitle": {"size": FontSize.SUBTITLE, "weight": FontWeight.NORMAL},
        "mono": {"size": FontSize.MD, "weight": FontWeight.NORMAL, "family": "data"},
        "pnl": {"size": FontSize.MD, "weight": FontWeight.BOLD, "family": "data"},
        "direction": {"size": FontSize.MD, "weight": FontWeight.BOLD},
    }

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "",
        style: str = "body",
        value: Any = None,
        fg: str = None,
        bg: str = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Get style preset
        preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["body"])

        # Determine colors
        if fg is None:
            if preset.get("muted"):
                fg = colors.fg_muted
            elif style == "pnl" and value is not None:
                fg = get_pnl_color(float(value), colors)
            elif style == "direction" and value is not None:
                fg = get_direction_color(str(value), colors)
            else:
                fg = colors.fg_primary

        if bg is None:
            bg = colors.bg_primary

        # Font
        family = preset.get("family", "ui")
        font = theme.get_font(preset["size"], preset["weight"], family)

        # Apply configuration
        kwargs.setdefault('fg', fg)
        kwargs.setdefault('bg', bg)
        kwargs.setdefault('font', font)
        kwargs.setdefault('anchor', 'w')

        super().__init__(parent, text=text, **kwargs)

        self._style = style
        self._value = value

    def set_value(self, value: Any, text: str = None) -> None:
        """Update value and optionally text."""
        self._value = value
        theme = get_theme()
        colors = theme.colors

        if self._style == "pnl":
            self.config(fg=get_pnl_color(float(value), colors))
        elif self._style == "direction":
            self.config(fg=get_direction_color(str(value), colors))

        if text is not None:
            self.config(text=text)


class StyledButton(tk.Button):
    """
    Themed button with variants.

    Usage:
        btn = StyledButton(parent, text="Submit", variant="primary", command=on_click)
    """

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "",
        variant: str = "default",
        command: Callable = None,
        width: int = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Variant styling
        variants = {
            "default": {
                "bg": colors.bg_tertiary,
                "fg": colors.fg_primary,
                "activebackground": colors.bg_hover,
            },
            "primary": {
                "bg": colors.accent_primary,
                "fg": colors.fg_inverse,
                "activebackground": colors.accent_secondary,
            },
            "success": {
                "bg": colors.success,
                "fg": colors.fg_inverse,
                "activebackground": colors.bullish,
            },
            "danger": {
                "bg": colors.error,
                "fg": colors.fg_inverse,
                "activebackground": colors.bearish,
            },
            "ghost": {
                "bg": colors.bg_primary,
                "fg": colors.fg_secondary,
                "activebackground": colors.bg_hover,
            },
        }

        style_config = variants.get(variant, variants["default"])

        # Apply styling
        kwargs.setdefault('bg', style_config["bg"])
        kwargs.setdefault('fg', style_config["fg"])
        kwargs.setdefault('activebackground', style_config["activebackground"])
        kwargs.setdefault('activeforeground', style_config["fg"])
        kwargs.setdefault('font', theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"))
        kwargs.setdefault('relief', tk.FLAT)
        kwargs.setdefault('cursor', 'hand2')
        kwargs.setdefault('padx', Spacing.MD)
        kwargs.setdefault('pady', Spacing.XS)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('bd', 0)

        if width:
            kwargs['width'] = width

        super().__init__(parent, text=text, command=command, **kwargs)

        self._variant = variant

        # Bind hover effects
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event):
        """Handle mouse enter."""
        theme = get_theme()
        colors = theme.colors
        self.config(bg=colors.bg_hover if self._variant == "ghost" else self.cget('activebackground'))

    def _on_leave(self, event):
        """Handle mouse leave."""
        theme = get_theme()
        colors = theme.colors
        variants = {
            "default": colors.bg_tertiary,
            "primary": colors.accent_primary,
            "success": colors.success,
            "danger": colors.error,
            "ghost": colors.bg_primary,
        }
        self.config(bg=variants.get(self._variant, colors.bg_tertiary))


class StyledEntry(tk.Entry):
    """
    Themed text entry field.

    Usage:
        entry = StyledEntry(parent, placeholder="Enter symbol...")
    """

    def __init__(
        self,
        parent: tk.Widget,
        placeholder: str = "",
        width: int = 20,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        # Apply styling
        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('fg', colors.fg_primary)
        kwargs.setdefault('insertbackground', colors.fg_primary)
        kwargs.setdefault('font', theme.get_font(FontSize.MD, FontWeight.NORMAL, "data"))
        kwargs.setdefault('relief', tk.FLAT)
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', colors.border_light)
        kwargs.setdefault('highlightcolor', colors.border_focus)
        kwargs.setdefault('width', width)

        super().__init__(parent, **kwargs)

        self._placeholder = placeholder
        self._placeholder_color = colors.fg_muted
        self._fg_color = colors.fg_primary
        self._has_placeholder = False

        if placeholder:
            self._show_placeholder()
            self.bind('<FocusIn>', self._on_focus_in)
            self.bind('<FocusOut>', self._on_focus_out)

    def _show_placeholder(self) -> None:
        """Show placeholder text."""
        if not self.get():
            self._has_placeholder = True
            self.config(fg=self._placeholder_color)
            self.insert(0, self._placeholder)

    def _hide_placeholder(self) -> None:
        """Hide placeholder text."""
        if self._has_placeholder:
            self._has_placeholder = False
            self.delete(0, tk.END)
            self.config(fg=self._fg_color)

    def _on_focus_in(self, event) -> None:
        """Handle focus in."""
        self._hide_placeholder()

    def _on_focus_out(self, event) -> None:
        """Handle focus out."""
        if not self.get():
            self._show_placeholder()

    def get_value(self) -> str:
        """Get entry value, excluding placeholder."""
        if self._has_placeholder:
            return ""
        return self.get()

    def set_value(self, value: str) -> None:
        """Set entry value."""
        self._hide_placeholder()
        self.delete(0, tk.END)
        self.insert(0, value)


class Separator(tk.Frame):
    """
    Horizontal or vertical separator line.

    Usage:
        sep = Separator(parent, orient="horizontal")
    """

    def __init__(
        self,
        parent: tk.Widget,
        orient: str = "horizontal",
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        if orient == "horizontal":
            kwargs.setdefault('height', 1)
        else:
            kwargs.setdefault('width', 1)

        kwargs.setdefault('bg', colors.border_light)

        super().__init__(parent, **kwargs)


class Tooltip:
    """
    Tooltip for widgets.

    Usage:
        Tooltip(button, "Click to submit")
    """

    def __init__(self, widget: tk.Widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self._id = None

        widget.bind('<Enter>', self._on_enter)
        widget.bind('<Leave>', self._on_leave)
        widget.bind('<Button>', self._on_leave)

    def _on_enter(self, event) -> None:
        """Schedule tooltip display."""
        self._id = self.widget.after(self.delay, self._show)

    def _on_leave(self, event) -> None:
        """Cancel and hide tooltip."""
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None
        self._hide()

    def _show(self) -> None:
        """Show the tooltip."""
        if self.tooltip_window:
            return

        theme = get_theme()
        colors = theme.colors

        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            bg=colors.bg_elevated,
            fg=colors.fg_primary,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            padx=Spacing.SM,
            pady=Spacing.XS,
            relief=tk.SOLID,
            borderwidth=1,
        )
        label.pack()

    def _hide(self) -> None:
        """Hide the tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
