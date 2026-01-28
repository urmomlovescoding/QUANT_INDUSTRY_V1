"""
QUANT_INDUSTRY_V1 Alpha Research View

Professional view for monitoring the Alpha Discovery Agent.

Features:
- Real-time agent status
- Strategy pipeline visualization
- Performance heatmaps
- Research report browser
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

from ..theme import get_theme, Spacing, FontSize, FontWeight
from ..state import get_store, get_event_bus, EventType
from ..components.base import StyledFrame, Card, StyledLabel, StyledButton
from ..components.indicators import StatusBadge, ConfidenceBar

logger = logging.getLogger(__name__)


class AlphaResearchView(tk.Frame):
    """
    Alpha research and discovery monitoring view.

    Layout:
    ┌─────────────────────────────────────────────────────────────┐
    │  Agent Status Bar                                           │
    ├───────────────────────────┬─────────────────────────────────┤
    │  Strategy Pipeline        │  Deployed Strategies            │
    │  - Candidates             │  - Active list                  │
    │  - Validated              │  - Performance metrics          │
    │  - Deployed               │                                 │
    ├───────────────────────────┴─────────────────────────────────┤
    │  Research Reports / Evolution Progress                       │
    └─────────────────────────────────────────────────────────────┘
    """

    def __init__(self, parent: tk.Widget, agent=None, **kwargs):
        theme = get_theme()
        colors = theme.colors
        kwargs.setdefault('bg', colors.bg_primary)

        super().__init__(parent, **kwargs)

        self.agent = agent
        self._store = get_store()
        self._event_bus = get_event_bus()

        self._setup_ui()
        self._start_refresh()

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        theme = get_theme()
        colors = theme.colors

        # Configure grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        # Agent status bar
        self._status_bar = self._create_status_bar()
        self._status_bar.grid(row=0, column=0, columnspan=2, sticky="ew",
                              padx=Spacing.MD, pady=Spacing.SM)

        # Strategy pipeline (left)
        self._pipeline_card = self._create_pipeline_card()
        self._pipeline_card.grid(row=1, column=0, sticky="nsew",
                                 padx=(Spacing.MD, Spacing.SM), pady=Spacing.SM)

        # Deployed strategies (right)
        self._deployed_card = self._create_deployed_card()
        self._deployed_card.grid(row=1, column=1, sticky="nsew",
                                 padx=(Spacing.SM, Spacing.MD), pady=Spacing.SM)

        # Research reports (bottom)
        self._reports_card = self._create_reports_card()
        self._reports_card.grid(row=2, column=0, columnspan=2, sticky="nsew",
                                padx=Spacing.MD, pady=Spacing.SM)

    def _create_status_bar(self) -> tk.Frame:
        """Create agent status bar."""
        theme = get_theme()
        colors = theme.colors

        frame = tk.Frame(self, bg=colors.bg_secondary, height=60)
        frame.pack_propagate(False)

        # Left: Agent state
        left = tk.Frame(frame, bg=colors.bg_secondary)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=Spacing.MD)

        StyledLabel(left, text="ALPHA DISCOVERY AGENT", style="title").pack(side=tk.LEFT)

        self._state_badge = StatusBadge(left, status="info", text="IDLE")
        self._state_badge.pack(side=tk.LEFT, padx=Spacing.MD)

        # Center: Metrics
        center = tk.Frame(frame, bg=colors.bg_secondary)
        center.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        metrics_frame = tk.Frame(center, bg=colors.bg_secondary)
        metrics_frame.pack(expand=True)

        # Exploration count
        exp_frame = tk.Frame(metrics_frame, bg=colors.bg_secondary)
        exp_frame.pack(side=tk.LEFT, padx=Spacing.LG)
        StyledLabel(exp_frame, text="Explorations", style="caption").pack()
        self._exploration_label = StyledLabel(exp_frame, text="0", style="subtitle")
        self._exploration_label.pack()

        # Hypotheses tested
        hyp_frame = tk.Frame(metrics_frame, bg=colors.bg_secondary)
        hyp_frame.pack(side=tk.LEFT, padx=Spacing.LG)
        StyledLabel(hyp_frame, text="Tested", style="caption").pack()
        self._tested_label = StyledLabel(hyp_frame, text="0", style="subtitle")
        self._tested_label.pack()

        # Deployed
        dep_frame = tk.Frame(metrics_frame, bg=colors.bg_secondary)
        dep_frame.pack(side=tk.LEFT, padx=Spacing.LG)
        StyledLabel(dep_frame, text="Deployed", style="caption").pack()
        self._deployed_label = StyledLabel(dep_frame, text="0", style="subtitle")
        self._deployed_label.pack()

        # Retired
        ret_frame = tk.Frame(metrics_frame, bg=colors.bg_secondary)
        ret_frame.pack(side=tk.LEFT, padx=Spacing.LG)
        StyledLabel(ret_frame, text="Retired", style="caption").pack()
        self._retired_label = StyledLabel(ret_frame, text="0", style="subtitle")
        self._retired_label.pack()

        # Right: Controls
        right = tk.Frame(frame, bg=colors.bg_secondary)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=Spacing.MD)

        self._start_btn = StyledButton(
            right, text="Start Agent", variant="primary",
            command=self._on_start
        )
        self._start_btn.pack(side=tk.LEFT, padx=2)

        self._stop_btn = StyledButton(
            right, text="Stop", variant="secondary",
            command=self._on_stop
        )
        self._stop_btn.pack(side=tk.LEFT, padx=2)

        self._explore_btn = StyledButton(
            right, text="Force Explore", variant="ghost",
            command=self._on_explore
        )
        self._explore_btn.pack(side=tk.LEFT, padx=2)

        return frame

    def _create_pipeline_card(self) -> Card:
        """Create strategy pipeline visualization."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Strategy Pipeline", padding="normal")

        # Pipeline stages
        stages = [
            ("candidates", "Candidates", "0"),
            ("testing", "Testing", "0"),
            ("validated", "Validated", "0"),
            ("deployed", "Deployed", "0"),
        ]

        self._pipeline_labels = {}

        for stage_id, label, default in stages:
            stage_frame = tk.Frame(card.content, bg=colors.bg_elevated)
            stage_frame.pack(fill=tk.X, pady=2)

            StyledLabel(stage_frame, text=label, style="body").pack(side=tk.LEFT)

            count_label = StyledLabel(stage_frame, text=default, style="subtitle")
            count_label.pack(side=tk.RIGHT)
            self._pipeline_labels[stage_id] = count_label

            # Progress bar visualization
            bar_frame = tk.Frame(card.content, bg=colors.bg_tertiary, height=4)
            bar_frame.pack(fill=tk.X, pady=(0, Spacing.SM))

        return card

    def _create_deployed_card(self) -> Card:
        """Create deployed strategies list."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Deployed Strategies", padding="tight")

        # Treeview for strategies
        columns = ("id", "sharpe", "decay", "return")
        self._strategies_tree = ttk.Treeview(
            card.content, columns=columns, show="headings", height=8
        )

        self._strategies_tree.heading("id", text="Strategy ID")
        self._strategies_tree.heading("sharpe", text="Sharpe")
        self._strategies_tree.heading("decay", text="Decay")
        self._strategies_tree.heading("return", text="Return")

        self._strategies_tree.column("id", width=120)
        self._strategies_tree.column("sharpe", width=60)
        self._strategies_tree.column("decay", width=60)
        self._strategies_tree.column("return", width=80)

        scrollbar = ttk.Scrollbar(
            card.content, orient="vertical",
            command=self._strategies_tree.yview
        )
        self._strategies_tree.configure(yscrollcommand=scrollbar.set)

        self._strategies_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        return card

    def _create_reports_card(self) -> Card:
        """Create research reports browser."""
        theme = get_theme()
        colors = theme.colors

        card = Card(self, title="Research Reports", padding="tight")

        # Split: list on left, content on right
        paned = ttk.PanedWindow(card.content, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Report list
        list_frame = tk.Frame(paned, bg=colors.bg_elevated)
        paned.add(list_frame, weight=1)

        self._reports_list = tk.Listbox(
            list_frame, bg=colors.bg_elevated, fg=colors.fg_primary,
            selectmode=tk.SINGLE, font=("Consolas", 9)
        )
        self._reports_list.pack(fill=tk.BOTH, expand=True)
        self._reports_list.bind('<<ListboxSelect>>', self._on_report_select)

        # Report content
        content_frame = tk.Frame(paned, bg=colors.bg_elevated)
        paned.add(content_frame, weight=2)

        self._report_text = scrolledtext.ScrolledText(
            content_frame, wrap=tk.WORD, font=("Consolas", 9),
            bg=colors.bg_elevated, fg=colors.fg_primary
        )
        self._report_text.pack(fill=tk.BOTH, expand=True)

        return card

    def _start_refresh(self) -> None:
        """Start periodic refresh."""
        self._refresh()
        self.after(2000, self._start_refresh)

    def _refresh(self) -> None:
        """Refresh UI with agent status."""
        if not self.agent:
            return

        try:
            status = self.agent.get_status()

            # Update state badge
            state = status.get('state', 'idle')
            state_colors = {
                'idle': 'info',
                'exploring': 'warning',
                'testing': 'warning',
                'evolving': 'warning',
                'validating': 'warning',
                'monitoring': 'success',
                'sleeping': 'info',
            }
            self._state_badge.set_status(
                state_colors.get(state, 'info'),
                state.upper()
            )

            # Update metrics
            self._exploration_label.config(text=str(status.get('exploration_count', 0)))
            self._tested_label.config(text=str(status.get('hypotheses_tested', 0)))
            self._deployed_label.config(text=str(status.get('deployed_count', 0)))
            self._retired_label.config(text=str(status.get('retired_count', 0)))

            # Update pipeline
            self._pipeline_labels['candidates'].config(
                text=str(status.get('candidate_pool_size', 0))
            )
            self._pipeline_labels['validated'].config(
                text=str(status.get('validated_pool_size', 0))
            )
            self._pipeline_labels['deployed'].config(
                text=str(status.get('deployed_count', 0))
            )

            # Update deployed strategies table
            for item in self._strategies_tree.get_children():
                self._strategies_tree.delete(item)

            for strategy in status.get('deployed_strategies', []):
                self._strategies_tree.insert("", "end", values=(
                    strategy['id'],
                    f"{strategy['current_sharpe']:.2f}",
                    f"{strategy['decay_score']:.0%}",
                    f"{strategy['cumulative_return']:.1%}"
                ))

        except Exception as e:
            logger.error(f"Refresh error: {e}")

    def _on_start(self) -> None:
        """Handle start button."""
        if self.agent:
            self.agent.start()

    def _on_stop(self) -> None:
        """Handle stop button."""
        if self.agent:
            self.agent.stop()

    def _on_explore(self) -> None:
        """Handle force explore button."""
        if self.agent:
            self.agent.force_exploration()

    def _on_report_select(self, event) -> None:
        """Handle report selection."""
        selection = self._reports_list.curselection()
        if not selection or not self.agent:
            return

        report_id = self._reports_list.get(selection[0])
        report = self.agent.get_report(report_id)

        if report:
            self._report_text.delete(1.0, tk.END)
            self._report_text.insert(tk.END, report)

    def set_agent(self, agent) -> None:
        """Set the alpha discovery agent."""
        self.agent = agent

        # Populate reports list
        if agent and hasattr(agent, 'reports'):
            self._reports_list.delete(0, tk.END)
            for report_id in agent.reports:
                self._reports_list.insert(tk.END, report_id)

    def destroy(self) -> None:
        """Clean up on destroy."""
        super().destroy()
