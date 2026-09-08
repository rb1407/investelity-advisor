"""
Portfolio construction engine.

Wraps PyPortfolioOpt (mean-variance optimization) to expose the four
strategies consultants asked for:

  - minimum_variance : lowest-volatility portfolio available
  - maximum_sharpe    : best risk-adjusted return (return / risk)
  - maximum_return    : highest return subject only to the diversification
                        cap (a true *unconstrained* max-return portfolio is
                        degenerate -- 100% into the single highest-return
                        asset -- so this is solved as a linear program
                        against the same position-size cap, not against
                        PyPortfolioOpt's quadratic objective)
  - target_risk        : a specific point on the efficient frontier, chosen
                        by risk level (for "custom" risk-tolerance clients)

All expected returns/covariances are estimated from historical price data
(mean historical return + Ledoit-Wolf shrinkage covariance, both standard,
well-tested estimators from PyPortfolioOpt). This is inherently backward-
looking -- see the disclaimer surfaced in the UI.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, expected_returns, risk_models
from scipy.optimize import linprog

RISK_FREE_RATE = 0.02  # illustrative; make this configurable if it matters to you


@dataclass
class PortfolioResult:
    strategy: str
    weights: dict[str, float]  # ticker -> weight, only non-zero (>0.5%) positions
    expected_return: float
    expected_risk: float
    sharpe_ratio: float

    def as_table(self) -> pd.DataFrame:
        df = pd.DataFrame(
            [{"Ticker": t, "Weight": w} for t, w in sorted(self.weights.items(), key=lambda x: -x[1])]
        )
        return df


@dataclass
class OptimizationInputs:
    prices: pd.DataFrame
    excluded_tickers: list[str] = field(default_factory=list)
    max_weight: float = 0.35

    def filtered_prices(self) -> pd.DataFrame:
        cols = [c for c in self.prices.columns if c not in self.excluded_tickers]
        if len(cols) < 2:
            raise ValueError(
                "Fewer than 2 assets remain after exclusions -- relax the "
                "client's exclusion list or ESG filter."
            )
        return self.prices[cols]


class PortfolioOptimizer:
    def __init__(self, inputs: OptimizationInputs):
        self.inputs = inputs
        prices = inputs.filtered_prices()
        self.tickers = list(prices.columns)
        self.mu = expected_returns.mean_historical_return(prices)
        self.S = risk_models.CovarianceShrinkage(prices).ledoit_wolf()

    def _clean(self, weights: dict[str, float]) -> dict[str, float]:
        return {t: round(float(w), 4) for t, w in weights.items() if w > 0.005}

    def _performance(self, weights: dict[str, float]) -> tuple[float, float, float]:
        w = np.array([weights.get(t, 0.0) for t in self.tickers])
        ret = float(w @ self.mu.values)
        risk = float(np.sqrt(w @ self.S.values @ w))
        sharpe = (ret - RISK_FREE_RATE) / risk if risk > 0 else 0.0
        return ret, risk, sharpe

    def _ef(self) -> EfficientFrontier:
        return EfficientFrontier(self.mu, self.S, weight_bounds=(0, self.inputs.max_weight))

    def minimum_variance(self) -> PortfolioResult:
        ef = self._ef()
        ef.min_volatility()
        weights = self._clean(ef.clean_weights())
        ret, risk, sharpe = self._performance(weights)
        return PortfolioResult("Minimum Variance", weights, ret, risk, sharpe)

    def maximum_sharpe(self) -> PortfolioResult:
        ef = self._ef()
        ef.max_sharpe(risk_free_rate=RISK_FREE_RATE)
        weights = self._clean(ef.clean_weights())
        ret, risk, sharpe = self._performance(weights)
        return PortfolioResult("Maximum Sharpe Ratio", weights, ret, risk, sharpe)

    def maximum_return(self) -> PortfolioResult:
        """Highest-return portfolio subject to the same diversification cap
        used everywhere else. Solved directly as a linear program since this
        is not a quadratic (risk-based) objective."""
        n = len(self.tickers)
        c = -self.mu.values  # linprog minimizes, so negate to maximize return
        A_eq = [np.ones(n)]
        b_eq = [1.0]
        bounds = [(0, self.inputs.max_weight)] * n
        res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
        if not res.success:
            raise RuntimeError(f"Maximum-return optimization failed: {res.message}")
        weights = self._clean({t: w for t, w in zip(self.tickers, res.x)})
        ret, risk, sharpe = self._performance(weights)
        return PortfolioResult("Maximum Return", weights, ret, risk, sharpe)

    def risk_bounds(self) -> tuple[float, float]:
        """(min achievable risk, max achievable risk) under current constraints,
        for setting slider bounds in the UI."""
        min_risk = self.minimum_variance().expected_risk
        max_risk = self.maximum_return().expected_risk
        return min_risk, max_risk

    def target_risk(self, target_volatility: float) -> PortfolioResult:
        ef = self._ef()
        min_r, max_r = self.risk_bounds()
        target_volatility = float(np.clip(target_volatility, min_r * 1.001, max_r * 0.999))
        ef.efficient_risk(target_volatility)
        weights = self._clean(ef.clean_weights())
        ret, risk, sharpe = self._performance(weights)
        return PortfolioResult(f"Target Risk ({target_volatility:.1%})", weights, ret, risk, sharpe)

    def efficient_frontier_curve(self, n_points: int = 25) -> pd.DataFrame:
        """Sample the frontier for charting."""
        min_r, max_r = self.risk_bounds()
        points = []
        for vol in np.linspace(min_r, max_r, n_points):
            try:
                ef = self._ef()
                ef.efficient_risk(float(np.clip(vol, min_r * 1.001, max_r * 0.999)))
                w = ef.clean_weights()
                ret, risk, _ = self._performance(w)
                points.append({"risk": risk, "return": ret})
            except Exception:
                continue
        return pd.DataFrame(points)

    def compare_all(self, target_volatility: float | None = None) -> list[PortfolioResult]:
        results = [self.minimum_variance(), self.maximum_sharpe(), self.maximum_return()]
        if target_volatility is not None:
            results.append(self.target_risk(target_volatility))
        return results


STRATEGY_FOR_RISK_TOLERANCE = {
    "conservative": "minimum_variance",
    "moderate": "maximum_sharpe",
    "aggressive": "maximum_return",
    "custom": "target_risk",
}
