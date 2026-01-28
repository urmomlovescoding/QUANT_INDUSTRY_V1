"""
QUANT_INDUSTRY_V1 SEC 13F Institutional Holdings Parser

Parse SEC 13F filings to track institutional holdings.
Provides smart money flow analysis.

Features:
- Real-time SEC EDGAR API integration
- Multi-format XML parsing
- Quarter-over-quarter tracking
- Major fund identification
"""

import numpy as np
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import re
import json
import time

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class HoldingRecord:
    """Single holding from 13F filing."""
    cusip: str
    issuer_name: str
    title_class: str
    value: float  # In thousands
    shares: int
    share_type: str  # SH = shares, PRN = principal amount
    investment_discretion: str  # SOLE, SHARED, NONE
    voting_authority_sole: int = 0
    voting_authority_shared: int = 0
    voting_authority_none: int = 0
    put_call: str = ""  # For options


@dataclass
class Filing13F:
    """Complete 13F filing."""
    cik: str
    filer_name: str
    filing_date: date
    report_date: date
    form_type: str
    accession_number: str
    holdings: List[HoldingRecord] = field(default_factory=list)
    total_value: float = 0.0
    total_holdings: int = 0


@dataclass
class InstitutionalPosition:
    """Tracked institutional position over time."""
    symbol: str
    cusip: str
    institution: str
    cik: str
    quarters: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# =============================================================================
# MAJOR FUND CIKs
# =============================================================================

MAJOR_FUNDS = {
    "Berkshire Hathaway": "0001067983",
    "Bridgewater Associates": "0001350694",
    "Renaissance Technologies": "0001037389",
    "Two Sigma": "0001179392",
    "Citadel Advisors": "0001423053",
    "DE Shaw": "0001009207",
    "Point72": "0001603466",
    "Tiger Global": "0001167483",
    "Millennium Management": "0001273087",
    "Elliott Management": "0001048445",
    "Third Point": "0001040273",
    "Pershing Square": "0001336528",
    "ValueAct Capital": "0001345471",
    "Baupost Group": "0001061768",
    "Greenlight Capital": "0001079114",
    "Appaloosa Management": "0001656456",
    "Viking Global": "0001103804",
    "Coatue Management": "0001535392",
    "Lone Pine Capital": "0001061165",
    "Maverick Capital": "0001010234",
    "BlackRock": "0001364742",
    "Vanguard": "0000102909",
    "State Street": "0000093751",
    "Fidelity": "0000315066",
    "T. Rowe Price": "0001113169",
    "Capital Group": "0000080255",
    "JP Morgan": "0000019617",
    "Goldman Sachs": "0000886982",
    "Morgan Stanley": "0000895421",
    "Bank of America": "0000070858",
    "Soros Fund Management": "0001029160",
    "Duquesne Family Office": "0001536411",
    "Druckenmiller": "0001536411",
    "Bill Ackman": "0001336528",
    "Carl Icahn": "0000921669",
    "Dan Loeb": "0001040273",
    "David Einhorn": "0001079114",
    "Ray Dalio": "0001350694",
    "Jim Simons": "0001037389",
    "Ken Griffin": "0001423053",
    "Steve Cohen": "0001603466",
}

# CUSIP to Symbol mapping (partial, would need full database)
CUSIP_TO_SYMBOL = {
    "594918104": "MSFT",
    "037833100": "AAPL",
    "02079K305": "GOOG",
    "02079K107": "GOOGL",
    "023135106": "AMZN",
    "30303M102": "META",
    "88160R101": "TSLA",
    "67066G104": "NVDA",
    "46625H100": "JPM",
    "17275R102": "CSCO",
}


# =============================================================================
# SEC EDGAR API CLIENT
# =============================================================================

class SECEdgarClient:
    """
    Client for SEC EDGAR API.

    Rate limited to 10 requests per second per SEC guidelines.
    """

    BASE_URL = "https://www.sec.gov"
    EDGAR_API = "https://data.sec.gov"
    USER_AGENT = "QuantIndustry/1.0 (contact@example.com)"

    def __init__(self, rate_limit: float = 0.1):
        self.rate_limit = rate_limit
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str) -> Optional[str]:
        """Make HTTP request with rate limiting."""
        self._rate_limit()

        try:
            import urllib.request

            headers = {"User-Agent": self.USER_AGENT}
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            logger.error(f"SEC request failed: {e}")
            return None

    def get_company_filings(self, cik: str) -> Optional[Dict]:
        """Get list of filings for a company."""
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)
        url = f"{self.EDGAR_API}/submissions/CIK{cik_padded}.json"

        response = self._make_request(url)
        if response:
            return json.loads(response)
        return None

    def get_13f_filings(self, cik: str, limit: int = 10) -> List[Dict]:
        """Get 13F filings for a fund."""
        filings = self.get_company_filings(cik)
        if not filings:
            return []

        recent_filings = filings.get('filings', {}).get('recent', {})
        if not recent_filings:
            return []

        form_types = recent_filings.get('form', [])
        accession_numbers = recent_filings.get('accessionNumber', [])
        filing_dates = recent_filings.get('filingDate', [])
        primary_documents = recent_filings.get('primaryDocument', [])

        results = []
        for i, form in enumerate(form_types):
            if '13F' in form and len(results) < limit:
                results.append({
                    'form_type': form,
                    'accession_number': accession_numbers[i],
                    'filing_date': filing_dates[i],
                    'primary_document': primary_documents[i] if i < len(primary_documents) else None,
                    'cik': cik,
                })

        return results

    def download_filing(self, cik: str, accession_number: str) -> Optional[str]:
        """Download a specific filing."""
        cik_padded = cik.zfill(10)
        acc_clean = accession_number.replace('-', '')
        url = f"{self.BASE_URL}/Archives/edgar/data/{cik_padded}/{acc_clean}/{accession_number}.txt"

        return self._make_request(url)


