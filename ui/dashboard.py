"""
QUANT_INDUSTRY_V1 Trading Dashboard

Real-time Tkinter-based monitoring UI for the trading engine.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import queue

logger = logging.getLogger(__name__)


class StatusIndicator(tk.Canvas):
    """Circular status indicator widget."""

    def __init__(self, parent, size: int = 16, **kwargs):
        super().__init__(parent, width=size, height=size, highlightthickness=0, **kwargs)
        self.size = size
        self._oval = self.create_oval(2, 2, size - 2, size - 2, fill="gray", outline="")

    def set_status(self, status: str):
        """Set status color."""
        colors = {
            "running": "#22c55e",  # Green
            "stopped": "#ef4444",  # Red
            "paused": "#f59e0b",   # Orange
            "error": "#dc2626",    # Dark red
            "starting": "#3b82f6", # Blue
        }
        color = colors.get(status.lower(), "gray")
        self.itemconfig(self._oval, fill=color)


class MetricCard(ttk.Frame):
    """Card widget for displaying a metric."""

    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(relief="solid", borderwidth=1, padding=10)

        self.title_label = ttk.Label(self, text=title, font=("Segoe UI", 9))
        self.title_label.pack(anchor="w")

        self.value_label = ttk.Label(self, text="--", font=("Segoe UI", 18, "bold"))
        self.value_label.pack(anchor="w")

        self.subtitle_label = ttk.Label(self, text="", font=("Segoe UI", 8), foreground="gray")
        self.subtitle_label.pack(anchor="w")

    def set_value(self, value: str, subtitle: str = "", color: str = None):
        """Update the displayed value."""
        self.value_label.configure(text=value)
        self.subtitle_label.configure(text=subtitle)
        if color:
            self.value_label.configure(foreground=color)


class PositionsTable(ttk.Frame):
    """Table widget for displaying positions."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        columns = ("symbol", "qty", "avg_price", "current", "unrealized", "pct")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=8)

        self.tree.heading("symbol", text="Symbol")
        self.tree.heading("qty", text="Qty")
        self.tree.heading("avg_price", text="Avg Price")
        self.tree.heading("current", text="Current")
        self.tree.heading("unrealized", text="Unrealized")
        self.tree.heading("pct", text="%")

        self.tree.column("symbol", width=80)
        self.tree.column("qty", width=60)
        self.tree.column("avg_price", width=80)
        self.tree.column("current", width=80)
        self.tree.column("unrealized", width=90)
        self.tree.column("pct", width=60)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def update_positions(self, positions: Dict[str, Dict[str, Any]]):
        """Update the positions table."""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add positions
        for symbol, pos in positions.items():
            qty = pos.get("quantity", 0)
            avg_price = pos.get("avg_price", 0)
            current = pos.get("current_price", avg_price)
            unrealized = pos.get("unrealized_pnl", 0)
            pct = (current - avg_price) / avg_price * 100 if avg_price else 0

            self.tree.insert("", "end", values=(
                symbol,
                f"{qty:,}",
                f"${avg_price:.2f}",
                f"${current:.2f}",
                f"${unrealized:,.2f}",
                f"{pct:+.1f}%"
            ))


class TradesTable(ttk.Frame):
    """Table widget for displaying recent trades."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        columns = ("time", "symbol", "side", "qty", "price", "pnl")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=6)

        self.tree.heading("time", text="Time")
        self.tree.heading("symbol", text="Symbol")
        self.tree.heading("side", text="Side")
        self.tree.heading("qty", text="Qty")
        self.tree.heading("price", text="Price")
        self.tree.heading("pnl", text="PnL")

        self.tree.column("time", width=70)
        self.tree.column("symbol", width=70)
        self.tree.column("side", width=50)
        self.tree.column("qty", width=60)
        self.tree.column("price", width=70)
        self.tree.column("pnl", width=80)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def update_trades(self, trades: List[Dict[str, Any]]):
        """Update the trades table."""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add trades (reversed so newest first)
        for trade in reversed(trades):
            timestamp = trade.get("timestamp", datetime.now(timezone.utc))
            if isinstance(timestamp, str):
                time_str = timestamp.split("T")[1][:8] if "T" in timestamp else timestamp
            else:
                time_str = timestamp.strftime("%H:%M:%S")

            pnl = trade.get("pnl", 0)
            self.tree.insert("", "end", values=(
                time_str,
                trade.get("symbol", ""),
                trade.get("side", "").upper(),
                f"{trade.get('quantity', 0):,}",
                f"${trade.get('price', 0):.2f}",
                f"${pnl:+,.2f}" if pnl else "--"
            ))


class LogPanel(ttk.Frame):
    """Panel for displaying log messages."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.text = scrolledtext.ScrolledText(
            self, height=8, wrap=tk.WORD,
            font=("Consolas", 9), state="disabled"
        )
        self.text.pack(fill="both", expand=True)

        # Tags for coloring
        self.text.tag_configure("INFO", foreground="black")
        self.text.tag_configure("WARNING", foreground="#f59e0b")
        self.text.tag_configure("ERROR", foreground="#ef4444")
        self.text.tag_configure("SIGNAL", foreground="#3b82f6")
        self.text.tag_configure("TRADE", foreground="#22c55e")

    def add_message(self, message: str, level: str = "INFO"):
        """Add a log message."""
        self.text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text.insert(tk.END, f"[{timestamp}] {message}\n", level)
        self.text.see(tk.END)
        self.text.configure(state="disabled")


