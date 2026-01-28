"""
QUANT_INDUSTRY_V1 Watchlist Component

Real-time symbol watchlist with price updates and quick actions.
"""

import tkinter as tk
from typing import List, Dict, Optional, Callable
import logging
import random

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class WatchlistItem(tk.Frame):
    """Single watchlist item with price and change."""

    def __init__(
        self,
        parent: tk.Widget,
        symbol: str,
        price: float = 0,
        change: float = 0,
        change_pct: float = 0,
        on_click: Callable = None,
        on_trade: Callable = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('cursor', 'hand2')
        super().__init__(parent, **kwargs)

        self._symbol = symbol
        self._price = price
        self._change = change
        self._change_pct = change_pct
        self._on_click = on_click
        self._on_trade = on_trade
        self._colors = colors
        self._theme = theme
        self._is_hovered = False

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self) -> None:
        """Build the item UI."""
        colors = self._colors
        theme = self._theme

        # Main container with padding
        container = tk.Frame(self, bg=colors.bg_elevated)
        container.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        # Left: Symbol
        left = tk.Frame(container, bg=colors.bg_elevated)
        left.pack(side=tk.LEFT, fill=tk.Y)

        self._symbol_label = tk.Label(
            left,
            text=self._symbol,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        )
        self._symbol_label.pack(anchor="w")

        # Mini sparkline placeholder (just a dot for now)
        trend_color = colors.bullish if self._change >= 0 else colors.bearish
        self._trend_dot = tk.Label(
            left,
            text="━━━" if self._change == 0 else ("↗" if self._change > 0 else "↘"),
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=trend_color,
            bg=colors.bg_elevated,
        )
        self._trend_dot.pack(anchor="w")

        # Right: Price and change
        right = tk.Frame(container, bg=colors.bg_elevated)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self._price_label = tk.Label(
            right,
            text=f"${self._price:.2f}",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
            anchor="e",
        )
        self._price_label.pack(anchor="e")

        change_color = colors.bullish if self._change >= 0 else colors.bearish
        change_sign = "+" if self._change >= 0 else ""

        self._change_label = tk.Label(
            right,
            text=f"{change_sign}{self._change_pct:.2f}%",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=change_color,
            bg=colors.bg_elevated,
            anchor="e",
        )
        self._change_label.pack(anchor="e")

        # Quick trade buttons (hidden by default, shown on hover)
        self._buttons_frame = tk.Frame(container, bg=colors.bg_elevated)

        self._buy_btn = tk.Label(
            self._buttons_frame,
            text="BUY",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.bullish,
            padx=4,
            pady=1,
            cursor="hand2",
        )
        self._buy_btn.pack(side=tk.LEFT, padx=1)

        self._sell_btn = tk.Label(
            self._buttons_frame,
            text="SELL",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.bearish,
            padx=4,
            pady=1,
            cursor="hand2",
        )
        self._sell_btn.pack(side=tk.LEFT, padx=1)

    def _bind_events(self) -> None:
        """Bind hover and click events."""
        widgets = [self, self._symbol_label, self._price_label, self._change_label, self._trend_dot]

        for widget in widgets:
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
            widget.bind('<Button-1>', self._handle_click)

        self._buy_btn.bind('<Button-1>', lambda e: self._handle_trade("BUY"))
        self._sell_btn.bind('<Button-1>', lambda e: self._handle_trade("SELL"))

    def _on_enter(self, event) -> None:
        """Show action buttons on hover."""
        self._is_hovered = True
        self.configure(bg=self._colors.bg_hover)
        for child in self.winfo_children():
            self._set_bg_recursive(child, self._colors.bg_hover)
        self._buttons_frame.pack(side=tk.RIGHT, padx=Spacing.XS)

    def _on_leave(self, event) -> None:
        """Hide action buttons."""
        self._is_hovered = False
        self.configure(bg=self._colors.bg_elevated)
        for child in self.winfo_children():
            self._set_bg_recursive(child, self._colors.bg_elevated)
        self._buttons_frame.pack_forget()

    def _set_bg_recursive(self, widget, color) -> None:
        """Recursively set background color."""
        try:
            if widget != self._buy_btn and widget != self._sell_btn:
                widget.configure(bg=color)
            for child in widget.winfo_children():
                self._set_bg_recursive(child, color)
        except tk.TclError:
            pass

    def _handle_click(self, event) -> None:
        """Handle item click."""
        if self._on_click:
            self._on_click(self._symbol)

    def _handle_trade(self, side: str) -> None:
        """Handle trade button click."""
        if self._on_trade:
            self._on_trade(self._symbol, side)

    def update_price(self, price: float, change: float, change_pct: float) -> None:
        """Update price display."""
        self._price = price
        self._change = change
        self._change_pct = change_pct

        self._price_label.config(text=f"${price:.2f}")

        change_color = self._colors.bullish if change >= 0 else self._colors.bearish
        change_sign = "+" if change >= 0 else ""
        self._change_label.config(text=f"{change_sign}{change_pct:.2f}%", fg=change_color)

        trend = "━━━" if change == 0 else ("↗" if change > 0 else "↘")
        self._trend_dot.config(text=trend, fg=change_color)


