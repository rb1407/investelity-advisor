"""
Synthetic offline data provider.

This app was built inside a network-restricted sandbox with no path to
Yahoo Finance (or any other live market data source), so it ships with a
generated-but-realistic price history for the curated universe: correlated
geometric-Brownian-motion paths, parameterized with plausible long-run
annualized return/volatility assumptions per asset class and a hand-built
inter-asset-class correlation structure (equities correlated with each
other, bonds weakly/negatively correlated with equities, gold and cash
mostly uncorrelated with everything, etc).

This is clearly labeled everywhere it surfaces (`as_of()`, and a banner in
the UI) as SAMPLE DATA, not real prices — it exists so the optimizer, the
UI, and the whole workflow can be built, tested, and demoed end-to-end.
Swap in `YFinanceProvider` (or a licensed vendor) for real numbers; see
that file's module docstring.

The generation is deterministic (fixed seed) so the same "sample market"
shows up every time the cache is regenerated.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .base import MarketDataProvider
from .cache import write_cached_prices
from .universe import TICKERS, ASSET_BY_TICKER

# Illustrative long-run annualized (return, volatility) assumptions by asset
# class. These are reasonable ballpark figures for a demo, not forecasts or
# back-tested figures.
ASSET_CLASS_ASSUMPTIONS: dict[str, tuple[float, float]] = {
    "US Equity": (0.095, 0.16),
    "Intl Developed Equity": (0.075, 0.17),
    "Emerging Market Equity": (0.085, 0.22),
    "US Bonds": (0.045, 0.06),
    "US Treasuries": (0.038, 0.09),
    "High Yield Bonds": (0.065, 0.10),
    "Intl Bonds": (0.032, 0.06),
    "REITs": (0.075, 0.19),
    "Commodities": (0.045, 0.16),
    "Cash Equivalent": (0.022, 0.008),
}

# Correlation between asset CLASSES. Symmetric; diagonal filled in below.
CLASS_CORRELATION: dict[tuple[str, str], float] = {
    ("US Equity", "Intl Developed Equity"): 0.82,
    ("US Equity", "Emerging Market Equity"): 0.72,
    ("US Equity", "US Bonds"): 0.05,
    ("US Equity", "US Treasuries"): -0.15,
    ("US Equity", "High Yield Bonds"): 0.55,
    ("US Equity", "Intl Bonds"): -0.05,
    ("US Equity", "REITs"): 0.62,
    ("US Equity", "Commodities"): 0.28,
    ("US Equity", "Cash Equivalent"): 0.0,
    ("Intl Developed Equity", "Emerging Market Equity"): 0.78,
    ("Intl Developed Equity", "US Bonds"): 0.0,
    ("Intl Developed Equity", "US Treasuries"): -0.1,
    ("Intl Developed Equity", "High Yield Bonds"): 0.5,
    ("Intl Developed Equity", "Intl Bonds"): 0.1,
    ("Intl Developed Equity", "REITs"): 0.55,
    ("Intl Developed Equity", "Commodities"): 0.32,
    ("Intl Developed Equity", "Cash Equivalent"): 0.0,
    ("Emerging Market Equity", "US Bonds"): -0.05,
    ("Emerging Market Equity", "US Treasuries"): -0.1,
    ("Emerging Market Equity", "High Yield Bonds"): 0.48,
    ("Emerging Market Equity", "Intl Bonds"): 0.1,
    ("Emerging Market Equity", "REITs"): 0.45,
    ("Emerging Market Equity", "Commodities"): 0.4,
    ("Emerging Market Equity", "Cash Equivalent"): 0.0,
    ("US Bonds", "US Treasuries"): 0.85,
    ("US Bonds", "High Yield Bonds"): 0.45,
    ("US Bonds", "Intl Bonds"): 0.6,
    ("US Bonds", "REITs"): 0.25,
    ("US Bonds", "Commodities"): -0.05,
    ("US Bonds", "Cash Equivalent"): 0.15,
    ("US Treasuries", "High Yield Bonds"): 0.05,
    ("US Treasuries", "Intl Bonds"): 0.5,
    ("US Treasuries", "REITs"): 0.15,
    ("US Treasuries", "Commodities"): -0.15,
    ("US Treasuries", "Cash Equivalent"): 0.2,
    ("High Yield Bonds", "Intl Bonds"): 0.2,
    ("High Yield Bonds", "REITs"): 0.4,
    ("High Yield Bonds", "Commodities"): 0.25,
    ("High Yield Bonds", "Cash Equivalent"): 0.0,
    ("Intl Bonds", "REITs"): 0.15,
    ("Intl Bonds", "Commodities"): 0.0,
    ("Intl Bonds", "Cash Equivalent"): 0.1,
    ("REITs", "Commodities"): 0.2,
    ("REITs", "Cash Equivalent"): 0.0,
    ("Commodities", "Cash Equivalent"): 0.0,
}


def _class_corr(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return CLASS_CORRELATION.get((a, b), CLASS_CORRELATION.get((b, a), 0.0))


def _nearest_psd(corr: np.ndarray) -> np.ndarray:
    """Clip negative eigenvalues so the matrix is a valid correlation matrix."""
    eigvals, eigvecs = np.linalg.eigh(corr)
    eigvals = np.clip(eigvals, 1e-8, None)
    fixed = eigvecs @ np.diag(eigvals) @ eigvecs.T
    d = np.sqrt(np.diag(fixed))
    fixed = fixed / np.outer(d, d)
    np.fill_diagonal(fixed, 1.0)
    return fixed


def _build_correlation_matrix(tickers: list[str], rng: np.random.Generator) -> np.ndarray:
    n = len(tickers)
    corr = np.zeros((n, n))
    for i, ti in enumerate(tickers):
        ci = ASSET_BY_TICKER[ti].asset_class
        for j, tj in enumerate(tickers):
            cj = ASSET_BY_TICKER[tj].asset_class
            if i == j:
                corr[i, j] = 1.0
            elif ci == cj:
                # Same asset class: highly correlated but not identical
                corr[i, j] = 0.93 + 0.05 * rng.random()
            else:
                corr[i, j] = _class_corr(ci, cj)
    corr = (corr + corr.T) / 2
    return _nearest_psd(corr)


def generate_sample_prices(
    tickers: list[str] | None = None,
    years: float = 5.0,
    seed: int = 42,
    start_price: float = 100.0,
) -> pd.DataFrame:
    tickers = tickers or TICKERS
    rng = np.random.default_rng(seed)

    n_days = int(round(years * 252))
    corr = _build_correlation_matrix(tickers, rng)

    ann_returns = np.array([ASSET_CLASS_ASSUMPTIONS[ASSET_BY_TICKER[t].asset_class][0] for t in tickers])
    ann_vols = np.array([ASSET_CLASS_ASSUMPTIONS[ASSET_BY_TICKER[t].asset_class][1] for t in tickers])

    daily_mu = np.log1p(ann_returns) / 252 - 0.5 * (ann_vols / np.sqrt(252)) ** 2
    daily_sigma = ann_vols / np.sqrt(252)

    cov = np.outer(daily_sigma, daily_sigma) * corr
    chol = np.linalg.cholesky(cov + np.eye(len(tickers)) * 1e-12)

    z = rng.standard_normal((n_days, len(tickers)))
    correlated_shocks = z @ chol.T
    log_returns = daily_mu + correlated_shocks

    log_prices = np.cumsum(log_returns, axis=0)
    prices = start_price * np.exp(log_prices)

    end = datetime.now(timezone.utc).date()
    dates = pd.bdate_range(end=end - timedelta(days=1), periods=n_days)

    df = pd.DataFrame(prices, index=dates, columns=tickers)
    df.index.name = "Date"
    return df


class SampleDataProvider(MarketDataProvider):
    """Deterministic synthetic data — for demos/dev only. See module docstring."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._as_of = "Sample data (synthetic, not real prices)"

    def get_price_history(self, tickers: list[str], years: float = 5.0) -> pd.DataFrame:
        df = generate_sample_prices(tickers=tickers, years=years, seed=self._seed)
        write_cached_prices(df, self._as_of)
        return df

    def as_of(self) -> str:
        return self._as_of