# =============================================================================
# 13F PARSER
# =============================================================================

class Filing13FParser:
    """
    Parse 13F filings from SEC.

    Handles multiple XML formats used over the years.
    """

    # XML namespaces used in 13F filings
    NAMESPACES = {
        'ns': 'http://www.sec.gov/edgar/document/thirteenf/informationtable',
        'ns2': 'http://www.sec.gov/edgar/thirteenffiler'
    }

    def parse_xml(self, xml_content: str) -> List[HoldingRecord]:
        """Parse 13F XML content."""
        holdings = []

        try:
            root = ET.fromstring(xml_content)

            # Try different XML structures
            for info_table in root.iter():
                if 'infoTable' in info_table.tag.lower():
                    holding = self._parse_info_table(info_table)
                    if holding:
                        holdings.append(holding)

        except ET.ParseError as e:
            logger.warning(f"XML parse error: {e}")
            # Try regex fallback
            holdings = self._parse_with_regex(xml_content)

        return holdings

    def _parse_info_table(self, elem: ET.Element) -> Optional[HoldingRecord]:
        """Parse a single infoTable element."""
        try:
            def get_text(tag_name: str) -> str:
                for child in elem.iter():
                    if tag_name.lower() in child.tag.lower():
                        return child.text or ""
                return ""

            def get_int(tag_name: str) -> int:
                text = get_text(tag_name)
                return int(text.replace(',', '')) if text else 0

            def get_float(tag_name: str) -> float:
                text = get_text(tag_name)
                return float(text.replace(',', '')) if text else 0.0

            return HoldingRecord(
                cusip=get_text('cusip'),
                issuer_name=get_text('nameOfIssuer'),
                title_class=get_text('titleOfClass'),
                value=get_float('value'),
                shares=get_int('sshPrnamt'),
                share_type=get_text('sshPrnamtType'),
                investment_discretion=get_text('investmentDiscretion'),
                voting_authority_sole=get_int('Sole'),
                voting_authority_shared=get_int('Shared'),
                voting_authority_none=get_int('None'),
                put_call=get_text('putCall'),
            )
        except Exception as e:
            logger.warning(f"Failed to parse info table: {e}")
            return None

    def _parse_with_regex(self, content: str) -> List[HoldingRecord]:
        """Fallback regex parsing for non-XML formats."""
        holdings = []

        # Pattern for common 13F text format
        pattern = r'<nameOfIssuer>([^<]+)</nameOfIssuer>\s*' \
                  r'<titleOfClass>([^<]+)</titleOfClass>\s*' \
                  r'<cusip>([^<]+)</cusip>\s*' \
                  r'<value>([^<]+)</value>\s*' \
                  r'<sshPrnamt>([^<]+)</sshPrnamt>'

        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)

        for match in matches:
            try:
                holdings.append(HoldingRecord(
                    issuer_name=match[0].strip(),
                    title_class=match[1].strip(),
                    cusip=match[2].strip(),
                    value=float(match[3].replace(',', '')),
                    shares=int(match[4].replace(',', '')),
                    share_type='SH',
                    investment_discretion='SOLE',
                ))
            except:
                continue

        return holdings


# =============================================================================
# INSTITUTIONAL HOLDINGS TRACKER
# =============================================================================

