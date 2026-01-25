"""
QUANT_INDUSTRY_V1 Settings Configuration

Environment-aware configuration with validation.
Uses Pydantic for type safety and validation.

Configuration priority (highest to lowest):
1. Explicit programmatic configuration
2. Environment variables
3. .env file
4. Default values

Environment Variables:
    QUANT_ENV: Environment name (development, staging, production)
    QUANT_DB_PATH: SQLite database path
    QUANT_LOG_LEVEL: Logging level
    ALPACA_API_KEY: Alpaca API key
    ALPACA_SECRET_KEY: Alpaca secret key
    ALPACA_BASE_URL: Alpaca API base URL
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class Environment(Enum):
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'
    TEST = 'test'


class TradingMode(Enum):
    BACKTEST = 'backtest'
    PAPER = 'paper'
    LIVE = 'live'


class DataSource(Enum):
    ALPACA = 'alpaca'
    YAHOO = 'yahoo'
    POLYGON = 'polygon'


@dataclass
class DataConfig:
    """Data fetching and caching configuration."""
    primary_source: DataSource = DataSource.ALPACA
    fallback_sources: List[DataSource] = field(default_factory=lambda: [DataSource.YAHOO])
    cache_ttl_seconds: int = 300  # 5 minutes
    rate_limit_per_minute: int = 200
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    default_timeframe: str = '1d'
    history_days: int = 365
    symbols: List[str] = field(default_factory=lambda: ['SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL'])

    # Data quality settings
    max_staleness_seconds: int = 86400  # 24 hours for daily data
    outlier_zscore_threshold: float = 4.0
    min_volume_threshold: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'primary_source': self.primary_source.value,
            'fallback_sources': [s.value for s in self.fallback_sources],
            'cache_ttl_seconds': self.cache_ttl_seconds,
            'rate_limit_per_minute': self.rate_limit_per_minute,
            'max_retries': self.max_retries,
            'default_timeframe': self.default_timeframe,
            'history_days': self.history_days,
            'symbols': self.symbols,
        }


@dataclass
class BrainConfig:
    """ML/AI brain configuration."""
    # Ensemble settings
    enable_supervised: bool = True
    enable_rl: bool = True
    enable_meta_learner: bool = True

    # Model settings
    confidence_threshold: float = 0.6
    min_samples_for_training: int = 100
    retrain_frequency_hours: int = 24

    # Feature settings
    feature_window: int = 60  # Days of history for features
    feature_scaling: str = 'standard'  # 'standard', 'minmax', 'robust'

    # RL settings
    rl_algorithm: str = 'PPO'
    rl_learning_rate: float = 3e-4
    rl_clip_range: float = 0.2
    rl_n_steps: int = 2048
    rl_batch_size: int = 64

    # Regime detection
    regime_detection_method: str = 'hmm'  # 'hmm', 'clustering', 'rule_based'
    num_regimes: int = 3  # low_vol, normal, high_vol

    # Model persistence
    checkpoint_dir: str = 'checkpoints'
    save_frequency_steps: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            'enable_supervised': self.enable_supervised,
            'enable_rl': self.enable_rl,
            'enable_meta_learner': self.enable_meta_learner,
            'confidence_threshold': self.confidence_threshold,
            'min_samples_for_training': self.min_samples_for_training,
            'feature_window': self.feature_window,
            'rl_algorithm': self.rl_algorithm,
            'regime_detection_method': self.regime_detection_method,
        }


@dataclass
class ExecutionConfig:
    """Trade execution configuration."""
    mode: TradingMode = TradingMode.PAPER
    max_position_pct: float = 0.20  # 20% max per position
    default_stop_loss_pct: float = 0.02  # 2%
    default_take_profit_pct: float = 0.04  # 4%
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.03  # 3%

    # Position sizing
    position_sizing_method: str = 'kelly'  # 'kelly', 'fixed', 'volatility_scaled'
    kelly_fraction: float = 0.5  # Half-Kelly

    # Order settings
    default_order_type: str = 'market'
    time_in_force: str = 'day'

    # Transaction costs (for backtesting)
    commission_per_share: float = 0.0
    slippage_bps: float = 5.0  # 5 basis points

    # Kill switch
    max_daily_loss_pct: float = 0.05  # 5%
    max_orders_per_minute: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode.value,
            'max_position_pct': self.max_position_pct,
            'default_stop_loss_pct': self.default_stop_loss_pct,
            'default_take_profit_pct': self.default_take_profit_pct,
            'position_sizing_method': self.position_sizing_method,
            'kelly_fraction': self.kelly_fraction,
            'max_daily_loss_pct': self.max_daily_loss_pct,
        }


@dataclass
class RiskConfig:
    """Risk management configuration."""
    # Exposure limits
    max_gross_exposure: float = 2.0  # 200% gross
    max_net_exposure: float = 1.0  # 100% net
    max_single_position: float = 0.25  # 25% per position
    max_sector_exposure: float = 0.40  # 40% per sector

    # Risk metrics
    var_confidence: float = 0.95
    var_lookback_days: int = 252
    max_drawdown_pct: float = 0.15  # 15%

    # Volatility targeting
    target_volatility: float = 0.15  # 15% annualized
    volatility_lookback_days: int = 20

    # Beta limits
    max_beta: float = 1.5
    min_beta: float = -0.5

    # Correlation limits
    max_correlation: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            'max_gross_exposure': self.max_gross_exposure,
            'max_net_exposure': self.max_net_exposure,
            'max_single_position': self.max_single_position,
            'var_confidence': self.var_confidence,
            'max_drawdown_pct': self.max_drawdown_pct,
            'target_volatility': self.target_volatility,
        }


@dataclass
class UIConfig:
    """UI/Dashboard configuration."""
    # Tkinter settings (current)
    theme: str = 'dark'
    refresh_interval_ms: int = 1000
    chart_candles: int = 100

    # Performance settings
    enable_virtualization: bool = True
    max_table_rows: int = 1000
    debounce_ms: int = 100

    # Layout
    default_layout: str = 'trader_mode'
    enable_command_palette: bool = True

    # Notifications
    enable_notifications: bool = True
    notification_sound: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'theme': self.theme,
            'refresh_interval_ms': self.refresh_interval_ms,
            'default_layout': self.default_layout,
        }


@dataclass
class Settings:
    """
    Master settings configuration.

    Aggregates all subsystem configurations into a single object.
    Provides hashing for reproducibility tracking.
    """
    # Environment
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = 'INFO'

    # Paths
    base_dir: Path = field(default_factory=lambda: Path.home() / 'QUANT_INDUSTRY_V1')
    db_path: Optional[Path] = None
    log_dir: Optional[Path] = None

    # API Keys (loaded from environment)
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_base_url: str = 'https://paper-api.alpaca.markets'

    # Subsystem configurations
    data: DataConfig = field(default_factory=DataConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    def __post_init__(self):
        """Initialize derived paths and load environment variables."""
        # Set derived paths
        if self.db_path is None:
            self.db_path = self.base_dir / 'data' / 'quant.db'
        if self.log_dir is None:
            self.log_dir = self.base_dir / 'logs'

        # Load from environment
        self._load_from_env()

    def _load_from_env(self):
        """Load settings from environment variables."""
        # Environment
        env_name = os.getenv('QUANT_ENV', self.environment.value)
        try:
            self.environment = Environment(env_name)
        except ValueError:
            logger.warning(f"Unknown environment: {env_name}, using development")

        self.debug = os.getenv('QUANT_DEBUG', str(self.debug)).lower() == 'true'
        self.log_level = os.getenv('QUANT_LOG_LEVEL', self.log_level)

        # Paths
        if db_path := os.getenv('QUANT_DB_PATH'):
            self.db_path = Path(db_path)

        # API Keys
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY', self.alpaca_api_key)
        self.alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY', self.alpaca_secret_key)
        self.alpaca_base_url = os.getenv('ALPACA_BASE_URL', self.alpaca_base_url)

        # Trading mode
        if mode := os.getenv('QUANT_TRADING_MODE'):
            try:
                self.execution.mode = TradingMode(mode)
            except ValueError:
                pass

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check API keys for non-backtest modes
        if self.execution.mode != TradingMode.BACKTEST:
            if not self.alpaca_api_key:
                errors.append("ALPACA_API_KEY required for paper/live trading")
            if not self.alpaca_secret_key:
                errors.append("ALPACA_SECRET_KEY required for paper/live trading")

        # Check live trading restrictions
        if self.execution.mode == TradingMode.LIVE:
            if self.environment != Environment.PRODUCTION:
                errors.append("Live trading only allowed in production environment")
            if 'paper' in self.alpaca_base_url:
                errors.append("Live trading cannot use paper API URL")

        # Check risk limits
        if self.risk.max_single_position > self.risk.max_net_exposure:
            errors.append("max_single_position cannot exceed max_net_exposure")

        # Check paths exist or can be created
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create required directories: {e}")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

    def get_hash(self) -> str:
        """
        Get configuration hash for reproducibility.

        Returns:
            16-character hex hash of configuration
        """
        config_dict = self.to_dict()
        # Remove sensitive/variable fields
        config_dict.pop('alpaca_api_key', None)
        config_dict.pop('alpaca_secret_key', None)

        config_str = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            'environment': self.environment.value,
            'debug': self.debug,
            'log_level': self.log_level,
            'base_dir': str(self.base_dir),
            'db_path': str(self.db_path),
            'alpaca_base_url': self.alpaca_base_url,
            'data': self.data.to_dict(),
            'brain': self.brain.to_dict(),
            'execution': self.execution.to_dict(),
            'risk': self.risk.to_dict(),
            'ui': self.ui.to_dict(),
        }

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to JSON file."""
        if path is None:
            path = self.base_dir / 'config' / 'settings.json'

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Settings saved to {path}")

    @classmethod
    def load(cls, path: Path) -> 'Settings':
        """Load configuration from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        settings = cls()

        # Load environment
        if env := data.get('environment'):
            settings.environment = Environment(env)

        settings.debug = data.get('debug', settings.debug)
        settings.log_level = data.get('log_level', settings.log_level)

        if base_dir := data.get('base_dir'):
            settings.base_dir = Path(base_dir)
        if db_path := data.get('db_path'):
            settings.db_path = Path(db_path)

        # Load subsystem configs
        if data_config := data.get('data'):
            if primary := data_config.get('primary_source'):
                settings.data.primary_source = DataSource(primary)
            if symbols := data_config.get('symbols'):
                settings.data.symbols = symbols
            if cache_ttl := data_config.get('cache_ttl_seconds'):
                settings.data.cache_ttl_seconds = cache_ttl

        if brain_config := data.get('brain'):
            settings.brain.confidence_threshold = brain_config.get(
                'confidence_threshold', settings.brain.confidence_threshold
            )

        if exec_config := data.get('execution'):
            if mode := exec_config.get('mode'):
                settings.execution.mode = TradingMode(mode)
            settings.execution.max_position_pct = exec_config.get(
                'max_position_pct', settings.execution.max_position_pct
            )

        if risk_config := data.get('risk'):
            settings.risk.max_drawdown_pct = risk_config.get(
                'max_drawdown_pct', settings.risk.max_drawdown_pct
            )

        logger.info(f"Settings loaded from {path}")
        return settings


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings(settings: Optional[Settings] = None, **kwargs) -> Settings:
    """
    Initialize global settings.

    Args:
        settings: Optional Settings instance
        **kwargs: Arguments to pass to Settings constructor

    Returns:
        Initialized Settings instance
    """
    global _settings

    if settings is not None:
        _settings = settings
    else:
        _settings = Settings(**kwargs)

    # Validate
    errors = _settings.validate()
    if errors:
        for error in errors:
            logger.warning(f"Configuration warning: {error}")

    return _settings
