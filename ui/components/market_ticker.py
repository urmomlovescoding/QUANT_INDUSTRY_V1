"""
QUANT_INDUSTRY_V1 Market Ticker

Scrolling ticker tape showing market updates and prices.
"""

import tkinter as tk
from typing import List, Dict, Tuple
import logging
import random

from ..theme import get_theme, Spacing, FontSize, FontWeight

logger = logging.getLogger(__name__)


class TickerItem:
    """Single ticker item data."""

    def __init__(self, symbol: str, price: float, change: float, change_pct: float):
        self.symbol = symbol
        self.price = price
        self.change = change
        self.change_pct = change_pct


class MarketTicker(tk.Canvas):
    """
    Scrolling market ticker tape.

    Features:
    - Smooth scrolling animation
    - Color-coded price changes
    - Click to view symbol details
    - Auto-update prices
    """

    def __init__(
        self,
        parent: tk.Widget,
        symbols: List[str] = None,
        speed: int = 2,  # pixels per frame
        **kwargs
    ):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_tertiary)
        kwargs.setdefault('highlightthickness', 0)
        kwargs.setdefault('height', 28)

        super().__init__(parent, **kwargs)

        self._symbols = symbols or [
            "SPY", "QQQ", "DIA", "IWM", "AAPL", "MSFT", "GOOGL", "AMZN",
            "TSLA", "NVDA", "META", "BRK.B", "VIX", "GLD", "TLT", "USO"
        ]
        self._speed = speed
        self._colors = colors
        self._theme = theme
        self._items: List[TickerItem] = []
        self._text_ids: List[int] = []
        self._offset = 0
        self._running = False
        self._total_width = 0

        self._generate_data()
        self._create_ticker()
        self.bind('<Configure>', self._on_configure)

    def _generate_data(self) -> None:
        """Generate mock price data."""
        self._items = []
        for symbol in self._symbols:
            price = random.uniform(50, 500)
            change = random.uniform(-5, 5)
            change_pct = (change / price) * 100
            self._items.append(TickerItem(symbol, price, change, change_pct))

    def _create_ticker(self) -> None:
        """Create ticker text items."""
        self.delete("all")
        self._text_ids = []

        x = 0
        spacing = 30
        item_width = 150

        for item in self._items:
            # Format text
            change_sign = "+" if item.change >= 0 else ""
            text = f"{item.symbol}  ${item.price:.2f}  {change_sign}{item.change_pct:.2f}%"

            # Determine color
            color = self._colors.bullish if item.change >= 0 else self._colors.bearish

            # Create text
            text_id = self.create_text(
                x, 14,
                text=text,
                font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
                fill=color,
                anchor="w",
                tags="ticker"
            )
            self._text_ids.append(text_id)

            # Get text width
            bbox = self.bbox(text_id)
            if bbox:
                text_width = bbox[2] - bbox[0]
                x += text_width + spacing

        self._total_width = x

        # Duplicate for seamless loop
        for item in self._items:
            change_sign = "+" if item.change >= 0 else ""
            text = f"{item.symbol}  ${item.price:.2f}  {change_sign}{item.change_pct:.2f}%"
            color = self._colors.bullish if item.change >= 0 else self._colors.bearish

            text_id = self.create_text(
                x, 14,
                text=text,
                font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "data"),
                fill=color,
                anchor="w",
                tags="ticker"
            )
            self._text_ids.append(text_id)

            bbox = self.bbox(text_id)
            if bbox:
                text_width = bbox[2] - bbox[0]
                x += text_width + spacing

    def _on_configure(self, event) -> None:
        """Handle resize."""
        if not self._running:
            self.start()

    def start(self) -> None:
        """Start ticker animation."""
        if not self._running:
            self._running = True
            self._animate()

    def stop(self) -> None:
        """Stop ticker animation."""
        self._running = False

    def _animate(self) -> None:
        """Animation loop."""
        if not self._running:
            return

        # Move all items left
        self.move("ticker", -self._speed, 0)
        self._offset += self._speed

        # Reset when first set scrolls off
        if self._offset >= self._total_width:
            self._offset = 0
            self.move("ticker", self._total_width, 0)

        self.after(33, self._animate)  # ~30fps

    def update_prices(self) -> None:
        """Update prices with simulated changes."""
        for item in self._items:
            change = item.price * random.uniform(-0.001, 0.001)
            item.price += change
            item.change = change
            item.change_pct = (change / item.price) * 100

        # Recreate ticker with new prices
        self._offset = 0
        self._create_ticker()


