"""
QUANT_INDUSTRY_V1 Main Application Shell - PROFESSIONAL EDITION

Modern Tkinter-based main window with enhanced navigation,
command palette, toast notifications, and right rail.

Rollback Plan: Delete this file
Tests Required: Window creation, navigation, view switching
Failure Modes: View error -> show error message, don't crash
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
from typing import Optional, Dict, Type, Callable, List, Tuple
from datetime import datetime, timezone

from .theme import get_theme, init_theme, ColorScheme, Spacing, FontSize, FontWeight
from .state import (
    get_store, get_event_bus, init_store,
    EventType, dispatch, notify,
)
from .components.base import StyledFrame, StyledButton, StyledLabel
from .components.command_palette import CommandPalette, get_command_registry
from .components.right_rail import RightRail
from .components.toast import ToastManager, set_toast_manager, ToastLevel
from .components.market_ticker import CompactTicker
from .components.keyboard_shortcuts import KeyboardShortcutsOverlay
from .components.trade_entry import TradeEntryForm
from .components.watchlist import Watchlist
from .components.settings_panel import SettingsPanel
from .components.notification_center import NotificationCenter
from .views.dashboard import DashboardView
from .views.signals import SignalsView
from .views.positions import PositionsView
from .views.health import HealthView
from .views.alpha_research import AlphaResearchView
from .views.analytics import AnalyticsView

logger = logging.getLogger(__name__)


class AppShell(tk.Tk):
    """
    Main application window - Professional Edition.

    Layout:
    ┌────────────────────────────────────────────────────────────────────┐
    │  Header Bar (Logo, Mode, Search, Notifications, Kill Switch)      │
    ├──────┬─────────────────────────────────────────────────┬───────────┤
    │      │                                                 │           │
    │ Nav  │              Main Content                       │  Right    │
    │ Rail │              (Views)                            │  Rail     │
    │      │                                                 │           │
    │      │                                                 │           │
    ├──────┴─────────────────────────────────────────────────┴───────────┤
    │  Status Bar                                                        │
    └────────────────────────────────────────────────────────────────────┘
    """

    VIEWS: Dict[str, Type[tk.Frame]] = {
        "dashboard": DashboardView,
        "signals": SignalsView,
        "positions": PositionsView,
        "health": HealthView,
        "alpha": AlphaResearchView,
        "analytics": AnalyticsView,
    }

    NAV_ITEMS = [
        ("dashboard", "Dashboard", "⌂", "Ctrl+1"),
        ("signals", "Signals", "⚑", "Ctrl+2"),
        ("positions", "Positions", "☰", "Ctrl+3"),
        ("alpha", "Alpha Lab", "★", "Ctrl+4"),
        ("analytics", "Analytics", "≡", "Ctrl+5"),
        ("health", "Health", "♥", "Ctrl+6"),
    ]

    def __init__(
        self,
        title: str = "QUANT_INDUSTRY_V1",
        width: int = 1400,
        height: int = 900,
        theme: ColorScheme = ColorScheme.DARK,
        run_id: str = None,
        mode: str = "paper",
    ):
        super().__init__()

        # Initialize theme
        init_theme(theme)

        # Initialize state
        init_store(run_id=run_id, mode=mode)

        self._theme_config = get_theme()
        self._store = get_store()
        self._event_bus = get_event_bus()
        self._mode = mode

        # Window configuration
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.minsize(1000, 700)

        # Apply theme to window
        colors = self._theme_config.colors
        self.configure(bg=colors.bg_primary)

        # Task queue for thread-safe UI updates
        self._task_queue = queue.Queue()

        # Current view
        self._current_view_name: str = "dashboard"
        self._current_view: Optional[tk.Frame] = None
        self._nav_buttons: Dict[str, tk.Frame] = {}

        # Initialize toast manager
        self._toast_manager = ToastManager(self)
        set_toast_manager(self._toast_manager)

        # Build UI
        self._setup_ui()

        # Command palette
        self._setup_command_palette()

        # Event bindings
        self._bind_events()

        # Process queue
        self._process_queue()

        # Start with dashboard
        self.switch_view("dashboard")

        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Show welcome toast
        self.after(500, lambda: self._toast_manager.info(
            f"Trading in {mode.upper()} mode",
            title="Welcome to QUANT_INDUSTRY_V1"
        ))

        logger.info(f"App shell initialized: {width}x{height}, mode={mode}")

    def _setup_ui(self) -> None:
        """Setup the main UI structure."""
        colors = self._theme_config.colors

        # Configure grid
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)  # Main content row

        # Header bar
        self._header = self._create_header()
        self._header.grid(row=0, column=0, columnspan=3, sticky="ew")

        # Market ticker bar
        self._ticker = CompactTicker(self)
        self._ticker.grid(row=1, column=0, columnspan=3, sticky="ew")

        # Navigation rail
        self._nav_rail = self._create_nav_rail()
        self._nav_rail.grid(row=2, column=0, sticky="ns")

        # Main content area
        self._content = tk.Frame(self, bg=colors.bg_primary)
        self._content.grid(row=2, column=1, sticky="nsew", padx=1)
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

        # Right rail with watchlist
        self._right_rail = self._create_right_rail()
        self._right_rail.grid(row=2, column=2, sticky="ns")

        # Status bar
        self._status_bar = self._create_status_bar()
        self._status_bar.grid(row=3, column=0, columnspan=3, sticky="ew")

    def _create_header(self) -> tk.Frame:
        """Create enhanced header bar."""
        colors = self._theme_config.colors
        theme = self._theme_config

        frame = tk.Frame(self, bg=colors.bg_tertiary, height=48)
        frame.pack_propagate(False)

        # Left section: Logo
        left = tk.Frame(frame, bg=colors.bg_tertiary)
        left.pack(side=tk.LEFT, padx=Spacing.MD)

        # Logo
        logo = tk.Label(
            left,
            text="◈ QUANT_INDUSTRY",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.accent_primary,
            bg=colors.bg_tertiary,
        )
        logo.pack(side=tk.LEFT)

        # Mode badge
        mode_colors = {
            "paper": (colors.warning, "PAPER"),
            "live": (colors.bearish, "LIVE"),
            "backtest": (colors.accent_secondary, "BACKTEST"),
        }
        badge_color, badge_text = mode_colors.get(self._mode, (colors.fg_muted, "UNKNOWN"))

        mode_badge = tk.Label(
            left,
            text=f"  {badge_text}  ",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=badge_color,
        )
        mode_badge.pack(side=tk.LEFT, padx=Spacing.MD)

        # Center section: Command palette trigger
        center = tk.Frame(frame, bg=colors.bg_tertiary)
        center.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=Spacing.XL)

        search_btn = tk.Frame(
            center,
            bg=colors.bg_secondary,
            cursor="hand2",
        )
        search_btn.pack(pady=Spacing.SM)

        search_inner = tk.Frame(search_btn, bg=colors.bg_secondary)
        search_inner.pack(padx=Spacing.MD, pady=Spacing.XS)

        search_icon = tk.Label(
            search_inner,
            text="🔍",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
        )
        search_icon.pack(side=tk.LEFT)

        search_text = tk.Label(
            search_inner,
            text="Search commands...",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
        )
        search_text.pack(side=tk.LEFT, padx=Spacing.SM)

        shortcut_badge = tk.Label(
            search_inner,
            text="Ctrl+K",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
            padx=4,
            pady=1,
        )
        shortcut_badge.pack(side=tk.LEFT)

        # Bind click to command palette
        for widget in [search_btn, search_inner, search_icon, search_text]:
            widget.bind('<Button-1>', lambda e: self._show_command_palette())

        # Right section: Actions
        right = tk.Frame(frame, bg=colors.bg_tertiary)
        right.pack(side=tk.RIGHT, padx=Spacing.MD)

        # Notification bell
        self._notification_count = 0
        notif_frame = tk.Frame(right, bg=colors.bg_tertiary, cursor="hand2")
        notif_frame.pack(side=tk.LEFT, padx=Spacing.SM)

        notif_btn = tk.Label(
            notif_frame,
            text="🔔",
            font=theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
        )
        notif_btn.pack()
        notif_btn.bind('<Button-1>', lambda e: self._show_notifications())

        # Theme toggle
        theme_btn = tk.Label(
            right,
            text="☾",
            font=theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
            cursor="hand2",
        )
        theme_btn.pack(side=tk.LEFT, padx=Spacing.SM)
        theme_btn.bind('<Button-1>', lambda e: self._toggle_theme())

        # Kill switch (for live mode)
        if self._mode == "live":
            kill_btn = tk.Label(
                right,
                text="  KILL  ",
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=colors.bg_primary,
                bg=colors.bearish,
                cursor="hand2",
            )
            kill_btn.pack(side=tk.LEFT, padx=Spacing.SM)
            kill_btn.bind('<Button-1>', lambda e: self._emergency_stop())

        return frame

    def _create_nav_rail(self) -> tk.Frame:
        """Create compact navigation rail."""
        colors = self._theme_config.colors
        theme = self._theme_config

        frame = tk.Frame(self, bg=colors.bg_secondary, width=56)
        frame.pack_propagate(False)

        # Nav items container
        nav_container = tk.Frame(frame, bg=colors.bg_secondary)
        nav_container.pack(fill=tk.Y, expand=True, pady=Spacing.MD)

        for view_name, label, icon, shortcut in self.NAV_ITEMS:
            # Container for icon button
            btn_frame = tk.Frame(
                nav_container,
                bg=colors.bg_secondary,
                cursor="hand2",
            )
            btn_frame.pack(pady=2)

            # Icon button
            btn = tk.Label(
                btn_frame,
                text=icon,
                font=theme.get_font(FontSize.HEADING, FontWeight.NORMAL, "ui"),
                fg=colors.fg_secondary,
                bg=colors.bg_secondary,
                width=3,
                height=1,
                padx=Spacing.SM,
                pady=Spacing.XS,
            )
            btn.pack()

            self._nav_buttons[view_name] = btn_frame

            # Bindings
            for widget in [btn_frame, btn]:
                widget.bind('<Button-1>', lambda e, v=view_name: self.switch_view(v))
                widget.bind('<Enter>', lambda e, b=btn, f=btn_frame, v=view_name: self._on_nav_hover(b, f, v, True))
                widget.bind('<Leave>', lambda e, b=btn, f=btn_frame, v=view_name: self._on_nav_hover(b, f, v, False))

            # Tooltip
            self._create_tooltip(btn, f"{label} ({shortcut})")

        # Bottom: Settings
        settings_container = tk.Frame(frame, bg=colors.bg_secondary)
        settings_container.pack(side=tk.BOTTOM, pady=Spacing.MD)

        settings_btn = tk.Label(
            settings_container,
            text="⚙",
            font=theme.get_font(FontSize.HEADING, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
            cursor="hand2",
        )
        settings_btn.pack()
        settings_btn.bind('<Button-1>', lambda e: self._show_settings())
        self._create_tooltip(settings_btn, "Settings")

        return frame

    def _create_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Create tooltip for widget."""
        colors = self._theme_config.colors
        theme = self._theme_config

        tooltip = None

        def show(event):
            nonlocal tooltip
            x = widget.winfo_rootx() + widget.winfo_width() + 5
            y = widget.winfo_rooty()

            tooltip = tk.Toplevel(self)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")
            tooltip.attributes('-topmost', True)

            label = tk.Label(
                tooltip,
                text=text,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_primary,
                bg=colors.bg_elevated,
                padx=Spacing.SM,
                pady=Spacing.XS,
            )
            label.pack()

        def hide(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind('<Enter>', show, add='+')
        widget.bind('<Leave>', hide, add='+')

    def _on_nav_hover(self, btn: tk.Label, frame: tk.Frame, view_name: str, enter: bool) -> None:
        """Handle navigation button hover."""
        colors = self._theme_config.colors

        if enter:
            frame.config(bg=colors.bg_hover)
            btn.config(bg=colors.bg_hover)
        else:
            if view_name == self._current_view_name:
                frame.config(bg=colors.bg_active)
                btn.config(bg=colors.bg_active, fg=colors.accent_primary)
            else:
                frame.config(bg=colors.bg_secondary)
                btn.config(bg=colors.bg_secondary, fg=colors.fg_secondary)

    def _create_status_bar(self) -> tk.Frame:
        """Create enhanced status bar."""
        colors = self._theme_config.colors
        theme = self._theme_config

        frame = tk.Frame(self, bg=colors.bg_tertiary, height=26)
        frame.pack_propagate(False)

        # Left: Status text
        self._status_label = tk.Label(
            frame,
            text="● Ready",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.bullish,
            bg=colors.bg_tertiary,
            anchor="w",
        )
        self._status_label.pack(side=tk.LEFT, padx=Spacing.MD)

        # Center: Connection status
        conn_frame = tk.Frame(frame, bg=colors.bg_tertiary)
        conn_frame.pack(side=tk.LEFT, padx=Spacing.XL)

        conn_dot = tk.Canvas(conn_frame, width=8, height=8, bg=colors.bg_tertiary, highlightthickness=0)
        conn_dot.pack(side=tk.LEFT)
        conn_dot.create_oval(1, 1, 7, 7, fill=colors.bullish, outline="")

        conn_label = tk.Label(
            conn_frame,
            text="Connected",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        conn_label.pack(side=tk.LEFT, padx=(4, 0))

        # Right: Run ID and time
        right_frame = tk.Frame(frame, bg=colors.bg_tertiary)
        right_frame.pack(side=tk.RIGHT, padx=Spacing.MD)

        run_id = self._store.get('run_id', 'N/A')
        run_label = tk.Label(
            right_frame,
            text=f"Run: {run_id[:8] if run_id else 'N/A'}",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        run_label.pack(side=tk.LEFT, padx=Spacing.MD)

        # Time
        self._time_label = tk.Label(
            right_frame,
            text="",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        self._time_label.pack(side=tk.LEFT)
        self._update_time()

        return frame

    def _update_time(self) -> None:
        """Update time display."""
        now = datetime.now()
        self._time_label.config(text=now.strftime("%H:%M:%S"))
        self.after(1000, self._update_time)

    def _create_right_rail(self) -> tk.Frame:
        """Create right rail with watchlist and quick stats."""
        colors = self._theme_config.colors
        theme = self._theme_config

        frame = tk.Frame(self, bg=colors.bg_secondary, width=220)
        frame.pack_propagate(False)

        # Watchlist at top
        self._watchlist = Watchlist(
            frame,
            on_symbol_click=self._on_watchlist_click,
            on_trade=self._on_quick_trade,
        )
        self._watchlist.pack(fill=tk.BOTH, expand=True)

        # Quick stats at bottom
        stats_frame = tk.Frame(frame, bg=colors.bg_tertiary)
        stats_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Risk meters row
        from .components.right_rail import RiskMeter

        meters = tk.Frame(stats_frame, bg=colors.bg_tertiary)
        meters.pack(fill=tk.X, padx=Spacing.XS, pady=Spacing.SM)

        self._portfolio_risk = RiskMeter(meters, value=35, label="Portfolio")
        self._portfolio_risk.pack(side=tk.LEFT, padx=2)

        self._drawdown_risk = RiskMeter(meters, value=15, label="Drawdown")
        self._drawdown_risk.pack(side=tk.LEFT, padx=2)

        return frame

    def _on_watchlist_click(self, symbol: str) -> None:
        """Handle watchlist symbol click."""
        self._toast_manager.info(f"Selected {symbol}", title="Symbol")

    def _on_quick_trade(self, symbol: str, side: str) -> None:
        """Handle quick trade from watchlist."""
        self._show_trade_entry(symbol, side)

    def _show_trade_entry(self, symbol: str = "", side: str = "BUY") -> None:
        """Show trade entry form."""
        TradeEntryForm(
            self,
            symbol=symbol,
            on_submit=self._on_trade_submit,
        )

    def _on_trade_submit(self, order: dict) -> None:
        """Handle trade submission."""
        self._toast_manager.success(
            f"{order['side']} {order['quantity']} {order['symbol']}",
            title="Order Submitted"
        )

    def _setup_command_palette(self) -> None:
        """Setup command palette with commands."""
        registry = get_command_registry()
        registry.clear()

        # Navigation commands
        for view_name, label, icon, shortcut in self.NAV_ITEMS:
            registry.register(
                "Navigation",
                f"Go to {label}",
                lambda v=view_name: self.switch_view(v),
                shortcut,
            )

        # Action commands
        registry.register("Actions", "Refresh View", self._refresh_current_view, "F5")
        registry.register("Actions", "Toggle Theme", self._toggle_theme, "")
        registry.register("Actions", "Show Settings", self._show_settings, "")
        registry.register("Actions", "Keyboard Shortcuts", self._show_shortcuts, "Ctrl+?")
        registry.register("Actions", "Clear Notifications", lambda: self._toast_manager.clear_all(), "")
        registry.register("Actions", "New Trade", lambda: self._show_trade_entry(), "Ctrl+N")

        # Trading commands (if live/paper)
        if self._mode in ("live", "paper"):
            registry.register("Trading", "Emergency Stop", self._emergency_stop, "")
            registry.register("Trading", "Close All Positions", lambda: self._confirm_close_all(), "")

        # Create palette
        self._command_palette = CommandPalette(self, registry.get_commands())

        # Keyboard shortcuts overlay
        self._shortcuts_overlay = KeyboardShortcutsOverlay(self)

    def _bind_events(self) -> None:
        """Bind keyboard shortcuts and events."""
        # Command palette
        self.bind('<Control-k>', lambda e: self._show_command_palette())
        self.bind('<Control-K>', lambda e: self._show_command_palette())

        # Refresh
        self.bind('<F5>', lambda e: self._refresh_current_view())

        # Quit
        self.bind('<Control-q>', lambda e: self._on_close())
        self.bind('<Control-Q>', lambda e: self._on_close())

        # Keyboard shortcuts overlay
        self.bind('<Control-question>', lambda e: self._show_shortcuts())
        self.bind('<Control-slash>', lambda e: self._show_shortcuts())

        # New trade
        self.bind('<Control-n>', lambda e: self._show_trade_entry())
        self.bind('<Control-N>', lambda e: self._show_trade_entry())

        # View shortcuts
        self.bind('<Control-Key-1>', lambda e: self.switch_view('dashboard'))
        self.bind('<Control-Key-2>', lambda e: self.switch_view('signals'))
        self.bind('<Control-Key-3>', lambda e: self.switch_view('positions'))
        self.bind('<Control-Key-4>', lambda e: self.switch_view('alpha'))
        self.bind('<Control-Key-5>', lambda e: self.switch_view('analytics'))
        self.bind('<Control-Key-6>', lambda e: self.switch_view('health'))

        # State events
        self._event_bus.subscribe(EventType.VIEW_CHANGED, self._on_view_changed)
        self._event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)
        self._event_bus.subscribe(EventType.NOTIFICATION, self._on_notification)

    def switch_view(self, view_name: str) -> None:
        """Switch to a different view."""
        if view_name not in self.VIEWS:
            logger.warning(f"Unknown view: {view_name}")
            return

        if view_name == self._current_view_name and self._current_view is not None:
            return

        colors = self._theme_config.colors

        # Update nav button states
        for name, btn_frame in self._nav_buttons.items():
            btn = btn_frame.winfo_children()[0] if btn_frame.winfo_children() else None
            if btn:
                if name == view_name:
                    btn_frame.config(bg=colors.bg_active)
                    btn.config(bg=colors.bg_active, fg=colors.accent_primary)
                else:
                    btn_frame.config(bg=colors.bg_secondary)
                    btn.config(bg=colors.bg_secondary, fg=colors.fg_secondary)

        # Destroy current view
        if self._current_view is not None:
            self._current_view.destroy()

        # Create new view
        try:
            view_class = self.VIEWS[view_name]
            self._current_view = view_class(self._content)
            self._current_view.grid(row=0, column=0, sticky="nsew")
            self._current_view_name = view_name

            # Update state
            self._store.set_view(view_name)

            logger.info(f"Switched to view: {view_name}")

        except Exception as e:
            logger.exception(f"Error creating view {view_name}: {e}")
            self._show_error_view(str(e))
            self._toast_manager.error(f"Failed to load {view_name} view", title="View Error")

    def _show_error_view(self, error: str) -> None:
        """Show error message when view fails to load."""
        colors = self._theme_config.colors
        theme = self._theme_config

        if self._current_view:
            self._current_view.destroy()

        error_frame = tk.Frame(self._content, bg=colors.bg_primary)
        error_frame.grid(row=0, column=0, sticky="nsew")

        # Error icon
        tk.Label(
            error_frame,
            text="⚠",
            font=theme.get_font(48, FontWeight.NORMAL, "ui"),
            fg=colors.error,
            bg=colors.bg_primary,
        ).pack(pady=(Spacing.XL, Spacing.MD))

        tk.Label(
            error_frame,
            text="Error Loading View",
            font=theme.get_font(FontSize.HEADING, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_primary,
        ).pack(pady=Spacing.SM)

        tk.Label(
            error_frame,
            text=error,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "data"),
            fg=colors.fg_secondary,
            bg=colors.bg_primary,
            wraplength=400,
        ).pack(pady=Spacing.MD)

        StyledButton(
            error_frame,
            text="Return to Dashboard",
            variant="primary",
            command=lambda: self.switch_view("dashboard"),
        ).pack(pady=Spacing.MD)

        self._current_view = error_frame

    def _show_command_palette(self) -> None:
        """Show command palette (Ctrl+K)."""
        self._command_palette.show()

    def _show_notifications(self) -> None:
        """Show notifications panel."""
        if not hasattr(self, '_notification_center') or not self._notification_center.winfo_exists():
            self._notification_center = NotificationCenter(self)
        else:
            self._notification_center.lift()
            self._notification_center.focus_set()

    def _show_settings(self) -> None:
        """Show settings panel."""
        SettingsPanel(self, on_save=self._on_settings_save)

    def _on_settings_save(self, settings: dict) -> None:
        """Handle settings save."""
        logger.info(f"Settings saved: {settings}")
        # Apply theme change if different
        if settings.get('theme') != self._theme_config.colors.__class__.__name__.lower():
            self._toast_manager.info("Theme change will apply on restart", title="Settings")

    def _show_shortcuts(self) -> None:
        """Show keyboard shortcuts overlay."""
        self._shortcuts_overlay.show()

    def _refresh_current_view(self) -> None:
        """Refresh the current view."""
        dispatch(EventType.REFRESH_REQUESTED)
        self.set_status("Refreshing...")
        self._toast_manager.info("View refreshed")

    def _toggle_theme(self) -> None:
        """Toggle between light and dark theme."""
        self._toast_manager.info("Theme toggle coming soon", title="Theme")

    def _emergency_stop(self) -> None:
        """Emergency stop all trading."""
        if messagebox.askyesno("Emergency Stop", "Are you sure you want to stop all trading?"):
            dispatch(EventType.EMERGENCY_STOP)
            self._toast_manager.warning("Emergency stop activated", title="TRADING HALTED")

    def _confirm_close_all(self) -> None:
        """Confirm and close all positions."""
        if messagebox.askyesno("Close All", "Are you sure you want to close all positions?"):
            dispatch(EventType.CLOSE_ALL_POSITIONS)
            self._toast_manager.info("Closing all positions...", title="Position Management")

    def _on_view_changed(self, event) -> None:
        """Handle view change event."""
        pass

    def _on_error(self, event) -> None:
        """Handle error event."""
        error = event.data.get('error', 'Unknown error')
        self.set_status(f"● Error: {error}")
        self._toast_manager.error(error, title="Error")

    def _on_notification(self, event) -> None:
        """Handle notification event."""
        message = event.data.get('message', '')
        level = event.data.get('level', 'info')

        level_map = {
            'info': ToastLevel.INFO,
            'success': ToastLevel.SUCCESS,
            'warning': ToastLevel.WARNING,
            'error': ToastLevel.ERROR,
        }
        toast_level = level_map.get(level, ToastLevel.INFO)
        self._toast_manager.show(message, toast_level)

    def set_status(self, text: str, success: bool = True) -> None:
        """Set status bar text."""
        colors = self._theme_config.colors
        color = colors.bullish if success else colors.bearish
        self._status_label.config(text=f"● {text}", fg=color)

    def schedule_task(self, task: Callable) -> None:
        """Schedule a task to run on the main thread."""
        self._task_queue.put(task)

    def _process_queue(self) -> None:
        """Process tasks from the queue."""
        try:
            while True:
                task = self._task_queue.get_nowait()
                try:
                    task()
                except Exception as e:
                    logger.error(f"Task error: {e}")
        except queue.Empty:
            pass

        # Schedule next check
        self.after(100, self._process_queue)

    def _on_close(self) -> None:
        """Handle window close."""
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?"):
            logger.info("Application closing")
            self.destroy()

    def run(self) -> None:
        """Start the application main loop."""
        logger.info("Starting application main loop")
        self.mainloop()


def launch_ui(
    run_id: str = None,
    mode: str = "paper",
    theme: ColorScheme = ColorScheme.DARK,
) -> AppShell:
    """
    Launch the UI application.

    Args:
        run_id: Current run ID
        mode: Trading mode (paper, live, backtest)
        theme: Color scheme

    Returns:
        AppShell instance
    """
    app = AppShell(
        run_id=run_id,
        mode=mode,
        theme=theme,
    )
    return app


if __name__ == "__main__":
    # Test launch
    logging.basicConfig(level=logging.DEBUG)
    app = launch_ui(run_id="test-run-001", mode="paper")
    app.run()
