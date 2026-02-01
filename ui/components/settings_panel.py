"""
QUANT_INDUSTRY_V1 Settings Panel

Application settings and preferences modal.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Any
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight, ColorScheme

logger = logging.getLogger(__name__)


class SettingsPanel(tk.Toplevel):
    """
    Settings modal with tabs for different categories.

    Categories:
    - Appearance (theme, fonts)
    - Trading (defaults, confirmations)
    - Notifications (sounds, alerts)
    - Keyboard shortcuts
    - Data (refresh rates, sources)
    """

    def __init__(self, parent: tk.Tk, on_save: Callable = None):
        super().__init__(parent)

        self._parent = parent
        self._on_save = on_save

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Current settings
        self._settings: Dict[str, Any] = {
            'theme': 'dark',
            'confirm_trades': True,
            'confirm_close_all': True,
            'sound_enabled': True,
            'auto_refresh': True,
            'refresh_interval': 5,
            'show_tooltips': True,
            'compact_mode': False,
        }

        # Window setup
        self.title("Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self._center_window()

    def _setup_ui(self) -> None:
        """Build the settings UI."""
        colors = self._colors
        theme = self._theme

        self.configure(bg=colors.bg_elevated)

        # Main container
        container = tk.Frame(self, bg=colors.bg_elevated)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(container, bg=colors.bg_tertiary)
        header.pack(fill=tk.X)

        title = tk.Label(
            header,
            text="[CONFIG] Settings",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            pady=Spacing.MD,
            padx=Spacing.MD,
        )
        title.pack(side=tk.LEFT)

        # Tabs frame
        tabs_frame = tk.Frame(container, bg=colors.bg_secondary)
        tabs_frame.pack(fill=tk.X)

        self._tabs = ["Appearance", "Trading", "Notifications", "Data"]
        self._tab_buttons = {}
        self._current_tab = "Appearance"

        for tab in self._tabs:
            btn = tk.Label(
                tabs_frame,
                text=tab,
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                fg=colors.fg_secondary,
                bg=colors.bg_secondary,
                padx=Spacing.MD,
                pady=Spacing.SM,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT)
            btn.bind('<Button-1>', lambda e, t=tab: self._switch_tab(t))
            self._tab_buttons[tab] = btn

        self._update_tab_styles()

        # Content area
        self._content = tk.Frame(container, bg=colors.bg_elevated)
        self._content.pack(fill=tk.BOTH, expand=True, padx=Spacing.LG, pady=Spacing.MD)

        self._show_tab_content("Appearance")

        # Footer with buttons
        footer = tk.Frame(container, bg=colors.bg_tertiary)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        footer_inner = tk.Frame(footer, bg=colors.bg_tertiary)
        footer_inner.pack(pady=Spacing.MD, padx=Spacing.MD)

        cancel_btn = tk.Label(
            footer_inner,
            text="Cancel",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_secondary,
            padx=Spacing.LG,
            pady=Spacing.SM,
            cursor="hand2",
        )
        cancel_btn.pack(side=tk.LEFT, padx=Spacing.SM)
        cancel_btn.bind('<Button-1>', lambda e: self.destroy())

        save_btn = tk.Label(
            footer_inner,
            text="Save Changes",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.accent_primary,
            padx=Spacing.LG,
            pady=Spacing.SM,
            cursor="hand2",
        )
        save_btn.pack(side=tk.LEFT, padx=Spacing.SM)
        save_btn.bind('<Button-1>', lambda e: self._save())

    def _switch_tab(self, tab: str) -> None:
        """Switch to a different tab."""
        self._current_tab = tab
        self._update_tab_styles()
        self._show_tab_content(tab)

    def _update_tab_styles(self) -> None:
        """Update tab button styles."""
        for tab, btn in self._tab_buttons.items():
            if tab == self._current_tab:
                btn.configure(
                    bg=self._colors.bg_elevated,
                    fg=self._colors.accent_primary,
                    font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                )
            else:
                btn.configure(
                    bg=self._colors.bg_secondary,
                    fg=self._colors.fg_secondary,
                    font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                )

    def _show_tab_content(self, tab: str) -> None:
        """Show content for a tab."""
        # Clear current content
        for widget in self._content.winfo_children():
            widget.destroy()

        if tab == "Appearance":
            self._show_appearance_tab()
        elif tab == "Trading":
            self._show_trading_tab()
        elif tab == "Notifications":
            self._show_notifications_tab()
        elif tab == "Data":
            self._show_data_tab()

    def _show_appearance_tab(self) -> None:
        """Show appearance settings."""
        colors = self._colors
        theme = self._theme

        # Theme selection
        self._add_section_header("Theme")

        theme_frame = tk.Frame(self._content, bg=colors.bg_elevated)
        theme_frame.pack(fill=tk.X, pady=Spacing.SM)

        self._theme_var = tk.StringVar(value=self._settings['theme'])

        themes = [
            ("Dark", "dark", "Professional dark theme"),
            ("Midnight", "midnight", "Deep blue dark theme"),
            ("TradingView", "tradingview", "TradingView-inspired"),
            ("Bloomberg", "bloomberg", "Bloomberg terminal style"),
            ("Light", "light", "Light theme for bright environments"),
        ]

        for name, value, desc in themes:
            row = tk.Frame(theme_frame, bg=colors.bg_elevated)
            row.pack(fill=tk.X, pady=2)

            rb = tk.Radiobutton(
                row,
                text=name,
                variable=self._theme_var,
                value=value,
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                fg=colors.fg_primary,
                bg=colors.bg_elevated,
                selectcolor=colors.bg_tertiary,
                activebackground=colors.bg_elevated,
            )
            rb.pack(side=tk.LEFT)

            desc_label = tk.Label(
                row,
                text=f"- {desc}",
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
                fg=colors.fg_muted,
                bg=colors.bg_elevated,
            )
            desc_label.pack(side=tk.LEFT, padx=Spacing.SM)

        # UI Options
        self._add_section_header("Interface")

        self._tooltips_var = tk.BooleanVar(value=self._settings['show_tooltips'])
        self._add_checkbox("Show tooltips", self._tooltips_var)

        self._compact_var = tk.BooleanVar(value=self._settings['compact_mode'])
        self._add_checkbox("Compact mode (smaller fonts)", self._compact_var)

    def _show_trading_tab(self) -> None:
        """Show trading settings."""
        colors = self._colors
        theme = self._theme

        self._add_section_header("Confirmations")

        self._confirm_trades_var = tk.BooleanVar(value=self._settings['confirm_trades'])
        self._add_checkbox("Confirm before executing trades", self._confirm_trades_var)

        self._confirm_close_var = tk.BooleanVar(value=self._settings['confirm_close_all'])
        self._add_checkbox("Confirm before closing all positions", self._confirm_close_var)

        self._add_section_header("Defaults")

        # Default quantity
        qty_frame = tk.Frame(self._content, bg=colors.bg_elevated)
        qty_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            qty_frame,
            text="Default order quantity:",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        self._default_qty = tk.Entry(
            qty_frame,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            width=10,
            relief=tk.FLAT,
        )
        self._default_qty.insert(0, "100")
        self._default_qty.pack(side=tk.LEFT, padx=Spacing.SM)

    def _show_notifications_tab(self) -> None:
        """Show notification settings."""
        self._add_section_header("Alerts")

        self._sound_var = tk.BooleanVar(value=self._settings['sound_enabled'])
        self._add_checkbox("Enable sound alerts", self._sound_var)

        self._add_section_header("Toast Notifications")

        self._toast_trades_var = tk.BooleanVar(value=True)
        self._add_checkbox("Show trade execution notifications", self._toast_trades_var)

        self._toast_signals_var = tk.BooleanVar(value=True)
        self._add_checkbox("Show new signal notifications", self._toast_signals_var)

        self._toast_errors_var = tk.BooleanVar(value=True)
        self._add_checkbox("Show error notifications", self._toast_errors_var)

    def _show_data_tab(self) -> None:
        """Show data settings."""
        colors = self._colors
        theme = self._theme

        self._add_section_header("Auto Refresh")

        self._auto_refresh_var = tk.BooleanVar(value=self._settings['auto_refresh'])
        self._add_checkbox("Enable auto-refresh", self._auto_refresh_var)

        # Refresh interval
        interval_frame = tk.Frame(self._content, bg=colors.bg_elevated)
        interval_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            interval_frame,
            text="Refresh interval (seconds):",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
        ).pack(side=tk.LEFT)

        self._refresh_interval = tk.Entry(
            interval_frame,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            width=5,
            relief=tk.FLAT,
        )
        self._refresh_interval.insert(0, str(self._settings['refresh_interval']))
        self._refresh_interval.pack(side=tk.LEFT, padx=Spacing.SM)

        self._add_section_header("Data Sources")

        tk.Label(
            self._content,
            text="Data source configuration coming soon...",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w", pady=Spacing.SM)

    def _add_section_header(self, text: str) -> None:
        """Add a section header."""
        header = tk.Label(
            self._content,
            text=text.upper(),
            font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_elevated,
        )
        header.pack(anchor="w", pady=(Spacing.MD, Spacing.XS))

    def _add_checkbox(self, text: str, variable: tk.BooleanVar) -> None:
        """Add a checkbox option."""
        cb = tk.Checkbutton(
            self._content,
            text=text,
            variable=variable,
            font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_primary,
            bg=self._colors.bg_elevated,
            selectcolor=self._colors.bg_tertiary,
            activebackground=self._colors.bg_elevated,
        )
        cb.pack(anchor="w", pady=2)

    def _center_window(self) -> None:
        """Center on parent."""
        self.update_idletasks()

        width = 500
        height = 450

        parent_x = self._parent.winfo_x()
        parent_y = self._parent.winfo_y()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _save(self) -> None:
        """Save settings and close."""
        # Gather settings
        self._settings['theme'] = self._theme_var.get()
        self._settings['show_tooltips'] = self._tooltips_var.get()
        self._settings['compact_mode'] = self._compact_var.get()

        logger.info(f"Settings saved: {self._settings}")

        if self._on_save:
            self._on_save(self._settings)

        # Show confirmation
        from .toast import toast_success
        toast_success("Settings saved successfully", title="Settings")

        self.destroy()
