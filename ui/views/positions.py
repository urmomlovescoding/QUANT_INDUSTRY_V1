"""
QUANT_INDUSTRY_V1 Positions View

Open and closed positions display.
"""

import tkinter as tk
from typing import Dict, Any
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight
from ..state import get_store, get_event_bus, EventType
from ..components.base import Card, StyledLabel
from ..components.indicators import PnLDisplay
from ..components.tables import DataTable, Column, ColumnAlign, format_currency, format_percent
from ..components.empty_states import NoPositionsState

logger = logging.getLogger(__name__)


class PositionsView(tk.Frame):
    """Positions view with open and closed positions."""

    def __init__(self, parent: tk.Widget, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_primary)

        super().__init__(parent, **kwargs)

        self._store = get_store()
        self._event_bus = get_event_bus()

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self) -> None:
        """Setup positions view UI."""
        theme = get_theme()
        colors = theme.colors

        # Configure grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        # Row 0: Header
        header = self._create_header()
        header.grid(row=0, column=0, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)

        # Open positions
        open_card = Card(self, title="Open Positions", padding="tight")
        open_card.grid(row=1, column=0, sticky="nsew", padx=Spacing.MD, pady=Spacing.MD)

        columns = [
            Column("symbol", "Symbol", width=80),
            Column("side", "Side", width=60, align=ColumnAlign.CENTER,
                   color_fn=lambda s: colors.bullish if s == "long" else colors.bearish),
            Column("qty", "Quantity", width=80, align=ColumnAlign.RIGHT),
            Column("entry_price", "Entry", width=80, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}"),
            Column("current_price", "Current", width=80, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}"),
            Column("unrealized_pnl", "Unrealized P&L", width=100, align=ColumnAlign.RIGHT,
                   formatter=format_currency,
                   color_fn=lambda v: colors.bullish if v > 0 else colors.bearish if v < 0 else colors.fg_secondary),
            Column("stop_loss", "Stop", width=70, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}" if v else "-"),
            Column("take_profit", "Target", width=70, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}" if v else "-"),
        ]

        self._open_table = DataTable(
            open_card.content,
            columns=columns,
        )
        self._open_table.pack(fill=tk.BOTH, expand=True)

        # Summary bar
        summary_frame = tk.Frame(open_card.content, bg=colors.bg_elevated)
        summary_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(summary_frame, text="Total Unrealized:", style="caption").pack(side=tk.LEFT)
        self._total_unrealized = PnLDisplay(summary_frame, value=0)
        self._total_unrealized.pack(side=tk.LEFT, padx=Spacing.SM)

        StyledLabel(summary_frame, text="Positions:", style="caption").pack(side=tk.LEFT, padx=(Spacing.LG, 0))
        self._position_count = StyledLabel(summary_frame, text="0", style="body")
        self._position_count.pack(side=tk.LEFT)

        # Closed positions (placeholder)
        closed_card = Card(self, title="Recent Trades", padding="tight")
        closed_card.grid(row=2, column=0, sticky="nsew", padx=Spacing.MD, pady=Spacing.MD)

        closed_columns = [
            Column("symbol", "Symbol", width=80),
            Column("side", "Side", width=60, align=ColumnAlign.CENTER),
            Column("qty", "Quantity", width=80, align=ColumnAlign.RIGHT),
            Column("entry_price", "Entry", width=80, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}"),
            Column("exit_price", "Exit", width=80, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}"),
            Column("realized_pnl", "P&L", width=100, align=ColumnAlign.RIGHT,
                   formatter=format_currency,
                   color_fn=lambda v: colors.bullish if v > 0 else colors.bearish if v < 0 else colors.fg_secondary),
            Column("exit_reason", "Reason", width=100),
        ]

        self._closed_table = DataTable(
            closed_card.content,
            columns=closed_columns,
        )
        self._closed_table.pack(fill=tk.BOTH, expand=True)

        self._refresh_data()

    def _create_header(self) -> tk.Frame:
        """Create header with summary and actions."""
        theme = get_theme()
        colors = theme.colors

        frame = tk.Frame(self, bg=colors.bg_secondary)

        inner = tk.Frame(frame, bg=colors.bg_secondary)
        inner.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        # Left: Title and summary
        left = tk.Frame(inner, bg=colors.bg_secondary)
        left.pack(side=tk.LEFT, fill=tk.Y)

        title = tk.Label(
            left,
            text="Position Management",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_secondary,
        )
        title.pack(side=tk.LEFT)

        # Position stats
        state = self._store.state
        pos_count = len(state.positions)
        total_value = sum(pos.qty * pos.current_price for pos in state.positions.values())
        total_pnl = sum(pos.unrealized_pnl for pos in state.positions.values())

        pnl_color = colors.bullish if total_pnl >= 0 else colors.bearish
        pnl_sign = "+" if total_pnl >= 0 else ""

        summary = tk.Label(
            left,
            text=f"  {pos_count} positions  •  ${total_value:,.0f} value  •  {pnl_sign}${total_pnl:,.2f} P&L",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_secondary,
        )
        summary.pack(side=tk.LEFT, padx=Spacing.MD)

        # Right: Quick actions
        right = tk.Frame(inner, bg=colors.bg_secondary)
        right.pack(side=tk.RIGHT)

        # Close selected button
        close_btn = tk.Label(
            right,
            text="[FAIL] Close Selected",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.bearish,
            cursor="hand2",
            padx=Spacing.MD,
            pady=Spacing.XS,
        )
        close_btn.pack(side=tk.LEFT, padx=Spacing.XS)
        close_btn.bind('<Button-1>', lambda e: self._close_selected())

        # Add to position
        add_btn = tk.Label(
            right,
            text="+ Add Position",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
            cursor="hand2",
            padx=Spacing.MD,
            pady=Spacing.XS,
        )
        add_btn.pack(side=tk.LEFT, padx=Spacing.XS)

        return frame

    def _close_selected(self) -> None:
        """Close selected position."""
        from ..components.toast import toast_warning
        toast_warning("Position close queued", title="Trade")

    def _bind_events(self) -> None:
        """Bind to state events."""
        self._event_bus.subscribe(EventType.POSITIONS_UPDATED, self._on_positions_updated)

    def _refresh_data(self) -> None:
        """Refresh positions data."""
        state = self._store.state

        positions_data = [
            {
                'symbol': pos.symbol,
                'side': pos.side,
                'qty': pos.qty,
                'entry_price': pos.entry_price,
                'current_price': pos.current_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'stop_loss': pos.stop_loss,
                'take_profit': pos.take_profit,
            }
            for pos in state.positions.values()
        ]
        self._open_table.set_data(positions_data)

        # Update summary
        total_unrealized = sum(pos.unrealized_pnl for pos in state.positions.values())
        self._total_unrealized.set_value(total_unrealized)
        self._position_count.config(text=str(len(state.positions)))

    def _on_positions_updated(self, event) -> None:
        """Handle positions update."""
        self.after(0, self._refresh_data)

    def destroy(self) -> None:
        """Clean up."""
        self._event_bus.unsubscribe(EventType.POSITIONS_UPDATED, self._on_positions_updated)
        super().destroy()
