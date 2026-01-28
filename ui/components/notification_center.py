"""
QUANT_INDUSTRY_V1 Notification Center

History of notifications and alerts.
"""

import tkinter as tk
from typing import List, Dict, Callable
from datetime import datetime
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class NotificationItem:
    """Single notification data."""

    def __init__(
        self,
        title: str,
        message: str,
        level: str = "info",
        timestamp: datetime = None,
        read: bool = False,
    ):
        self.title = title
        self.message = message
        self.level = level
        self.timestamp = timestamp or datetime.now()
        self.read = read


class NotificationCenter(tk.Toplevel):
    """
    Notification history panel.

    Features:
    - List of past notifications
    - Filter by type
    - Mark as read
    - Clear all
    """

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)

        self._parent = parent

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Sample notifications
        self._notifications: List[NotificationItem] = [
            NotificationItem("Welcome", "Trading in PAPER mode", "info"),
            NotificationItem("Signal Detected", "AAPL LONG signal with 85% confidence", "success"),
            NotificationItem("Position Opened", "Bought 100 AAPL @ $185.50", "success"),
            NotificationItem("High Volatility", "VIX above 20 - increased risk", "warning"),
            NotificationItem("Order Filled", "TSLA limit order filled @ $242.00", "info"),
            NotificationItem("Risk Alert", "Portfolio exposure above 60%", "warning"),
        ]

        # Window setup
        self.title("Notifications")
        self.resizable(False, False)
        self.transient(parent)

        self._setup_ui()
        self._center_window()
        self._populate_notifications()

    def _setup_ui(self) -> None:
        """Build the notification center UI."""
        colors = self._colors
        theme = self._theme

        self.configure(bg=colors.bg_elevated)

        # Header
        header = tk.Frame(self, bg=colors.bg_tertiary)
        header.pack(fill=tk.X)

        header_inner = tk.Frame(header, bg=colors.bg_tertiary)
        header_inner.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        title = tk.Label(
            header_inner,
            text="🔔 Notifications",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
        )
        title.pack(side=tk.LEFT)

        # Unread count
        unread = sum(1 for n in self._notifications if not n.read)
        if unread > 0:
            badge = tk.Label(
                header_inner,
                text=str(unread),
                font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
                fg=colors.bg_primary,
                bg=colors.accent_primary,
                padx=6,
                pady=2,
            )
            badge.pack(side=tk.LEFT, padx=Spacing.SM)

        # Clear all button
        clear_btn = tk.Label(
            header_inner,
            text="Clear All",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.accent_primary,
            bg=colors.bg_tertiary,
            cursor="hand2",
        )
        clear_btn.pack(side=tk.RIGHT)
        clear_btn.bind('<Button-1>', lambda e: self._clear_all())

        # Mark all read
        read_btn = tk.Label(
            header_inner,
            text="Mark All Read",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
            cursor="hand2",
        )
        read_btn.pack(side=tk.RIGHT, padx=Spacing.MD)
        read_btn.bind('<Button-1>', lambda e: self._mark_all_read())

        # Filter tabs
        filter_frame = tk.Frame(self, bg=colors.bg_secondary)
        filter_frame.pack(fill=tk.X)

        self._filter = "all"
        filters = [("All", "all"), ("Info", "info"), ("Success", "success"), ("Warnings", "warning")]

        for label, value in filters:
            btn = tk.Label(
                filter_frame,
                text=label,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_secondary if value != self._filter else colors.accent_primary,
                bg=colors.bg_secondary,
                padx=Spacing.MD,
                pady=Spacing.XS,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT)
            btn.bind('<Button-1>', lambda e, v=value: self._set_filter(v))

        # Notifications list
        self._list_frame = tk.Frame(self, bg=colors.bg_elevated)
        self._list_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for scrolling
        self._canvas = tk.Canvas(
            self._list_frame,
            bg=colors.bg_elevated,
            highlightthickness=0,
        )
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            self._list_frame,
            orient=tk.VERTICAL,
            command=self._canvas.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._items_frame = tk.Frame(self._canvas, bg=colors.bg_elevated)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._items_frame, anchor="nw"
        )

        self._items_frame.bind('<Configure>', self._on_frame_configure)
        self._canvas.bind('<Configure>', self._on_canvas_configure)

        # Empty state
        self._empty_label = tk.Label(
            self._items_frame,
            text="No notifications",
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
            pady=Spacing.XL,
        )

    def _on_frame_configure(self, event) -> None:
        """Update scroll region."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        """Update frame width."""
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _populate_notifications(self) -> None:
        """Populate notification list."""
        # Clear existing
        for widget in self._items_frame.winfo_children():
            if widget != self._empty_label:
                widget.destroy()

        # Filter notifications
        filtered = [
            n for n in self._notifications
            if self._filter == "all" or n.level == self._filter
        ]

        if not filtered:
            self._empty_label.pack(fill=tk.X)
            return

        self._empty_label.pack_forget()

        for notif in reversed(filtered):
            self._create_notification_item(notif)

    def _create_notification_item(self, notif: NotificationItem) -> None:
        """Create a notification item widget."""
        colors = self._colors
        theme = self._theme

        # Background based on read status
        bg = colors.bg_elevated if notif.read else colors.bg_secondary

        frame = tk.Frame(self._items_frame, bg=bg)
        frame.pack(fill=tk.X, pady=1)

        inner = tk.Frame(frame, bg=bg)
        inner.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        # Level indicator
        level_colors = {
            "info": colors.info,
            "success": colors.bullish,
            "warning": colors.warning,
            "error": colors.bearish,
        }
        indicator_color = level_colors.get(notif.level, colors.fg_muted)

        indicator = tk.Label(
            inner,
            text="●",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=indicator_color,
            bg=bg,
        )
        indicator.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        # Content
        content = tk.Frame(inner, bg=bg)
        content.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Title
        title = tk.Label(
            content,
            text=notif.title,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=bg,
            anchor="w",
        )
        title.pack(anchor="w")

        # Message
        msg = tk.Label(
            content,
            text=notif.message,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=bg,
            anchor="w",
        )
        msg.pack(anchor="w")

        # Time
        time_str = notif.timestamp.strftime("%H:%M")
        time_label = tk.Label(
            inner,
            text=time_str,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=bg,
        )
        time_label.pack(side=tk.RIGHT)

        # Click to mark as read
        for widget in [frame, inner, content, title, msg]:
            widget.bind('<Button-1>', lambda e, n=notif: self._mark_read(n))

    def _set_filter(self, filter_type: str) -> None:
        """Set notification filter."""
        self._filter = filter_type
        self._populate_notifications()

    def _mark_read(self, notif: NotificationItem) -> None:
        """Mark notification as read."""
        notif.read = True
        self._populate_notifications()

    def _mark_all_read(self) -> None:
        """Mark all notifications as read."""
        for notif in self._notifications:
            notif.read = True
        self._populate_notifications()

    def _clear_all(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()
        self._populate_notifications()

    def _center_window(self) -> None:
        """Center on parent."""
        self.update_idletasks()

        width = 400
        height = 500

        parent_x = self._parent.winfo_x()
        parent_y = self._parent.winfo_y()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")

    def add_notification(self, title: str, message: str, level: str = "info") -> None:
        """Add a new notification."""
        self._notifications.append(NotificationItem(title, message, level))
        self._populate_notifications()
