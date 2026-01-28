"""
QUANT_INDUSTRY_V1 Keyboard Shortcuts Overlay

Modal overlay showing all available keyboard shortcuts.
"""

import tkinter as tk
from typing import List, Tuple
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class KeyboardShortcutsOverlay(tk.Toplevel):
    """
    Modal overlay showing keyboard shortcuts.

    Opens with Ctrl+? or from help menu.
    """

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)

        self._parent = parent

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Window setup
        self.withdraw()
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self) -> None:
        """Build the overlay UI."""
        # Semi-transparent background simulation
        self.configure(bg=self._colors.bg_elevated)

        # Main container with border
        container = tk.Frame(
            self,
            bg=self._colors.bg_elevated,
            highlightbackground=self._colors.border_light,
            highlightthickness=1,
        )
        container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Header
        header = tk.Frame(container, bg=self._colors.bg_tertiary)
        header.pack(fill=tk.X)

        title = tk.Label(
            header,
            text="⌨ Keyboard Shortcuts",
            font=self._theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_primary,
            bg=self._colors.bg_tertiary,
            pady=Spacing.MD,
        )
        title.pack(side=tk.LEFT, padx=Spacing.MD)

        close_btn = tk.Label(
            header,
            text="✕",
            font=self._theme.get_font(FontSize.LG, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_tertiary,
            cursor="hand2",
            padx=Spacing.MD,
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind('<Button-1>', lambda e: self.hide())
        close_btn.bind('<Enter>', lambda e: close_btn.config(fg=self._colors.fg_primary))
        close_btn.bind('<Leave>', lambda e: close_btn.config(fg=self._colors.fg_muted))

        # Shortcuts content
        content = tk.Frame(container, bg=self._colors.bg_elevated)
        content.pack(fill=tk.BOTH, expand=True, padx=Spacing.LG, pady=Spacing.MD)

        # Define shortcuts by category
        categories = [
            ("Navigation", [
                ("Ctrl+1", "Go to Dashboard"),
                ("Ctrl+2", "Go to Signals"),
                ("Ctrl+3", "Go to Positions"),
                ("Ctrl+4", "Go to Alpha Lab"),
                ("Ctrl+5", "Go to Analytics"),
                ("Ctrl+6", "Go to Health"),
            ]),
            ("Actions", [
                ("Ctrl+K", "Open Command Palette"),
                ("F5", "Refresh Current View"),
                ("Ctrl+?", "Show Keyboard Shortcuts"),
                ("Ctrl+Q", "Quit Application"),
            ]),
            ("Trading", [
                ("Ctrl+N", "New Order"),
                ("Ctrl+E", "Execute All Signals"),
                ("Ctrl+Shift+X", "Close All Positions"),
                ("Escape", "Emergency Stop"),
            ]),
            ("Data", [
                ("Ctrl+R", "Refresh Data"),
                ("Ctrl+S", "Save Workspace"),
                ("Ctrl+F", "Find Symbol"),
            ]),
        ]

        # Create columns
        columns_frame = tk.Frame(content, bg=self._colors.bg_elevated)
        columns_frame.pack(fill=tk.BOTH, expand=True)

        for i in range(2):
            columns_frame.columnconfigure(i, weight=1)

        col = 0
        row = 0

        for category, shortcuts in categories:
            # Category frame
            cat_frame = tk.Frame(columns_frame, bg=self._colors.bg_elevated)
            cat_frame.grid(row=row, column=col, sticky="nw", padx=Spacing.MD, pady=Spacing.SM)

            # Category header
            cat_label = tk.Label(
                cat_frame,
                text=category.upper(),
                font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
                fg=self._colors.accent_primary,
                bg=self._colors.bg_elevated,
            )
            cat_label.pack(anchor="w", pady=(0, Spacing.XS))

            # Shortcuts
            for key, description in shortcuts:
                shortcut_frame = tk.Frame(cat_frame, bg=self._colors.bg_elevated)
                shortcut_frame.pack(fill=tk.X, pady=2)

                # Key badge
                key_label = tk.Label(
                    shortcut_frame,
                    text=key,
                    font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "data"),
                    fg=self._colors.fg_primary,
                    bg=self._colors.bg_tertiary,
                    padx=6,
                    pady=2,
                )
                key_label.pack(side=tk.LEFT)

                # Description
                desc_label = tk.Label(
                    shortcut_frame,
                    text=description,
                    font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                    fg=self._colors.fg_secondary,
                    bg=self._colors.bg_elevated,
                )
                desc_label.pack(side=tk.LEFT, padx=Spacing.SM)

            # Move to next column
            col += 1
            if col > 1:
                col = 0
                row += 1

        # Footer hint
        footer = tk.Frame(container, bg=self._colors.bg_tertiary)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        hint = tk.Label(
            footer,
            text="Press Escape or click outside to close",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_tertiary,
            pady=Spacing.SM,
        )
        hint.pack()

    def _bind_events(self) -> None:
        """Bind keyboard events."""
        self.bind('<Escape>', lambda e: self.hide())
        self.bind('<FocusOut>', self._on_focus_out)

    def _on_focus_out(self, event) -> None:
        """Handle focus loss."""
        self.after(100, self._check_focus)

    def _check_focus(self) -> None:
        """Check if should hide."""
        try:
            focused = self.focus_get()
            if focused and not str(focused).startswith(str(self)):
                self.hide()
        except tk.TclError:
            pass

    def show(self) -> None:
        """Show the overlay."""
        self.update_idletasks()

        # Center on parent
        parent_x = self._parent.winfo_x()
        parent_y = self._parent.winfo_y()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        overlay_width = 700
        overlay_height = 450

        x = parent_x + (parent_width - overlay_width) // 2
        y = parent_y + (parent_height - overlay_height) // 2

        self.geometry(f"{overlay_width}x{overlay_height}+{x}+{y}")
        self.deiconify()
        self.focus_set()

        logger.info("Keyboard shortcuts overlay opened")

    def hide(self) -> None:
        """Hide the overlay."""
        self.withdraw()
        self._parent.focus_set()


class ShortcutHint(tk.Frame):
    """
    Small inline shortcut hint badge.

    Example: [Ctrl+K]
    """

    def __init__(self, parent: tk.Widget, shortcut: str, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_tertiary)
        super().__init__(parent, **kwargs)

        label = tk.Label(
            self,
            text=shortcut,
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
            padx=4,
            pady=1,
        )
        label.pack()


class ShortcutToast(tk.Toplevel):
    """
    Brief toast showing executed shortcut.

    Appears briefly when a shortcut is used.
    """

    def __init__(self, parent: tk.Tk, action: str, shortcut: str):
        super().__init__(parent)

        self._parent = parent

        theme = get_theme()
        colors = theme.colors

        # Window setup
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=colors.bg_elevated)

        # Content
        container = tk.Frame(self, bg=colors.bg_elevated)
        container.pack(padx=Spacing.MD, pady=Spacing.SM)

        # Shortcut badge
        key_label = tk.Label(
            container,
            text=shortcut,
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            padx=6,
            pady=2,
        )
        key_label.pack(side=tk.LEFT)

        # Action text
        action_label = tk.Label(
            container,
            text=action,
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_elevated,
        )
        action_label.pack(side=tk.LEFT, padx=Spacing.SM)

        # Position at top center
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_width = parent.winfo_width()
        parent_y = parent.winfo_y()

        toast_width = self.winfo_width()
        x = parent_x + (parent_width - toast_width) // 2
        y = parent_y + 60

        self.geometry(f"+{x}+{y}")

        # Auto-hide after delay
        self.after(1500, self.destroy)
