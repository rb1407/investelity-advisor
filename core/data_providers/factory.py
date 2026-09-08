"""Single place that decides which MarketDataProvider the app uses.

Controlled by the DATA_PROVIDER environment variable:
  - "sample"   -> SampleDataProvider (synthetic, offline, default)
  - "yfinance" -> YFinanceProvider (real, needs open internet)

This is the one line you change to point the whole app at a different
vendor later.
"""

import os

from .base import MarketDataProvider


def get_provider() -> MarketDataProvider:
    kind = os.environ.get("DATA_PROVIDER", "sample").lower()
    if kind == "yfinance":
        from .yfinance_provider import YFinanceProvider

        return YFinanceProvider()

    from .sample_provider import SampleDataProvider

    return SampleDataProvider()
