"""
QUANT_INDUSTRY_V1 Quick Actions Bar

One-click action buttons for common trading operations.
"""

import tkinter as tk
from typing import Callable, Optional, List, Tuple
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class ActionButton(tk.Frame):
    """Styled action button with icon and tooltip."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        icon: str = "",
        command: Callable = None,
        variant: str = "default",  # default, primary, success, warning, danger
        tooltip: str = "",
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        kwargs.setdefault('cursor', 'hand2')
        super().__init__(parent, **kwargs)

        self._command = command
        self._variant = variant
        self._colors = colors
        self._theme = theme

        # Variant colors
        variant_config = {
            "default": (colors.bg_tertiary, colors.fg_secondary, colors.bg_hover),
            "primary": (colors.accent_primary, colors.bg_primary, colors.accent_secondary),
            "success": (colors.bullish, colors.bg_primary, colors.success),
            "warning": (colors.warning, colors.bg_primary, colors.warning),
            "danger": (colors.bearish, colors.bg_primary, colors.error),
        }

        self._bg, self._fg, self._hover_bg = variant_config.get(variant, variant_config["default"])

        self._setup_ui(text, icon)
        self._bind_events()

        if tooltip:
            self._create_tooltip(tooltip)

    def _setup_ui(self, text: str, icon: str) -> None:
        """Build button UI."""
        self.configure(bg=self._bg)

        content = tk.Frame(self, bg=self._bg)
        content.pack(padx=Spacing.SM, pady=Spacing.XS)

        if icon:
            icon_label = tk.Label(
                content,
                text=icon,
                font=self._theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
                fg=self._fg,
                bg=self._bg,
            )
            icon_label.pack(side=tk.LEFT, padx=(0, Spacing.XS))
            self._icon_label = icon_label

        self._text_label = tk.Label(
            content,
            text=text,
            font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=self._fg,
            bg=self._bg,
        )
        self._text_label.pack(side=tk.LEFT)

        self._content = content

    def _bind_events(self) -> None:
        """Bind click and hover."""
        widgets = [self, self._content, self._text_label]
        if hasattr(self, '_icon_label'):
            widgets.append(self._icon_label)

        for widget in widgets:
            widget.bind('<Button-1>', self._on_click)
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)

    def _on_click(self, event) -> None:
        """Handle click."""
        if self._command:
            self._command()

    def _on_enter(self, event) -> None:
        """Hover effect."""
        self.configure(bg=self._hover_bg)
        self._content.configure(bg=self._hover_bg)
        self._text_label.configure(bg=self._hover_bg)
        if hasattr(self, '_icon_label'):
            self._icon_label.configure(bg=self._hover_bg)

    def _on_leave(self, event) -> None:
        """Remove hover effect."""
        self.configure(bg=self._bg)
        self._content.configure(bg=self._bg)
        self._text_label.configure(bg=self._bg)
        if hasattr(self, '_icon_label'):
            self._icon_label.configure(bg=self._bg)

    def _create_tooltip(self, text: str) -> None:
        """Create tooltip."""
        tooltip = None

        def show(event):
            nonlocal tooltip
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height() + 5

            tooltip = tk.Toplevel(self)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")
            tooltip.attributes('-topmost', True)

            label = tk.Label(
                tooltip,
                text=text,
                font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=self._colors.fg_primary,
                bg=self._colors.bg_elevated,
                padx=Spacing.SM,
                pady=Spacing.XS,
            )
            label.pack()

        def hide(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        self.bind('<Enter>', lambda e: [self._on_enter(e), show(e)], add='+')
        self.bind('<Leave>', lambda e: [self._on_leave(e), hide(e)], add='+')


class QuickActionsBar(tk.Frame):
    """
    Horizontal bar with quick action buttons.

    Default actions:
    - Execute All Signals
    - Close All Positions
    - Refresh Data
    - Toggle Auto-Trade
    - Emergency Stop
    """

    def __init__(
        self,
        parent: tk.Widget,
        actions: List[Tuple[str, str, str, Callable, str]] = None,  # (text, icon, variant, command, tooltip)
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._actions = actions

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build actions bar."""
        # Container with padding
        container = tk.Frame(self, bg=self._colors.bg_secondary)
        container.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.XS)

        # Left side: Label
        label = tk.Label(
            container,
            text="QUICK ACTIONS",
            font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_secondary,
        )
        label.pack(side=tk.LEFT, padx=(0, Spacing.MD))

        # Default actions if none provided
        if not self._actions:
            self._actions = [
                ("Execute Signals", "▶", "success", self._placeholder, "Execute all active signals"),
                ("Close All", "[FAIL]", "danger", self._placeholder, "Close all open positions"),
                ("Refresh", "↻", "default", self._placeholder, "Refresh market data (F5)"),
                ("Auto-Trade", "⚡", "primary", self._placeholder, "Toggle auto-trading"),
            ]

        # Create action buttons
        for text, icon, variant, command, tooltip in self._actions:
            btn = ActionButton(
                container,
                text=text,
                icon=icon,
                variant=variant,
                command=command,
                tooltip=tooltip,
            )
            btn.pack(side=tk.LEFT, padx=Spacing.XS)

    def _placeholder(self) -> None:
        """Placeholder command."""
        logger.info("Quick action triggered")

    def set_actions(self, actions: List[Tuple[str, str, str, Callable, str]]) -> None:
        """Update actions."""
        # Clear existing
        for child in self.winfo_children():
            child.destroy()

        self._actions = actions
        self._setup_ui()


