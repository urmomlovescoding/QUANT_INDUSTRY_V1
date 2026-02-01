"""
QUANT_INDUSTRY_V1 Command Palette

Professional command palette (Ctrl+K) for quick navigation and actions.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Tuple
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class CommandPalette(tk.Toplevel):
    """
    Command palette overlay for quick actions.

    Features:
    - Fuzzy search
    - Keyboard navigation
    - Categorized commands
    - Recent commands
    """

    def __init__(
        self,
        parent: tk.Tk,
        commands: List[Tuple[str, str, str, Callable]],  # (category, name, shortcut, callback)
    ):
        super().__init__(parent)

        self._parent = parent
        self._commands = commands
        self._filtered_commands = commands.copy()
        self._selected_index = 0

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Window setup
        self.withdraw()  # Hide initially
        self.overrideredirect(True)  # No window decorations
        self.attributes('-topmost', True)

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self) -> None:
        """Build the command palette UI."""
        # Main container with border
        self.configure(bg=self._colors.border_light)

        container = tk.Frame(
            self,
            bg=self._colors.bg_elevated,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Search input
        search_frame = tk.Frame(container, bg=self._colors.bg_elevated)
        search_frame.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.MD)

        # Search icon
        search_icon = tk.Label(
            search_frame,
            text="🔍",
            font=self._theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_elevated,
        )
        search_icon.pack(side=tk.LEFT, padx=(0, Spacing.SM))

        # Search entry
        self._search_var = tk.StringVar()
        self._search_var.trace('w', self._on_search_change)

        self._search_entry = tk.Entry(
            search_frame,
            textvariable=self._search_var,
            font=self._theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_primary,
            bg=self._colors.bg_elevated,
            insertbackground=self._colors.accent_primary,
            relief=tk.FLAT,
            width=50,
        )
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Escape hint
        esc_label = tk.Label(
            search_frame,
            text="ESC",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_tertiary,
            padx=4,
            pady=2,
        )
        esc_label.pack(side=tk.RIGHT, padx=Spacing.SM)

        # Separator
        separator = tk.Frame(container, bg=self._colors.border_light, height=1)
        separator.pack(fill=tk.X, pady=0)

        # Results list
        self._results_frame = tk.Frame(
            container,
            bg=self._colors.bg_elevated,
        )
        self._results_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Canvas for scrolling
        self._canvas = tk.Canvas(
            self._results_frame,
            bg=self._colors.bg_elevated,
            highlightthickness=0,
            height=300,
        )
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            self._results_frame,
            orient=tk.VERTICAL,
            command=self._canvas.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        # Inner frame for items
        self._items_frame = tk.Frame(self._canvas, bg=self._colors.bg_elevated)
        self._canvas_window = self._canvas.create_window(
            (0, 0),
            window=self._items_frame,
            anchor="nw",
        )

        self._items_frame.bind('<Configure>', self._on_frame_configure)
        self._canvas.bind('<Configure>', self._on_canvas_configure)

        # Footer with hint
        footer = tk.Frame(container, bg=self._colors.bg_tertiary, height=28)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        hint = tk.Label(
            footer,
            text="^v Navigate  ↵ Select  ⎋ Close",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_tertiary,
        )
        hint.pack(side=tk.LEFT, padx=Spacing.MD)

        # Populate initial results
        self._populate_results()

    def _on_frame_configure(self, event) -> None:
        """Update scroll region."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        """Update inner frame width."""
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _bind_events(self) -> None:
        """Bind keyboard events."""
        self._search_entry.bind('<Up>', self._on_key_up)
        self._search_entry.bind('<Down>', self._on_key_down)
        self._search_entry.bind('<Return>', self._on_select)
        self._search_entry.bind('<Escape>', self._on_escape)
        self.bind('<FocusOut>', self._on_focus_out)

    def _on_search_change(self, *args) -> None:
        """Handle search input change."""
        query = self._search_var.get().lower().strip()

        if not query:
            self._filtered_commands = self._commands.copy()
        else:
            self._filtered_commands = [
                cmd for cmd in self._commands
                if query in cmd[1].lower() or query in cmd[0].lower()
            ]

        self._selected_index = 0
        self._populate_results()

    def _populate_results(self) -> None:
        """Populate the results list."""
        # Clear existing
        for widget in self._items_frame.winfo_children():
            widget.destroy()

        self._result_widgets = []
        current_category = None

        for i, (category, name, shortcut, callback) in enumerate(self._filtered_commands):
            # Category header
            if category != current_category:
                current_category = category
                cat_label = tk.Label(
                    self._items_frame,
                    text=category.upper(),
                    font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
                    fg=self._colors.fg_muted,
                    bg=self._colors.bg_elevated,
                    anchor="w",
                    padx=Spacing.MD,
                    pady=Spacing.XS,
                )
                cat_label.pack(fill=tk.X, pady=(Spacing.SM, 2))

            # Command item
            item_frame = tk.Frame(
                self._items_frame,
                bg=self._colors.bg_elevated,
                cursor="hand2",
            )
            item_frame.pack(fill=tk.X, padx=Spacing.XS)

            # Selection background
            if i == self._selected_index:
                item_frame.configure(bg=self._colors.bg_active)
                fg_color = self._colors.fg_primary
            else:
                fg_color = self._colors.fg_secondary

            # Command name
            name_label = tk.Label(
                item_frame,
                text=name,
                font=self._theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
                fg=fg_color,
                bg=item_frame['bg'],
                anchor="w",
                padx=Spacing.MD,
                pady=Spacing.SM,
            )
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Shortcut badge
            if shortcut:
                shortcut_label = tk.Label(
                    item_frame,
                    text=shortcut,
                    font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                    fg=self._colors.fg_muted,
                    bg=self._colors.bg_tertiary,
                    padx=4,
                    pady=2,
                )
                shortcut_label.pack(side=tk.RIGHT, padx=Spacing.MD)

            # Bind click
            for widget in [item_frame, name_label]:
                widget.bind('<Button-1>', lambda e, idx=i: self._select_item(idx))
                widget.bind('<Enter>', lambda e, frame=item_frame: self._on_item_hover(frame, True))
                widget.bind('<Leave>', lambda e, frame=item_frame, idx=i: self._on_item_hover(frame, False, idx))

            self._result_widgets.append(item_frame)

        # Show "no results" if empty
        if not self._filtered_commands:
            no_results = tk.Label(
                self._items_frame,
                text="No matching commands",
                font=self._theme.get_font(FontSize.MD, FontWeight.NORMAL, "ui"),
                fg=self._colors.fg_muted,
                bg=self._colors.bg_elevated,
                pady=Spacing.XL,
            )
            no_results.pack(fill=tk.X)

    def _on_item_hover(self, frame: tk.Frame, enter: bool, idx: int = None) -> None:
        """Handle item hover."""
        if enter:
            frame.configure(bg=self._colors.bg_hover)
            for child in frame.winfo_children():
                if isinstance(child, tk.Label) and child['bg'] != self._colors.bg_tertiary:
                    child.configure(bg=self._colors.bg_hover)
        else:
            if idx == self._selected_index:
                bg = self._colors.bg_active
            else:
                bg = self._colors.bg_elevated
            frame.configure(bg=bg)
            for child in frame.winfo_children():
                if isinstance(child, tk.Label) and child['bg'] != self._colors.bg_tertiary:
                    child.configure(bg=bg)

    def _on_key_up(self, event) -> None:
        """Handle up arrow."""
        if self._selected_index > 0:
            self._selected_index -= 1
            self._populate_results()
            self._ensure_visible()
        return "break"

    def _on_key_down(self, event) -> None:
        """Handle down arrow."""
        if self._selected_index < len(self._filtered_commands) - 1:
            self._selected_index += 1
            self._populate_results()
            self._ensure_visible()
        return "break"

    def _ensure_visible(self) -> None:
        """Ensure selected item is visible."""
        if self._result_widgets and self._selected_index < len(self._result_widgets):
            widget = self._result_widgets[self._selected_index]
            self._canvas.yview_moveto(0)  # Reset
            # Calculate position
            y = widget.winfo_y()
            canvas_height = self._canvas.winfo_height()
            if y > canvas_height - 50:
                self._canvas.yview_scroll(1, "units")

    def _select_item(self, idx: int) -> None:
        """Select item by index."""
        self._selected_index = idx
        self._on_select(None)

    def _on_select(self, event) -> None:
        """Handle selection."""
        if self._filtered_commands and self._selected_index < len(self._filtered_commands):
            _, name, _, callback = self._filtered_commands[self._selected_index]
            logger.info(f"Command selected: {name}")
            self.hide()
            callback()

    def _on_escape(self, event) -> None:
        """Handle escape key."""
        self.hide()

    def _on_focus_out(self, event) -> None:
        """Handle focus loss."""
        # Check if focus moved to a child
        if event.widget == self:
            self.after(100, self._check_focus)

    def _check_focus(self) -> None:
        """Check if we should hide."""
        try:
            focused = self.focus_get()
            if focused and not str(focused).startswith(str(self)):
                self.hide()
        except tk.TclError:
            pass

    def show(self) -> None:
        """Show the command palette."""
        # Position at top center of parent
        self.update_idletasks()

        parent_x = self._parent.winfo_x()
        parent_y = self._parent.winfo_y()
        parent_width = self._parent.winfo_width()

        palette_width = 600
        x = parent_x + (parent_width - palette_width) // 2
        y = parent_y + 80

        self.geometry(f"{palette_width}x400+{x}+{y}")

        # Reset state
        self._search_var.set("")
        self._selected_index = 0
        self._filtered_commands = self._commands.copy()
        self._populate_results()

        # Show and focus
        self.deiconify()
        self._search_entry.focus_set()

        logger.info("Command palette opened")

    def hide(self) -> None:
        """Hide the command palette."""
        self.withdraw()
        self._parent.focus_set()


class CommandRegistry:
    """Registry for command palette commands."""

    def __init__(self):
        self._commands: List[Tuple[str, str, str, Callable]] = []

    def register(
        self,
        category: str,
        name: str,
        callback: Callable,
        shortcut: str = "",
    ) -> None:
        """Register a command."""
        self._commands.append((category, name, shortcut, callback))

    def get_commands(self) -> List[Tuple[str, str, str, Callable]]:
        """Get all registered commands."""
        return self._commands.copy()

    def clear(self) -> None:
        """Clear all commands."""
        self._commands.clear()


# Global registry
_registry = CommandRegistry()


def get_command_registry() -> CommandRegistry:
    """Get the global command registry."""
    return _registry
