"""
QUANT_INDUSTRY_V1 Empty States

Professional empty state displays with guidance.
"""

import tkinter as tk
from typing import Callable, Optional
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class EmptyState(tk.Frame):
    """
    Empty state display with icon, message, and action.

    Used when:
    - No data available
    - First-time user experience
    - Error states
    - Loading completed with no results
    """

    def __init__(
        self,
        parent: tk.Widget,
        icon: str = "📭",
        title: str = "No Data",
        message: str = "There's nothing to show here yet.",
        action_text: str = None,
        action_command: Callable = None,
        variant: str = "default",  # default, info, warning, error
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_primary)
        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._variant = variant

        self._setup_ui(icon, title, message, action_text, action_command)

    def _setup_ui(
        self,
        icon: str,
        title: str,
        message: str,
        action_text: str,
        action_command: Callable,
    ) -> None:
        """Build empty state UI."""
        colors = self._colors
        theme = self._theme

        # Variant colors
        variant_colors = {
            "default": colors.fg_muted,
            "info": colors.info,
            "warning": colors.warning,
            "error": colors.error,
        }
        accent = variant_colors.get(self._variant, colors.fg_muted)

        # Center container
        container = tk.Frame(self, bg=colors.bg_primary)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Icon
        icon_label = tk.Label(
            container,
            text=icon,
            font=("Segoe UI Emoji", 48),
            fg=accent,
            bg=colors.bg_primary,
        )
        icon_label.pack(pady=(0, Spacing.MD))

        # Title
        title_label = tk.Label(
            container,
            text=title,
            font=theme.get_font(FontSize.HEADING, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_primary,
        )
        title_label.pack(pady=(0, Spacing.SM))

        # Message
        msg_label = tk.Label(
            container,
            text=message,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_primary,
            wraplength=300,
            justify=tk.CENTER,
        )
        msg_label.pack(pady=(0, Spacing.LG))

        # Action button
        if action_text and action_command:
            action_btn = tk.Label(
                container,
                text=action_text,
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=colors.bg_primary,
                bg=colors.accent_primary,
                cursor="hand2",
                padx=Spacing.LG,
                pady=Spacing.SM,
            )
            action_btn.pack()
            action_btn.bind('<Button-1>', lambda e: action_command())


class NoSignalsState(EmptyState):
    """Empty state for no signals."""

    def __init__(self, parent: tk.Widget, on_refresh: Callable = None, **kwargs):
        super().__init__(
            parent,
            icon="📡",
            title="No Active Signals",
            message="The system is analyzing market conditions. Signals will appear here when trading opportunities are detected.",
            action_text="Refresh Data" if on_refresh else None,
            action_command=on_refresh,
            **kwargs
        )


class NoPositionsState(EmptyState):
    """Empty state for no positions."""

    def __init__(self, parent: tk.Widget, on_new_trade: Callable = None, **kwargs):
        super().__init__(
            parent,
            icon="[CHART]",
            title="No Open Positions",
            message="You don't have any open positions. Execute a signal or enter a manual trade to get started.",
            action_text="New Trade" if on_new_trade else None,
            action_command=on_new_trade,
            **kwargs
        )


class NoDataState(EmptyState):
    """Empty state for no data."""

    def __init__(self, parent: tk.Widget, on_refresh: Callable = None, **kwargs):
        super().__init__(
            parent,
            icon="📭",
            title="No Data Available",
            message="There's no data to display. This could be due to market hours or data feed issues.",
            action_text="Refresh" if on_refresh else None,
            action_command=on_refresh,
            variant="info",
            **kwargs
        )


class ErrorState(EmptyState):
    """Error state display."""

    def __init__(
        self,
        parent: tk.Widget,
        error_message: str = "Something went wrong",
        on_retry: Callable = None,
        **kwargs
    ):
        super().__init__(
            parent,
            icon="[WARN]️",
            title="Error",
            message=error_message,
            action_text="Retry" if on_retry else None,
            action_command=on_retry,
            variant="error",
            **kwargs
        )


class LoadingState(tk.Frame):
    """Loading state with spinner."""

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
        self._phase = 0
        self._running = False

        self._setup_ui(message)

    def _setup_ui(self, message: str) -> None:
        """Build loading UI."""
        colors = self._colors
        theme = self._theme

        container = tk.Frame(self, bg=colors.bg_primary)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Spinner
        self._spinner = tk.Label(
            container,
            text="[~]",
            font=("Segoe UI", 32),
            fg=colors.accent_primary,
            bg=colors.bg_primary,
        )
        self._spinner.pack(pady=(0, Spacing.MD))

        # Message
        tk.Label(
            container,
            text=message,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_primary,
        ).pack()

        self.start()

    def start(self) -> None:
        """Start spinner animation."""
        if not self._running:
            self._running = True
            self._animate()

    def stop(self) -> None:
        """Stop spinner animation."""
        self._running = False

    def _animate(self) -> None:
        """Animate spinner."""
        if not self._running:
            return

        frames = ["[~]", "◓", "◑", "◒"]
        self._phase = (self._phase + 1) % len(frames)
        self._spinner.config(text=frames[self._phase])

        self.after(100, self._animate)


class FirstTimeState(EmptyState):
    """First-time user onboarding state."""

    def __init__(
        self,
        parent: tk.Widget,
        feature: str = "this feature",
        on_learn_more: Callable = None,
        **kwargs
    ):
        super().__init__(
            parent,
            icon="👋",
            title=f"Welcome to {feature}!",
            message="This is your first time here. Let's get you started with a quick overview.",
            action_text="Learn More" if on_learn_more else None,
            action_command=on_learn_more,
            variant="info",
            **kwargs
        )


class MaintenanceState(EmptyState):
    """Maintenance mode state."""

    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(
            parent,
            icon="[FIX]",
            title="Under Maintenance",
            message="We're performing scheduled maintenance. Please check back shortly.",
            variant="warning",
            **kwargs
        )


class OfflineState(EmptyState):
    """Offline state."""

    def __init__(self, parent: tk.Widget, on_reconnect: Callable = None, **kwargs):
        super().__init__(
            parent,
            icon="📡",
            title="Connection Lost",
            message="Unable to connect to the server. Please check your internet connection.",
            action_text="Reconnect" if on_reconnect else None,
            action_command=on_reconnect,
            variant="error",
            **kwargs
        )
