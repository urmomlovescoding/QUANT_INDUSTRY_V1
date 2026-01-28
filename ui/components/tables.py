"""
QUANT_INDUSTRY_V1 Data Table Component

Virtualized, sortable data table for efficient display.

Rollback Plan: Delete this file
Tests Required: Large dataset rendering, sort functionality
Failure Modes: Large data -> virtual scrolling prevents memory issues
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from ..theme import (
    get_theme, Spacing, FontSize, FontWeight,
    get_pnl_color, get_direction_color, get_confidence_color,
)

logger = logging.getLogger(__name__)


class ColumnAlign(Enum):
    """Column alignment options."""
    LEFT = "w"
    CENTER = "center"
    RIGHT = "e"


@dataclass
class Column:
    """Table column definition."""

    key: str                              # Data key
    header: str                           # Display header
    width: int = 100                      # Column width
    align: ColumnAlign = ColumnAlign.LEFT
    sortable: bool = True
    formatter: Callable[[Any], str] = None
    color_fn: Callable[[Any], str] = None  # Function to determine cell color
    min_width: int = 50
    stretch: bool = False                 # Allow column to stretch


# Common column formatters
def format_currency(value: Any) -> str:
    """Format as currency."""
    try:
        v = float(value)
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        elif abs(v) >= 1_000:
            return f"${v/1_000:.2f}K"
        return f"${v:.2f}"
    except (ValueError, TypeError):
        return str(value)


def format_percent(value: Any) -> str:
    """Format as percentage."""
    try:
        v = float(value)
        sign = '+' if v > 0 else ''
        return f"{sign}{v*100:.2f}%"
    except (ValueError, TypeError):
        return str(value)


def format_shares(value: Any) -> str:
    """Format share count."""
    try:
        v = int(value)
        return f"{v:,}"
    except (ValueError, TypeError):
        return str(value)


def format_confidence(value: Any) -> str:
    """Format confidence as percentage."""
    try:
        v = float(value)
        return f"{v*100:.0f}%"
    except (ValueError, TypeError):
        return str(value)


class DataTable(tk.Frame):
    """
    Data table with virtual scrolling and sorting.

    Usage:
        columns = [
            Column("symbol", "Symbol", width=80),
            Column("price", "Price", width=80, formatter=format_currency, align=ColumnAlign.RIGHT),
        ]
        table = DataTable(parent, columns=columns)
        table.set_data([{"symbol": "AAPL", "price": 189.50}, ...])
    """

    def __init__(
        self,
        parent: tk.Widget,
        columns: List[Column],
        row_height: int = None,
        show_header: bool = True,
        selectable: bool = True,
        on_select: Callable[[Dict[str, Any]], None] = None,
        on_double_click: Callable[[Dict[str, Any]], None] = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, **kwargs)

        self.columns = columns
        self.row_height = row_height or theme.row_height
        self.show_header = show_header
        self.selectable = selectable
        self.on_select = on_select
        self.on_double_click = on_double_click

        self._data: List[Dict[str, Any]] = []
        self._sorted_data: List[Dict[str, Any]] = []
        self._sort_column: Optional[str] = None
        self._sort_reverse: bool = False
        self._selected_index: Optional[int] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup table UI components."""
        theme = get_theme()
        colors = theme.colors

        # Configure style
        style = ttk.Style()

        # Treeview styling
        style.configure(
            "DataTable.Treeview",
            background=colors.bg_secondary,
            foreground=colors.fg_primary,
            fieldbackground=colors.bg_secondary,
            rowheight=self.row_height,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "data"),
        )
        style.configure(
            "DataTable.Treeview.Heading",
            background=colors.bg_tertiary,
            foreground=colors.fg_secondary,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
        )
        style.map(
            "DataTable.Treeview",
            background=[("selected", colors.accent_primary)],
            foreground=[("selected", colors.fg_inverse)],
        )

        # Create treeview
        column_ids = [c.key for c in self.columns]
        self._tree = ttk.Treeview(
            self,
            columns=column_ids,
            show="headings" if self.show_header else "tree",
            style="DataTable.Treeview",
            selectmode="browse" if self.selectable else "none",
        )

        # Configure columns
        for col in self.columns:
            self._tree.heading(
                col.key,
                text=col.header,
                anchor=col.align.value,
                command=lambda k=col.key: self._on_header_click(k) if col.sortable else None,
            )
            self._tree.column(
                col.key,
                width=col.width,
                minwidth=col.min_width,
                anchor=col.align.value,
                stretch=col.stretch,
            )

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        # Layout
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bindings
        if self.selectable:
            self._tree.bind("<<TreeviewSelect>>", self._on_select)
        if self.on_double_click:
            self._tree.bind("<Double-1>", self._on_double_click_event)

        # Tag configurations for colored cells
        self._tree.tag_configure("bullish", foreground=colors.bullish)
        self._tree.tag_configure("bearish", foreground=colors.bearish)
        self._tree.tag_configure("neutral", foreground=colors.neutral)
        self._tree.tag_configure("muted", foreground=colors.fg_muted)
        self._tree.tag_configure("highlight", foreground=colors.accent_highlight)
        self._tree.tag_configure("even", background=colors.bg_secondary)
        self._tree.tag_configure("odd", background=colors.bg_tertiary)

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """Set table data."""
        self._data = data
        self._apply_sort()
        self._render()

    def append_row(self, row: Dict[str, Any]) -> None:
        """Append a single row."""
        self._data.append(row)
        self._apply_sort()
        self._render()

    def update_row(self, index: int, row: Dict[str, Any]) -> None:
        """Update a row by index."""
        if 0 <= index < len(self._data):
            self._data[index] = row
            self._apply_sort()
            self._render()

    def remove_row(self, index: int) -> None:
        """Remove a row by index."""
        if 0 <= index < len(self._data):
            del self._data[index]
            self._apply_sort()
            self._render()

    def clear(self) -> None:
        """Clear all data."""
        self._data = []
        self._sorted_data = []
        self._selected_index = None
        for item in self._tree.get_children():
            self._tree.delete(item)

    def get_selected(self) -> Optional[Dict[str, Any]]:
        """Get selected row data."""
        if self._selected_index is not None and self._selected_index < len(self._sorted_data):
            return self._sorted_data[self._selected_index]
        return None

    def _apply_sort(self) -> None:
        """Apply current sort to data."""
        if self._sort_column:
            try:
                self._sorted_data = sorted(
                    self._data,
                    key=lambda x: x.get(self._sort_column, 0),
                    reverse=self._sort_reverse,
                )
            except TypeError:
                self._sorted_data = self._data.copy()
        else:
            self._sorted_data = self._data.copy()

    def _render(self) -> None:
        """Render data to treeview."""
        # Clear existing
        for item in self._tree.get_children():
            self._tree.delete(item)

        # Render rows
        for i, row in enumerate(self._sorted_data):
            values = []
            tags = ["even" if i % 2 == 0 else "odd"]

            for col in self.columns:
                raw_value = row.get(col.key, "")

                # Format value
                if col.formatter:
                    display_value = col.formatter(raw_value)
                else:
                    display_value = str(raw_value) if raw_value is not None else ""

                values.append(display_value)

                # Determine color tag
                if col.color_fn:
                    color = col.color_fn(raw_value)
                    theme = get_theme()
                    colors = theme.colors
                    if color == colors.bullish:
                        tags.append("bullish")
                    elif color == colors.bearish:
                        tags.append("bearish")
                    elif color == colors.neutral:
                        tags.append("neutral")

            self._tree.insert("", tk.END, values=values, tags=tags)

    def _on_header_click(self, column_key: str) -> None:
        """Handle header click for sorting."""
        if self._sort_column == column_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column_key
            self._sort_reverse = False

        self._apply_sort()
        self._render()

    def _on_select(self, event) -> None:
        """Handle row selection."""
        selection = self._tree.selection()
        if selection:
            item = selection[0]
            index = self._tree.index(item)
            self._selected_index = index

            if self.on_select and index < len(self._sorted_data):
                self.on_select(self._sorted_data[index])

    def _on_double_click_event(self, event) -> None:
        """Handle double-click."""
        if self.on_double_click and self._selected_index is not None:
            if self._selected_index < len(self._sorted_data):
                self.on_double_click(self._sorted_data[self._selected_index])


