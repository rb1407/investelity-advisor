"""
The curated investable universe.

Design choice: rather than optimizing across thousands of individual global
stocks (which is what the original `investelity` scripts ranked), this app
builds portfolios from a small set of liquid, low-cost ETFs that each
represent a whole asset class or region. This is the standard approach used
by advisor-facing portfolio tools (model portfolios / asset allocation),
and it keeps the optimizer numerically stable and the recommendations easy
for a consultant to explain to a client.

Consultants can exclude any subset of these assets per-client (e.g. to
respect a mandate or a client's existing concentrated position).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    ticker: str
    name: str
    asset_class: str
    region: str
    esg_friendly: bool = True  # see README: simple placeholder screen, not a real ESG score


UNIVERSE: list[Asset] = [
    # US Equities
    Asset("VTI", "Vanguard Total US Stock Market", "US Equity", "United States"),
    Asset("SPY", "SPDR S&P 500", "US Equity", "United States"),
    Asset("IJH", "iShares Core S&P Mid-Cap", "US Equity", "United States"),
    Asset("IJR", "iShares Core S&P Small-Cap", "US Equity", "United States"),
    # International Equities
    Asset("VEA", "Vanguard FTSE Developed Markets", "Intl Developed Equity", "Global ex-US"),
    Asset("VWO", "Vanguard FTSE Emerging Markets", "Emerging Market Equity", "Global"),
    Asset("EFA", "iShares MSCI EAFE", "Intl Developed Equity", "Global ex-US"),
    # Fixed Income
    Asset("AGG", "iShares Core US Aggregate Bond", "US Bonds", "United States"),
    Asset("BND", "Vanguard Total Bond Market", "US Bonds", "United States"),
    Asset("IEF", "iShares 7-10 Year Treasury Bond", "US Treasuries", "United States"),
    Asset("TLT", "iShares 20+ Year Treasury Bond", "US Treasuries", "United States"),
    Asset("HYG", "iShares iBoxx High Yield Corporate Bond", "High Yield Bonds", "United States", esg_friendly=False),
    Asset("BNDX", "Vanguard Total International Bond", "Intl Bonds", "Global ex-US"),
    # Real Assets / Diversifiers
    Asset("VNQ", "Vanguard Real Estate", "REITs", "United States"),
    Asset("GLD", "SPDR Gold Shares", "Commodities", "Global", esg_friendly=False),
    Asset("DBC", "Invesco DB Commodity Index Tracking", "Commodities", "Global", esg_friendly=False),
    # Cash equivalent
    Asset("BIL", "SPDR Bloomberg 1-3 Month T-Bill", "Cash Equivalent", "United States"),
]

TICKERS: list[str] = [a.ticker for a in UNIVERSE]
ASSET_BY_TICKER: dict[str, Asset] = {a.ticker: a for a in UNIVERSE}


def esg_excluded_tickers() -> list[str]:
    """Tickers filtered out when a client has an ESG focus flag set.

    NOTE: this is a simple placeholder screen (commodities / high-yield only)
    and is NOT a substitute for a real ESG data feed or scoring methodology.
    See README for how to wire up a real ESG data source.
    """
    return [a.ticker for a in UNIVERSE if not a.esg_friendly]
