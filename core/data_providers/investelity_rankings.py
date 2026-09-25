"""Loads the investelity pipeline's own output (individual-stock rankings by
country, by risk-adjusted return) as static, bundled data.

This is deliberately separate from `MarketDataProvider` / `factory.py`: those
feed the optimizer, which works on the app's small curated ETF universe
(see `universe.py`) -- investelity's tickers don't overlap with that universe
at all, since investelity ranks individual country-listed equities/funds, not
broad-market ETFs. This module instead powers a standalone "browse the
pipeline's rankings" page, reading the CSVs the investelity GitHub Actions
pipeline (https://github.com/rb1407/investelity) already produced and
committed, bundled here as static files under data/investelity/.

To refresh this data after a newer investelity pipeline run: copy that
repo's `final/1y/<month>_<year>/*.csv` and `final/3y/<month>_<year>/*.csv`
into `data/investelity/1y/` and `data/investelity/3y/`, and update
`data/investelity/meta.txt`'s PERIOD line to match.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "investelity"

# ISO code -> display name, from investelity's Markets_by_Country.xlsx.
# "usf" isn't a country in that file -- it's investelity's own bucket for
# US-listed funds/ETFs, ranked separately from ordinary US equities ("us").
COUNTRY_NAMES: dict[str, str] = {
    "ar": "Argentina", "at": "Austria", "au": "Australia", "be": "Belgium",
    "br": "Brazil", "ca": "Canada", "ch": "Switzerland", "cl": "Chile",
    "cn": "China", "cz": "Czechia", "de": "Germany", "dk": "Denmark",
    "ee": "Estonia", "eg": "Egypt", "es": "Spain", "fi": "Finland",
    "fr": "France", "gb": "United Kingdom", "gr": "Greece", "hk": "Hong Kong",
    "hu": "Hungary", "id": "Indonesia", "ie": "Ireland", "il": "Israel",
    "in": "India", "is": "Iceland", "it": "Italy", "jp": "Japan",
    "kr": "South Korea", "kw": "Kuwait", "lt": "Lithuania", "lv": "Latvia",
    "mx": "Mexico", "my": "Malaysia", "nl": "Netherlands", "no": "Norway",
    "nz": "New Zealand", "pl": "Poland", "pt": "Portugal", "qa": "Qatar",
    "ro": "Romania", "sa": "Saudi Arabia", "se": "Sweden", "sg": "Singapore",
    "th": "Thailand", "tr": "Turkey", "tw": "Taiwan", "us": "United States",
    "usf": "United States (Funds / ETFs)", "ve": "Venezuela", "za": "South Africa",
}

RANKING_COLUMNS = ["Rank", "Name", "Ticker", "Return (%)", "Risk", "Volatility", "Follows Market Direction ?"]


def data_available() -> bool:
    return DATA_DIR.exists() and any(DATA_DIR.glob("*/*.csv"))


@st.cache_data
def period_label() -> str:
    meta_path = DATA_DIR / "meta.txt"
    if not meta_path.exists():
        return "unknown period"
    for line in meta_path.read_text().splitlines():
        if line.startswith("PERIOD="):
            month, year = line.split("=", 1)[1].split("_")
            months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            return f"{months[int(month)]} {year}"
    return "unknown period"


@st.cache_data
def list_countries(period: str) -> list[tuple[str, str]]:
    """Returns [(code, display name)] for every country with a ranking file
    for this period, sorted by name -- with "usf" pinned to the end since
    it's a fund bucket, not a country."""
    codes = sorted(p.stem for p in (DATA_DIR / period).glob("*.csv") if p.stem not in ("markets", "usf"))
    pairs = [(c, COUNTRY_NAMES.get(c, c.upper())) for c in codes]
    pairs.sort(key=lambda p: p[1])
    if (DATA_DIR / period / "usf.csv").exists():
        pairs.append(("usf", COUNTRY_NAMES["usf"]))
    return pairs


@st.cache_data
def load_rankings(period: str, code: str) -> pd.DataFrame:
    """Ranked individual assets for one country/period, straight from the
    pipeline's output -- Rank is by Sharpe ratio (return / risk), descending.
    Volatility (beta vs. the country's market index) and "Follows Market
    Direction ?" can be blank for a ticker the pipeline didn't have enough
    overlapping history to compute a beta for; that's expected, not missing
    data on our end. For about half of countries, the pipeline's own market
    index ticker wasn't present in that country's price data at all, so
    calc_beta() never ran and the source CSV is missing the Volatility /
    Follows Market Direction columns entirely (not just individual blank
    cells) -- reindex to RANKING_COLUMNS so callers always see the full,
    consistent column set regardless of which case this file is."""
    path = DATA_DIR / period / f"{code}.csv"
    if not path.exists():
        return pd.DataFrame(columns=RANKING_COLUMNS)
    df = pd.read_csv(path)
    return df.reindex(columns=RANKING_COLUMNS)


@st.cache_data
def load_market_overview(period: str) -> pd.DataFrame:
    """Country-level market index performance (e.g. S&P 500 for the US),
    ranked the same way -- gives context for how a country's index itself
    did alongside its individual-asset rankings."""
    path = DATA_DIR / period / "markets.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["Rank"] = df["Rank"].astype("Int64")
    return df
