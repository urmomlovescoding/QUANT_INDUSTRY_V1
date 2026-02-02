"""
QUANT INDUSTRY - API Keys Configuration
Secure storage and management of API credentials
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlpacaKeys:
    api_key: str = ""
    secret_key: str = ""
    base_url: str = "https://paper-api.alpaca.markets"  # Paper trading by default
    data_url: str = "https://data.alpaca.markets"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.secret_key)


@dataclass
class TradierKeys:
    api_key: str = ""
    account_id: str = ""
    base_url: str = "https://sandbox.tradier.com"  # Sandbox by default
    is_sandbox: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.account_id)


@dataclass
class PolygonKeys:
    api_key: str = ""
    base_url: str = "https://api.polygon.io"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class FinnhubKeys:
    api_key: str = ""
    base_url: str = "https://finnhub.io/api/v1"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class FINRAKeys:
    api_key: str = ""
    base_url: str = "https://api.finra.org"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class NewsAPIKeys:
    api_key: str = ""
    base_url: str = "https://newsapi.org/v2"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class AlphaVantageKeys:
    api_key: str = ""
    base_url: str = "https://www.alphavantage.co/query"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class FMPKeys:
    api_key: str = ""
    base_url: str = "https://financialmodelingprep.com/api/v3"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class APIKeys:
    alpaca: AlpacaKeys = field(default_factory=AlpacaKeys)
    tradier: TradierKeys = field(default_factory=TradierKeys)
    polygon: PolygonKeys = field(default_factory=PolygonKeys)
    finnhub: FinnhubKeys = field(default_factory=FinnhubKeys)
    finra: FINRAKeys = field(default_factory=FINRAKeys)
    news_api: NewsAPIKeys = field(default_factory=NewsAPIKeys)
    alpha_vantage: AlphaVantageKeys = field(default_factory=AlphaVantageKeys)
    fmp: FMPKeys = field(default_factory=FMPKeys)

    # Metadata
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "alpaca": asdict(self.alpaca),
            "tradier": asdict(self.tradier),
            "polygon": asdict(self.polygon),
            "finnhub": asdict(self.finnhub),
            "finra": asdict(self.finra),
            "news_api": asdict(self.news_api),
            "alpha_vantage": asdict(self.alpha_vantage),
            "fmp": asdict(self.fmp),
            "last_updated": self.last_updated,
        }

    def to_safe_dict(self) -> Dict:
        """Return dict with masked keys for display"""
        def mask_key(key: str) -> str:
            if not key:
                return ""
            if len(key) <= 8:
                return "*" * len(key)
            return key[:4] + "*" * (len(key) - 8) + key[-4:]

        return {
            "alpaca": {
                "api_key": mask_key(self.alpaca.api_key),
                "secret_key": mask_key(self.alpaca.secret_key),
                "base_url": self.alpaca.base_url,
                "is_configured": self.alpaca.is_configured,
            },
            "tradier": {
                "api_key": mask_key(self.tradier.api_key),
                "account_id": self.tradier.account_id,
                "is_sandbox": self.tradier.is_sandbox,
                "is_configured": self.tradier.is_configured,
            },
            "polygon": {
                "api_key": mask_key(self.polygon.api_key),
                "is_configured": self.polygon.is_configured,
            },
            "finnhub": {
                "api_key": mask_key(self.finnhub.api_key),
                "is_configured": self.finnhub.is_configured,
            },
            "finra": {
                "api_key": mask_key(self.finra.api_key),
                "is_configured": self.finra.is_configured,
            },
            "news_api": {
                "api_key": mask_key(self.news_api.api_key),
                "is_configured": self.news_api.is_configured,
            },
            "alpha_vantage": {
                "api_key": mask_key(self.alpha_vantage.api_key),
                "is_configured": self.alpha_vantage.is_configured,
            },
            "fmp": {
                "api_key": mask_key(self.fmp.api_key),
                "is_configured": self.fmp.is_configured,
            },
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "APIKeys":
        """Create APIKeys from dictionary"""
        keys = cls()

        if "alpaca" in data:
            for key, value in data["alpaca"].items():
                if hasattr(keys.alpaca, key):
                    setattr(keys.alpaca, key, value)

        if "tradier" in data:
            for key, value in data["tradier"].items():
                if hasattr(keys.tradier, key):
                    setattr(keys.tradier, key, value)

        if "polygon" in data:
            for key, value in data["polygon"].items():
                if hasattr(keys.polygon, key):
                    setattr(keys.polygon, key, value)

        if "finnhub" in data:
            for key, value in data["finnhub"].items():
                if hasattr(keys.finnhub, key):
                    setattr(keys.finnhub, key, value)

        if "finra" in data:
            for key, value in data["finra"].items():
                if hasattr(keys.finra, key):
                    setattr(keys.finra, key, value)

        if "news_api" in data:
            for key, value in data["news_api"].items():
                if hasattr(keys.news_api, key):
                    setattr(keys.news_api, key, value)

        if "alpha_vantage" in data:
            for key, value in data["alpha_vantage"].items():
                if hasattr(keys.alpha_vantage, key):
                    setattr(keys.alpha_vantage, key, value)

        if "fmp" in data:
            for key, value in data["fmp"].items():
                if hasattr(keys.fmp, key):
                    setattr(keys.fmp, key, value)

        keys.last_updated = datetime.now().isoformat()
        return keys

    def get_status(self) -> Dict[str, bool]:
        """Get configuration status for all APIs"""
        return {
            "alpaca": self.alpaca.is_configured,
            "tradier": self.tradier.is_configured,
            "polygon": self.polygon.is_configured,
            "finnhub": self.finnhub.is_configured,
            "finra": self.finra.is_configured,
            "news_api": self.news_api.is_configured,
            "alpha_vantage": self.alpha_vantage.is_configured,
            "fmp": self.fmp.is_configured,
        }


# Global API keys instance
_api_keys: Optional[APIKeys] = None
_keys_path: str = os.path.join(
    os.path.dirname(__file__), "..", "data", "api_keys.json"
)


def get_api_keys() -> APIKeys:
    """Get current API keys"""
    global _api_keys

    if _api_keys is None:
        _api_keys = _load_api_keys()

    return _api_keys


def save_api_keys(keys: APIKeys = None) -> bool:
    """Save API keys to file"""
    global _api_keys

    if keys:
        _api_keys = keys

    if _api_keys is None:
        _api_keys = _get_default_keys()

    try:
        os.makedirs(os.path.dirname(_keys_path), exist_ok=True)

        with open(_keys_path, 'w') as f:
            json.dump(_api_keys.to_dict(), f, indent=2)

        logger.info("API keys saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving API keys: {e}")
        return False


def _load_api_keys() -> APIKeys:
    """Load API keys from file"""
    try:
        if os.path.exists(_keys_path):
            with open(_keys_path) as f:
                data = json.load(f)
                return APIKeys.from_dict(data)
    except Exception as e:
        logger.error(f"Error loading API keys: {e}")

    # Return default keys if file doesn't exist
    return _get_default_keys()


def _get_default_keys() -> APIKeys:
    """
    Get API keys from environment variables.

    SECURITY: API keys must come from environment variables or api_keys.json file.
    Never hardcode keys in source code.
    """
    keys = APIKeys()

    # Load from environment variables (SECURE)
    keys.alpaca.api_key = os.getenv("ALPACA_API_KEY", "")
    keys.alpaca.secret_key = os.getenv("ALPACA_API_SECRET", "")
    keys.alpaca.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    keys.tradier.api_key = os.getenv("TRADIER_API_KEY", "")
    keys.tradier.account_id = os.getenv("TRADIER_ACCOUNT_ID", "")
    keys.tradier.is_sandbox = os.getenv("TRADIER_SANDBOX", "true").lower() == "true"
    keys.tradier.base_url = os.getenv("TRADIER_BASE_URL", "https://sandbox.tradier.com")

    keys.polygon.api_key = os.getenv("POLYGON_API_KEY", "")

    keys.finnhub.api_key = os.getenv("FINNHUB_API_KEY", "")

    keys.finra.api_key = os.getenv("FINRA_API_KEY", "")

    keys.news_api.api_key = os.getenv("NEWS_API_KEY", "")

    keys.alpha_vantage.api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")

    keys.fmp.api_key = os.getenv("FMP_API_KEY", "")

    return keys


def update_api_key(provider: str, key_data: Dict) -> APIKeys:
    """Update API key for a specific provider"""
    global _api_keys

    if _api_keys is None:
        _api_keys = get_api_keys()

    if hasattr(_api_keys, provider):
        provider_keys = getattr(_api_keys, provider)
        for key, value in key_data.items():
            if hasattr(provider_keys, key):
                setattr(provider_keys, key, value)

    _api_keys.last_updated = datetime.now().isoformat()
    save_api_keys(_api_keys)

    return _api_keys


def test_api_connection(provider: str) -> Dict:
    """Test API connection for a provider"""
    keys = get_api_keys()

    result = {
        "provider": provider,
        "success": False,
        "message": "",
        "latency_ms": 0,
    }

    try:
        import time

        import requests

        start = time.time()

        if provider == "alpaca" and keys.alpaca.is_configured:
            headers = {
                "APCA-API-KEY-ID": keys.alpaca.api_key,
                "APCA-API-SECRET-KEY": keys.alpaca.secret_key,
            }
            response = requests.get(
                f"{keys.alpaca.base_url}/v2/account",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                result["success"] = True
                result["message"] = "Connected to Alpaca"
            else:
                result["message"] = f"HTTP {response.status_code}"

        elif provider == "tradier" and keys.tradier.is_configured:
            headers = {
                "Authorization": f"Bearer {keys.tradier.api_key}",
                "Accept": "application/json",
            }
            response = requests.get(
                f"{keys.tradier.base_url}/v1/user/profile",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                result["success"] = True
                result["message"] = "Connected to Tradier"
            else:
                result["message"] = f"HTTP {response.status_code}"

        elif provider == "finnhub" and keys.finnhub.is_configured:
            response = requests.get(
                f"{keys.finnhub.base_url}/quote",
                params={"symbol": "AAPL", "token": keys.finnhub.api_key},
                timeout=10
            )
            if response.status_code == 200:
                result["success"] = True
                result["message"] = "Connected to Finnhub"
            else:
                result["message"] = f"HTTP {response.status_code}"

        elif provider == "news_api" and keys.news_api.is_configured:
            response = requests.get(
                f"{keys.news_api.base_url}/top-headlines",
                params={"country": "us", "category": "business", "apiKey": keys.news_api.api_key},
                timeout=10
            )
            if response.status_code == 200:
                result["success"] = True
                result["message"] = "Connected to NewsAPI"
            else:
                result["message"] = f"HTTP {response.status_code}"

        else:
            result["message"] = "Provider not configured"

        result["latency_ms"] = int((time.time() - start) * 1000)

    except Exception as e:
        result["message"] = str(e)

    return result


# Initialize keys on module load
def _init_keys():
    """Initialize API keys on module load"""
    global _api_keys

    if not os.path.exists(_keys_path):
        _api_keys = _get_default_keys()
        save_api_keys(_api_keys)
    else:
        _api_keys = _load_api_keys()


# Auto-initialize
_init_keys()
