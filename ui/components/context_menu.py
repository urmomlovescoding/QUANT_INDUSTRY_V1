"""
QUANT_INDUSTRY_V1 Context Menu

Professional right-click context menus with keyboard shortcuts.
"""

import tkinter as tk
from typing import List, Tuple, Callable, Optional
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class ContextMenu(tk.Toplevel):
    """
    Modern context menu with icons and keyboard shortcuts.

    Features:
    - Icons support
    - Keyboard shortcut hints
    - Separators
    - Hover highlighting
    - Auto-dismiss on click outside
    """

    def __init__(
        self,
        parent: tk.Widget,
        items: List[Tuple[str, str, str, Callable]] = None,
        **kwargs
    ):
        """
        Initialize context menu.

        Args:
            parent: Parent widget
            items: List of (icon, label, shortcut, callback) tuples
                   Use None for separator
        """
        super().__init__(parent)

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme
        self._items = items or []
        self._item_widgets: List[tk.Frame] = []

        # Window setup
        self.withdraw()  # Hidden initially
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        self._setup_ui()

        # Bind events
        self.bind('<FocusOut>', lambda e: self.hide())
        self.bind('<Escape>', lambda e: self.hide())

    def _setup_ui(self) -> None:
        """Build the context menu UI."""
        colors = self._colors
        theme = self._theme

        self.configure(bg=colors.border)

        # Inner frame with padding (creates border effect)
        inner = tk.Frame(self, bg=colors.bg_elevated)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        for item in self._items:
            if item is None:
                # Separator
                sep = tk.Frame(inner, bg=colors.border, height=1)
                sep.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)
            else:
                icon, label, shortcut, callback = item
                self._create_item(inner, icon, label, shortcut, callback)

    def _create_item(
        self,
        parent: tk.Frame,
        icon: str,
        label: str,
        shortcut: str,
        callback: Callable
    ) -> None:
        """Create a menu item."""
        colors = self._colors
        theme = self._theme

        frame = tk.Frame(parent, bg=colors.bg_elevated, cursor="hand2")
        frame.pack(fill=tk.X)

        inner = tk.Frame(frame, bg=colors.bg_elevated)
        inner.pack(fill=tk.X, padx=Spacing.SM, pady=Spacing.XS)

        # Icon
        if icon:
            icon_label = tk.Label(
                inner,
                text=icon,
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                fg=colors.fg_secondary,
                bg=colors.bg_elevated,
                width=2,
            )
            icon_label.pack(side=tk.LEFT)

        # Label
        text_label = tk.Label(
            inner,
            text=label,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
            anchor="w",
        )
        text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=Spacing.XS)

        # Shortcut
        if shortcut:
            shortcut_label = tk.Label(
                inner,
                text=shortcut,
                font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                fg=colors.fg_muted,
                bg=colors.bg_elevated,
            )
            shortcut_label.pack(side=tk.RIGHT)

        # Bindings
        widgets = [frame, inner, text_label]
        if icon:
            widgets.append(icon_label)
        if shortcut:
            widgets.append(shortcut_label)

        for widget in widgets:
            widget.bind('<Enter>', lambda e, f=frame, i=inner: self._on_hover(f, i, True))
            widget.bind('<Leave>', lambda e, f=frame, i=inner: self._on_hover(f, i, False))
            widget.bind('<Button-1>', lambda e, cb=callback: self._on_click(cb))

        self._item_widgets.append(frame)

    def _on_hover(self, frame: tk.Frame, inner: tk.Frame, enter: bool) -> None:
        """Handle hover effect."""
        colors = self._colors
        bg = colors.bg_hover if enter else colors.bg_elevated

        frame.config(bg=bg)
        inner.config(bg=bg)
        for child in inner.winfo_children():
            child.config(bg=bg)

    def _on_click(self, callback: Callable) -> None:
        """Handle menu item click."""
        self.hide()
        if callback:
            callback()

    def show(self, x: int, y: int) -> None:
        """Show menu at position."""
        self.update_idletasks()

        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Get menu dimensions
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        # Adjust position to stay on screen
        if x + width > screen_width:
            x = screen_width - width - 5
        if y + height > screen_height:
            y = screen_height - height - 5

        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.focus_set()

    def hide(self) -> None:
        """Hide the menu."""
        self.withdraw()