class FloatingActionButton(tk.Toplevel):
    """
    Floating action button that stays in corner.

    For emergency stop or other critical actions.
    """

    def __init__(
        self,
        parent: tk.Tk,
        text: str = "STOP",
        icon: str = "[WARN]",
        command: Callable = None,
        position: str = "bottom-right",  # bottom-right, bottom-left, top-right, top-left
    ):
        super().__init__(parent)

        self._parent = parent
        self._command = command
        self._position = position

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Window setup
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=self._colors.bearish)

        self._setup_ui(text, icon)
        self._position_window()

        # Reposition on parent move
        parent.bind('<Configure>', lambda e: self._position_window())

    def _setup_ui(self, text: str, icon: str) -> None:
        """Build FAB UI."""
        container = tk.Frame(self, bg=self._colors.bearish, cursor="hand2")
        container.pack(padx=3, pady=3)

        if icon:
            icon_label = tk.Label(
                container,
                text=icon,
                font=self._theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
                fg=self._colors.bg_primary,
                bg=self._colors.bearish,
            )
            icon_label.pack(side=tk.LEFT, padx=(Spacing.SM, Spacing.XS))

        text_label = tk.Label(
            container,
            text=text,
            font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=self._colors.bg_primary,
            bg=self._colors.bearish,
        )
        text_label.pack(side=tk.LEFT, padx=(0, Spacing.SM), pady=Spacing.XS)

        # Bind click
        for widget in [self, container, text_label]:
            widget.bind('<Button-1>', self._on_click)
            if icon:
                icon_label.bind('<Button-1>', self._on_click)

    def _position_window(self) -> None:
        """Position the FAB."""
        self.update_idletasks()

        parent_x = self._parent.winfo_x()
        parent_y = self._parent.winfo_y()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        fab_width = self.winfo_width() or 100
        fab_height = self.winfo_height() or 40

        margin = 20

        positions = {
            "bottom-right": (parent_x + parent_width - fab_width - margin,
                           parent_y + parent_height - fab_height - margin - 30),
            "bottom-left": (parent_x + margin,
                          parent_y + parent_height - fab_height - margin - 30),
            "top-right": (parent_x + parent_width - fab_width - margin,
                         parent_y + margin + 50),
            "top-left": (parent_x + margin, parent_y + margin + 50),
        }

        x, y = positions.get(self._position, positions["bottom-right"])
        self.geometry(f"+{int(x)}+{int(y)}")

    def _on_click(self, event) -> None:
        """Handle click."""
        if self._command:
            self._command()
