"""
QUANT_INDUSTRY_V1 Health View

System health and diagnostics display.
"""

import tkinter as tk
from typing import Dict, Any
import logging

from ..theme import get_theme, Spacing, FontSize
from ..state import get_store, get_event_bus, EventType
from ..components.base import Card, StyledLabel, StyledButton
from ..components.indicators import StatusBadge, ProgressBar
from ..components.charts import GaugeChart

logger = logging.getLogger(__name__)


class HealthView(tk.Frame):
    """System health and diagnostics view."""

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
        """Setup health view UI."""
        theme = get_theme()
        colors = theme.colors

        # Configure grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # System status card
        status_card = Card(self, title="System Status", padding="normal")
        status_card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=Spacing.MD, pady=Spacing.MD)

        status_frame = tk.Frame(status_card.content, bg=colors.bg_elevated)
        status_frame.pack(fill=tk.X)

        # Overall status
        overall_frame = tk.Frame(status_frame, bg=colors.bg_elevated)
        overall_frame.pack(side=tk.LEFT, expand=True)

        StyledLabel(overall_frame, text="Overall", style="caption").pack()
        self._overall_status = StatusBadge(overall_frame, status="success", text="Healthy")
        self._overall_status.pack()

        # Database status
        db_frame = tk.Frame(status_frame, bg=colors.bg_elevated)
        db_frame.pack(side=tk.LEFT, expand=True)

        StyledLabel(db_frame, text="Database", style="caption").pack()
        self._db_status = StatusBadge(db_frame, status="success", text="OK")
        self._db_status.pack()

        # API status
        api_frame = tk.Frame(status_frame, bg=colors.bg_elevated)
        api_frame.pack(side=tk.LEFT, expand=True)

        StyledLabel(api_frame, text="API", style="caption").pack()
        self._api_status = StatusBadge(api_frame, status="success", text="OK")
        self._api_status.pack()

        # Model status
        model_frame = tk.Frame(status_frame, bg=colors.bg_elevated)
        model_frame.pack(side=tk.LEFT, expand=True)

        StyledLabel(model_frame, text="Models", style="caption").pack()
        self._model_status = StatusBadge(model_frame, status="success", text="OK")
        self._model_status.pack()

        # Metrics card
        metrics_card = Card(self, title="Performance Metrics", padding="normal")
        metrics_card.grid(row=1, column=0, sticky="nsew", padx=Spacing.MD, pady=Spacing.MD)

        metrics_content = metrics_card.content

        # Data freshness
        fresh_frame = tk.Frame(metrics_content, bg=colors.bg_elevated)
        fresh_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(fresh_frame, text="Data Freshness:", style="caption", width=15).pack(side=tk.LEFT)
        self._freshness_bar = ProgressBar(fresh_frame, value=1.0, width=100)
        self._freshness_bar.pack(side=tk.LEFT, padx=Spacing.SM)
        self._freshness_label = StyledLabel(fresh_frame, text="0s", style="body")
        self._freshness_label.pack(side=tk.LEFT)

        # Error count
        error_frame = tk.Frame(metrics_content, bg=colors.bg_elevated)
        error_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(error_frame, text="Errors (24h):", style="caption", width=15).pack(side=tk.LEFT)
        self._error_count = StyledLabel(error_frame, text="0", style="body")
        self._error_count.pack(side=tk.LEFT)

        # Warning count
        warn_frame = tk.Frame(metrics_content, bg=colors.bg_elevated)
        warn_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(warn_frame, text="Warnings (24h):", style="caption", width=15).pack(side=tk.LEFT)
        self._warning_count = StyledLabel(warn_frame, text="0", style="body")
        self._warning_count.pack(side=tk.LEFT)

        # CPU usage
        cpu_frame = tk.Frame(metrics_content, bg=colors.bg_elevated)
        cpu_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(cpu_frame, text="CPU Usage:", style="caption", width=15).pack(side=tk.LEFT)
        self._cpu_bar = ProgressBar(cpu_frame, value=0.0, width=100)
        self._cpu_bar.pack(side=tk.LEFT, padx=Spacing.SM)
        self._cpu_label = StyledLabel(cpu_frame, text="0%", style="body")
        self._cpu_label.pack(side=tk.LEFT)

        # Memory usage
        mem_frame = tk.Frame(metrics_content, bg=colors.bg_elevated)
        mem_frame.pack(fill=tk.X, pady=Spacing.SM)

        StyledLabel(mem_frame, text="Memory Usage:", style="caption", width=15).pack(side=tk.LEFT)
        self._mem_bar = ProgressBar(mem_frame, value=0.0, width=100)
        self._mem_bar.pack(side=tk.LEFT, padx=Spacing.SM)
        self._mem_label = StyledLabel(mem_frame, text="0%", style="body")
        self._mem_label.pack(side=tk.LEFT)

        # Actions card
        actions_card = Card(self, title="Actions", padding="normal")
        actions_card.grid(row=1, column=1, sticky="nsew", padx=Spacing.MD, pady=Spacing.MD)

        actions_content = actions_card.content

        StyledButton(
            actions_content,
            text="Refresh Health",
            variant="primary",
            command=self._on_refresh,
        ).pack(fill=tk.X, pady=Spacing.SM)

        StyledButton(
            actions_content,
            text="Export Diagnostics",
            variant="default",
            command=self._on_export,
        ).pack(fill=tk.X, pady=Spacing.SM)

        StyledButton(
            actions_content,
            text="Clear Errors",
            variant="ghost",
            command=self._on_clear_errors,
        ).pack(fill=tk.X, pady=Spacing.SM)

        self._refresh_data()

    def _bind_events(self) -> None:
        """Bind to state events."""
        self._event_bus.subscribe(EventType.HEALTH_UPDATED, self._on_health_updated)

    def _refresh_data(self) -> None:
        """Refresh health data."""
        state = self._store.state
        health = state.health

        # Update status badges
        status_map = {'ok': 'success', 'warning': 'warning', 'error': 'error'}

        self._overall_status.set_status(
            status_map.get(health.status, 'info'),
            health.status.title()
        )
        self._db_status.set_status(
            status_map.get(health.db_status, 'info'),
            health.db_status.upper()
        )
        self._api_status.set_status(
            status_map.get(health.api_status, 'info'),
            health.api_status.upper()
        )
        self._model_status.set_status(
            status_map.get(health.model_status, 'info'),
            health.model_status.upper()
        )

        # Update metrics
        freshness = health.data_freshness
        freshness_pct = max(0, min(1, 1 - freshness / 60))  # 60s max staleness
        self._freshness_bar.set_value(freshness_pct)
        self._freshness_label.config(text=f"{int(freshness)}s")

        self._error_count.config(text=str(health.error_count))
        self._warning_count.config(text=str(health.warning_count))

        self._cpu_bar.set_value(health.cpu_usage / 100)
        self._cpu_label.config(text=f"{int(health.cpu_usage)}%")

        self._mem_bar.set_value(health.memory_usage / 100)
        self._mem_label.config(text=f"{int(health.memory_usage)}%")

    def _on_health_updated(self, event) -> None:
        """Handle health update."""
        self.after(0, self._refresh_data)

    def _on_refresh(self) -> None:
        """Refresh health check."""
        logger.info("Manual health refresh requested")
        self._refresh_data()

    def _on_export(self) -> None:
        """Export diagnostics bundle."""
        logger.info("Diagnostics export requested")
        # TODO: Implement diagnostics export

    def _on_clear_errors(self) -> None:
        """Clear error log."""
        logger.info("Clear errors requested")
        # TODO: Implement error clearing

    def destroy(self) -> None:
        """Clean up."""
        self._event_bus.unsubscribe(EventType.HEALTH_UPDATED, self._on_health_updated)
        super().destroy()