class TableContextMenu(ContextMenu):
    """
    Specialized context menu for data tables.

    Pre-configured with common table operations.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_copy: Callable = None,
        on_copy_row: Callable = None,
        on_copy_all: Callable = None,
        on_export_csv: Callable = None,
        on_filter: Callable = None,
        on_sort_asc: Callable = None,
        on_sort_desc: Callable = None,
        extra_items: List[Tuple[str, str, str, Callable]] = None,
        **kwargs
    ):
        items = []

        if on_copy:
            items.append(("[LIST]", "Copy Cell", "Ctrl+C", on_copy))
        if on_copy_row:
            items.append(("[FILE]", "Copy Row", "Ctrl+Shift+C", on_copy_row))
        if on_copy_all:
            items.append(("📑", "Copy All", "", on_copy_all))

        if items and (on_export_csv or on_filter or on_sort_asc):
            items.append(None)  # Separator

        if on_export_csv:
            items.append(("💾", "Export to CSV", "", on_export_csv))

        if on_filter:
            items.append(("🔍", "Filter...", "Ctrl+F", on_filter))

        if on_sort_asc or on_sort_desc:
            items.append(None)  # Separator

        if on_sort_asc:
            items.append(("^", "Sort Ascending", "", on_sort_asc))
        if on_sort_desc:
            items.append(("v", "Sort Descending", "", on_sort_desc))

        if extra_items:
            items.append(None)  # Separator
            items.extend(extra_items)

        super().__init__(parent, items, **kwargs)


class PositionContextMenu(ContextMenu):
    """
    Context menu for position table rows.

    Includes trading actions.
    """

    def __init__(
        self,
        parent: tk.Widget,
        symbol: str = "",
        on_close: Callable = None,
        on_add: Callable = None,
        on_reduce: Callable = None,
        on_set_stop: Callable = None,
        on_set_target: Callable = None,
        on_view_chart: Callable = None,
        on_copy: Callable = None,
        **kwargs
    ):
        items = []

        if on_close:
            items.append(("[FAIL]", f"Close {symbol} Position", "", on_close))
        if on_add:
            items.append(("➕", "Add to Position", "", on_add))
        if on_reduce:
            items.append(("➖", "Reduce Position", "", on_reduce))

        if items:
            items.append(None)  # Separator

        if on_set_stop:
            items.append(("🛑", "Set Stop Loss", "", on_set_stop))
        if on_set_target:
            items.append(("[TARGET]", "Set Take Profit", "", on_set_target))

        if on_view_chart:
            items.append(None)  # Separator
            items.append(("[UP]", f"View {symbol} Chart", "", on_view_chart))

        if on_copy:
            items.append(None)  # Separator
            items.append(("[LIST]", "Copy Details", "Ctrl+C", on_copy))

        super().__init__(parent, items, **kwargs)


class SignalContextMenu(ContextMenu):
    """
    Context menu for signal table rows.

    Includes signal execution actions.
    """

    def __init__(
        self,
        parent: tk.Widget,
        symbol: str = "",
        direction: str = "LONG",
        on_execute: Callable = None,
        on_execute_partial: Callable = None,
        on_dismiss: Callable = None,
        on_add_watchlist: Callable = None,
        on_view_details: Callable = None,
        on_view_chart: Callable = None,
        on_copy: Callable = None,
        **kwargs
    ):
        items = []

        exec_label = f"Execute {symbol} {direction}"
        if on_execute:
            items.append(("▶", exec_label, "Enter", on_execute))
        if on_execute_partial:
            items.append(("[~]", "Execute Partial (50%)", "", on_execute_partial))

        if items:
            items.append(None)  # Separator

        if on_dismiss:
            items.append(("[FAIL]", "Dismiss Signal", "Delete", on_dismiss))

        if on_add_watchlist:
            items.append(None)  # Separator
            items.append(("★", f"Add {symbol} to Watchlist", "", on_add_watchlist))

        if on_view_details:
            items.append(("[INFO]", "View Signal Details", "", on_view_details))

        if on_view_chart:
            items.append(("[UP]", f"View {symbol} Chart", "", on_view_chart))

        if on_copy:
            items.append(None)  # Separator
            items.append(("[LIST]", "Copy Signal", "Ctrl+C", on_copy))

        super().__init__(parent, items, **kwargs)


class WatchlistContextMenu(ContextMenu):
    """
    Context menu for watchlist items.
    """

    def __init__(
        self,
        parent: tk.Widget,
        symbol: str = "",
        on_buy: Callable = None,
        on_sell: Callable = None,
        on_remove: Callable = None,
        on_set_alert: Callable = None,
        on_view_chart: Callable = None,
        on_view_details: Callable = None,
        **kwargs
    ):
        items = []

        if on_buy:
            items.append(("🟢", f"Buy {symbol}", "", on_buy))
        if on_sell:
            items.append(("🔴", f"Sell {symbol}", "", on_sell))

        if items:
            items.append(None)  # Separator

        if on_set_alert:
            items.append(("🔔", "Set Price Alert", "", on_set_alert))

        if on_view_chart:
            items.append(("[UP]", f"View {symbol} Chart", "", on_view_chart))
        if on_view_details:
            items.append(("[INFO]", "View Details", "", on_view_details))

        if on_remove:
            items.append(None)  # Separator
            items.append(("[FAIL]", f"Remove {symbol}", "Delete", on_remove))

        super().__init__(parent, items, **kwargs)


def bind_context_menu(widget: tk.Widget, menu_class: type, **menu_kwargs) -> None:
    """
    Utility to bind context menu to a widget.

    Args:
        widget: Widget to bind to
        menu_class: ContextMenu class to use
        **menu_kwargs: Arguments for the menu constructor
    """
    menu = None

    def show_menu(event):
        nonlocal menu
        if menu:
            menu.destroy()
        menu = menu_class(widget, **menu_kwargs)
        menu.show(event.x_root, event.y_root)

    # Right-click binding (platform-specific)
    widget.bind('<Button-3>', show_menu)  # Windows/Linux
    widget.bind('<Button-2>', show_menu)  # Mac
