"""
QUANT_INDUSTRY_V1 Professional UI Components

High-performance terminal UI components for institutional-grade trading.

Features:
- Real-time data rendering
- Sophisticated visualizations
- Professional color schemes
- Responsive layouts
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
from datetime import datetime, timezone
import threading
import time


# =============================================================================
# COLOR SYSTEM
# =============================================================================

class Colors:
    """Professional color palette using ANSI escape codes."""

    # Reset
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"

    # Professional Trading Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright variants
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # 256-color mode
    @staticmethod
    def fg256(code: int) -> str:
        return f"\033[38;5;{code}m"

    @staticmethod
    def bg256(code: int) -> str:
        return f"\033[48;5;{code}m"

    # RGB True color
    @staticmethod
    def fg_rgb(r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def bg_rgb(r: int, g: int, b: int) -> str:
        return f"\033[48;2;{r};{g};{b}m"


class Theme:
    """Professional trading terminal theme."""

    # Main colors
    PRIMARY = Colors.fg_rgb(70, 130, 180)      # Steel blue
    SECONDARY = Colors.fg_rgb(119, 136, 153)   # Light slate gray
    ACCENT = Colors.fg_rgb(255, 193, 7)        # Amber

    # Trading colors
    PROFIT = Colors.fg_rgb(0, 200, 83)         # Green
    LOSS = Colors.fg_rgb(255, 82, 82)          # Red
    NEUTRAL = Colors.fg_rgb(158, 158, 158)     # Gray

    # Status colors
    SUCCESS = Colors.fg_rgb(76, 175, 80)       # Green
    WARNING = Colors.fg_rgb(255, 152, 0)       # Orange
    ERROR = Colors.fg_rgb(244, 67, 54)         # Red
    INFO = Colors.fg_rgb(33, 150, 243)         # Blue

    # Background
    BG_DARK = Colors.bg_rgb(18, 18, 18)
    BG_CARD = Colors.bg_rgb(30, 30, 30)
    BG_HOVER = Colors.bg_rgb(45, 45, 45)

    # Text
    TEXT_PRIMARY = Colors.fg_rgb(255, 255, 255)
    TEXT_SECONDARY = Colors.fg_rgb(176, 176, 176)
    TEXT_DISABLED = Colors.fg_rgb(97, 97, 97)

    # Borders
    BORDER = Colors.fg_rgb(66, 66, 66)
    BORDER_LIGHT = Colors.fg_rgb(97, 97, 97)


# =============================================================================
# TERMINAL UTILITIES
# =============================================================================

class Terminal:
    """Terminal manipulation utilities."""

    @staticmethod
    def clear() -> None:
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def move_cursor(row: int, col: int) -> str:
        """Move cursor to position."""
        return f"\033[{row};{col}H"

    @staticmethod
    def hide_cursor() -> str:
        return "\033[?25l"

    @staticmethod
    def show_cursor() -> str:
        return "\033[?25h"

    @staticmethod
    def save_cursor() -> str:
        return "\033[s"

    @staticmethod
    def restore_cursor() -> str:
        return "\033[u"

    @staticmethod
    def clear_line() -> str:
        return "\033[2K"

    @staticmethod
    def clear_to_end() -> str:
        return "\033[K"

    @staticmethod
    def get_size() -> Tuple[int, int]:
        """Get terminal size (columns, rows)."""
        try:
            import shutil
            size = shutil.get_terminal_size()
            return size.columns, size.lines
        except:
            return 120, 40


# =============================================================================
# BOX DRAWING
# =============================================================================

class BoxChars:
    """Unicode box drawing characters."""

    # Single line
    HORIZONTAL = "─"
    VERTICAL = "│"
    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOTTOM_LEFT = "└"
    BOTTOM_RIGHT = "┘"
    T_DOWN = "┬"
    T_UP = "┴"
    T_RIGHT = "├"
    T_LEFT = "┤"
    CROSS = "┼"

    # Double line
    D_HORIZONTAL = "═"
    D_VERTICAL = "║"
    D_TOP_LEFT = "╔"
    D_TOP_RIGHT = "╗"
    D_BOTTOM_LEFT = "╚"
    D_BOTTOM_RIGHT = "╝"

    # Rounded corners
    R_TOP_LEFT = "╭"
    R_TOP_RIGHT = "╮"
    R_BOTTOM_LEFT = "╰"
    R_BOTTOM_RIGHT = "╯"

    # Block elements
    FULL_BLOCK = "█"
    LIGHT_SHADE = "░"
    MEDIUM_SHADE = "▒"
    DARK_SHADE = "▓"

    # Bars for charts
    BAR_1_8 = "▁"
    BAR_2_8 = "▂"
    BAR_3_8 = "▃"
    BAR_4_8 = "▄"
    BAR_5_8 = "▅"
    BAR_6_8 = "▆"
    BAR_7_8 = "▇"
    BAR_8_8 = "█"

    BARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


# =============================================================================
# UI COMPONENTS
# =============================================================================

@dataclass
class Box:
    """Renderable box component."""

    title: str = ""
    width: int = 40
    height: int = 10
    style: str = "single"  # single, double, rounded
    color: str = Theme.BORDER

    def get_chars(self) -> Tuple[str, ...]:
        """Get box characters based on style."""
        if self.style == "double":
            return (
                BoxChars.D_TOP_LEFT, BoxChars.D_TOP_RIGHT,
                BoxChars.D_BOTTOM_LEFT, BoxChars.D_BOTTOM_RIGHT,
                BoxChars.D_HORIZONTAL, BoxChars.D_VERTICAL
            )
        elif self.style == "rounded":
            return (
                BoxChars.R_TOP_LEFT, BoxChars.R_TOP_RIGHT,
                BoxChars.R_BOTTOM_LEFT, BoxChars.R_BOTTOM_RIGHT,
                BoxChars.HORIZONTAL, BoxChars.VERTICAL
            )
        else:
            return (
                BoxChars.TOP_LEFT, BoxChars.TOP_RIGHT,
                BoxChars.BOTTOM_LEFT, BoxChars.BOTTOM_RIGHT,
                BoxChars.HORIZONTAL, BoxChars.VERTICAL
            )

    def render(self, content: List[str] = None) -> str:
        """Render box with content."""
        tl, tr, bl, br, h, v = self.get_chars()
        lines = []

        # Top border with title
        if self.title:
            title_display = f" {self.title} "
            padding = self.width - 2 - len(title_display)
            top = f"{self.color}{tl}{h}{Theme.TEXT_PRIMARY}{title_display}{self.color}{h * padding}{tr}{Colors.RESET}"
        else:
            top = f"{self.color}{tl}{h * (self.width - 2)}{tr}{Colors.RESET}"
        lines.append(top)

        # Content area
        content = content or []
        for i in range(self.height - 2):
            if i < len(content):
                text = content[i][:self.width - 4]
                padding = self.width - 4 - len(self._strip_ansi(text))
                line = f"{self.color}{v}{Colors.RESET} {text}{' ' * padding} {self.color}{v}{Colors.RESET}"
            else:
                line = f"{self.color}{v}{Colors.RESET}{' ' * (self.width - 2)}{self.color}{v}{Colors.RESET}"
            lines.append(line)

        # Bottom border
        bottom = f"{self.color}{bl}{h * (self.width - 2)}{br}{Colors.RESET}"
        lines.append(bottom)

        return "\n".join(lines)

    def _strip_ansi(self, text: str) -> str:
        """Strip ANSI codes for length calculation."""
        import re
        return re.sub(r'\033\[[0-9;]*m', '', text)


class ProgressBar:
    """Professional progress bar component."""

    def __init__(
        self,
        width: int = 30,
        filled_char: str = "█",
        empty_char: str = "░",
        color_gradient: bool = True,
    ):
        self.width = width
        self.filled_char = filled_char
        self.empty_char = empty_char
        self.color_gradient = color_gradient

    def render(self, value: float, max_value: float = 100, label: str = "") -> str:
        """Render progress bar."""
        percentage = min(value / max_value, 1.0) if max_value > 0 else 0
        filled_width = int(percentage * self.width)
        empty_width = self.width - filled_width

        if self.color_gradient:
            if percentage < 0.3:
                color = Theme.ERROR
            elif percentage < 0.7:
                color = Theme.WARNING
            else:
                color = Theme.SUCCESS
        else:
            color = Theme.PRIMARY

        bar = f"{color}{self.filled_char * filled_width}{Theme.TEXT_DISABLED}{self.empty_char * empty_width}{Colors.RESET}"
        pct_str = f"{percentage * 100:5.1f}%"

        if label:
            return f"{label}: {bar} {pct_str}"
        return f"{bar} {pct_str}"


class SparkLine:
    """Sparkline chart component."""

    def __init__(self, width: int = 20):
        self.width = width
        self.bars = BoxChars.BARS

    def render(self, data: List[float], color: str = None) -> str:
        """Render sparkline from data."""
        if not data:
            return " " * self.width

        # Normalize data to last N points
        data = data[-self.width:]

        if len(data) < self.width:
            data = [data[0]] * (self.width - len(data)) + data

        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val if max_val != min_val else 1

        # Map to bar characters
        result = []
        for val in data:
            normalized = (val - min_val) / range_val
            bar_idx = min(int(normalized * 7), 7)
            result.append(self.bars[bar_idx])

        spark = "".join(result)

        if color:
            # Determine color based on trend
            if data[-1] > data[0]:
                return f"{Theme.PROFIT}{spark}{Colors.RESET}"
            elif data[-1] < data[0]:
                return f"{Theme.LOSS}{spark}{Colors.RESET}"

        return f"{Theme.TEXT_SECONDARY}{spark}{Colors.RESET}"


class Table:
    """Professional table component."""

    def __init__(
        self,
        headers: List[str],
        widths: List[int] = None,
        alignments: List[str] = None,
    ):
        self.headers = headers
        self.widths = widths or [15] * len(headers)
        self.alignments = alignments or ["left"] * len(headers)

    def _align(self, text: str, width: int, alignment: str) -> str:
        """Align text within width."""
        text = str(text)[:width]
        if alignment == "right":
            return text.rjust(width)
        elif alignment == "center":
            return text.center(width)
        return text.ljust(width)

    def render_header(self) -> str:
        """Render table header."""
        cells = []
        for i, header in enumerate(self.headers):
            cells.append(self._align(header, self.widths[i], self.alignments[i]))

        header_line = f"{Theme.TEXT_PRIMARY}{Colors.BOLD}{' │ '.join(cells)}{Colors.RESET}"
        separator = "─" * (sum(self.widths) + 3 * (len(self.widths) - 1))

        return f"{header_line}\n{Theme.BORDER}{separator}{Colors.RESET}"

    def render_row(self, row: List[Any], colors: List[str] = None) -> str:
        """Render a single row."""
        colors = colors or [Theme.TEXT_SECONDARY] * len(row)
        cells = []

        for i, (cell, color) in enumerate(zip(row, colors)):
            aligned = self._align(str(cell), self.widths[i], self.alignments[i])
            cells.append(f"{color}{aligned}{Colors.RESET}")

        return " │ ".join(cells)

    def render(self, rows: List[List[Any]], row_colors: List[List[str]] = None) -> str:
        """Render full table."""
        lines = [self.render_header()]

        for i, row in enumerate(rows):
            colors = row_colors[i] if row_colors and i < len(row_colors) else None
            lines.append(self.render_row(row, colors))

        return "\n".join(lines)


class MiniChart:
    """Mini candlestick-like chart."""

    def __init__(self, width: int = 40, height: int = 8):
        self.width = width
        self.height = height

    def render(self, prices: List[float]) -> List[str]:
        """Render mini chart as list of lines."""
        if not prices or len(prices) < 2:
            return [" " * self.width] * self.height

        # Use last N prices
        prices = prices[-self.width:]

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price if max_price != min_price else 1

        # Create grid
        grid = [[" " for _ in range(len(prices))] for _ in range(self.height)]

        # Plot prices
        for i, price in enumerate(prices):
            normalized = (price - min_price) / price_range
            row = self.height - 1 - int(normalized * (self.height - 1))
            row = max(0, min(self.height - 1, row))

            # Determine color based on movement
            if i > 0:
                if price > prices[i - 1]:
                    grid[row][i] = f"{Theme.PROFIT}[*]{Colors.RESET}"
                elif price < prices[i - 1]:
                    grid[row][i] = f"{Theme.LOSS}[*]{Colors.RESET}"
                else:
                    grid[row][i] = f"{Theme.NEUTRAL}[*]{Colors.RESET}"
            else:
                grid[row][i] = f"{Theme.NEUTRAL}[*]{Colors.RESET}"

        return ["".join(row) for row in grid]


class StatusIndicator:
    """Status indicator component."""

    ICONS = {
        "connected": "[*]",
        "disconnected": "[ ]",
        "warning": "[~]",
        "loading": "[.]",
        "success": "[OK]",
        "error": "[FAIL]",
        "pending": "[ ]",
    }

    @classmethod
    def render(cls, status: str, label: str = "") -> str:
        """Render status indicator."""
        icon = cls.ICONS.get(status, "?")

        if status == "connected" or status == "success":
            color = Theme.SUCCESS
        elif status == "disconnected" or status == "error":
            color = Theme.ERROR
        elif status == "warning":
            color = Theme.WARNING
        else:
            color = Theme.INFO

        result = f"{color}{icon}{Colors.RESET}"
        if label:
            result += f" {Theme.TEXT_SECONDARY}{label}{Colors.RESET}"

        return result


class KeyValue:
    """Key-value display component."""

    @staticmethod
    def render(
        key: str,
        value: Any,
        key_width: int = 15,
        value_color: str = None,
    ) -> str:
        """Render key-value pair."""
        key_str = f"{Theme.TEXT_SECONDARY}{key.ljust(key_width)}{Colors.RESET}"

        if value_color:
            val_str = f"{value_color}{value}{Colors.RESET}"
        else:
            val_str = f"{Theme.TEXT_PRIMARY}{value}{Colors.RESET}"

        return f"{key_str}: {val_str}"


class Gauge:
    """Circular gauge indicator (text-based)."""

    def __init__(self, width: int = 10):
        self.width = width

    def render(self, value: float, max_value: float = 100, label: str = "") -> str:
        """Render gauge."""
        percentage = min(value / max_value, 1.0) if max_value > 0 else 0

        # Determine color
        if percentage < 0.3:
            color = Theme.SUCCESS
        elif percentage < 0.7:
            color = Theme.WARNING
        else:
            color = Theme.ERROR

        # Create gauge visualization
        filled = int(percentage * 10)
        gauge = "▰" * filled + "▱" * (10 - filled)

        pct = f"{percentage * 100:.0f}%"

        if label:
            return f"{label}: {color}{gauge}{Colors.RESET} {pct}"
        return f"{color}{gauge}{Colors.RESET} {pct}"


# =============================================================================
# LAYOUT SYSTEM
# =============================================================================

class Grid:
    """Grid layout manager."""

    def __init__(self, columns: int = 2, gutter: int = 2):
        self.columns = columns
        self.gutter = gutter
        self.cells: List[List[str]] = []

    def add(self, content: str) -> None:
        """Add content to grid."""
        self.cells.append(content.split("\n"))

    def render(self, width: int = None) -> str:
        """Render grid layout."""
        if not self.cells:
            return ""

        width = width or Terminal.get_size()[0]
        cell_width = (width - self.gutter * (self.columns - 1)) // self.columns

        rows = []
        for i in range(0, len(self.cells), self.columns):
            row_cells = self.cells[i:i + self.columns]
            max_height = max(len(cell) for cell in row_cells)

            for line_idx in range(max_height):
                line_parts = []
                for cell in row_cells:
                    if line_idx < len(cell):
                        line_parts.append(cell[line_idx].ljust(cell_width))
                    else:
                        line_parts.append(" " * cell_width)

                rows.append((" " * self.gutter).join(line_parts))

        return "\n".join(rows)


# =============================================================================
# ANIMATION
# =============================================================================

class Spinner:
    """Loading spinner component."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Loading"):
        self.message = message
        self.frame_idx = 0

    def next_frame(self) -> str:
        """Get next animation frame."""
        frame = self.FRAMES[self.frame_idx]
        self.frame_idx = (self.frame_idx + 1) % len(self.FRAMES)
        return f"{Theme.PRIMARY}{frame}{Colors.RESET} {self.message}"


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'Colors',
    'Theme',
    'Terminal',
    'BoxChars',
    'Box',
    'ProgressBar',
    'SparkLine',
    'Table',
    'MiniChart',
    'StatusIndicator',
    'KeyValue',
    'Gauge',
    'Grid',
    'Spinner',
]
