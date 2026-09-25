"""Lets Portfolio Builder (and, through it, Rebalancing) run on investelity's
own ranked stocks instead of only the curated 17-ETF model universe in
universe.py.

Why a separate, bounded universe rather than optimizing over investelity's
full ticker list: a country like "us" or "usf" has 9,000-79,000 tickers --
feeding that straight into PyPortfolioOpt's mean-variance optimizer would be
numerically unstable and slow (the whole point of universe.py's curated
17-ETF list, see its module docstring). Instead, this uses investelity's own
Sharpe-ratio ranking to pick the top TOP_N tickers per country/period -- a
small, still-diversified set the optimizer can handle the same way it
handles the ETF universe.

Price history for just those top-N tickers per country/period is bundled
under data/investelity/top_prices/ (extracted from the investelity
pipeline's prices_cleaned/ output -- see the comment in that data's
generating step for how to refresh it). This is intentionally much smaller
than data/investelity/{1y,3y}/ (the full rankings the Top Ranked Assets page
reads), since it only needs to cover the tickers actually selectable here.
"""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from .investelity_rankings import DATA_DIR as RANKINGS_DIR
from .investelity_rankings import COUNTRY_NAMES, list_countries, load_rankings, period_label  # noqa: F401

TOP_PRICES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "investelity" / "top_prices"
TOP_N = 25  # tickers per country/period -- see module docstring


def universe_available() -> bool:
    return TOP_PRICES_DIR.exists() and any(TOP_PRICES_DIR.glob("*/*.csv"))


@st.cache_data
def load_top_prices(period: str, code: str) -> pd.DataFrame:
    """Adjusted-close-style price levels for this country/period's top
    TOP_N tickers -- Date-indexed, ascending, one column per ticker. Same
    shape MarketDataProvider.get_price_history returns, so it drops straight
    into the existing PortfolioOptimizer."""
    path = TOP_PRICES_DIR / period / f"{code}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, index_col="Date", parse_dates=True).sort_index()
    return df


@st.cache_data
def top_assets(period: str, code: str) -> pd.DataFrame:
    """The ranking rows (Rank/Name/Ticker/Return/Risk/...) for exactly the
    tickers load_top_prices() has price history for -- use this for display
    metadata, not the full country ranking."""
    prices = load_top_prices(period, code)
    if prices.empty:
        return pd.DataFrame()
    ranked = load_rankings(period, code)
    return ranked[ranked["Ticker"].isin(prices.columns)].reset_index(drop=True)


def asset_meta_for(period: str, code: str) -> dict[str, SimpleNamespace]:
    """ticker -> object with .name/.asset_class, matching universe.py's
    Asset shape closely enough to reuse the same save_portfolio()/table
    code Portfolio Builder already has for the ETF universe. Individual
    stocks don't have a meaningful fixed asset class the way model ETFs do,
    so everything here is grouped under one class -- "Individual Equity" --
    which is also what Holdings offers as a class so Rebalancing has
    something to compare against."""
    assets = top_assets(period, code)
    return {
        row.Ticker: SimpleNamespace(name=row.Name, asset_class="Individual Equity")
        for row in assets.itertuples()
    }
