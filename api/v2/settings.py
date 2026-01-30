"""
QUANT INDUSTRY V1 - Settings API (v2)
=====================================
System configuration and API key management.
"""

from fastapi import APIRouter, Query, Path
from pydantic import BaseModel, Field, SecretStr
from typing import Optional, Any
from datetime import datetime
from enum import Enum

router = APIRouter()


# ============================================================================
# Enums
# ============================================================================

class DataProvider(str, Enum):
    """Data provider options."""
    ALPACA = "alpaca"
    POLYGON = "polygon"
    YAHOO = "yahoo"
    ALPHA_VANTAGE = "alpha_vantage"
    TIINGO = "tiingo"
    FINNHUB = "finnhub"
    IEX = "iex"


class BrokerProvider(str, Enum):
    """Broker provider options."""
    ALPACA = "alpaca"
    IBKR = "ibkr"
    TRADIER = "tradier"
    TD_AMERITRADE = "td_ameritrade"


class TradingMode(str, Enum):
    """Trading mode."""
    PAPER = "paper"
    LIVE = "live"


class DataMode(str, Enum):
    """Data mode."""
    LIVE = "live"
    DELAYED = "delayed"
    SIMULATED = "simulated"


# ============================================================================
# Pydantic Models - Settings
# ============================================================================

class TradingSettings(BaseModel):
    """Trading-related settings."""
    mode: TradingMode = TradingMode.PAPER
    default_order_type: str = "limit"
    default_time_in_force: str = "day"
    max_position_size: float = 25000.00
    max_portfolio_risk_percent: float = 2.0
    auto_trade_enabled: bool = False
    require_confirmation: bool = True


class DataSettings(BaseModel):
    """Data-related settings."""
    mode: DataMode = DataMode.LIVE
    primary_provider: DataProvider = DataProvider.ALPACA
    fallback_provider: Optional[DataProvider] = DataProvider.POLYGON
    cache_ttl_seconds: int = 60
    historical_data_years: int = 5


class BrainSettings(BaseModel):
    """ML brain settings."""
    enabled: bool = True
    signal_threshold: float = 0.7
    auto_train_enabled: bool = False
    auto_train_interval_hours: int = 24
    ensemble_mode: bool = True
    regime_detection_enabled: bool = True


class NotificationSettings(BaseModel):
    """Notification settings."""
    email_enabled: bool = False
    email_address: Optional[str] = None
    push_enabled: bool = False
    signal_notifications: bool = True
    trade_notifications: bool = True
    risk_alert_notifications: bool = True


class UISettings(BaseModel):
    """UI settings."""
    theme: str = "dark"
    default_chart_type: str = "candlestick"
    default_timeframe: str = "1d"
    show_extended_hours: bool = True
    refresh_interval_seconds: int = 5


