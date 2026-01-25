"""
RESEARCH SERVICE
================

Provides research data (13F holdings, SEC filings, dark pool, earnings).
Returns UNAVAILABLE status instead of fake data when real sources aren't configured.

Real data sources (to be connected):
- SEC EDGAR API for 13F and SEC filings
- FINRA ATS data for dark pool
- Alpha Vantage / FMP for earnings

This replaces the random data generation with proper unavailability signals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ResearchDataStatus(Enum):
    """Status of research data availability"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass
class ResearchResponse:
    """Standard response wrapper for research data"""
    status: ResearchDataStatus
    data: Optional[Dict] = None
    message: str = ""
    source: str = "none"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        result = {
            "status": self.status.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.data:
            result["data"] = self.data
        if self.message:
            result["message"] = self.message
        return result


class ResearchService:
    """
    Research data service.

    Currently returns UNAVAILABLE for all endpoints since real data sources
    are not yet connected. This is the correct behavior per data integrity rules.
    """

    def __init__(self):
        self.sec_edgar_api_key: Optional[str] = None
        self.finra_api_key: Optional[str] = None
        self.earnings_api_key: Optional[str] = None
        self._initialized = False

    def initialize(self, config: Dict = None):
        """Initialize with API keys if available"""
        config = config or {}
        self.sec_edgar_api_key = config.get("sec_edgar_api_key")
        self.finra_api_key = config.get("finra_api_key")
        self.earnings_api_key = config.get("earnings_api_key")
        self._initialized = True
        logger.info("ResearchService initialized")

    def get_13f_holdings(self, symbol: str) -> ResearchResponse:
        """
        Get 13F institutional holdings for a symbol.

        Real implementation would connect to SEC EDGAR API.
        Currently returns UNAVAILABLE status.
        """
        symbol = symbol.upper()

        if not self.sec_edgar_api_key:
            return ResearchResponse(
                status=ResearchDataStatus.UNAVAILABLE,
                message="13F data requires SEC EDGAR API connection. Configure sec_edgar_api_key to enable.",
                source="none",
                data={
                    "symbol": symbol,
                    "holders": [],
                    "total_institutional_ownership": None,
                    "quarterly_change": None,
                    "_note": "Real institutional holdings data not available. Connect SEC EDGAR API for live data."
                }
            )

        # TODO: Implement real SEC EDGAR API call
        # https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}&type=13F
        return ResearchResponse(
            status=ResearchDataStatus.UNAVAILABLE,
            message="SEC EDGAR API integration not yet implemented",
            source="sec_edgar"
        )

    def get_sec_filings(self, symbol: str, limit: int = 20) -> ResearchResponse:
        """
        Get SEC filings for a symbol.

        Real implementation would connect to SEC EDGAR API.
        Currently returns UNAVAILABLE status.
        """
        symbol = symbol.upper()

        if not self.sec_edgar_api_key:
            return ResearchResponse(
                status=ResearchDataStatus.UNAVAILABLE,
                message="SEC filings require SEC EDGAR API connection. Configure sec_edgar_api_key to enable.",
                source="none",
                data={
                    "symbol": symbol,
                    "filings": [],
                    "_note": "Real SEC filing data not available. Connect SEC EDGAR API for live data.",
                    "_link": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}"
                }
            )

        # TODO: Implement real SEC EDGAR API call
        return ResearchResponse(
            status=ResearchDataStatus.UNAVAILABLE,
            message="SEC EDGAR API integration not yet implemented",
            source="sec_edgar"
        )

    def get_dark_pool_data(self, symbol: str) -> ResearchResponse:
        """
        Get dark pool / ATS activity for a symbol.

        Real implementation would connect to FINRA ATS data.
        Currently returns UNAVAILABLE status.
        """
        symbol = symbol.upper()

        if not self.finra_api_key:
            return ResearchResponse(
                status=ResearchDataStatus.UNAVAILABLE,
                message="Dark pool data requires FINRA ATS API connection. Configure finra_api_key to enable.",
                source="none",
                data={
                    "symbol": symbol,
                    "dark_pool_volume": None,
                    "lit_volume": None,
                    "dark_pool_pct": None,
                    "activity_by_venue": [],
                    "_note": "Real dark pool data not available. Connect FINRA ATS API for live data.",
                    "_link": "https://www.finra.org/finra-data/browse-catalog/equity-short-interest/api"
                }
            )

        # TODO: Implement real FINRA ATS API call
        return ResearchResponse(
            status=ResearchDataStatus.UNAVAILABLE,
            message="FINRA ATS API integration not yet implemented",
            source="finra"
        )

    def get_earnings(self, symbol: str = None, symbols: List[str] = None) -> ResearchResponse:
        """
        Get earnings data for symbol(s).

        Real implementation would connect to earnings API (Alpha Vantage, FMP, etc.).
        Currently returns UNAVAILABLE status.
        """
        if symbol:
            symbols = [symbol.upper()]
        elif symbols:
            symbols = [s.upper() for s in symbols]
        else:
            symbols = []

        if not self.earnings_api_key:
            return ResearchResponse(
                status=ResearchDataStatus.UNAVAILABLE,
                message="Earnings data requires API connection (Alpha Vantage or FMP). Configure earnings_api_key to enable.",
                source="none",
                data={
                    "symbols": symbols,
                    "calendar": [],
                    "_note": "Real earnings data not available. Connect earnings API for live data."
                }
            )

        # TODO: Implement real earnings API call
        return ResearchResponse(
            status=ResearchDataStatus.UNAVAILABLE,
            message="Earnings API integration not yet implemented",
            source="earnings_api"
        )


# Singleton instance
_research_service: Optional[ResearchService] = None


def get_research_service() -> ResearchService:
    """Get or create the research service singleton"""
    global _research_service
    if _research_service is None:
        _research_service = ResearchService()
        _research_service.initialize()
    return _research_service
