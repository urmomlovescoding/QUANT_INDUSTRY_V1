"""
QUANT_INDUSTRY_V1 UI Components - PROFESSIONAL EDITION

Reusable, themed Tkinter widgets for institutional-grade UI.
Includes advanced charts, animations, and modern styling.
"""

from .base import (
    StyledFrame,
    Card,
    StyledLabel,
    StyledButton,
    StyledEntry,
    Separator,
    Tooltip,
)
from .tables import (
    DataTable,
    Column,
    ColumnAlign,
    format_currency,
    format_percent,
)
from .indicators import (
    ProgressBar,
    ConfidenceBar,
    StatusBadge,
    DirectionIndicator,
    RegimeBadge,
    PnLDisplay,
    LoadingSpinner,
)
from .charts import (
    SparkLine,
    MiniBarChart,
    GaugeChart,
    HeatmapCell,
)
from .advanced_charts import (
    EquityCurveChart,
    CandlestickChart,
    DonutChart,
    MetricCard,
    HorizontalBarChart,
)
from .animations import (
    Animator,
    EasingFunctions,
    PulsingIndicator,
    CountUpLabel,
    ProgressAnimator,
    TypewriterLabel,
    ShimmerEffect,
)
from .command_palette import (
    CommandPalette,
    CommandRegistry,
    get_command_registry,
)
from .right_rail import (
    RightRail,
    QuickStat,
    RiskMeter,
    SignalItem,
)
from .toast import (
    Toast,
    ToastLevel,
    ToastManager,
    get_toast_manager,
    set_toast_manager,
    toast_info,
    toast_success,
    toast_warning,
    toast_error,
)
from .watchlist import (
    Watchlist,
    WatchlistItem,
)
from .quick_actions import (
    QuickActionsBar,
    ActionButton,
    FloatingActionButton,
)
from .market_ticker import (
    MarketTicker,
    CompactTicker,
)
from .keyboard_shortcuts import (
    KeyboardShortcutsOverlay,
    ShortcutHint,
    ShortcutToast,
)
from .trade_entry import (
    TradeEntryForm,
)
from .empty_states import (
    EmptyState,
    NoSignalsState,
    NoPositionsState,
    NoDataState,
    ErrorState,
    LoadingState,
    FirstTimeState,
    MaintenanceState,
    OfflineState,
)
from .strategy_cards import (
    StrategyCard,
    StrategyCardsGrid,
)
from .settings_panel import (
    SettingsPanel,
)
from .notification_center import (
    NotificationCenter,
    NotificationItem,
)
from .portfolio_summary import (
    PortfolioSummary,
    AllocationBar,
    MiniDonutChart,
    PerformanceRow,
    PortfolioCard,
)
from .context_menu import (
    ContextMenu,
    TableContextMenu,
    PositionContextMenu,
    SignalContextMenu,
    WatchlistContextMenu,
    bind_context_menu,
)
from .activity_log import (
    ActivityLog,
    ActivityEntry,
    ActivityType,
    CompactActivityLog,
)
from .progress import (
    CircularProgress,
    LinearProgress,
    SkeletonLoader,
    PulsingDot,
    DotsLoader,
    LoadingOverlay,
    ProgressWithLabel,
)
from .symbol_search import (
    SymbolSearch,
    SymbolSearchPopup,
)

__all__ = [
    # Base components
    'StyledFrame',
    'Card',
    'StyledLabel',
    'StyledButton',
    'StyledEntry',
    'Separator',
    'Tooltip',
    # Tables
    'DataTable',
    'Column',
    'ColumnAlign',
    'format_currency',
    'format_percent',
    # Indicators
    'ProgressBar',
    'ConfidenceBar',
    'StatusBadge',
    'DirectionIndicator',
    'RegimeBadge',
    'PnLDisplay',
    'LoadingSpinner',
    # Charts
    'SparkLine',
    'MiniBarChart',
    'GaugeChart',
    'HeatmapCell',
    # Advanced Charts
    'EquityCurveChart',
    'CandlestickChart',
    'DonutChart',
    'MetricCard',
    'HorizontalBarChart',
    # Animations
    'Animator',
    'EasingFunctions',
    'PulsingIndicator',
    'CountUpLabel',
    'ProgressAnimator',
    'TypewriterLabel',
    'ShimmerEffect',
    # Command Palette
    'CommandPalette',
    'CommandRegistry',
    'get_command_registry',
    # Right Rail
    'RightRail',
    'QuickStat',
    'RiskMeter',
    'SignalItem',
    # Toast Notifications
    'Toast',
    'ToastLevel',
    'ToastManager',
    'get_toast_manager',
    'set_toast_manager',
    'toast_info',
    'toast_success',
    'toast_warning',
    'toast_error',
    # Watchlist
    'Watchlist',
    'WatchlistItem',
    # Quick Actions
    'QuickActionsBar',
    'ActionButton',
    'FloatingActionButton',
    # Market Ticker
    'MarketTicker',
    'CompactTicker',
    # Keyboard Shortcuts
    'KeyboardShortcutsOverlay',
    'ShortcutHint',
    'ShortcutToast',
    # Trade Entry
    'TradeEntryForm',
    # Empty States
    'EmptyState',
    'NoSignalsState',
    'NoPositionsState',
    'NoDataState',
    'ErrorState',
    'LoadingState',
    'FirstTimeState',
    'MaintenanceState',
    'OfflineState',
    # Strategy Cards
    'StrategyCard',
    'StrategyCardsGrid',
    # Settings Panel
    'SettingsPanel',
    # Notification Center
    'NotificationCenter',
    'NotificationItem',
    # Portfolio Summary
    'PortfolioSummary',
    'AllocationBar',
    'MiniDonutChart',
    'PerformanceRow',
    'PortfolioCard',
    # Context Menu
    'ContextMenu',
    'TableContextMenu',
    'PositionContextMenu',
    'SignalContextMenu',
    'WatchlistContextMenu',
    'bind_context_menu',
    # Activity Log
    'ActivityLog',
    'ActivityEntry',
    'ActivityType',
    'CompactActivityLog',
    # Progress Indicators
    'CircularProgress',
    'LinearProgress',
    'SkeletonLoader',
    'PulsingDot',
    'DotsLoader',
    'LoadingOverlay',
    'ProgressWithLabel',
    # Symbol Search
    'SymbolSearch',
    'SymbolSearchPopup',
]