class CompactTicker(tk.Frame):
    """
    Compact ticker bar with key indices.

    Shows major indices in a static row.
    """

    def __init__(self, parent: tk.Widget, **kwargs):
        theme = get_theme()
        colors = theme.colors

        kwargs.setdefault('bg', colors.bg_tertiary)
        super().__init__(parent, **kwargs)

        self._colors = colors
        self._theme = theme
        self._labels: Dict[str, Tuple[tk.Label, tk.Label]] = {}

        self._setup_ui()
        self._start_updates()

    def _setup_ui(self) -> None:
        """Build compact ticker."""
        indices = [
            ("SPY", "S&P 500", 450.25, 0.85),
            ("QQQ", "NASDAQ", 380.50, 1.23),
            ("DIA", "DOW", 355.75, 0.42),
            ("IWM", "RUSSELL", 195.30, -0.35),
            ("VIX", "VIX", 18.45, -2.50),
        ]

        for symbol, name, price, change in indices:
            item_frame = tk.Frame(self, bg=self._colors.bg_tertiary)
            item_frame.pack(side=tk.LEFT, padx=Spacing.MD, pady=Spacing.XS)

            # Symbol
            sym_label = tk.Label(
                item_frame,
                text=symbol,
                font=self._theme.get_font(FontSize.XS, FontWeight.BOLD, "data"),
                fg=self._colors.fg_muted,
                bg=self._colors.bg_tertiary,
            )
            sym_label.pack(side=tk.LEFT)

            # Price
            price_label = tk.Label(
                item_frame,
                text=f"${price:.2f}",
                font=self._theme.get_font(FontSize.SM, FontWeight.BOLD, "data"),
                fg=self._colors.fg_primary,
                bg=self._colors.bg_tertiary,
            )
            price_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

            # Change
            change_color = self._colors.bullish if change >= 0 else self._colors.bearish
            change_sign = "+" if change >= 0 else ""
            change_label = tk.Label(
                item_frame,
                text=f"{change_sign}{change:.2f}%",
                font=self._theme.get_font(FontSize.XS, FontWeight.NORMAL, "data"),
                fg=change_color,
                bg=self._colors.bg_tertiary,
            )
            change_label.pack(side=tk.LEFT, padx=(Spacing.XS, 0))

            self._labels[symbol] = (price_label, change_label)

            # Separator
            if symbol != "VIX":
                sep = tk.Label(
                    self,
                    text="|",
                    font=self._theme.get_font(FontSize.SM, FontWeight.NORMAL, "ui"),
                    fg=self._colors.border_light,
                    bg=self._colors.bg_tertiary,
                )
                sep.pack(side=tk.LEFT)

    def _start_updates(self) -> None:
        """Start price update simulation."""
        self._update_prices()

    def _update_prices(self) -> None:
        """Simulate price updates."""
        for symbol, (price_label, change_label) in self._labels.items():
            # Parse current price
            try:
                current_text = price_label.cget('text')
                current_price = float(current_text.replace('$', ''))

                # Small random change
                change = current_price * random.uniform(-0.001, 0.001)
                new_price = current_price + change
                change_pct = (change / current_price) * 100

                # Update labels
                price_label.config(text=f"${new_price:.2f}")

                change_color = self._colors.bullish if change >= 0 else self._colors.bearish
                change_sign = "+" if change >= 0 else ""
                change_label.config(text=f"{change_sign}{change_pct:.2f}%", fg=change_color)
            except (ValueError, tk.TclError):
                pass

        self.after(3000, self._update_prices)

    def set_price(self, symbol: str, price: float, change: float) -> None:
        """Manually set a price."""
        if symbol in self._labels:
            price_label, change_label = self._labels[symbol]
            price_label.config(text=f"${price:.2f}")

            change_color = self._colors.bullish if change >= 0 else self._colors.bearish
            change_sign = "+" if change >= 0 else ""
            change_label.config(text=f"{change_sign}{change:.2f}%", fg=change_color)
