"""
Fast Headline Parsing for Trading
=================================
Extracts actionable information from headlines in real-time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Set
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class HeadlineAction(Enum):
    """Actionable event from headline."""
    # Price targets
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    PRICE_TARGET_RAISED = "pt_raised"
    PRICE_TARGET_CUT = "pt_cut"
    INITIATED = "initiated"
    
    # Earnings
    BEAT = "beat"
    MISS = "miss"
    GUIDANCE_RAISED = "guidance_raised"
    GUIDANCE_CUT = "guidance_cut"
    
    # Corporate actions
    ACQUISITION = "acquisition"
    MERGER = "merger"
    BUYBACK = "buyback"
    DIVIDEND = "dividend"
    SPLIT = "split"
    SPINOFF = "spinoff"
    
    # Management
    CEO_CHANGE = "ceo_change"
    CFO_CHANGE = "cfo_change"
    INSIDER_BUY = "insider_buy"
    INSIDER_SELL = "insider_sell"
    
    # Regulatory
    FDA_APPROVAL = "fda_approval"
    FDA_REJECTION = "fda_rejection"
    SEC_INVESTIGATION = "sec_investigation"
    LAWSUIT = "lawsuit"
    
    # Market
    IPO = "ipo"
    HALT = "halt"
    BANKRUPTCY = "bankruptcy"
    
    # Macro
    FED_HIKE = "fed_hike"
    FED_CUT = "fed_cut"
    FED_PAUSE = "fed_pause"
    
    UNKNOWN = "unknown"


@dataclass
class ParsedHeadline:
    """Result of headline parsing."""
    original: str
    timestamp: datetime
    
    # Extracted actions
    action: HeadlineAction
    action_confidence: float
    
    # Entities
    symbols: List[str]
    companies: List[str]
    people: List[str]
    
    # Numbers
    price_target: Optional[float] = None
    price_target_prev: Optional[float] = None
    eps: Optional[float] = None
    revenue: Optional[float] = None
    percentage: Optional[float] = None
    dollar_amount: Optional[float] = None
    
    # Analyst/source
    analyst_firm: Optional[str] = None
    rating: Optional[str] = None  # buy, hold, sell
    
    # Direction
    is_bullish: Optional[bool] = None
    sentiment_score: float = 0.0
    
    # Quality
    parse_quality: float = 0.0  # 0-1, how well we parsed it
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original": self.original,
            "action": self.action.value,
            "action_confidence": self.action_confidence,
            "symbols": self.symbols,
            "price_target": self.price_target,
            "analyst_firm": self.analyst_firm,
            "rating": self.rating,
            "is_bullish": self.is_bullish,
            "parse_quality": self.parse_quality,
        }


class HeadlineParser:
    """
    Fast parser for financial headlines.
    
    Optimized for:
    - Speed (sub-millisecond parsing)
    - Accuracy on common patterns
    - Symbol extraction
    - Price target extraction
    - Action classification
    """
    
    def __init__(self):
        # Symbol patterns
        self._symbol_pattern = re.compile(r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})(?=\s+(?:shares|stock|Inc|Corp|rises|falls|up|down|beats|misses))', re.IGNORECASE)
        
        # Price target pattern: "PT $XXX" or "price target $XXX"
        self._pt_pattern = re.compile(r'(?:PT|price\s+target|target)\s*(?:to|at|of|raised to|cut to|lowered to)?\s*\$?([\d,]+(?:\.\d+)?)', re.IGNORECASE)
        self._pt_from_pattern = re.compile(r'from\s+\$?([\d,]+(?:\.\d+)?)', re.IGNORECASE)
        
        # Percentage pattern
        self._pct_pattern = re.compile(r'([\d.]+)\s*%')
        
        # Dollar amount pattern
        self._dollar_pattern = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:B|billion|M|million|K|thousand)?', re.IGNORECASE)
        
        # EPS pattern
        self._eps_pattern = re.compile(r'EPS\s*(?:of)?\s*\$?([\d.]+)', re.IGNORECASE)
        
        # Known analyst firms
        self._analyst_firms = {
            "morgan stanley", "goldman sachs", "jpmorgan", "jp morgan",
            "bank of america", "bofa", "citi", "citigroup", "barclays",
            "ubs", "credit suisse", "deutsche bank", "hsbc", "wells fargo",
            "raymond james", "jefferies", "piper sandler", "cowen",
            "needham", "wedbush", "oppenheimer", "baird", "stifel",
            "bernstein", "rbc", "td cowen", "wolfe research", "keybanc",
            "mizuho", "btig", "truist", "evercore", "leerink",
        }
        
        # Action patterns with associated actions
        self._action_patterns = [
            # Analyst actions
            (r'\b(?:upgrade[ds]?)\b', HeadlineAction.UPGRADE),
            (r'\b(?:downgrade[ds]?)\b', HeadlineAction.DOWNGRADE),
            (r'\b(?:raise[ds]?|hike[ds]?|boost[ds]?)\s+(?:PT|price\s+target)', HeadlineAction.PRICE_TARGET_RAISED),
            (r'\b(?:cut[s]?|lower[s]?|reduce[ds]?|slash)', HeadlineAction.PRICE_TARGET_CUT),
            (r'\b(?:initiate[ds]?|start[s]?)\s+(?:coverage|at)', HeadlineAction.INITIATED),
            
            # Earnings
            (r'\b(?:beat[s]?|top[s]?|exceed[s]?)\s+(?:estimate|expectation|EPS)', HeadlineAction.BEAT),
            (r'\b(?:miss(?:es)?|fall[s]?\s+short|below)\s+(?:estimate|expectation)', HeadlineAction.MISS),
            (r'\b(?:raise[ds]?|boost[s]?|increase[ds]?)\s+(?:guidance|outlook|forecast)', HeadlineAction.GUIDANCE_RAISED),
            (r'\b(?:cut[s]?|lower[s]?|reduce[ds]?)\s+(?:guidance|outlook|forecast)', HeadlineAction.GUIDANCE_CUT),
            
            # Corporate
            (r'\b(?:acquir|acquisition|to\s+buy|purchase|takeover)', HeadlineAction.ACQUISITION),
            (r'\b(?:merger|merge[ds]?|combining)', HeadlineAction.MERGER),
            (r'\b(?:buyback|repurchase|share\s+repurchase)', HeadlineAction.BUYBACK),
            (r'\b(?:dividend|distribution)', HeadlineAction.DIVIDEND),
            (r'\b(?:split|stock\s+split)', HeadlineAction.SPLIT),
            (r'\b(?:spinoff|spin-off|spin\s+off)', HeadlineAction.SPINOFF),
            
            # Management
            (r'\b(?:CEO|chief\s+executive)\s+(?:step|resign|retire|leave|replace|appoint|name)', HeadlineAction.CEO_CHANGE),
            (r'\b(?:CFO|chief\s+financial)\s+(?:step|resign|retire|leave|replace|appoint|name)', HeadlineAction.CFO_CHANGE),
            (r'\b(?:insider|director|executive)\s+(?:buy|purchase|acquire)', HeadlineAction.INSIDER_BUY),
            (r'\b(?:insider|director|executive)\s+(?:sell|sold|dispose)', HeadlineAction.INSIDER_SELL),
            
            # Regulatory
            (r'\bFDA\s+(?:approv|clear|authorize)', HeadlineAction.FDA_APPROVAL),
            (r'\bFDA\s+(?:reject|decline|refuse|CRL)', HeadlineAction.FDA_REJECTION),
            (r'\bSEC\s+(?:investigat|probe|subpoena)', HeadlineAction.SEC_INVESTIGATION),
            (r'\b(?:lawsuit|sue[ds]?|litigation|legal\s+action)', HeadlineAction.LAWSUIT),
            
            # Market
            (r'\b(?:IPO|goes?\s+public|initial\s+public)', HeadlineAction.IPO),
            (r'\b(?:halt|halted|suspended)', HeadlineAction.HALT),
            (r'\b(?:bankrupt|chapter\s+11|insolvent)', HeadlineAction.BANKRUPTCY),
            
            # Fed
            (r'\bFed\s+(?:raise[ds]?|hike[ds]?|increase[ds]?)\s+(?:rate|interest)', HeadlineAction.FED_HIKE),
            (r'\bFed\s+(?:cut[s]?|lower[s]?|reduce[ds]?)\s+(?:rate|interest)', HeadlineAction.FED_CUT),
            (r'\bFed\s+(?:hold[s]?|pause[ds]?|unchanged)', HeadlineAction.FED_PAUSE),
        ]
        
        # Compile patterns
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), a) for p, a in self._action_patterns
        ]
        
        # Bullish/bearish indicators
        self._bullish_words = {"upgrade", "raised", "beat", "bullish", "buy", "outperform", "positive", "strong"}
        self._bearish_words = {"downgrade", "cut", "miss", "bearish", "sell", "underperform", "negative", "weak"}
        
    def parse(self, headline: str) -> ParsedHeadline:
        """
        Parse headline and extract structured information.
        
        Args:
            headline: Raw headline text
            
        Returns:
            ParsedHeadline with extracted data
        """
        result = ParsedHeadline(
            original=headline,
            timestamp=datetime.now(),
            action=HeadlineAction.UNKNOWN,
            action_confidence=0.0,
            symbols=[],
            companies=[],
            people=[],
        )
        
        headline_lower = headline.lower()
        
        # Extract symbols
        result.symbols = self._extract_symbols(headline)
        
        # Extract action
        result.action, result.action_confidence = self._extract_action(headline_lower)
        
        # Extract price target
        result.price_target = self._extract_price_target(headline)
        result.price_target_prev = self._extract_prev_price_target(headline)
        
        # Extract percentages
        result.percentage = self._extract_percentage(headline)
        
        # Extract dollar amounts
        result.dollar_amount = self._extract_dollar(headline)
        
        # Extract EPS
        result.eps = self._extract_eps(headline)
        
        # Extract analyst firm
        result.analyst_firm = self._extract_analyst(headline_lower)
        
        # Extract rating
        result.rating = self._extract_rating(headline_lower)
        
        # Determine direction
        result.is_bullish = self._determine_direction(headline_lower, result.action)
        
        # Calculate sentiment score
        result.sentiment_score = self._calculate_sentiment(headline_lower, result.is_bullish)
        
        # Calculate parse quality
        result.parse_quality = self._calculate_quality(result)
        
        return result
    
    def _extract_symbols(self, headline: str) -> List[str]:
        """Extract stock symbols from headline."""
        symbols = set()
        
        # Direct $SYMBOL mentions
        for match in re.finditer(r'\$([A-Z]{1,5})\b', headline):
            symbols.add(match.group(1))
            
        # Context-based extraction
        for match in self._symbol_pattern.finditer(headline):
            sym = match.group(1) or match.group(2)
            if sym:
                sym = sym.upper()
                # Filter common words
                if sym not in {"A", "I", "CEO", "CFO", "FDA", "SEC", "IPO", "EPS", "PT"}:
                    symbols.add(sym)
                    
        return list(symbols)
    
    def _extract_action(self, headline_lower: str) -> Tuple[HeadlineAction, float]:
        """Extract action from headline."""
        for pattern, action in self._compiled_patterns:
            if pattern.search(headline_lower):
                return action, 0.9
                
        return HeadlineAction.UNKNOWN, 0.0
    
    def _extract_price_target(self, headline: str) -> Optional[float]:
        """Extract price target."""
        match = self._pt_pattern.search(headline)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None
    
    def _extract_prev_price_target(self, headline: str) -> Optional[float]:
        """Extract previous price target (from $X)."""
        match = self._pt_from_pattern.search(headline)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None
    
    def _extract_percentage(self, headline: str) -> Optional[float]:
        """Extract percentage value."""
        match = self._pct_pattern.search(headline)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
    
    def _extract_dollar(self, headline: str) -> Optional[float]:
        """Extract dollar amount."""
        match = self._dollar_pattern.search(headline)
        if match:
            try:
                value = float(match.group(1).replace(",", ""))
                # Check for multiplier
                full_match = match.group(0).lower()
                if "b" in full_match or "billion" in full_match:
                    value *= 1_000_000_000
                elif "m" in full_match or "million" in full_match:
                    value *= 1_000_000
                elif "k" in full_match or "thousand" in full_match:
                    value *= 1_000
                return value
            except ValueError:
                pass
        return None
    
    def _extract_eps(self, headline: str) -> Optional[float]:
        """Extract EPS value."""
        match = self._eps_pattern.search(headline)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
    
    def _extract_analyst(self, headline_lower: str) -> Optional[str]:
        """Extract analyst firm name."""
        for firm in self._analyst_firms:
            if firm in headline_lower:
                return firm.title()
        return None
    
    def _extract_rating(self, headline_lower: str) -> Optional[str]:
        """Extract rating (buy/hold/sell)."""
        if any(w in headline_lower for w in ["buy", "outperform", "overweight"]):
            return "buy"
        elif any(w in headline_lower for w in ["sell", "underperform", "underweight"]):
            return "sell"
        elif any(w in headline_lower for w in ["hold", "neutral", "equal-weight", "market perform"]):
            return "hold"
        return None
    
    def _determine_direction(
        self,
        headline_lower: str,
        action: HeadlineAction,
    ) -> Optional[bool]:
        """Determine if headline is bullish or bearish."""
        # Action-based
        bullish_actions = {
            HeadlineAction.UPGRADE,
            HeadlineAction.PRICE_TARGET_RAISED,
            HeadlineAction.BEAT,
            HeadlineAction.GUIDANCE_RAISED,
            HeadlineAction.BUYBACK,
            HeadlineAction.DIVIDEND,
            HeadlineAction.FDA_APPROVAL,
            HeadlineAction.INSIDER_BUY,
        }
        
        bearish_actions = {
            HeadlineAction.DOWNGRADE,
            HeadlineAction.PRICE_TARGET_CUT,
            HeadlineAction.MISS,
            HeadlineAction.GUIDANCE_CUT,
            HeadlineAction.FDA_REJECTION,
            HeadlineAction.LAWSUIT,
            HeadlineAction.INSIDER_SELL,
            HeadlineAction.BANKRUPTCY,
        }
        
        if action in bullish_actions:
            return True
        elif action in bearish_actions:
            return False
            
        # Word-based
        bullish_count = sum(1 for w in self._bullish_words if w in headline_lower)
        bearish_count = sum(1 for w in self._bearish_words if w in headline_lower)
        
        if bullish_count > bearish_count:
            return True
        elif bearish_count > bullish_count:
            return False
            
        return None
    
    def _calculate_sentiment(
        self,
        headline_lower: str,
        is_bullish: Optional[bool],
    ) -> float:
        """Calculate sentiment score (-1 to 1)."""
        if is_bullish is True:
            base = 0.5
        elif is_bullish is False:
            base = -0.5
        else:
            base = 0.0
            
        # Adjust based on word count
        bullish_count = sum(1 for w in self._bullish_words if w in headline_lower)
        bearish_count = sum(1 for w in self._bearish_words if w in headline_lower)
        
        adjustment = (bullish_count - bearish_count) * 0.1
        
        return max(-1, min(1, base + adjustment))
    
    def _calculate_quality(self, result: ParsedHeadline) -> float:
        """Calculate parse quality score."""
        quality = 0.0
        
        # Has symbols
        if result.symbols:
            quality += 0.3
            
        # Has action
        if result.action != HeadlineAction.UNKNOWN:
            quality += 0.3
            
        # Has numbers
        if result.price_target or result.percentage or result.eps:
            quality += 0.2
            
        # Has direction
        if result.is_bullish is not None:
            quality += 0.2
            
        return quality
    
    def batch_parse(self, headlines: List[str]) -> List[ParsedHeadline]:
        """Parse multiple headlines."""
        return [self.parse(h) for h in headlines]
    
    def filter_actionable(
        self,
        parsed: List[ParsedHeadline],
        min_quality: float = 0.5,
    ) -> List[ParsedHeadline]:
        """Filter to only actionable headlines."""
        return [
            p for p in parsed
            if p.parse_quality >= min_quality
            and p.action != HeadlineAction.UNKNOWN
            and p.symbols
        ]
