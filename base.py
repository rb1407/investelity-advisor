"""
Abstract interface for market data providers.

The optimization engine and the rest of the app depend ONLY on this
interface, never on a specific vendor. That is what makes the data source
swappable: to move off yfinance later (e.g. to a licensed vendor such as
Tiingo, Polygon.io or Alpha Vantage once this is a paid product), write a
new class implementing `MarketDataProvider` and point `get_provider()` in
`factory.py` at it. Nothing else in the app needs to change.
"""

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    """Contract every market data source must satisfy."""

    @abstractmethod
    def get_price_history(self, tickers: list[str], years: float = 5.0) -> pd.DataFrame:
        """Return a DataFrame of adjusted close prices.

        Index: dates (ascending). Columns: tickers. Values: price levels
        (not returns). Missing tickers/data should be dropped, not raise,
        so the optimizer can proceed with whatever is available.
        """
        raise NotImplementedError

    @abstractmethod
    def as_of(self) -> str:
        """Human-readable label describing how fresh/what kind this data is,
        e.g. 'Live data as of 2026-09-02' or 'Sample/demo data (synthetic)'.
        Surfaced in the UI so nobody mistakes demo data for the real thing.
        """
        raise NotImplementedError