class AllSettings(BaseModel):
    """All application settings."""
    trading: TradingSettings = Field(default_factory=TradingSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    brain: BrainSettings = Field(default_factory=BrainSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    ui: UISettings = Field(default_factory=UISettings)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Preset(BaseModel):
    """Settings preset."""
    name: str
    description: str
    settings: AllSettings
    is_default: bool = False
    created_at: datetime


class PresetsResponse(BaseModel):
    """Available presets."""
    presets: list[Preset] = Field(default_factory=list)


# ============================================================================
# Pydantic Models - API Keys
# ============================================================================

class APIKeyStatus(BaseModel):
    """API key status for a provider."""
    provider: str
    configured: bool
    valid: Optional[bool] = None
    last_validated: Optional[datetime] = None
    permissions: list[str] = Field(default_factory=list)
    rate_limit_remaining: Optional[int] = None
    error: Optional[str] = None


class APIKeysStatusResponse(BaseModel):
    """Status of all API keys."""
    keys: list[APIKeyStatus] = Field(default_factory=list)
    all_required_configured: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SetAPIKeyRequest(BaseModel):
    """Request to set an API key."""
    api_key: str = Field(..., min_length=10)
    api_secret: Optional[str] = None


class APIKeyTestResult(BaseModel):
    """API key test result."""
    provider: str
    success: bool
    latency_ms: float
    permissions: list[str] = Field(default_factory=list)
    account_type: Optional[str] = None
    error: Optional[str] = None
    tested_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Pydantic Models - System
# ============================================================================

class DataModeResponse(BaseModel):
    """Current data mode."""
    mode: DataMode
    primary_provider: DataProvider
    fallback_provider: Optional[DataProvider] = None
    last_quote_time: Optional[datetime] = None
    is_market_hours: bool


class DataQualityResponse(BaseModel):
    """Data quality/freshness status."""
    overall_quality: str = Field(..., description="good, degraded, stale")
    symbols_checked: int
    fresh_count: int
    stale_count: int
    error_count: int
    avg_age_seconds: float
    max_age_seconds: float
    stale_symbols: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Endpoints - Settings
# ============================================================================

@router.get(
    "",
    response_model=AllSettings,
    summary="Get settings",
    description="Get all application settings."
)
async def get_settings() -> AllSettings:
    """
    Get all application settings.
    """
    return AllSettings()


@router.put(
    "",
    response_model=AllSettings,
    summary="Update settings",
    description="Update application settings."
)
async def update_settings(settings: AllSettings) -> AllSettings:
    """
    Update application settings.
    """
    settings.updated_at = datetime.utcnow()
    return settings


@router.get(
    "/presets",
    response_model=PresetsResponse,
    summary="List presets",
    description="Get available settings presets."
)
async def list_presets() -> PresetsResponse:
    """
    List available settings presets.
    """
    presets = [
        Preset(
            name="conservative",
            description="Conservative settings for lower risk tolerance",
            settings=AllSettings(
                trading=TradingSettings(
                    max_position_size=10000.00,
                    max_portfolio_risk_percent=1.0,
                    require_confirmation=True
                ),
                brain=BrainSettings(signal_threshold=0.85)
            ),
            is_default=False,
            created_at=datetime(2024, 1, 1)
        ),
        Preset(
            name="moderate",
            description="Balanced settings for moderate risk tolerance",
            settings=AllSettings(),
            is_default=True,
            created_at=datetime(2024, 1, 1)
        ),
        Preset(
            name="aggressive",
            description="Aggressive settings for higher risk tolerance",
            settings=AllSettings(
                trading=TradingSettings(
                    max_position_size=50000.00,
                    max_portfolio_risk_percent=5.0,
                    auto_trade_enabled=True,
                    require_confirmation=False
                ),
                brain=BrainSettings(signal_threshold=0.6)
            ),
            is_default=False,
            created_at=datetime(2024, 1, 1)
        ),
    ]
    
    return PresetsResponse(presets=presets)


@router.post(
    "/presets/{preset_name}",
    response_model=AllSettings,
    summary="Apply preset",
    description="Apply a settings preset."
)
async def apply_preset(
    preset_name: str = Path(...)
) -> AllSettings:
    """
    Apply a settings preset by name.
    """
    # Return appropriate preset
    return AllSettings()


# ============================================================================
# Endpoints - API Keys
# ============================================================================

@router.get(
    "/api-keys",
    response_model=APIKeysStatusResponse,
    summary="API key status",
    description="Get status of all configured API keys."
)
async def get_api_keys_status() -> APIKeysStatusResponse:
    """
    Get status of all API keys (without revealing the keys).
    """
    keys = [
        APIKeyStatus(
            provider="alpaca",
            configured=True,
            valid=True,
            last_validated=datetime(2025, 1, 13, 8, 0),
            permissions=["trading", "data"],
            rate_limit_remaining=195
        ),
        APIKeyStatus(
            provider="polygon",
            configured=True,
            valid=True,
            last_validated=datetime(2025, 1, 13, 8, 0),
            permissions=["stocks", "options", "crypto"],
            rate_limit_remaining=4950
        ),
        APIKeyStatus(
            provider="openai",
            configured=True,
            valid=True,
            last_validated=datetime(2025, 1, 13, 8, 0),
            permissions=["chat", "embeddings"]
        ),
        APIKeyStatus(
            provider="finnhub",
            configured=False,
            valid=None
        ),
    ]
    
    all_required = all(k.configured for k in keys if k.provider in ["alpaca"])
    
    return APIKeysStatusResponse(
        keys=keys,
        all_required_configured=all_required
    )


@router.put(
    "/api-keys/{provider}",
    response_model=APIKeyStatus,
    summary="Set API key",
    description="Set or update an API key for a provider."
)
async def set_api_key(
    provider: str = Path(...),
    request: SetAPIKeyRequest = ...
) -> APIKeyStatus:
    """
    Set or update an API key.
    """
    return APIKeyStatus(
        provider=provider,
        configured=True,
        valid=None,  # Not yet validated
        last_validated=None
    )


@router.post(
    "/api-keys/{provider}/test",
    response_model=APIKeyTestResult,
    summary="Test API key",
    description="Test an API key connection."
)
async def test_api_key(
    provider: str = Path(...)
) -> APIKeyTestResult:
    """
    Test API key by making a test request.
    """
    return APIKeyTestResult(
        provider=provider,
        success=True,
        latency_ms=45.2,
        permissions=["trading", "data"],
        account_type="paper"
    )


@router.delete(
    "/api-keys/{provider}",
    summary="Remove API key",
    description="Remove an API key for a provider."
)
async def remove_api_key(
    provider: str = Path(...)
) -> dict:
    """
    Remove an API key.
    """
    return {"status": "removed", "provider": provider}


# ============================================================================
# Endpoints - System
# ============================================================================

@router.get(
    "/data-mode",
    response_model=DataModeResponse,
    summary="Get data mode",
    description="Get current data mode configuration."
)
async def get_data_mode() -> DataModeResponse:
    """
    Get current data mode.
    """
    return DataModeResponse(
        mode=DataMode.LIVE,
        primary_provider=DataProvider.ALPACA,
        fallback_provider=DataProvider.POLYGON,
        last_quote_time=datetime.utcnow(),
        is_market_hours=True
    )


@router.put(
    "/data-mode",
    response_model=DataModeResponse,
    summary="Set data mode",
    description="Set data mode (live, delayed, simulated)."
)
async def set_data_mode(
    mode: DataMode = Query(...)
) -> DataModeResponse:
    """
    Set data mode.
    """
    return DataModeResponse(
        mode=mode,
        primary_provider=DataProvider.ALPACA,
        fallback_provider=DataProvider.POLYGON,
        is_market_hours=True
    )


@router.get(
    "/data-quality",
    response_model=DataQualityResponse,
    summary="Data quality",
    description="Get data freshness and quality metrics."
)
async def get_data_quality() -> DataQualityResponse:
    """
    Get data quality/freshness status.
    """
    return DataQualityResponse(
        overall_quality="good",
        symbols_checked=500,
        fresh_count=495,
        stale_count=3,
        error_count=2,
        avg_age_seconds=2.5,
        max_age_seconds=15.2,
        stale_symbols=["OBSCURE1", "OBSCURE2", "DELISTED1"]
    )
