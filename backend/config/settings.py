"""
QUANT INDUSTRY - Settings Configuration
Platform settings, preferences, and API configuration
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Theme(Enum):
    DARK = "DARK"
    LIGHT = "LIGHT"
    BLOOMBERG = "BLOOMBERG"
    TRADINGVIEW = "TRADINGVIEW"
    CUSTOM = "CUSTOM"


class ChartStyle(Enum):
    CANDLESTICK = "CANDLESTICK"
    OHLC = "OHLC"
    LINE = "LINE"
    AREA = "AREA"
    HEIKIN_ASHI = "HEIKIN_ASHI"


class DataRefreshRate(Enum):
    REALTIME = "REALTIME"      # As fast as possible
    FAST = "FAST"              # 1 second
    NORMAL = "NORMAL"          # 5 seconds
    SLOW = "SLOW"              # 15 seconds
    MANUAL = "MANUAL"          # Manual refresh only


@dataclass
class UISettings:
    theme: str = "BLOOMBERG"
    chart_style: str = "CANDLESTICK"
    sidebar_collapsed: bool = False
    show_ticker_tape: bool = True
    show_volume: bool = True
    show_indicators: bool = True
    default_timeframe: str = "1D"

    # Colors (can be customized)
    background_color: str = "#0a0a12"
    panel_color: str = "#12121a"
    accent_color: str = "#00d4aa"
    bullish_color: str = "#00c853"
    bearish_color: str = "#ff5252"
    text_color: str = "#e0e0e0"
    muted_color: str = "#6b7280"

    # Chart settings
    chart_grid: bool = True
    chart_crosshair: bool = True
    volume_overlay: bool = False

    # Animation
    animations_enabled: bool = True
    transition_duration: int = 200

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DataSettings:
    refresh_rate: str = "NORMAL"
    cache_duration_minutes: int = 5
    max_historical_days: int = 365
    default_symbols: List[str] = field(default_factory=lambda: [
        "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"
    ])

    # Data sources priority
    data_source_priority: List[str] = field(default_factory=lambda: [
        "alpaca", "yfinance", "tradier", "finnhub", "polygon"
    ])

    # Options data
    options_expiry_filter: str = "all"  # all, weekly, monthly
    options_strike_range: int = 10  # strikes above/below ATM

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TradingSettings:
    paper_trading: bool = True
    default_order_type: str = "MARKET"
    confirm_orders: bool = True
    default_quantity: int = 100
    max_position_pct: float = 15.0
    max_daily_loss: float = 1000.0

    # Risk settings
    auto_stop_loss: bool = True
    default_stop_loss_pct: float = 3.0
    default_take_profit_pct: float = 6.0

    # Bot settings
    bot_enabled: bool = False
    bot_strategy: str = "ML_ENSEMBLE"
    bot_max_positions: int = 5

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NotificationSettings:
    enabled: bool = True
    sound_enabled: bool = True
    desktop_notifications: bool = True

    # Alert types
    price_alerts: bool = True
    trade_alerts: bool = True
    risk_alerts: bool = True
    news_alerts: bool = False

    # Alert thresholds
    price_change_threshold: float = 5.0  # %
    volume_spike_threshold: float = 200.0  # % of average

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Settings:
    ui: UISettings = field(default_factory=UISettings)
    data: DataSettings = field(default_factory=DataSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)

    # Metadata
    version: str = "10.0.0"
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "ui": self.ui.to_dict(),
            "data": self.data.to_dict(),
            "trading": self.trading.to_dict(),
            "notifications": self.notifications.to_dict(),
            "version": self.version,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Settings":
        """Create Settings from dictionary"""
        settings = cls()

        if "ui" in data:
            for key, value in data["ui"].items():
                if hasattr(settings.ui, key):
                    setattr(settings.ui, key, value)

        if "data" in data:
            for key, value in data["data"].items():
                if hasattr(settings.data, key):
                    setattr(settings.data, key, value)

        if "trading" in data:
            for key, value in data["trading"].items():
                if hasattr(settings.trading, key):
                    setattr(settings.trading, key, value)

        if "notifications" in data:
            for key, value in data["notifications"].items():
                if hasattr(settings.notifications, key):
                    setattr(settings.notifications, key, value)

        settings.version = data.get("version", settings.version)
        settings.last_updated = datetime.now().isoformat()

        return settings


# Global settings instance
_settings: Optional[Settings] = None
_settings_path: str = os.path.join(
    os.path.dirname(__file__), "..", "data", "settings.json"
)


def get_settings() -> Settings:
    """Get current settings"""
    global _settings

    if _settings is None:
        _settings = _load_settings()

    return _settings


def save_settings(settings: Settings = None) -> bool:
    """Save settings to file"""
    global _settings

    if settings:
        _settings = settings

    if _settings is None:
        _settings = Settings()

    try:
        os.makedirs(os.path.dirname(_settings_path), exist_ok=True)

        with open(_settings_path, 'w') as f:
            json.dump(_settings.to_dict(), f, indent=2)

        logger.info("Settings saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False


def _load_settings() -> Settings:
    """Load settings from file"""
    try:
        if os.path.exists(_settings_path):
            with open(_settings_path) as f:
                data = json.load(f)
                return Settings.from_dict(data)
    except Exception as e:
        logger.error(f"Error loading settings: {e}")

    return Settings()


def update_settings(updates: Dict) -> Settings:
    """Update specific settings"""
    global _settings

    if _settings is None:
        _settings = get_settings()

    # Apply updates
    for section, values in updates.items():
        if hasattr(_settings, section):
            section_obj = getattr(_settings, section)
            if isinstance(values, dict):
                for key, value in values.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)

    _settings.last_updated = datetime.now().isoformat()
    save_settings(_settings)

    return _settings


def reset_settings() -> Settings:
    """Reset to default settings"""
    global _settings
    _settings = Settings()
    save_settings(_settings)
    return _settings


# UI Presets
UI_PRESETS = {
    "bloomberg": {
        "theme": "BLOOMBERG",
        "background_color": "#0a0a12",
        "panel_color": "#12121a",
        "accent_color": "#00d4aa",
        "bullish_color": "#00c853",
        "bearish_color": "#ff5252",
        "text_color": "#e0e0e0",
    },
    "tradingview_dark": {
        "theme": "TRADINGVIEW",
        "background_color": "#131722",
        "panel_color": "#1e222d",
        "accent_color": "#2962ff",
        "bullish_color": "#26a69a",
        "bearish_color": "#ef5350",
        "text_color": "#d1d4dc",
    },
    "dark_pro": {
        "theme": "DARK",
        "background_color": "#0d1117",
        "panel_color": "#161b22",
        "accent_color": "#58a6ff",
        "bullish_color": "#3fb950",
        "bearish_color": "#f85149",
        "text_color": "#c9d1d9",
    },
    "midnight": {
        "theme": "CUSTOM",
        "background_color": "#0f0f23",
        "panel_color": "#1a1a2e",
        "accent_color": "#e94560",
        "bullish_color": "#00ff88",
        "bearish_color": "#ff4444",
        "text_color": "#eaeaea",
    },
    "cyberpunk": {
        "theme": "CUSTOM",
        "background_color": "#0a0a0f",
        "panel_color": "#13131a",
        "accent_color": "#00ffff",
        "bullish_color": "#00ff00",
        "bearish_color": "#ff00ff",
        "text_color": "#ffffff",
    },
    "forest": {
        "theme": "CUSTOM",
        "background_color": "#0d1912",
        "panel_color": "#142318",
        "accent_color": "#4ade80",
        "bullish_color": "#22c55e",
        "bearish_color": "#ef4444",
        "text_color": "#d1fae5",
    },
}


def apply_ui_preset(preset_name: str) -> Settings:
    """Apply a UI preset"""
    global _settings

    if preset_name not in UI_PRESETS:
        logger.warning(f"Unknown preset: {preset_name}")
        return get_settings()

    preset = UI_PRESETS[preset_name]

    if _settings is None:
        _settings = get_settings()

    for key, value in preset.items():
        if hasattr(_settings.ui, key):
            setattr(_settings.ui, key, value)

    _settings.last_updated = datetime.now().isoformat()
    save_settings(_settings)

    return _settings


def get_available_presets() -> List[str]:
    """Get list of available UI presets"""
    return list(UI_PRESETS.keys())
