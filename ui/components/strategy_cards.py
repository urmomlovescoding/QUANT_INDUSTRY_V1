"""
QUANT_INDUSTRY_V1 Strategy Performance Cards

Cards showing individual strategy performance metrics.
"""

import tkinter as tk
from typing import Dict, List, Optional, Callable
import logging
import random

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class StrategyCard(tk.Frame):
    """
    Individual strategy performance card.

    Shows:
    - Strategy name and status
    - Return and Sharpe
    - Mini equity curve
    - Win rate bar
    - Active signals count
    """

    def __init__(
        self,
        parent: tk.Widget,
        name: str,
        strategy_type: str = "Alpha",
        total_return: float = 0,
        sharpe: float = 0,
        win_rate: float = 0,
        trades: int = 0,
        active_signals: int = 0,
        status: str = "active",  # active, paused, stopped
        on_click: Callable = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_elevated)
        kwargs.setdefault('cursor', 'hand2')
        kwargs.setdefault('highlightthickness', 1)
        kwargs.setdefault('highlightbackground', colors.border_subtle)
        super().__init__(parent, **kwargs)

        self._name = name
        self._strategy_type = strategy_type
        self._total_return = total_return
        self._sharpe = sharpe
        self._win_rate = win_rate
        self._trades = trades
        self._active_signals = active_signals
        self._status = status
        self._on_click = on_click
        self._colors = colors
        self._theme = theme

        self._setup_ui()
        self._bind_events()

    def _setup_ui(self) -> None:
        """Build card UI."""
        colors = self._colors
        theme = self._theme

        # Main container
        container = tk.Frame(self, bg=colors.bg_elevated)
        container.pack(fill=tk.BOTH, expand=True, padx=Spacing.MD, pady=Spacing.SM)

        # Header row: Name and status
        header = tk.Frame(container, bg=colors.bg_elevated)
        header.pack(fill=tk.X)

        # Strategy type badge
        type_colors = {
            "Alpha": colors.accent_primary,
            "ML": colors.accent_secondary,
            "ICT": colors.warning,
            "SMC": colors.info,
        }
        badge_color = type_colors.get(self._strategy_type, colors.fg_muted)

        type_badge = tk.Label(
            header,
            text=self._strategy_type,
            font=theme.get_font(FontSize.XS, FontWeight.BOLD, "ui"),
            fg=colors.bg_primary,
            bg=badge_color,
            padx=4,
            pady=1,
        )
        type_badge.pack(side=tk.LEFT)

        # Status indicator
        status_colors = {
            "active": colors.bullish,
            "paused": colors.warning,
            "stopped": colors.fg_muted,
        }
        status_color = status_colors.get(self._status, colors.fg_muted)

        status_dot = tk.Label(
            header,
            text="[*]",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=status_color,
            bg=colors.bg_elevated,
        )
        status_dot.pack(side=tk.RIGHT)

        # Strategy name
        name_label = tk.Label(
            container,
            text=self._name,
            font=theme.get_font(FontSize.MD, FontWeight.BOLD, "ui"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
            anchor="w",
        )
        name_label.pack(fill=tk.X, pady=(Spacing.XS, 0))

        # Mini equity curve
        self._mini_chart = tk.Canvas(
            container,
            bg=colors.bg_tertiary,
            height=40,
            highlightthickness=0,
        )
        self._mini_chart.pack(fill=tk.X, pady=Spacing.SM)
        self._draw_mini_curve()

        # Metrics row
        metrics = tk.Frame(container, bg=colors.bg_elevated)
        metrics.pack(fill=tk.X)

        # Return
        ret_color = colors.bullish if self._total_return >= 0 else colors.bearish
        ret_sign = "+" if self._total_return >= 0 else ""

        ret_frame = tk.Frame(metrics, bg=colors.bg_elevated)
        ret_frame.pack(side=tk.LEFT, expand=True)

        tk.Label(
            ret_frame,
            text="Return",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        tk.Label(
            ret_frame,
            text=f"{ret_sign}{self._total_return:.1f}%",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=ret_color,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        # Sharpe
        sharpe_frame = tk.Frame(metrics, bg=colors.bg_elevated)
        sharpe_frame.pack(side=tk.LEFT, expand=True)

        tk.Label(
            sharpe_frame,
            text="Sharpe",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        sharpe_color = colors.bullish if self._sharpe >= 1.5 else colors.fg_primary
        tk.Label(
            sharpe_frame,
            text=f"{self._sharpe:.2f}",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=sharpe_color,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        # Win Rate
        wr_frame = tk.Frame(metrics, bg=colors.bg_elevated)
        wr_frame.pack(side=tk.LEFT, expand=True)

        tk.Label(
            wr_frame,
            text="Win Rate",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        tk.Label(
            wr_frame,
            text=f"{self._win_rate:.0f}%",
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=colors.fg_primary,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        # Signals
        sig_frame = tk.Frame(metrics, bg=colors.bg_elevated)
        sig_frame.pack(side=tk.LEFT, expand=True)

        tk.Label(
            sig_frame,
            text="Signals",
            font=theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=colors.fg_muted,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        sig_color = colors.accent_primary if self._active_signals > 0 else colors.fg_muted
        tk.Label(
            sig_frame,
            text=str(self._active_signals),
            font=theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
            fg=sig_color,
            bg=colors.bg_elevated,
        ).pack(anchor="w")

        # Win rate bar
        wr_bar = tk.Canvas(
            container,
            bg=colors.bg_tertiary,
            height=4,
            highlightthickness=0,
        )
        wr_bar.pack(fill=tk.X, pady=(Spacing.SM, 0))
        self._draw_win_rate_bar(wr_bar)

    def _draw_mini_curve(self) -> None:
        """Draw mini equity curve."""
        self._mini_chart.update_idletasks()
        width = self._mini_chart.winfo_width() or 150
        height = 40

        # Generate sample curve data
        points = []
        y = 20
        for i in range(20):
            y += random.uniform(-3, 4) if self._total_return >= 0 else random.uniform(-4, 3)
            y = max(5, min(35, y))
            x = (i / 19) * width
            points.append((x, y))

        # Draw line
        if len(points) >= 2:
            color = self._colors.bullish if self._total_return >= 0 else self._colors.bearish
            flat_points = [coord for point in points for coord in point]
            self._mini_chart.create_line(flat_points, fill=color, width=2, smooth=True)

    def _draw_win_rate_bar(self, canvas: tk.Canvas) -> None:
        """Draw win rate progress bar."""
        canvas.update_idletasks()
        width = canvas.winfo_width() or 150

        # Background
        canvas.create_rectangle(0, 0, width, 4, fill=self._colors.bg_tertiary, outline="")

        # Fill
        fill_width = int((self._win_rate / 100) * width)
        canvas.create_rectangle(0, 0, fill_width, 4, fill=self._colors.bullish, outline="")

    def _bind_events(self) -> None:
        """Bind click event."""
        def on_enter(e):
            self.configure(highlightbackground=self._colors.accent_primary)

        def on_leave(e):
            self.configure(highlightbackground=self._colors.border_subtle)

        self.bind('<Enter>', on_enter)
        self.bind('<Leave>', on_leave)
        self.bind('<Button-1>', lambda e: self._on_click(self._name) if self._on_click else None)


class StrategyCardsGrid(tk.Frame):
    """
    Grid of strategy performance cards.

    Shows all active strategies with their performance metrics.
    """

    def __init__(
        self,
        parent: tk.Widget,
        strategies: List[Dict] = None,
        columns: int = 3,
        on_strategy_click: Callable = None,
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_primary)
        super().__init__(parent, **kwargs)

        self._columns = columns
        self._on_click = on_strategy_click
        self._colors = colors
        self._theme = theme
        self._cards: Dict[str, StrategyCard] = {}

        # Default strategies if none provided
        self._strategies = strategies or [
            {
                "name": "Momentum Alpha",
                "type": "Alpha",
                "return": 24.5,
                "sharpe": 1.85,
                "win_rate": 62,
                "trades": 47,
                "signals": 3,
                "status": "active",
            },
            {
                "name": "ICT Market Structure",
                "type": "ICT",
                "return": 18.2,
                "sharpe": 1.42,
                "win_rate": 58,
                "trades": 32,
                "signals": 1,
                "status": "active",
            },
            {
                "name": "ML Ensemble",
                "type": "ML",
                "return": 31.7,
                "sharpe": 2.15,
                "win_rate": 67,
                "trades": 89,
                "signals": 5,
                "status": "active",
            },
            {
                "name": "Smart Money Concepts",
                "type": "SMC",
                "return": 15.8,
                "sharpe": 1.28,
                "win_rate": 55,
                "trades": 28,
                "signals": 2,
                "status": "paused",
            },
            {
                "name": "Mean Reversion",
                "type": "Alpha",
                "return": -3.2,
                "sharpe": -0.45,
                "win_rate": 48,
                "trades": 15,
                "signals": 0,
                "status": "stopped",
            },
            {
                "name": "Volatility Breakout",
                "type": "Alpha",
                "return": 12.4,
                "sharpe": 1.12,
                "win_rate": 52,
                "trades": 41,
                "signals": 1,
                "status": "active",
            },
        ]

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the grid."""
        # Header
        header = tk.Frame(self, bg=self._colors.bg_primary)
        header.pack(fill=tk.X, padx=Spacing.MD, pady=Spacing.SM)

        tk.Label(
            header,
            text="STRATEGY PERFORMANCE",
            font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "ui"),
            fg=self._colors.fg_muted,
            bg=self._colors.bg_primary,
        ).pack(side=tk.LEFT)

        # Summary
        active_count = sum(1 for s in self._strategies if s.get("status") == "active")
        total_signals = sum(s.get("signals", 0) for s in self._strategies)

        summary = tk.Label(
            header,
            text=f"{active_count} active  •  {total_signals} signals",
            font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "ui"),
            fg=self._colors.fg_secondary,
            bg=self._colors.bg_primary,
        )
        summary.pack(side=tk.RIGHT)

        # Cards container
        cards_frame = tk.Frame(self, bg=self._colors.bg_primary)
        cards_frame.pack(fill=tk.BOTH, expand=True, padx=Spacing.SM)

        # Configure grid
        for i in range(self._columns):
            cards_frame.columnconfigure(i, weight=1)

        # Create cards
        for i, strategy in enumerate(self._strategies):
            row = i // self._columns
            col = i % self._columns

            card = StrategyCard(
                cards_frame,
                name=strategy["name"],
                strategy_type=strategy.get("type", "Alpha"),
                total_return=strategy.get("return", 0),
                sharpe=strategy.get("sharpe", 0),
                win_rate=strategy.get("win_rate", 0),
                trades=strategy.get("trades", 0),
                active_signals=strategy.get("signals", 0),
                status=strategy.get("status", "active"),
                on_click=self._on_click,
            )
            card.grid(row=row, column=col, sticky="nsew", padx=Spacing.XS, pady=Spacing.XS)
            self._cards[strategy["name"]] = card

    def update_strategy(self, name: str, data: Dict) -> None:
        """Update a strategy's metrics."""
        if name in self._cards:
            # Would need to recreate card with new data
            pass

    def add_strategy(self, strategy: Dict) -> None:
        """Add a new strategy card."""
        self._strategies.append(strategy)
        # Would need to rebuild grid
        pass
