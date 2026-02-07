"""
QUANT INDUSTRY V1 - Environment Configuration
==============================================
Centralized environment loading. Import this FIRST in any module
that needs environment variables.
"""

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

# Load .env file ONCE at module import
_env_loaded = False

def _load_env():
    """Load environment variables from .env file."""
    global _env_loaded
    if _env_loaded:
        return
    
    try:
        from dotenv import load_dotenv
        
        # Try multiple paths
        paths = [
            Path(__file__).parent.parent.parent / '.env',  # QUANT_INDUSTRY_V1/.env
            Path(__file__).parent.parent.parent.parent / '.env',  # clawd/.env
            Path.cwd() / '.env',
            Path('C:/QUANT_INDUSTRY_V1/.env'),  # Explicit path as fallback
        ]
        
        for env_path in paths:
            if env_path.exists():
                load_dotenv(env_path, override=True)
                print(f"[OK] Loaded environment from: {env_path}")
                break
        
        _env_loaded = True
    except ImportError:
        print("[WARN] python-dotenv not installed, using system environment only")
        _env_loaded = True

# Load immediately on import
_load_env()


_config_instance = None

def get_config():
    """Get configuration object (singleton without lru_cache for proper env loading)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


class Config:
    """Application configuration from environment."""
    
    def __init__(self):
        # Data Providers
        self.ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY', '')
        self.ALPACA_API_SECRET = os.environ.get('ALPACA_API_SECRET', '') or os.environ.get('ALPACA_SECRET_KEY', '')
        self.POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', '')

        # Data source preference: "alpaca", "polygon", "yfinance" (default)
        # When set to "yfinance", no API key is required for market data
        self.DATA_SOURCE = os.environ.get('DATA_SOURCE', 'yfinance')

        # Database
        self.DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./data/quant.db')
        self.REDIS_URL = os.environ.get('REDIS_URL', '')

        # API Settings
        self.API_HOST = os.environ.get('API_HOST', '0.0.0.0')
        self.API_PORT = int(os.environ.get('API_PORT', 8000))
        self.DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

        # Alerts
        self.DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '')
        self.TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
        
    @property
    def alpaca_configured(self) -> bool:
        return bool(self.ALPACA_API_KEY and self.ALPACA_API_SECRET)
    
    @property
    def polygon_configured(self) -> bool:
        return bool(self.POLYGON_API_KEY)
    
    @property
    def redis_configured(self) -> bool:
        return bool(self.REDIS_URL)
    
    def get_data_mode(self) -> str:
        """Determine which data source to use.

        Priority:
        1. Explicit DATA_SOURCE env var (if the required keys are available)
        2. Alpaca (if keys configured)
        3. Polygon (if key configured)
        4. yfinance (free, no API key required - default fallback)
        """
        # If user explicitly chose a source, respect it when keys are available
        if self.DATA_SOURCE == "alpaca" and self.alpaca_configured:
            return "alpaca"
        if self.DATA_SOURCE == "polygon" and self.polygon_configured:
            return "polygon"
        if self.DATA_SOURCE == "yfinance":
            return "yfinance"

        # Auto-detect based on available keys
        if self.alpaca_configured:
            return "alpaca"
        if self.polygon_configured:
            return "polygon"

        # Default to yfinance (free, no API key needed)
        return "yfinance"


# Convenience access
config = get_config()
