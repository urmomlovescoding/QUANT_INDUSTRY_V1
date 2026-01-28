"""
QUANT_INDUSTRY_V1 UI Module

Institutional-grade Tkinter UI with:
- Theme system (dark/light/bloomberg)
- State management with event bus
- Reusable components library
- Multiple views (dashboard, signals, positions, health)

Usage:
    from ui.app import launch_ui
    app = launch_ui(run_id="...", mode="paper")
    app.run()
"""

from .theme import (
    get_theme,
    set_theme,
    init_theme,
    ThemeConfig,
    ColorScheme,
    ColorPalette,
    Spacing,
    FontSize,
    FontWeight,
)
from .state import (
    get_store,
    get_event_bus,
    init_store,
    StateStore,
    EventBus,
    EventType,
    Event,
    AppState,
    SignalState,
    PositionState,
    PortfolioState,
    MarketState,
    dispatch,
    notify,
)
from .app import AppShell, launch_ui
from .engine_connector import EngineConnector, get_connector, connect_engine
from .dashboard import TradingDashboard, create_dashboard

__all__ = [
    # Theme
    'get_theme',
    'set_theme',
    'init_theme',
    'ThemeConfig',
    'ColorScheme',
    'ColorPalette',
    'Spacing',
    'FontSize',
    'FontWeight',
    # State
    'get_store',
    'get_event_bus',
    'init_store',
    'StateStore',
    'EventBus',
    'EventType',
    'Event',
    'AppState',
    'SignalState',
    'PositionState',
    'PortfolioState',
    'MarketState',
    'dispatch',
    'notify',
    # App
    'AppShell',
    'launch_ui',
    # Engine connector
    'EngineConnector',
    'get_connector',
    'connect_engine',
    # Dashboard
    'TradingDashboard',
    'create_dashboard',
]
