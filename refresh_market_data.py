"""Pull REAL prices from Yahoo Finance and refresh the shared cache.

Run this on a machine with normal (non-sandboxed) internet access — your
laptop, a VM, wherever you deploy the app. It cannot be run inside the
Claude cloud workspace this app was built in, because that workspace's
network is allowlisted and does not include Yahoo Finance.

Usage:
    pip install -r requirements.txt
    python scripts/refresh_market_data.py

After it finishes, launch the app with DATA_PROVIDER=yfinance so it reads
the freshly cached real prices instead of the bundled sample data:
    DATA_PROVIDER=yfinance streamlit run Home.py
(Windows PowerShell: $env:DATA_PROVIDER="yfinance"; streamlit run Home.py)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.data_providers.universe import TICKERS
from core.data_providers.yfinance_provider import YFinanceProvider


def main() -> None:
    provider = YFinanceProvider()
    print(f"Fetching {len(TICKERS)} tickers from Yahoo Finance...")
    prices = provider.get_price_history(TICKERS, years=5)
    print(f"Done: {prices.shape[0]} trading days x {prices.shape[1]} tickers.")
    print(provider.as_of())
    print("Cached to data/cache/prices.csv")


if __name__ == "__main__":
    main()
