"""
QUANT_INDUSTRY_V1 Trade Entry Form

Quick order entry form for manual trades.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class TradeEntryForm(tk.Toplevel):
    """
    Quick trade entry modal.

    Features:
    - Symbol lookup
    - Side selection (Buy/Sell)
    - Order type (Market/Limit/Stop)
    - Quantity and price inputs
    - Risk preview
    """

    def __init__(
        self,
        parent: tk.Tk,
        symbol: str = "",
        on_submit: Callable = None,
    ):
        super().__init__(parent)

        self._parent = parent
        self._symbol = symbol
        self._on_submit = on_submit

        theme = get_theme()
        self._colors = theme.colors
        self._theme = theme

        # Window setup
        self.title("Quick Trade")
        self.resizable(False, False)
        self.transient(parent)

        self._setup_ui()
        self._center_window()
        self._bind_events()

        # Focus symbol entry
        self._symbol_entry.focus_set()
        if symbol:
            self._symbol_var.set(symbol)

    def _setup_ui(self) -> None:
        """Build the form UI."""
        colors = self._colors
        theme = self._theme

        self.configure(bg=colors.bg_elevated)

        # Main container
        container = tk.Frame(self, bg=colors.bg_elevated)
        container.pack(fill=tk.BOTH, expand=True, padx=Spacing.LG, pady=Spacing.LG)

        # Header
        header = tk.Frame(container, bg=colors.bg_elevated)
        header.pack(fill=tk.X, pady=(0, Spacing.MD))

        title = tk.Label(
            header,
            text="Quick Trade Entry",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        )
        title.pack(side=tk.LEFT)

        # Symbol input
        symbol_frame = tk.Frame(container, bg=colors.bg_elevated)
        symbol_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            symbol_frame,
            text="Symbol",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        self._symbol_var = tk.StringVar()
        self._symbol_entry = tk.Entry(
            symbol_frame,
            textvariable=self._symbol_var,
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            insertbackground=colors.accent_primary,
            relief=tk.FLAT,
        )
        self._symbol_entry.pack(fill=tk.X, pady=Spacing.XS, ipady=Spacing.XS)

        # Side selection
        side_frame = tk.Frame(container, bg=colors.bg_elevated)
        side_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            side_frame,
            text="Side",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        self._side_var = tk.StringVar(value="BUY")

        side_buttons = tk.Frame(side_frame, bg=colors.bg_elevated)
        side_buttons.pack(fill=tk.X, pady=Spacing.XS)

        self._buy_btn = tk.Label(
            side_buttons,
            text="  BUY  ",
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.bullish,
            cursor="hand2",
            padx=Spacing.MD,
            pady=Spacing.SM,
        )
        self._buy_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, Spacing.XS))

        self._sell_btn = tk.Label(
            side_buttons,
            text="  SELL  ",
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
            cursor="hand2",
            padx=Spacing.MD,
            pady=Spacing.SM,
        )
        self._sell_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self._buy_btn.bind('<Button-1>', lambda e: self._set_side("BUY"))
        self._sell_btn.bind('<Button-1>', lambda e: self._set_side("SELL"))

        # Order type
        type_frame = tk.Frame(container, bg=colors.bg_elevated)
        type_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            type_frame,
            text="Order Type",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        self._type_var = tk.StringVar(value="MARKET")
        type_options = tk.Frame(type_frame, bg=colors.bg_elevated)
        type_options.pack(fill=tk.X, pady=Spacing.XS)

        for order_type in ["MARKET", "LIMIT", "STOP"]:
            btn = tk.Radiobutton(
                type_options,
                text=order_type,
                variable=self._type_var,
                value=order_type,
                font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                fg=colors.fg_secondary,
                bg=colors.bg_elevated,
                selectcolor=colors.bg_tertiary,
                activebackground=colors.bg_elevated,
                activeforeground=colors.accent_primary,
                command=self._on_type_change,
            )
            btn.pack(side=tk.LEFT, padx=Spacing.SM)

        # Quantity
        qty_frame = tk.Frame(container, bg=colors.bg_elevated)
        qty_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            qty_frame,
            text="Quantity",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        self._qty_var = tk.StringVar(value="100")
        qty_entry = tk.Entry(
            qty_frame,
            textvariable=self._qty_var,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            insertbackground=colors.accent_primary,
            relief=tk.FLAT,
            width=15,
        )
        qty_entry.pack(anchor="w", pady=Spacing.XS, ipady=Spacing.XS)

        # Price (for limit/stop)
        self._price_frame = tk.Frame(container, bg=colors.bg_elevated)
        self._price_frame.pack(fill=tk.X, pady=Spacing.SM)

        tk.Label(
            self._price_frame,
            text="Price",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        self._price_var = tk.StringVar()
        self._price_entry = tk.Entry(
            self._price_frame,
            textvariable=self._price_var,
            font=theme.get_font(FontSize.MD, FontWeight.NORMAL, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
            insertbackground=colors.accent_primary,
            relief=tk.FLAT,
            width=15,
            state=tk.DISABLED,
        )
        self._price_entry.pack(anchor="w", pady=Spacing.XS, ipady=Spacing.XS)

        # Risk preview
        risk_frame = tk.Frame(container, bg=colors.bg_tertiary)
        risk_frame.pack(fill=tk.X, pady=Spacing.MD)

        risk_inner = tk.Frame(risk_frame, bg=colors.bg_tertiary)
        risk_inner.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        tk.Label(
            risk_inner,
            text="Estimated Value:",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_tertiary,
        ).pack(side=tk.LEFT)

        self._value_label = tk.Label(
            risk_inner,
            text="$0.00",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_tertiary,
        )
        self._value_label.pack(side=tk.RIGHT)

        # Buttons
        buttons = tk.Frame(container, bg=colors.bg_elevated)
        buttons.pack(fill=tk.X, pady=(Spacing.MD, 0))

        cancel_btn = tk.Label(
            buttons,
            text="Cancel",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
            cursor="hand2",
            padx=Spacing.LG,
            pady=Spacing.SM,
        )
        cancel_btn.pack(side=tk.LEFT)
        cancel_btn.bind('<Button-1>', lambda e: self.destroy())

        submit_btn = tk.Label(
            buttons,
            text="Submit Order",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.accent_primary,
            cursor="hand2",
            padx=Spacing.LG,
            pady=Spacing.SM,
        )
        submit_btn.pack(side=tk.RIGHT)
        submit_btn.bind('<Button-1>', lambda e: self._submit())

    def _set_side(self, side: str) -> None:
        """Set order side."""
        self._side_var.set(side)

        if side == "BUY":
            self._buy_btn.config(bg=self._colors.bullish, fg=self._colors.bg_primary)
            self._sell_btn.config(bg=self._colors.bg_tertiary, fg=self._colors.fg_muted)
        else:
            self._sell_btn.config(bg=self._colors.bearish, fg=self._colors.bg_primary)
            self._buy_btn.config(bg=self._colors.bg_tertiary, fg=self._colors.fg_muted)

    def _on_type_change(self) -> None:
        """Handle order type change."""
        order_type = self._type_var.get()
        if order_type == "MARKET":
            self._price_entry.config(state=tk.DISABLED)
        else:
            self._price_entry.config(state=tk.NORMAL)

    def _bind_events(self) -> None:
        """Bind keyboard events."""
        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<Return>', lambda e: self._submit())

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

    def _submit(self) -> None:
        """Submit the order."""
        order = {
            'symbol': self._symbol_var.get().upper(),
            'side': self._side_var.get(),
            'type': self._type_var.get(),
            'quantity': int(self._qty_var.get() or 0),
            'price': float(self._price_var.get() or 0) if self._type_var.get() != "MARKET" else None,
        }

        logger.info(f"Order submitted: {order}")

        if self._on_submit:
            self._on_submit(order)

        self.destroy()
