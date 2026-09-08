"""Simple on-disk price cache shared by all providers.

Keeps the app fast (no network call on every page load) and gives it
something to fall back to if a live fetch fails mid-demo.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PRICES_PATH = CACHE_DIR / "prices.csv"
META_PATH = CACHE_DIR / "meta.txt"


def read_cached_prices() -> pd.DataFrame | None:
    if not PRICES_PATH.exists():
        return None
    df = pd.read_csv(PRICES_PATH, index_col=0, parse_dates=True)
    return df


def write_cached_prices(df: pd.DataFrame, source_label: str) -> None:
    df.to_csv(PRICES_PATH)
    META_PATH.write_text(
        f"{source_label}\nCached at {datetime.now(timezone.utc).isoformat()}Z\n"
    )


def read_cache_meta() -> str:
    if META_PATH.exists():
        return META_PATH.read_text().strip()
    return "No cached data yet"