class Watchlist(tk.Frame):
    """
    Watchlist panel with symbols and real-time updates.

    Features:
    - Add/remove symbols
    - Real-time price updates
    - Quick buy/sell actions
    - Search/filter
    """

    def __init__(
        self,
        parent: tk.Widget,
        symbols: List[str] = None,
        on_symbol_click: Callable = None,
        on_trade: Callable = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)
        super().__init__(parent, **kwargs)

        self._symbols = symbols or ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ"]
        self._on_symbol_click = on_symbol_click
        self._on_trade = on_trade
        self._items: Dict[str, WatchlistItem] = {}
        self._colors = colors
        self._theme = theme

        self._setup_ui()
        self._populate()
        self._start_updates()

    def _setup_ui(self) -> None:
        """Build watchlist UI."""
        colors = self._colors
        theme = self._theme

        # Header with title and add button
        header = tk.Frame(self, bg=colors.bg_secondary)
        header.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.SM)

        title = tk.Label(
            header,
            text="WATCHLIST",
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_secondary,
        )
        title.pack(side=tk.LEFT)

        add_btn = tk.Label(
            header,
            text="+",
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "ui"),
            fg=colors.accent_primary,
            bg=colors.bg_secondary,
            cursor="hand2",
        )
        add_btn.pack(side=tk.RIGHT)
        add_btn.bind('<Button-1>', lambda e: self._show_add_dialog())

        # Search entry
        self._search_var = tk.StringVar()
        self._search_var.trace('w', self._on_search)

        search_frame = tk.Frame(self, bg=colors.bg_tertiary)
        search_frame.pack(fill=tk.X, padx=Spacing.SM, pady=(0, Spacing.SM))

        search_icon = tk.Label(
            search_frame,
            text="🔍",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        search_icon.pack(side=tk.LEFT, padx=Spacing.XS)

        self._search_entry = tk.Entry(
            search_frame,
            textvariable=self._search_var,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            insertbackground=colors.accent_primary,
            relief=tk.FLAT,
        )
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=Spacing.XS)

        # Scrollable list
        self._list_frame = tk.Frame(self, bg=colors.bg_secondary)
        self._list_frame.pack(fill=tk.BOTH, expand=True)

    def _populate(self) -> None:
        """Populate watchlist with items."""
        for symbol in self._symbols:
            # Generate mock data
            base_price = random.uniform(50, 500)
            change = random.uniform(-5, 5)
            change_pct = (change / base_price) * 100

            item = WatchlistItem(
                self._list_frame,
                symbol=symbol,
                price=base_price,
                change=change,
                change_pct=change_pct,
                on_click=self._on_symbol_click,
                on_trade=self._on_trade,
            )
            item.pack(fill=tk.X, pady=1)
            self._items[symbol] = item

    def _on_search(self, *args) -> None:
        """Filter watchlist by search term."""
        query = self._search_var.get().upper()

        for symbol, item in self._items.items():
            if query in symbol:
                item.pack(fill=tk.X, pady=1)
            else:
                item.pack_forget()

    def _show_add_dialog(self) -> None:
        """Show add symbol dialog."""
        # TODO: Implement add symbol dialog
        logger.info("Add symbol dialog requested")

    def _start_updates(self) -> None:
        """Start simulated price updates."""
        self._update_prices()

    def _update_prices(self) -> None:
        """Simulate price updates."""
        for symbol, item in self._items.items():
            # Simulate small price movement
            current_price = item._price
            change = current_price * random.uniform(-0.001, 0.001)
            new_price = current_price + change
            total_change = new_price - (current_price - item._change)
            change_pct = (total_change / (new_price - total_change)) * 100 if new_price != total_change else 0

            item.update_price(new_price, change, change_pct)

        # Schedule next update
        self.after(2000, self._update_prices)

    def add_symbol(self, symbol: str) -> None:
        """Add a symbol to the watchlist."""
        if symbol not in self._items:
            self._symbols.append(symbol)
            base_price = random.uniform(50, 500)

            item = WatchlistItem(
                self._list_frame,
                symbol=symbol,
                price=base_price,
                change=0,
                change_pct=0,
                on_click=self._on_symbol_click,
                on_trade=self._on_trade,
            )
            item.pack(fill=tk.X, pady=1)
            self._items[symbol] = item

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol from the watchlist."""
        if symbol in self._items:
            self._items[symbol].destroy()
            del self._items[symbol]
            self._symbols.remove(symbol)
