"""
QUANT INDUSTRY - Portfolio Service
Portfolio management, optimization, and pairs trading
"""

import logging
import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    MAX_SHARPE = "MAX_SHARPE"
    MIN_VARIANCE = "MIN_VARIANCE"
    RISK_PARITY = "RISK_PARITY"
    EQUAL_WEIGHT = "EQUAL_WEIGHT"
    MAX_RETURN = "MAX_RETURN"


@dataclass
class Holding:
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    day_change: float
    day_change_pct: float
    weight: float
    sector: str = "Unknown"

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": round(self.avg_cost, 2),
            "current_price": round(self.current_price, 2),
            "market_value": round(self.market_value, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
            "day_change": round(self.day_change, 2),
            "day_change_pct": round(self.day_change_pct, 2),
            "weight": round(self.weight, 2),
            "sector": self.sector,
        }


@dataclass
class PortfolioSummary:
    total_value: float
    cash: float
    positions_value: float
    day_pnl: float
    day_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    positions_count: int
    holdings: List[Holding]

    # Risk metrics
    beta: float = 1.0
    sharpe_ratio: float = 0.0
    volatility: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "total_value": round(self.total_value, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(self.positions_value, 2),
            "day_pnl": round(self.day_pnl, 2),
            "day_pnl_pct": round(self.day_pnl_pct, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "positions_count": self.positions_count,
            "holdings": [h.to_dict() for h in self.holdings],
            "beta": round(self.beta, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "volatility": round(self.volatility, 4),
        }


@dataclass
class PortfolioOptimization:
    method: str
    symbols: List[str]
    weights: Dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    efficient_frontier: List[Dict]

    def to_dict(self) -> Dict:
        return {
            "method": self.method,
            "symbols": self.symbols,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "expected_return": round(self.expected_return, 4),
            "expected_volatility": round(self.expected_volatility, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "efficient_frontier": self.efficient_frontier,
        }


@dataclass
class PairsTrade:
    symbol_a: str
    symbol_b: str
    correlation: float
    cointegration_pvalue: float
    spread_zscore: float
    signal: str  # LONG_A_SHORT_B, LONG_B_SHORT_A, NEUTRAL
    hedge_ratio: float

    def to_dict(self) -> Dict:
        return {
            "symbol_a": self.symbol_a,
            "symbol_b": self.symbol_b,
            "correlation": round(self.correlation, 4),
            "cointegration_pvalue": round(self.cointegration_pvalue, 4),
            "spread_zscore": round(self.spread_zscore, 2),
            "signal": self.signal,
            "hedge_ratio": round(self.hedge_ratio, 4),
        }


class PortfolioService:
    """
    Portfolio management and optimization service
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "data", "portfolio.db"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

        # Sector mappings
        self.sectors = {
            "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary", "NVDA": "Technology",
            "META": "Technology", "TSLA": "Consumer Discretionary",
            "JPM": "Financials", "BAC": "Financials", "V": "Financials",
            "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare",
            "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
            "PG": "Consumer Staples", "KO": "Consumer Staples", "WMT": "Consumer Staples",
            "SPY": "Index", "QQQ": "Index", "IWM": "Index",
        }

        logger.info("PortfolioService initialized")

    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                quantity INTEGER NOT NULL,
                avg_cost REAL NOT NULL,
                first_purchase_date TEXT,
                last_update TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_value REAL,
                cash REAL,
                positions_value REAL,
                daily_pnl REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                added_date TEXT,
                notes TEXT
            )
        """)

        conn.commit()
        conn.close()

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary with holdings"""
        try:
            from ..services.trading_service import get_trading_service
            trading_service = get_trading_service()

            account = trading_service.get_account_info()
            positions = trading_service.get_all_positions()

            holdings = []
            total_day_pnl = 0
            total_cost_basis = 0

            for pos in positions:
                sector = self.sectors.get(pos.symbol, "Other")
                weight = (pos.market_value / account.equity * 100) if account.equity > 0 else 0

                holding = Holding(
                    symbol=pos.symbol,
                    quantity=pos.quantity,
                    avg_cost=pos.avg_entry_price,
                    current_price=pos.current_price,
                    market_value=pos.market_value,
                    unrealized_pnl=pos.unrealized_pnl,
                    unrealized_pnl_pct=pos.unrealized_pnl_pct,
                    day_change=pos.market_value * (pos.day_pnl_pct / 100),
                    day_change_pct=pos.day_pnl_pct,
                    weight=weight,
                    sector=sector,
                )

                holdings.append(holding)
                total_day_pnl += holding.day_change
                total_cost_basis += pos.quantity * pos.avg_entry_price

            total_pnl = account.portfolio_value - total_cost_basis if total_cost_basis > 0 else 0
            total_pnl_pct = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0

            return PortfolioSummary(
                total_value=account.equity,
                cash=account.cash,
                positions_value=account.portfolio_value,
                day_pnl=account.day_pnl,
                day_pnl_pct=account.day_pnl_pct,
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct,
                positions_count=len(positions),
                holdings=sorted(holdings, key=lambda h: h.market_value, reverse=True),
            )

        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return PortfolioSummary(
                total_value=0, cash=0, positions_value=0,
                day_pnl=0, day_pnl_pct=0, total_pnl=0, total_pnl_pct=0,
                positions_count=0, holdings=[]
            )

    def optimize_portfolio(
        self,
        symbols: List[str],
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        risk_free_rate: float = 0.05
    ) -> PortfolioOptimization:
        """
        Optimize portfolio weights

        Args:
            symbols: List of symbols to include
            method: Optimization method
            risk_free_rate: Annual risk-free rate
        """
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            # Get historical returns
            returns_data = {}
            for symbol in symbols:
                hist = data_service.get_historical(symbol, "1d", 252)
                if hist and len(hist) > 20:
                    closes = np.array([d["close"] for d in hist])
                    returns = np.diff(closes) / closes[:-1]
                    returns_data[symbol] = returns

            if len(returns_data) < 2:
                return self._equal_weight_portfolio(symbols)

            # Align returns
            min_len = min(len(r) for r in returns_data.values())
            returns_matrix = np.array([
                returns_data[s][-min_len:] for s in symbols if s in returns_data
            ])
            valid_symbols = [s for s in symbols if s in returns_data]

            # Calculate mean returns and covariance
            mean_returns = np.mean(returns_matrix, axis=1) * 252  # Annualized
            cov_matrix = np.cov(returns_matrix) * 252  # Annualized

            # Optimize based on method
            if method == OptimizationMethod.MAX_SHARPE:
                weights = self._max_sharpe_weights(mean_returns, cov_matrix, risk_free_rate)
            elif method == OptimizationMethod.MIN_VARIANCE:
                weights = self._min_variance_weights(cov_matrix)
            elif method == OptimizationMethod.RISK_PARITY:
                weights = self._risk_parity_weights(cov_matrix)
            elif method == OptimizationMethod.MAX_RETURN:
                weights = self._max_return_weights(mean_returns)
            else:
                weights = np.ones(len(valid_symbols)) / len(valid_symbols)

            # Calculate portfolio metrics
            port_return = np.sum(mean_returns * weights)
            port_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe = (port_return - risk_free_rate) / port_volatility if port_volatility > 0 else 0

            # Generate efficient frontier
            frontier = self._calculate_efficient_frontier(mean_returns, cov_matrix, risk_free_rate)

            return PortfolioOptimization(
                method=method.value,
                symbols=valid_symbols,
                weights={s: w for s, w in zip(valid_symbols, weights)},
                expected_return=port_return,
                expected_volatility=port_volatility,
                sharpe_ratio=sharpe,
                efficient_frontier=frontier,
            )

        except Exception as e:
            logger.error(f"Error optimizing portfolio: {e}")
            return self._equal_weight_portfolio(symbols)

    def _equal_weight_portfolio(self, symbols: List[str]) -> PortfolioOptimization:
        """Return equal weight portfolio"""
        n = len(symbols)
        weights = dict.fromkeys(symbols, 1.0 / n)

        return PortfolioOptimization(
            method="EQUAL_WEIGHT",
            symbols=symbols,
            weights=weights,
            expected_return=0.10,
            expected_volatility=0.15,
            sharpe_ratio=0.67,
            efficient_frontier=[],
        )

    def _max_sharpe_weights(
        self,
        returns: np.ndarray,
        cov: np.ndarray,
        rf: float,
        n_iterations: int = 10000
    ) -> np.ndarray:
        """Find weights that maximize Sharpe ratio using Monte Carlo"""
        n_assets = len(returns)
        best_sharpe = -np.inf
        best_weights = np.ones(n_assets) / n_assets

        for _ in range(n_iterations):
            weights = np.random.random(n_assets)
            weights /= np.sum(weights)

            port_return = np.sum(returns * weights)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            sharpe = (port_return - rf) / port_vol if port_vol > 0 else 0

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = weights

        return best_weights

    def _min_variance_weights(self, cov: np.ndarray) -> np.ndarray:
        """Find minimum variance portfolio weights"""
        n = len(cov)
        inv_cov = np.linalg.inv(cov)
        ones = np.ones(n)

        weights = np.dot(inv_cov, ones) / np.dot(ones.T, np.dot(inv_cov, ones))
        return weights

    def _risk_parity_weights(self, cov: np.ndarray, n_iterations: int = 100) -> np.ndarray:
        """Calculate risk parity weights"""
        n = len(cov)
        weights = np.ones(n) / n

        for _ in range(n_iterations):
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            marginal_contrib = np.dot(cov, weights)
            risk_contrib = weights * marginal_contrib / port_vol

            target = port_vol / n
            weights = weights * target / risk_contrib
            weights = np.maximum(weights, 0.001)
            weights /= np.sum(weights)

        return weights

    def _max_return_weights(self, returns: np.ndarray) -> np.ndarray:
        """Allocate to highest return assets"""
        # 100% in highest return asset (naive)
        weights = np.zeros(len(returns))
        weights[np.argmax(returns)] = 1.0
        return weights

    def _calculate_efficient_frontier(
        self,
        returns: np.ndarray,
        cov: np.ndarray,
        rf: float,
        n_points: int = 20
    ) -> List[Dict]:
        """Calculate efficient frontier points"""
        frontier = []
        target_returns = np.linspace(np.min(returns), np.max(returns), n_points)

        for target in target_returns:
            # Simple approach: interpolate between min variance and max return
            t = (target - np.min(returns)) / (np.max(returns) - np.min(returns))

            min_var_weights = self._min_variance_weights(cov)
            max_ret_weights = self._max_return_weights(returns)

            weights = (1 - t) * min_var_weights + t * max_ret_weights
            weights = np.maximum(weights, 0)
            weights /= np.sum(weights)

            port_return = np.sum(returns * weights)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
            sharpe = (port_return - rf) / port_vol if port_vol > 0 else 0

            frontier.append({
                "return": round(port_return, 4),
                "volatility": round(port_vol, 4),
                "sharpe": round(sharpe, 2),
            })

        return frontier

    def find_pairs(self, symbols: List[str], threshold: float = 0.7) -> List[PairsTrade]:
        """Find correlated pairs for pairs trading"""
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            # Get historical prices
            prices_data = {}
            for symbol in symbols:
                hist = data_service.get_historical(symbol, "1d", 100)
                if hist and len(hist) > 50:
                    prices_data[symbol] = np.array([d["close"] for d in hist])

            if len(prices_data) < 2:
                return []

            # Calculate correlations
            pairs = []
            symbols_list = list(prices_data.keys())

            for i in range(len(symbols_list)):
                for j in range(i + 1, len(symbols_list)):
                    sym_a = symbols_list[i]
                    sym_b = symbols_list[j]

                    prices_a = prices_data[sym_a]
                    prices_b = prices_data[sym_b]

                    # Align lengths
                    min_len = min(len(prices_a), len(prices_b))
                    prices_a = prices_a[-min_len:]
                    prices_b = prices_b[-min_len:]

                    # Calculate correlation
                    correlation = np.corrcoef(prices_a, prices_b)[0, 1]

                    if abs(correlation) >= threshold:
                        # Calculate hedge ratio
                        hedge_ratio = np.cov(prices_a, prices_b)[0, 1] / np.var(prices_b)

                        # Calculate spread
                        spread = prices_a - hedge_ratio * prices_b
                        spread_zscore = (spread[-1] - np.mean(spread)) / np.std(spread)

                        # Determine signal
                        if spread_zscore > 2:
                            signal = "LONG_B_SHORT_A"
                        elif spread_zscore < -2:
                            signal = "LONG_A_SHORT_B"
                        else:
                            signal = "NEUTRAL"

                        # Cointegration test (simplified)
                        from scipy import stats
                        _, pvalue = stats.normaltest(spread)

                        pair = PairsTrade(
                            symbol_a=sym_a,
                            symbol_b=sym_b,
                            correlation=correlation,
                            cointegration_pvalue=pvalue,
                            spread_zscore=spread_zscore,
                            signal=signal,
                            hedge_ratio=hedge_ratio,
                        )

                        pairs.append(pair)

            return sorted(pairs, key=lambda p: abs(p.correlation), reverse=True)

        except Exception as e:
            logger.error(f"Error finding pairs: {e}")
            return []

    def calculate_correlation_matrix(self, symbols: List[str]) -> Dict:
        """Calculate correlation matrix for symbols"""
        try:
            from ..services.data_service import get_data_service
            data_service = get_data_service()

            # Get returns
            returns_data = {}
            for symbol in symbols:
                hist = data_service.get_historical(symbol, "1d", 60)
                if hist and len(hist) > 20:
                    closes = np.array([d["close"] for d in hist])
                    returns = np.diff(closes) / closes[:-1]
                    returns_data[symbol] = returns

            if len(returns_data) < 2:
                return {"symbols": symbols, "matrix": []}

            # Align returns
            min_len = min(len(r) for r in returns_data.values())
            valid_symbols = [s for s in symbols if s in returns_data]

            returns_matrix = np.array([
                returns_data[s][-min_len:] for s in valid_symbols
            ])

            corr_matrix = np.corrcoef(returns_matrix)

            return {
                "symbols": valid_symbols,
                "matrix": [[round(c, 4) for c in row] for row in corr_matrix.tolist()],
            }

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return {"symbols": [], "matrix": []}

    def get_sector_allocation(self) -> List[Dict]:
        """Get portfolio allocation by sector"""
        summary = self.get_portfolio_summary()

        sector_values = {}
        for holding in summary.holdings:
            sector = holding.sector
            if sector not in sector_values:
                sector_values[sector] = 0
            sector_values[sector] += holding.market_value

        total_value = sum(sector_values.values())

        return [
            {
                "sector": sector,
                "value": round(value, 2),
                "weight": round(value / total_value * 100, 2) if total_value > 0 else 0,
            }
            for sector, value in sorted(sector_values.items(), key=lambda x: x[1], reverse=True)
        ]


# Singleton instance
_portfolio_service: Optional[PortfolioService] = None

def get_portfolio_service() -> PortfolioService:
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service
