"""
Real market data provider, backed by Yahoo Finance via the `yfinance`
package (the same library the original `investelity` scripts used).

IMPORTANT — read before going to production with this:
Yahoo Finance's terms of use restrict commercial redistribution of their
data. `yfinance` is a free, unofficial wrapper around a public endpoint
intended for personal/research use. It is fine for building and demoing
this app. Before charging consultants for a product built on this data,
switch to a provider with a commercial-use license (e.g. Tiingo, Polygon.io,
Alpha Vantage, IEX Cloud, or a market-data agreement with your broker).
Because the rest of the app only talks to the `MarketDataProvider`
interface (see base.py), that swap only requires writing one new class
here — no changes to the optimizer, the UI, or the database.

NOTE ON THIS SANDBOX: outbound network access in the Claude cloud
workspace used to build this app is restricted to an allowlist that does
not include Yahoo Finance, so this provider could not be *tested* live
from here (confirmed: connection attempts return HTTP 403 from the
network gateway). The code below is a standard, correct yfinance batch
download — it should work as-is on a normal machine with open internet
(your laptop, a VM, Streamlit Community Cloud, etc.). Run
`python scripts/refresh_market_data.py` there to pull real prices into
the shared cache; the sample data this app ships with (see
sample_provider.py) is what powers today's demo.
"""

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .base import MarketDataProvider
from .cache import read_cached_prices, write_cached_prices


class YFinanceProvider(MarketDataProvider):
    def __init__(self) -> None:
        self._as_of = "Live data: not yet fetched"

    def get_price_history(self, tickers: list[str], years: float = 5.0) -> pd.DataFrame:
        period = f"{max(1, round(years))}y"
        try:
            raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)
            if raw is None or len(raw) == 0:
                raise RuntimeError("yfinance returned no data")

            prices = raw["Close"] if "Close" in raw else raw
            prices = prices.dropna(axis=1, how="all").dropna(axis=0, how="all")
            prices = prices.ffill().dropna(axis=0, how="any")
            if prices.shape[1] < 2:
                raise RuntimeError("yfinance returned fewer than 2 usable tickers")
        except Exception as exc:
            cached = read_cached_prices()
            if cached is not None and cached.shape[1] >= 2:
                self._as_of = f"Live fetch failed ({exc}); showing last cached prices"
                return cached
            raise RuntimeError(
                "Live fetch from Yahoo Finance failed and no usable cache exists. "
                "Check your internet connection; Yahoo Finance also rate-limits "
                f"aggressive polling. Original error: {exc}"
            ) from exc

        self._as_of = f"Live data as of {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
        write_cached_prices(prices, self._as_of)
        return prices

    def as_of(self) -> str:
        return self._as_of