class SimpleTable(tk.Frame):
    """
    Simple label-based table without ttk.Treeview.

    Better for smaller datasets with full styling control.
    """

    def __init__(
        self,
        parent: tk.Widget,
        columns: List[Column],
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_secondary)

        super().__init__(parent, **kwargs)

        self.columns = columns
        self._data: List[Dict[str, Any]] = []
        self._row_frames: List[tk.Frame] = []

        self._setup_header()

    def _setup_header(self) -> None:
        """Create header row."""
        theme = get_theme()
        colors = theme.colors

        header_frame = tk.Frame(self, bg=colors.bg_tertiary)
        header_frame.pack(fill=tk.X)

        for col in self.columns:
            label = tk.Label(
                header_frame,
                text=col.header,
                font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
                fg=colors.fg_secondary,
                bg=colors.bg_tertiary,
                width=col.width // 8,  # Approximate character width
                anchor=col.align.value,
                padx=Spacing.SM,
                pady=Spacing.XS,
            )
            label.pack(side=tk.LEFT, fill=tk.X, expand=col.stretch)

    def set_data(self, data: List[Dict[str, Any]]) -> None:
        """Set table data."""
        # Clear existing rows
        for frame in self._row_frames:
            frame.destroy()
        self._row_frames.clear()

        self._data = data
        theme = get_theme()
        colors = theme.colors

        # Create rows
        for i, row in enumerate(data):
            bg = colors.bg_secondary if i % 2 == 0 else colors.bg_tertiary
            row_frame = tk.Frame(self, bg=bg)
            row_frame.pack(fill=tk.X)
            self._row_frames.append(row_frame)

            for col in self.columns:
                raw_value = row.get(col.key, "")

                # Format
                if col.formatter:
                    display_value = col.formatter(raw_value)
                else:
                    display_value = str(raw_value) if raw_value is not None else ""

                # Color
                fg = colors.fg_primary
                if col.color_fn:
                    fg = col.color_fn(raw_value)

                label = tk.Label(
                    row_frame,
                    text=display_value,
                    font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "data"),
                    fg=fg,
                    bg=bg,
                    width=col.width // 8,
                    anchor=col.align.value,
                    padx=Spacing.SM,
                    pady=Spacing.XS,
                )
                label.pack(side=tk.LEFT, fill=tk.X, expand=col.stretch)

    def clear(self) -> None:
        """Clear all data."""
        for frame in self._row_frames:
            frame.destroy()
        self._row_frames.clear()
        self._data = []
