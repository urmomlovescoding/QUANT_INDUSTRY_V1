"""
QUANT_INDUSTRY_V1 Toast Notification System

Non-blocking notifications that appear and auto-dismiss.
"""

import tkinter as tk
from typing import Optional, Callable, List
from enum import Enum
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class ToastLevel(Enum):
    """Toast notification levels."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Toast(tk.Toplevel):
    """
    Individual toast notification.

    Features:
    - Auto-dismiss with configurable timeout
    - Manual dismiss button
    - Action button support
    - Smooth animations
    """

    def __init__(
        self,
        parent: tk.Tk,
        message: str,
        level: ToastLevel = ToastLevel.INFO,
        duration: int = 5000,  # ms
        title: Optional[str] = None,
        action: Optional[tuple] = None,  # (label, callback)
        on_dismiss: Optional[Callable] = None,
    ):
        super().__init__(parent)

        self._parent = parent
        self._message = message
        self._level = level
        self._duration = duration
        self._title = title
        self._action = action
        self._on_dismiss = on_dismiss

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Window setup
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.withdraw()  # Hide initially

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the toast UI."""
        # Determine colors based on level
        level_colors = {
            ToastLevel.INFO: (self._colors.accent_primary, "ℹ"),
            ToastLevel.SUCCESS: (self._colors.bullish, "✓"),
            ToastLevel.WARNING: (self._colors.warning, "⚠"),
            ToastLevel.ERROR: (self._colors.bearish, "✕"),
        }

        accent_color, icon = level_colors.get(self._level, (self._colors.accent_primary, "ℹ"))

        # Main container with border
        self.configure(bg=accent_color)

        container = tk.Frame(
            self,
            bg=self._colors.bg_elevated,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Left accent bar
        accent_bar = tk.Frame(container, bg=accent_color, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        # Content
        content = tk.Frame(container, bg=self._colors.bg_elevated)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.SM)

        # Icon
        icon_label = tk.Label(
            content,
            text=icon,
            font=self._theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=accent_color,
            bg=self._colors.bg_elevated,
        )
        icon_label.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        # Text content
        text_frame = tk.Frame(content, bg=self._colors.bg_elevated)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Title (if provided)
        if self._title:
            title_label = tk.Label(
                text_frame,
                text=self._title,
                font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=self._colors.fg_primary,
                bg=self._colors.bg_elevated,
                anchor="w",
            )
            title_label.pack(anchor="w")

        # Message
        msg_label = tk.Label(
            text_frame,
            text=self._message,
            font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_secondary,
            bg=self._colors.bg_elevated,
            anchor="w",
            wraplength=280,
            justify=tk.LEFT,
        )
        msg_label.pack(anchor="w")

        # Right side: action and dismiss
        right_frame = tk.Frame(content, bg=self._colors.bg_elevated)
        right_frame.pack(side=tk.RIGHT, padx=(Spacing.MD, 0))

        # Action button (if provided)
        if self._action:
            action_label, action_callback = self._action
            action_btn = tk.Label(
                right_frame,
                text=action_label,
                font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=accent_color,
                bg=self._colors.bg_elevated,
                cursor="hand2",
            )
            action_btn.pack(side=tk.LEFT, padx=(0, Spacing.SM))
            action_btn.bind('<Button-1>', lambda e: self._handle_action(action_callback))

        # Dismiss button
        dismiss_btn = tk.Label(
            right_frame,
            text="×",
            font=self._theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_elevated,
            cursor="hand2",
        )
        dismiss_btn.pack(side=tk.RIGHT)
        dismiss_btn.bind('<Button-1>', lambda e: self.dismiss())
        dismiss_btn.bind('<Enter>', lambda e: dismiss_btn.config(fg=self._colors.fg_primary))
        dismiss_btn.bind('<Leave>', lambda e: dismiss_btn.config(fg=self._colors.fg_muted))

    def _handle_action(self, callback: Callable) -> None:
        """Handle action button click."""
        self.dismiss()
        callback()

    def show(self, x: int, y: int) -> None:
        """Show the toast at specified position."""
        self.geometry(f"+{x}+{y}")
        self.deiconify()

        # Auto-dismiss timer
        if self._duration > 0:
            self.after(self._duration, self.dismiss)

    def dismiss(self) -> None:
        """Dismiss the toast."""
        self.destroy()
        if self._on_dismiss:
            self._on_dismiss()


class ToastManager:
    """
    Manages toast notifications for the application.

    Features:
    - Stacking toasts
    - Position management
    - Queue management
    """

    def __init__(self, parent: tk.Tk):
        self._parent = parent
        self._toasts: List[Toast] = []
        self._gap = 10
        self._margin = 20
        self._toast_width = 350
        self._toast_height = 80

    def show(
        self,
        message: str,
        level: ToastLevel = ToastLevel.INFO,
        duration: int = 5000,
        title: Optional[str] = None,
        action: Optional[tuple] = None,
    ) -> Toast:
        """
        Show a toast notification.

        Args:
            message: The message to display
            level: Notification level (info, success, warning, error)
            duration: Auto-dismiss timeout in ms (0 = no auto-dismiss)
            title: Optional title
            action: Optional (label, callback) tuple for action button

        Returns:
            The Toast instance
        """
        toast = Toast(
            self._parent,
            message=message,
            level=level,
            duration=duration,
            title=title,
            action=action,
            on_dismiss=lambda: self._on_toast_dismiss(toast),
        )

        self._toasts.append(toast)

        # Calculate position (stack from bottom-right)
        x, y = self._get_position(len(self._toasts) - 1)
        toast.show(x, y)

        logger.info(f"Toast shown: [{level.value}] {message}")

        return toast

    def _get_position(self, index: int) -> tuple:
        """Calculate toast position."""
        self._parent.update_idletasks()

        parent_x = self._parent.winfo_x()
        parent_y = self._parent.winfo_y()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        x = parent_x + parent_width - self._toast_width - self._margin
        y = parent_y + parent_height - (self._toast_height + self._gap) * (index + 1) - self._margin

        return x, y

    def _on_toast_dismiss(self, toast: Toast) -> None:
        """Handle toast dismissal."""
        if toast in self._toasts:
            self._toasts.remove(toast)
            self._reposition_toasts()

    def _reposition_toasts(self) -> None:
        """Reposition remaining toasts."""
        for i, toast in enumerate(self._toasts):
            try:
                x, y = self._get_position(i)
                toast.geometry(f"+{x}+{y}")
            except tk.TclError:
                pass  # Toast already destroyed

    def info(self, message: str, **kwargs) -> Toast:
        """Show info toast."""
        return self.show(message, ToastLevel.INFO, **kwargs)

    def success(self, message: str, **kwargs) -> Toast:
        """Show success toast."""
        return self.show(message, ToastLevel.SUCCESS, **kwargs)

    def warning(self, message: str, **kwargs) -> Toast:
        """Show warning toast."""
        return self.show(message, ToastLevel.WARNING, **kwargs)

    def error(self, message: str, **kwargs) -> Toast:
        """Show error toast."""
        return self.show(message, ToastLevel.ERROR, **kwargs)

    def clear_all(self) -> None:
        """Dismiss all toasts."""
        for toast in self._toasts[:]:
            try:
                toast.dismiss()
            except tk.TclError:
                pass
        self._toasts.clear()


# Global toast manager (set by app shell)
_toast_manager: Optional[ToastManager] = None


def get_toast_manager() -> Optional[ToastManager]:
    """Get the global toast manager."""
    return _toast_manager


def set_toast_manager(manager: ToastManager) -> None:
    """Set the global toast manager."""
    global _toast_manager
    _toast_manager = manager


def toast_info(message: str, **kwargs) -> Optional[Toast]:
    """Quick helper to show info toast."""
    if _toast_manager:
        return _toast_manager.info(message, **kwargs)
    return None


def toast_success(message: str, **kwargs) -> Optional[Toast]:
    """Quick helper to show success toast."""
    if _toast_manager:
        return _toast_manager.success(message, **kwargs)
    return None


def toast_warning(message: str, **kwargs) -> Optional[Toast]:
    """Quick helper to show warning toast."""
    if _toast_manager:
        return _toast_manager.warning(message, **kwargs)
    return None


def toast_error(message: str, **kwargs) -> Optional[Toast]:
    """Quick helper to show error toast."""
    if _toast_manager:
        return _toast_manager.error(message, **kwargs)
    return None
