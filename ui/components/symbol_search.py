"""
QUANT_INDUSTRY_V1 Symbol Search

Professional symbol search with autocomplete and recent symbols.
"""

import tkinter as tk
from typing import List, Dict, Any, Callable, Optional
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


# Sample symbol data
SYMBOLS_DATA = [
    {"symbol": "AAPL", "name": "Apple Inc.", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "Stock", "exchange": "NASDAQ"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "type": "Stock", "exchange": "NYSE"},
    {"symbol": "V", "name": "Visa Inc.", "type": "Stock", "exchange": "NYSE"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "type": "Stock", "exchange": "NYSE"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "type": "ETF", "exchange": "NYSE"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "type": "ETF", "exchange": "NASDAQ"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "type": "ETF", "exchange": "NYSE"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "type": "ETF", "exchange": "NYSE"},
    {"symbol": "TLT", "name": "iShares 20+ Year Treasury Bond ETF", "type": "ETF", "exchange": "NASDAQ"},
    {"symbol": "BTC-USD", "name": "Bitcoin USD", "type": "Crypto", "exchange": "Crypto"},
    {"symbol": "ETH-USD", "name": "Ethereum USD", "type": "Crypto", "exchange": "Crypto"},
]


class SymbolSearch(tk.Frame):
    """
    Symbol search with autocomplete dropdown.

    Features:
    - Fuzzy search on symbol and name
    - Recent symbols history
    - Type indicators (Stock, ETF, Crypto)
    - Keyboard navigation
    """

    def __init__(
        self,
        parent: tk.Widget,
        symbols: List[Dict[str, Any]] = None,
        on_select: Callable[[Dict[str, Any]], None] = None,
        placeholder: str = "Search symbols...",
        max_results: int = 10,
        show_recent: bool = True,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)

        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._symbols = symbols or SYMBOLS_DATA
        self._on_select = on_select
        self._placeholder = placeholder
        self._max_results = max_results
        self._show_recent = show_recent

        self._recent: List[str] = []
        self._results: List[Dict[str, Any]] = []
        self._selected_index = -1
        self._dropdown = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the search UI."""
        colors = self._colors
        theme = self._theme

        # Search container
        search_frame = tk.Frame(self, bg=colors.bg_tertiary)
        search_frame.pack(fill=tk.X)

        inner = tk.Frame(search_frame, bg=colors.bg_tertiary)
        inner.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        # Search icon
        icon = tk.Label(
            inner,
            text="🔍",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        )
        icon.pack(side=tk.LEFT)

        # Search entry
        self._entry = tk.Entry(
            inner,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            insertbackground=colors.fg_primary,
            relief=tk.FLAT,
            width=20,
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=Spacing.XS)

        # Placeholder
        self._entry.insert(0, self._placeholder)
        self._entry.config(fg=colors.fg_muted)
        self._has_placeholder = True

        # Bindings
        self._entry.bind('<FocusIn>', self._on_focus_in)
        self._entry.bind('<FocusOut>', self._on_focus_out)
        self._entry.bind('<KeyRelease>', self._on_key_release)
        self._entry.bind('<Return>', self._on_enter)
        self._entry.bind('<Up>', self._on_arrow_up)
        self._entry.bind('<Down>', self._on_arrow_down)
        self._entry.bind('<Escape>', self._on_escape)

    def _on_focus_in(self, event) -> None:
        """Handle focus in."""
        if self._has_placeholder:
            self._entry.delete(0, tk.END)
            self._entry.config(fg=self._colors.fg_primary)
            self._has_placeholder = False

        # Show recent if empty
        if not self._entry.get() and self._show_recent and self._recent:
            self._show_recent_dropdown()

    def _on_focus_out(self, event) -> None:
        """Handle focus out."""
        # Delay to allow dropdown clicks
        self.after(200, self._check_focus_out)

    def _check_focus_out(self) -> None:
        """Check and handle focus out."""
        if not self._entry.get():
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=self._colors.fg_muted)
            self._has_placeholder = True

        self._hide_dropdown()

    def _on_key_release(self, event) -> None:
        """Handle key release for search."""
        if event.keysym in ('Up', 'Down', 'Return', 'Escape'):
            return

        query = self._entry.get().strip()
        if query and not self._has_placeholder:
            self._search(query)
        else:
            self._hide_dropdown()

    def _on_enter(self, event) -> None:
        """Handle enter key."""
        if self._results and 0 <= self._selected_index < len(self._results):
            self._select_result(self._results[self._selected_index])
        elif self._results:
            self._select_result(self._results[0])

    def _on_arrow_up(self, event) -> None:
        """Handle arrow up."""
        if self._results:
            self._selected_index = max(-1, self._selected_index - 1)
            self._update_selection()

    def _on_arrow_down(self, event) -> None:
        """Handle arrow down."""
        if self._results:
            self._selected_index = min(len(self._results) - 1, self._selected_index + 1)
            self._update_selection()

    def _on_escape(self, event) -> None:
        """Handle escape key."""
        self._hide_dropdown()
        self._entry.delete(0, tk.END)

    def _search(self, query: str) -> None:
        """Search for symbols."""
        query_lower = query.lower()

        results = []
        for symbol_data in self._symbols:
            symbol = symbol_data.get('symbol', '').lower()
            name = symbol_data.get('name', '').lower()

            # Score based on match position and type
            score = 0
            if symbol.startswith(query_lower):
                score = 100  # Best match
            elif query_lower in symbol:
                score = 80
            elif name.startswith(query_lower):
                score = 60
            elif query_lower in name:
                score = 40

            if score > 0:
                results.append((score, symbol_data))

        # Sort by score
        results.sort(key=lambda x: -x[0])
        self._results = [r[1] for r in results[:self._max_results]]
        self._selected_index = -1

        self._show_dropdown()

    def _show_dropdown(self) -> None:
        """Show search results dropdown."""
        self._hide_dropdown()

        if not self._results:
            return

        colors = self._colors
        theme = self._theme

        self._dropdown = tk.Toplevel(self)
        self._dropdown.overrideredirect(True)
        self._dropdown.attributes('-topmost', True)

        # Position below entry
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        width = self.winfo_width()

        self._dropdown.geometry(f"{width}x{min(len(self._results) * 40, 300)}+{x}+{y}")

        # Frame with border
        frame = tk.Frame(self._dropdown, bg=colors.border)
        frame.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(frame, bg=colors.bg_elevated)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._result_widgets = []
        for i, result in enumerate(self._results):
            widget = self._create_result_item(inner, result, i)
            self._result_widgets.append(widget)

    def _show_recent_dropdown(self) -> None:
        """Show recent symbols dropdown."""
        if not self._recent:
            return

        self._results = [
            s for s in self._symbols
            if s.get('symbol') in self._recent
        ]
        self._selected_index = -1
        self._show_dropdown()

    def _create_result_item(self, parent: tk.Frame, result: Dict[str, Any], index: int) -> tk.Frame:
        """Create a result item widget."""
        colors = self._colors
        theme = self._theme

        frame = tk.Frame(parent, bg=colors.bg_elevated, cursor="hand2")
        frame.pack(fill=tk.X)

        inner = tk.Frame(frame, bg=colors.bg_elevated)
        inner.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        # Type badge
        type_colors = {
            "Stock": colors.accent_primary,
            "ETF": colors.accent_secondary,
            "Crypto": colors.warning,
        }
        symbol_type = result.get('type', 'Stock')
        type_color = type_colors.get(symbol_type, colors.fg_muted)

        type_badge = tk.Label(
            inner,
            text=symbol_type[:3].upper(),
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=type_color,
            padx=4,
            pady=1,
        )
        type_badge.pack(side=tk.LEFT)

        # Symbol
        symbol_label = tk.Label(
            inner,
            text=result.get('symbol', ''),
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        )
        symbol_label.pack(side=tk.LEFT, padx=Spacing.SM)

        # Name
        name_label = tk.Label(
            inner,
            text=result.get('name', ''),
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
            anchor="w",
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Exchange
        exchange_label = tk.Label(
            inner,
            text=result.get('exchange', ''),
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        )
        exchange_label.pack(side=tk.RIGHT)

        # Bindings
        for widget in [frame, inner, type_badge, symbol_label, name_label, exchange_label]:
            widget.bind('<Button-1>', lambda e, r=result: self._select_result(r))
            widget.bind('<Enter>', lambda e, f=frame, i=inner, idx=index: self._on_result_hover(f, i, idx, True))
            widget.bind('<Leave>', lambda e, f=frame, i=inner, idx=index: self._on_result_hover(f, i, idx, False))

        return frame

    def _on_result_hover(self, frame: tk.Frame, inner: tk.Frame, index: int, enter: bool) -> None:
        """Handle result hover."""
        colors = self._colors
        bg = colors.bg_hover if enter else colors.bg_elevated

        frame.config(bg=bg)
        inner.config(bg=bg)
        for child in inner.winfo_children():
            if not hasattr(child, '_is_badge'):
                child.config(bg=bg)

    def _update_selection(self) -> None:
        """Update visual selection."""
        if not self._dropdown or not self._result_widgets:
            return

        colors = self._colors

        for i, widget in enumerate(self._result_widgets):
            if i == self._selected_index:
                widget.config(bg=colors.bg_hover)
                for child in widget.winfo_children():
                    child.config(bg=colors.bg_hover)
                    for grandchild in child.winfo_children():
                        if not hasattr(grandchild, '_is_badge'):
                            grandchild.config(bg=colors.bg_hover)
            else:
                widget.config(bg=colors.bg_elevated)
                for child in widget.winfo_children():
                    child.config(bg=colors.bg_elevated)
                    for grandchild in child.winfo_children():
                        if not hasattr(grandchild, '_is_badge'):
                            grandchild.config(bg=colors.bg_elevated)

    def _select_result(self, result: Dict[str, Any]) -> None:
        """Select a search result."""
        symbol = result.get('symbol', '')

        # Update entry
        self._entry.delete(0, tk.END)
        self._entry.insert(0, symbol)
        self._has_placeholder = False

        # Add to recent
        if symbol not in self._recent:
            self._recent.insert(0, symbol)
            self._recent = self._recent[:5]  # Keep last 5

        self._hide_dropdown()

        # Callback
        if self._on_select:
            self._on_select(result)

    def _hide_dropdown(self) -> None:
        """Hide the dropdown."""
        if self._dropdown:
            self._dropdown.destroy()
            self._dropdown = None
            self._results = []

    def get_value(self) -> str:
        """Get current symbol value."""
        if self._has_placeholder:
            return ""
        return self._entry.get().strip()

    def set_value(self, value: str) -> None:
        """Set the search value."""
        self._entry.delete(0, tk.END)
        if value:
            self._entry.insert(0, value)
            self._entry.config(fg=self._colors.fg_primary)
            self._has_placeholder = False
        else:
            self._entry.insert(0, self._placeholder)
            self._entry.config(fg=self._colors.fg_muted)
            self._has_placeholder = True

    def clear(self) -> None:
        """Clear the search."""
        self.set_value("")
        self._hide_dropdown()


class SymbolSearchPopup(tk.Toplevel):
    """
    Popup symbol search dialog.

    Full-featured search in a modal dialog.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Callable[[Dict[str, Any]], None] = None,
        title: str = "Search Symbols",
        **kwargs
    ):
        super().__init__(parent)

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme
        self._on_select = on_select

        # Window setup
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self._center_window()

    def _setup_ui(self) -> None:
        """Build the popup UI."""
        colors = self._colors
        theme = self._theme

        self.configure(bg=colors.bg_elevated)

        # Header
        header = tk.Frame(self, bg=colors.bg_tertiary)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="🔍 Search Symbols",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            pady=Spacing.MD,
            padx=Spacing.MD,
        ).pack(side=tk.LEFT)

        close_btn = tk.Label(
            header,
            text="[FAIL]",
            font=theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
            cursor="hand2",
            padx=Spacing.MD,
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind('<Button-1>', lambda e: self.destroy())

        # Search box
        search_frame = tk.Frame(self, bg=colors.bg_elevated)
        search_frame.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.MD)

        self._search = SymbolSearch(
            search_frame,
            on_select=self._on_symbol_select,
            placeholder="Type symbol or company name...",
            max_results=15,
        )
        self._search.pack(fill=tk.X)

        # Focus on entry
        self.after(100, lambda: self._search._entry.focus_set())

    def _on_symbol_select(self, result: Dict[str, Any]) -> None:
        """Handle symbol selection."""
        if self._on_select:
            self._on_select(result)
        self.destroy()

    def _center_window(self) -> None:
        """Center on parent."""
        self.update_idletasks()

        width = 400
        height = 120

        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")
