"""
QUANT_INDUSTRY_V1 Signals View

Detailed signal display with explanation.
"""

import tkinter as tk
from typing import Dict, Any, Optional
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight
from ..state import get_store, get_event_bus, EventType
from ..components.base import StyledFrame, Card, StyledLabel
from ..components.indicators import ConfidenceBar, DirectionIndicator
from ..components.tables import DataTable, Column, ColumnAlign, format_currency, format_percent
from ..components.empty_states import NoSignalsState
from ..components.quick_actions import QuickActionsBar

logger = logging.getLogger(__name__)


class SignalsView(tk.Frame):
    """Signals view with detailed signal information."""

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
        """Setup signals view UI."""
        theme = get_theme()
        colors = theme.colors

        # Configure grid
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Row 0: Header with actions and summary
        header = self._create_header()
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=Spacing.MD, pady=Spacing.SM)

        # Signals table
        signals_card = Card(self, title="All Signals", padding="tight")
        signals_card.grid(row=1, column=0, sticky="nsew", padx=Spacing.MD, pady=Spacing.MD)

        columns = [
            Column("symbol", "Symbol", width=70),
            Column("direction", "Direction", width=80, align=ColumnAlign.CENTER),
            Column("strength", "Strength", width=70, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"{v*100:.0f}%" if v else "-"),
            Column("confidence", "Confidence", width=80, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"{v*100:.0f}%" if v else "-"),
            Column("entry_price", "Entry", width=80, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}" if v else "-"),
            Column("stop_loss", "Stop", width=70, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}" if v else "-"),
            Column("take_profit", "Target", width=70, align=ColumnAlign.RIGHT,
                   formatter=lambda v: f"${v:.2f}" if v else "-"),
            Column("expected_return", "E[R]", width=70, align=ColumnAlign.RIGHT,
                   formatter=format_percent),
            Column("regime", "Regime", width=100),
        ]

        self._signals_table = DataTable(
            signals_card.content,
            columns=columns,
            on_select=self._on_signal_select,
        )
        self._signals_table.pack(fill=tk.BOTH, expand=True)

        # Detail panel
        detail_card = Card(self, title="Signal Details", padding="normal")
        detail_card.grid(row=1, column=1, sticky="nsew", padx=Spacing.MD, pady=Spacing.MD)

        self._detail_frame = detail_card.content
        self._detail_placeholder = StyledLabel(
            self._detail_frame,
            text="Select a signal to view details",
            style="caption",
        )
        self._detail_placeholder.pack(expand=True)

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
            text="Signal Analysis",
            font=theme.get_font(FontSize.LG, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_secondary,
        )
        title.pack(side=tk.LEFT)

        # Signal count badge
        state = self._store.state
        signal_count = len(state.signals)
        long_count = sum(1 for s in state.signals.values() if s.direction == "LONG")
        short_count = signal_count - long_count

        summary = tk.Label(
            left,
            text=f"  {signal_count} signals  •  {long_count} long  •  {short_count} short",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_secondary,
        )
        summary.pack(side=tk.LEFT, padx=Spacing.MD)

        # Right: Quick actions
        right = tk.Frame(inner, bg=colors.bg_secondary)
        right.pack(side=tk.RIGHT)

        # Execute selected button
        exec_btn = tk.Label(
            right,
            text="▶ Execute Selected",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=colors.bullish,
            cursor="hand2",
            padx=Spacing.MD,
            pady=Spacing.XS,
        )
        exec_btn.pack(side=tk.LEFT, padx=Spacing.XS)
        exec_btn.bind('<Button-1>', lambda e: self._execute_selected())

        # Filter dropdown placeholder
        filter_btn = tk.Label(
            right,
            text="Filter ▾",
            font=theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
            fg=colors.fg_secondary,
            bg=colors.bg_tertiary,
            cursor="hand2",
            padx=Spacing.MD,
            pady=Spacing.XS,
        )
        filter_btn.pack(side=tk.LEFT, padx=Spacing.XS)

        return frame

    def _execute_selected(self) -> None:
        """Execute selected signal."""
        from ..components.toast import toast_success
        toast_success("Signal execution queued", title="Trade")

    def _bind_events(self) -> None:
        """Bind to state events."""
        self._event_bus.subscribe(EventType.SIGNALS_UPDATED, self._on_signals_updated)

    def _refresh_data(self) -> None:
        """Refresh signals data."""
        state = self._store.state
        signals_data = [
            {
                'symbol': sig.symbol,
                'direction': sig.direction,
                'strength': sig.strength,
                'confidence': sig.confidence,
                'entry_price': sig.entry_price,
                'stop_loss': sig.stop_loss,
                'take_profit': sig.take_profit,
                'expected_return': sig.expected_return,
                'regime': sig.regime,
            }
            for sig in state.signals.values()
        ]
        self._signals_table.set_data(signals_data)

    def _on_signals_updated(self, event) -> None:
        """Handle signals update."""
        self.after(0, self._refresh_data)

    def _on_signal_select(self, row: Dict[str, Any]) -> None:
        """Handle signal selection."""
        # Clear detail frame
        for widget in self._detail_frame.winfo_children():
            widget.destroy()

        if not row:
            self._detail_placeholder = StyledLabel(
                self._detail_frame,
                text="Select a signal to view details",
                style="caption",
            )
            self._detail_placeholder.pack(expand=True)
            return

        theme = get_theme()
        colors = theme.colors

        # Symbol and direction
        header = tk.Frame(self._detail_frame, bg=colors.bg_elevated)
        header.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(header, text=row['symbol'], style="heading").pack(side=tk.LEFT)
        DirectionIndicator(header, direction=row['direction']).pack(side=tk.LEFT, padx=Spacing.MD)

        # Confidence
        conf_frame = tk.Frame(self._detail_frame, bg=colors.bg_elevated)
        conf_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(conf_frame, text="Confidence:", style="caption").pack(side=tk.LEFT)
        ConfidenceBar(conf_frame, confidence=row.get('confidence', 0)).pack(side=tk.LEFT, padx=Spacing.SM)

        # Key metrics
        metrics = [
            ("Entry Price", f"${row.get('entry_price', 0):.2f}"),
            ("Stop Loss", f"${row.get('stop_loss', 0):.2f}"),
            ("Take Profit", f"${row.get('take_profit', 0):.2f}"),
            ("Expected Return", f"{row.get('expected_return', 0)*100:.2f}%"),
            ("Regime", row.get('regime', 'Unknown')),
        ]

        for label, value in metrics:
            row_frame = tk.Frame(self._detail_frame, bg=colors.bg_elevated)
            row_frame.pack(fill=tk.X, pady=2)

            StyledLabel(row_frame, text=f"{label}:", style="caption", width=15).pack(side=tk.LEFT)
            StyledLabel(row_frame, text=value, style="body").pack(side=tk.LEFT)

    def destroy(self) -> None:
        """Clean up."""
        self._event_bus.unsubscribe(EventType.SIGNALS_UPDATED, self._on_signals_updated)
        super().destroy()