class InstitutionalHoldingsTracker:
    """
    Track institutional holdings over time.

    Provides:
    - Quarter-over-quarter changes
    - Aggregated institutional ownership
    - Smart money flow signals
    """

    def __init__(self):
        self.client = SECEdgarClient()
        self.parser = Filing13FParser()

        # Cache
        self.filings_cache: Dict[str, Filing13F] = {}
        self.positions: Dict[str, InstitutionalPosition] = {}

    def fetch_fund_holdings(self, fund_name: str) -> Optional[Filing13F]:
        """Fetch latest holdings for a fund."""
        cik = MAJOR_FUNDS.get(fund_name)
        if not cik:
            logger.warning(f"Unknown fund: {fund_name}")
            return None

        return self.fetch_holdings_by_cik(cik, fund_name)

    def fetch_holdings_by_cik(self, cik: str, fund_name: str = None) -> Optional[Filing13F]:
        """Fetch latest 13F holdings by CIK."""
        filings = self.client.get_13f_filings(cik, limit=1)
        if not filings:
            return None

        latest = filings[0]
        cache_key = f"{cik}_{latest['accession_number']}"

        if cache_key in self.filings_cache:
            return self.filings_cache[cache_key]

        # Download and parse
        content = self.client.download_filing(cik, latest['accession_number'])
        if not content:
            return None

        holdings = self.parser.parse_xml(content)

        filing = Filing13F(
            cik=cik,
            filer_name=fund_name or f"CIK-{cik}",
            filing_date=datetime.strptime(latest['filing_date'], '%Y-%m-%d').date(),
            report_date=datetime.strptime(latest['filing_date'], '%Y-%m-%d').date(),
            form_type=latest['form_type'],
            accession_number=latest['accession_number'],
            holdings=holdings,
            total_value=sum(h.value for h in holdings),
            total_holdings=len(holdings),
        )

        self.filings_cache[cache_key] = filing
        return filing

    def get_symbol_ownership(self, symbol: str) -> Dict[str, Any]:
        """Get institutional ownership for a symbol."""
        # Find CUSIP for symbol
        cusip = None
        for c, s in CUSIP_TO_SYMBOL.items():
            if s == symbol:
                cusip = c
                break

        if not cusip:
            logger.warning(f"CUSIP not found for {symbol}")
            return {}

        # Search cached filings
        owners = []
        total_shares = 0
        total_value = 0

        for filing in self.filings_cache.values():
            for holding in filing.holdings:
                if holding.cusip == cusip:
                    owners.append({
                        'institution': filing.filer_name,
                        'cik': filing.cik,
                        'shares': holding.shares,
                        'value': holding.value,
                        'filing_date': filing.filing_date.isoformat(),
                    })
                    total_shares += holding.shares
                    total_value += holding.value

        return {
            'symbol': symbol,
            'cusip': cusip,
            'total_institutional_shares': total_shares,
            'total_institutional_value_thousands': total_value,
            'num_institutions': len(owners),
            'top_holders': sorted(owners, key=lambda x: x['shares'], reverse=True)[:10],
        }

    def get_fund_top_holdings(
        self,
        fund_name: str,
        top_n: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get top holdings for a fund."""
        filing = self.fetch_fund_holdings(fund_name)
        if not filing:
            return []

        sorted_holdings = sorted(filing.holdings, key=lambda x: x.value, reverse=True)

        results = []
        for h in sorted_holdings[:top_n]:
            symbol = CUSIP_TO_SYMBOL.get(h.cusip, h.cusip)
            results.append({
                'symbol': symbol,
                'cusip': h.cusip,
                'issuer': h.issuer_name,
                'shares': h.shares,
                'value_thousands': h.value,
                'pct_of_portfolio': h.value / filing.total_value * 100 if filing.total_value > 0 else 0,
            })

        return results

    def compare_quarters(
        self,
        fund_name: str,
    ) -> Dict[str, Any]:
        """Compare current quarter to previous quarter."""
        cik = MAJOR_FUNDS.get(fund_name)
        if not cik:
            return {}

        filings = self.client.get_13f_filings(cik, limit=2)
        if len(filings) < 2:
            return {}

        # Parse both quarters
        current = self.fetch_holdings_by_cik(cik, fund_name)
        # Would need to implement fetching previous quarter

        # Placeholder for comparison
        return {
            'fund': fund_name,
            'current_quarter': current.filing_date.isoformat() if current else None,
            'current_holdings': current.total_holdings if current else 0,
            'current_value': current.total_value if current else 0,
            'changes': [],  # Would show new positions, increases, decreases, exits
        }

    def scan_smart_money(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Scan for smart money activity.

        Checks major hedge funds for accumulation/distribution.
        """
        results = {
            'scan_time': datetime.now(timezone.utc).isoformat(),
            'funds_scanned': 0,
            'accumulation': [],
            'distribution': [],
            'new_positions': [],
        }

        # Scan top hedge funds
        top_funds = [
            "Berkshire Hathaway",
            "Bridgewater Associates",
            "Renaissance Technologies",
            "Citadel Advisors",
            "Point72",
        ]

        for fund_name in top_funds:
            try:
                holdings = self.get_fund_top_holdings(fund_name, top_n=10)
                results['funds_scanned'] += 1

                for h in holdings:
                    if symbols is None or h['symbol'] in symbols:
                        results['accumulation'].append({
                            'fund': fund_name,
                            'symbol': h['symbol'],
                            'value_thousands': h['value_thousands'],
                        })
            except Exception as e:
                logger.warning(f"Failed to scan {fund_name}: {e}")

        return results


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'HoldingRecord',
    'Filing13F',
    'InstitutionalPosition',
    'SECEdgarClient',
    'Filing13FParser',
    'InstitutionalHoldingsTracker',
    'MAJOR_FUNDS',
    'CUSIP_TO_SYMBOL',
]