class TradingDashboard:
    """Main trading dashboard application."""

    def __init__(self, engine=None):
        self.engine = engine
        self.root = tk.Tk()
        self.root.title("QUANT_INDUSTRY_V1 Trading Dashboard")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)

        # Message queue for thread-safe updates
        self.update_queue = queue.Queue()

        # Update interval (ms)
        self.update_interval = 1000

        self._setup_styles()
        self._create_widgets()
        self._setup_callbacks()

        # Start update loop
        self._schedule_update()

    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))

    def _create_widgets(self):
        """Create all dashboard widgets."""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill="both", expand=True)

        # Header
        self._create_header()

        # Main content area (paned)
        self.paned = ttk.PanedWindow(self.main_frame, orient="horizontal")
        self.paned.pack(fill="both", expand=True, pady=10)

        # Left panel - metrics and positions
        self._create_left_panel()

        # Right panel - trades and logs
        self._create_right_panel()

    def _create_header(self):
        """Create the header section."""
        header = ttk.Frame(self.main_frame)
        header.pack(fill="x", pady=(0, 10))

        # Title and status
        title_frame = ttk.Frame(header)
        title_frame.pack(side="left")

        ttk.Label(title_frame, text="QUANT_INDUSTRY_V1", style="Title.TLabel").pack(side="left")

        self.status_indicator = StatusIndicator(title_frame)
        self.status_indicator.pack(side="left", padx=(10, 5))

        self.status_label = ttk.Label(title_frame, text="STOPPED", font=("Segoe UI", 9))
        self.status_label.pack(side="left")

        # Controls
        controls = ttk.Frame(header)
        controls.pack(side="right")

        self.start_btn = ttk.Button(controls, text="Start", command=self._on_start)
        self.start_btn.pack(side="left", padx=2)

        self.stop_btn = ttk.Button(controls, text="Stop", command=self._on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=10)

        self.mode_var = tk.StringVar(value="paper")
        ttk.Radiobutton(controls, text="Paper", variable=self.mode_var, value="paper").pack(side="left")
        ttk.Radiobutton(controls, text="Live", variable=self.mode_var, value="live").pack(side="left")

    def _create_left_panel(self):
        """Create the left panel with metrics and positions."""
        left_frame = ttk.Frame(self.paned, padding=5)
        self.paned.add(left_frame, weight=1)

        # Metrics row
        metrics_frame = ttk.Frame(left_frame)
        metrics_frame.pack(fill="x", pady=(0, 10))

        self.equity_card = MetricCard(metrics_frame, "Equity")
        self.equity_card.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.pnl_card = MetricCard(metrics_frame, "P&L")
        self.pnl_card.pack(side="left", fill="x", expand=True, padx=5)

        self.cash_card = MetricCard(metrics_frame, "Cash")
        self.cash_card.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Second metrics row
        metrics_frame2 = ttk.Frame(left_frame)
        metrics_frame2.pack(fill="x", pady=(0, 10))

        self.regime_card = MetricCard(metrics_frame2, "Regime")
        self.regime_card.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.positions_card = MetricCard(metrics_frame2, "Positions")
        self.positions_card.pack(side="left", fill="x", expand=True, padx=5)

        self.trades_card = MetricCard(metrics_frame2, "Trades Today")
        self.trades_card.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Positions table
        ttk.Label(left_frame, text="Positions", style="Header.TLabel").pack(anchor="w", pady=(10, 5))
        self.positions_table = PositionsTable(left_frame)
        self.positions_table.pack(fill="both", expand=True)

    def _create_right_panel(self):
        """Create the right panel with trades and logs."""
        right_frame = ttk.Frame(self.paned, padding=5)
        self.paned.add(right_frame, weight=1)

        # Recent trades
        ttk.Label(right_frame, text="Recent Trades", style="Header.TLabel").pack(anchor="w", pady=(0, 5))
        self.trades_table = TradesTable(right_frame)
        self.trades_table.pack(fill="x", pady=(0, 10))

        # Signal log
        ttk.Label(right_frame, text="Activity Log", style="Header.TLabel").pack(anchor="w", pady=(10, 5))
        self.log_panel = LogPanel(right_frame)
        self.log_panel.pack(fill="both", expand=True)

    def _setup_callbacks(self):
        """Setup engine callbacks."""
        if self.engine:
            self.engine.on_signal.append(self._on_signal)
            self.engine.on_trade.append(self._on_trade)
            self.engine.on_error.append(self._on_error)

    def _on_signal(self, signal_dict: Dict[str, Any]):
        """Handle signal callback."""
        signal = signal_dict.get("signal")
        if signal:
            msg = f"SIGNAL: {signal.symbol} {signal.direction.value} (strength: {signal.strength:.2f})"
            self.update_queue.put(("log", msg, "SIGNAL"))

    def _on_trade(self, trade: Dict[str, Any]):
        """Handle trade callback."""
        msg = f"TRADE: {trade.get('side', '').upper()} {trade.get('quantity', 0)} {trade.get('symbol', '')} @ ${trade.get('price', 0):.2f}"
        self.update_queue.put(("log", msg, "TRADE"))

    def _on_error(self, error: Exception):
        """Handle error callback."""
        msg = f"ERROR: {str(error)}"
        self.update_queue.put(("log", msg, "ERROR"))

    def _on_start(self):
        """Handle start button click."""
        if not self.engine:
            messagebox.showwarning("No Engine", "Trading engine not configured")
            return

        try:
            # Initialize if needed
            from core import EngineState
            if self.engine.state == EngineState.STOPPED:
                self.log_panel.add_message("Initializing engine...", "INFO")
                self.engine.initialize()

            self.engine.start()
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.log_panel.add_message("Engine started", "INFO")
        except Exception as e:
            messagebox.showerror("Start Error", str(e))
            self.log_panel.add_message(f"Failed to start: {e}", "ERROR")

    def _on_stop(self):
        """Handle stop button click."""
        if self.engine:
            self.engine.stop()
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.log_panel.add_message("Engine stopped", "INFO")

    def _schedule_update(self):
        """Schedule the next UI update."""
        self._update_ui()
        self.root.after(self.update_interval, self._schedule_update)

    def _update_ui(self):
        """Update all UI elements."""
        # Process queued messages
        while not self.update_queue.empty():
            try:
                item = self.update_queue.get_nowait()
                if item[0] == "log":
                    self.log_panel.add_message(item[1], item[2])
            except queue.Empty:
                break

        if not self.engine:
            return

        try:
            status = self.engine.get_status()

            # Update status
            state = status.get("state", "stopped")
            self.status_indicator.set_status(state)
            self.status_label.configure(text=state.upper())

            # Update metrics
            equity = status.get("equity", 0)
            pnl = status.get("pnl", 0)
            pnl_pct = status.get("pnl_pct", 0)
            cash = status.get("cash", 0)

            self.equity_card.set_value(
                f"${equity:,.2f}",
                f"Initial: ${self.engine.config.initial_capital:,.0f}"
            )

            pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
            self.pnl_card.set_value(
                f"${pnl:+,.2f}",
                f"{pnl_pct:+.2f}%",
                color=pnl_color
            )

            self.cash_card.set_value(f"${cash:,.2f}")

            self.regime_card.set_value(status.get("current_regime", "unknown").upper())
            self.positions_card.set_value(str(status.get("positions", 0)))
            self.trades_card.set_value(str(status.get("trades_count", 0)))

            # Update positions table
            positions = self.engine.get_positions()
            self.positions_table.update_positions(positions)

            # Update trades table
            trades = self.engine.get_recent_trades(10)
            self.trades_table.update_trades(trades)

        except Exception as e:
            logger.error(f"UI update error: {e}")

    def set_engine(self, engine):
        """Set the trading engine."""
        self.engine = engine
        self._setup_callbacks()

    def run(self):
        """Run the dashboard."""
        self.log_panel.add_message("Dashboard started", "INFO")
        self.root.mainloop()


def create_dashboard(engine=None) -> TradingDashboard:
    """Create and return a dashboard instance."""
    return TradingDashboard(engine)


if __name__ == "__main__":
    # Test with mock data
    dashboard = create_dashboard()
    dashboard.run()
