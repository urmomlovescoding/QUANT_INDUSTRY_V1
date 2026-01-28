"""
QUANT_INDUSTRY_V1 Activity Log

Real-time activity log with filtering and timestamps.
"""

import tkinter as tk
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    """Activity log entry types."""
    TRADE = "trade"
    SIGNAL = "signal"
    POSITION = "position"
    ALERT = "alert"
    SYSTEM = "system"
    ERROR = "error"
    INFO = "info"


class ActivityEntry:
    """Single activity log entry."""

    def __init__(
        self,
        type: ActivityType,
        message: str,
        details: str = None,
        timestamp: datetime = None,
        symbol: str = None,
        metadata: Dict[str, Any] = None,
    ):
        self.type = type
        self.message = message
        self.details = details
        self.timestamp = timestamp or datetime.now()
        self.symbol = symbol
        self.metadata = metadata or {}


class ActivityLog(tk.Frame):
    """
    Real-time activity log panel.

    Features:
    - Color-coded entries by type
    - Timestamps
    - Filter by type
    - Auto-scroll
    - Click to expand details
    - Export to file
    """

    TYPE_CONFIG = {
        ActivityType.TRADE: ("📊", "trade"),
        ActivityType.SIGNAL: ("⚑", "signal"),
        ActivityType.POSITION: ("☰", "position"),
        ActivityType.ALERT: ("⚠", "alert"),
        ActivityType.SYSTEM: ("⚙", "system"),
        ActivityType.ERROR: ("✕", "error"),
        ActivityType.INFO: ("ℹ", "info"),
    }

    def __init__(
        self,
        parent: tk.Widget,
        max_entries: int = 100,
        show_filter: bool = True,
        show_header: bool = True,
        on_entry_click: Callable = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._max_entries = max_entries
        self._show_filter = show_filter
        self._show_header = show_header
        self._on_entry_click = on_entry_click

        self._entries: List[ActivityEntry] = []
        self._active_filter: Optional[ActivityType] = None
        self._auto_scroll = True

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the activity log UI."""
        colors = self._colors
        theme = self._theme

        # Header
        if self._show_header:
            header = tk.Frame(self, bg=colors.bg_tertiary)
            header.pack(fill=tk.X)

            header_inner = tk.Frame(header, bg=colors.bg_tertiary)
            header_inner.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

            title = tk.Label(
                header_inner,
                text="Activity Log",
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=colors.fg_primary,
                bg=colors.bg_tertiary,
            )
            title.pack(side=tk.LEFT)

            # Entry count
            self._count_label = tk.Label(
                header_inner,
                text="0 entries",
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_muted,
                bg=colors.bg_tertiary,
            )
            self._count_label.pack(side=tk.LEFT, padx=Spacing.SM)

            # Clear button
            clear_btn = tk.Label(
                header_inner,
                text="Clear",
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.accent_primary,
                bg=colors.bg_tertiary,
                cursor="hand2",
            )
            clear_btn.pack(side=tk.RIGHT)
            clear_btn.bind('<Button-1>', lambda e: self.clear())

            # Auto-scroll toggle
            self._scroll_toggle = tk.Label(
                header_inner,
                text="⬇ Auto-scroll",
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.accent_primary if self._auto_scroll else colors.fg_muted,
                bg=colors.bg_tertiary,
                cursor="hand2",
            )
            self._scroll_toggle.pack(side=tk.RIGHT, padx=Spacing.MD)
            self._scroll_toggle.bind('<Button-1>', lambda e: self._toggle_auto_scroll())

        # Filter bar
        if self._show_filter:
            filter_frame = tk.Frame(self, bg=colors.bg_secondary)
            filter_frame.pack(fill=tk.X)

            self._filter_buttons: Dict[Optional[ActivityType], tk.Label] = {}

            # All filter
            all_btn = tk.Label(
                filter_frame,
                text="All",
                font=theme.get_font(FontSize.XS, FontWeight.BOLD if self._active_filter is None else FontWeight.NORMAL, "ui"),
                fg=colors.accent_primary if self._active_filter is None else colors.fg_secondary,
                bg=colors.bg_secondary,
                padx=Spacing.SM,
                pady=Spacing.XS,
                cursor="hand2",
            )
            all_btn.pack(side=tk.LEFT)
            all_btn.bind('<Button-1>', lambda e: self._set_filter(None))
            self._filter_buttons[None] = all_btn

            # Type filters
            for activity_type in ActivityType:
                icon, _ = self.TYPE_CONFIG[activity_type]
                btn = tk.Label(
                    filter_frame,
                    text=f"{icon} {activity_type.value.title()}",
                    font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                    fg=colors.fg_secondary,
                    bg=colors.bg_secondary,
                    padx=Spacing.SM,
                    pady=Spacing.XS,
                    cursor="hand2",
                )
                btn.pack(side=tk.LEFT)
                btn.bind('<Button-1>', lambda e, t=activity_type: self._set_filter(t))
                self._filter_buttons[activity_type] = btn

        # Log entries area
        self._log_frame = tk.Frame(self, bg=colors.bg_elevated)
        self._log_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for scrolling
        self._canvas = tk.Canvas(
            self._log_frame,
            bg=colors.bg_elevated,
            highlightthickness=0,
        )
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            self._log_frame,
            orient=tk.VERTICAL,
            command=self._canvas.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._entries_frame = tk.Frame(self._canvas, bg=colors.bg_elevated)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._entries_frame, anchor="nw"
        )

        self._entries_frame.bind('<Configure>', self._on_frame_configure)
        self._canvas.bind('<Configure>', self._on_canvas_configure)

        # Empty state
        self._empty_label = tk.Label(
            self._entries_frame,
            text="No activity yet",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
            pady=Spacing.XL,
        )
        self._empty_label.pack(fill=tk.X)

    def _on_frame_configure(self, event) -> None:
        """Update scroll region."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        if self._auto_scroll:
            self._canvas.yview_moveto(1.0)

    def _on_canvas_configure(self, event) -> None:
        """Update frame width."""
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll."""
        self._auto_scroll = not self._auto_scroll
        colors = self._colors
        self._scroll_toggle.config(
            fg=colors.accent_primary if self._auto_scroll else colors.fg_muted
        )

    def _set_filter(self, filter_type: Optional[ActivityType]) -> None:
        """Set activity filter."""
        self._active_filter = filter_type
        self._update_filter_styles()
        self._refresh_display()

    def _update_filter_styles(self) -> None:
        """Update filter button styles."""
        colors = self._colors
        theme = self._theme

        for activity_type, btn in self._filter_buttons.items():
            is_active = activity_type == self._active_filter
            btn.config(
                fg=colors.accent_primary if is_active else colors.fg_secondary,
                font=theme.get_font(
                    FontSize.XS,
                    FontWeight.BOLD if is_active else FontWeight.NORMAL,
                    "ui"
                ),
            )

    def _refresh_display(self) -> None:
        """Refresh the log display."""
        # Clear existing entries
        for widget in self._entries_frame.winfo_children():
            widget.destroy()

        # Filter entries
        filtered = [
            entry for entry in self._entries
            if self._active_filter is None or entry.type == self._active_filter
        ]

        if not filtered:
            self._empty_label = tk.Label(
                self._entries_frame,
                text="No activity" if self._active_filter is None else f"No {self._active_filter.value} activity",
                font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                fg=self._colors.fg_muted,
                bg=self._colors.bg_elevated,
                pady=Spacing.XL,
            )
            self._empty_label.pack(fill=tk.X)
            return

        # Create entry widgets
        for entry in filtered:
            self._create_entry_widget(entry)

        # Update count
        if self._show_header:
            self._count_label.config(text=f"{len(filtered)} entries")

    def _create_entry_widget(self, entry: ActivityEntry) -> None:
        """Create a log entry widget."""
        colors = self._colors
        theme = self._theme

        icon, type_name = self.TYPE_CONFIG.get(entry.type, ("●", "unknown"))

        # Color by type
        type_colors = {
            ActivityType.TRADE: colors.accent_primary,
            ActivityType.SIGNAL: colors.info,
            ActivityType.POSITION: colors.fg_primary,
            ActivityType.ALERT: colors.warning,
            ActivityType.SYSTEM: colors.fg_muted,
            ActivityType.ERROR: colors.bearish,
            ActivityType.INFO: colors.fg_secondary,
        }
        icon_color = type_colors.get(entry.type, colors.fg_secondary)

        frame = tk.Frame(self._entries_frame, bg=colors.bg_elevated)
        frame.pack(fill=tk.X, pady=1)

        inner = tk.Frame(frame, bg=colors.bg_elevated)
        inner.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        # Timestamp
        time_str = entry.timestamp.strftime("%H:%M:%S")
        time_label = tk.Label(
            inner,
            text=time_str,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
            width=8,
            anchor="w",
        )
        time_label.pack(side=tk.LEFT)

        # Icon
        icon_label = tk.Label(
            inner,
            text=icon,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=icon_color,
            bg=colors.bg_elevated,
        )
        icon_label.pack(side=tk.LEFT, padx=(0, Spacing.XS))

        # Symbol (if present)
        if entry.symbol:
            symbol_label = tk.Label(
                inner,
                text=entry.symbol,
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
                fg=colors.accent_primary,
                bg=colors.bg_elevated,
            )
            symbol_label.pack(side=tk.LEFT, padx=(0, Spacing.XS))

        # Message
        msg_label = tk.Label(
            inner,
            text=entry.message,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
            anchor="w",
        )
        msg_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Click binding
        if self._on_entry_click:
            for widget in [frame, inner, msg_label]:
                widget.bind('<Button-1>', lambda e, ent=entry: self._on_entry_click(ent))
                widget.config(cursor="hand2")

        # Hover effect
        for widget in [frame, inner, time_label, icon_label, msg_label]:
            widget.bind('<Enter>', lambda e, f=frame, i=inner: self._on_hover(f, i, True))
            widget.bind('<Leave>', lambda e, f=frame, i=inner: self._on_hover(f, i, False))

    def _on_hover(self, frame: tk.Frame, inner: tk.Frame, enter: bool) -> None:
        """Handle hover effect."""
        colors = self._colors
        bg = colors.bg_hover if enter else colors.bg_elevated

        frame.config(bg=bg)
        inner.config(bg=bg)
        for child in inner.winfo_children():
            child.config(bg=bg)

    def add_entry(
        self,
        type: ActivityType,
        message: str,
        details: str = None,
        symbol: str = None,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Add a new activity entry."""
        entry = ActivityEntry(
            type=type,
            message=message,
            details=details,
            symbol=symbol,
            metadata=metadata,
        )
        self._entries.append(entry)

        # Trim if over max
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        self._refresh_display()

    def add_trade(self, symbol: str, action: str, qty: int, price: float) -> None:
        """Add a trade activity."""
        self.add_entry(
            ActivityType.TRADE,
            f"{action} {qty} @ ${price:.2f}",
            symbol=symbol,
        )

    def add_signal(self, symbol: str, direction: str, confidence: float) -> None:
        """Add a signal activity."""
        self.add_entry(
            ActivityType.SIGNAL,
            f"{direction} signal ({confidence*100:.0f}% conf)",
            symbol=symbol,
        )

    def add_alert(self, message: str, symbol: str = None) -> None:
        """Add an alert activity."""
        self.add_entry(
            ActivityType.ALERT,
            message,
            symbol=symbol,
        )

    def add_error(self, message: str) -> None:
        """Add an error activity."""
        self.add_entry(
            ActivityType.ERROR,
            message,
        )

    def add_info(self, message: str) -> None:
        """Add an info activity."""
        self.add_entry(
            ActivityType.INFO,
            message,
        )

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self._refresh_display()

    def get_entries(self) -> List[ActivityEntry]:
        """Get all entries."""
        return self._entries.copy()


class CompactActivityLog(tk.Frame):
    """
    Compact activity log for sidebar display.

    Shows recent entries in a minimal format.
    """

    def __init__(
        self,
        parent: tk.Widget,
        max_entries: int = 10,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._max_entries = max_entries
        self._entries: List[ActivityEntry] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the compact log UI."""
        colors = self._colors
        theme = self._theme

        # Header
        header = tk.Frame(self, bg=colors.bg_elevated)
        header.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        tk.Label(
            header,
            text="RECENT ACTIVITY",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        # Entries container
        self._container = tk.Frame(self, bg=colors.bg_elevated)
        self._container.pack(fill=tk.BOTH, expand=True)

        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the log display."""
        colors = self._colors
        theme = self._theme

        for widget in self._container.winfo_children():
            widget.destroy()

        if not self._entries:
            tk.Label(
                self._container,
                text="No recent activity",
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_muted,
                bg=colors.bg_elevated,
            ).pack(pady=Spacing.SM)
            return

        for entry in self._entries[-self._max_entries:]:
            self._create_compact_entry(entry)

    def _create_compact_entry(self, entry: ActivityEntry) -> None:
        """Create a compact entry widget."""
        colors = self._colors
        theme = self._theme

        type_icons = {
            ActivityType.TRADE: ("📊", colors.accent_primary),
            ActivityType.SIGNAL: ("⚑", colors.info),
            ActivityType.ALERT: ("⚠", colors.warning),
            ActivityType.ERROR: ("✕", colors.bearish),
        }
        icon, color = type_icons.get(entry.type, ("●", colors.fg_muted))

        frame = tk.Frame(self._container, bg=colors.bg_elevated)
        frame.pack(fill=tk.X, padx=Spacing.SM, pady=1)

        tk.Label(
            frame,
            text=icon,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=color,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        # Truncate message
        msg = entry.message[:30] + "..." if len(entry.message) > 30 else entry.message

        tk.Label(
            frame,
            text=msg,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=Spacing.XS)

        # Time
        time_str = entry.timestamp.strftime("%H:%M")
        tk.Label(
            frame,
            text=time_str,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(side=tk.RIGHT)

    def add_entry(self, type: ActivityType, message: str, **kwargs) -> None:
        """Add a new entry."""
        entry = ActivityEntry(type=type, message=message, **kwargs)
        self._entries.append(entry)

        if len(self._entries) > self._max_entries * 2:
            self._entries = self._entries[-self._max_entries:]

        self._refresh_display()
