# Investelity Advisor

A portfolio construction and client-organizing tool for investment consultants. A
consultant logs in, keeps a roster of clients with saved risk preferences, and
generates minimum-variance / maximum-Sharpe / maximum-return / target-risk
portfolio recommendations across a curated set of asset-class ETFs — then saves
and tracks those recommendations over time per client.

This grew out of the [`investelity`](https://github.com/rb1407/investelity) data
project, which ranked individual global equities by risk-adjusted return. This
app takes a different, more advisor-friendly approach: it builds portfolios from
~17 liquid, low-cost ETFs that each represent a whole asset class (US equity,
international equity, emerging markets, bonds, treasuries, high yield, REITs,
gold, commodities, cash) rather than optimizing across thousands of individual
stocks. That's what most advisor-facing allocation tools do, and it keeps the
optimizer numerically stable and the output easy to explain to a client.

## Quick start

```bash
pip install -r requirements.txt
python scripts/seed_demo_data.py   # creates a demo login + sample clients
streamlit run Home.py
```

Open the URL Streamlit prints and log in with **username: `demo`, password:
`demo1234`**.

## ⚠️ Read this before showing it to a real client

**The app ships running on synthetic sample data, not real market prices.**
It was built inside a network-restricted sandbox with no path to Yahoo Finance
or any other live data source, so `core/data_providers/sample_provider.py`
generates a deterministic, statistically-plausible-but-fake price history
(correlated random walks parameterized with reasonable per-asset-class
return/volatility/correlation assumptions) so the whole app could be built and
tested end-to-end. Every page shows a banner and a sidebar note when it's
running on sample data.

To use real prices:

```bash
python scripts/refresh_market_data.py       # run on a machine with normal internet access
DATA_PROVIDER=yfinance streamlit run Home.py
```

**Before charging money for this**, also read the licensing note in
`core/data_providers/yfinance_provider.py`: Yahoo Finance's terms restrict
commercial redistribution of their data, so `yfinance` (a free, unofficial
wrapper) is fine for building/demoing but not for a paid product. The data layer
is deliberately abstracted (`core/data_providers/base.py`) so switching to a
licensed vendor (Tiingo, Polygon.io, Alpha Vantage, IEX Cloud, or a data
agreement through your broker) only means writing one new provider class — no
changes to the optimizer, database, or UI.

## What's in here

```
Home.py                       Dashboard (login gate, roster summary)
pages/1_Clients.py            Client roster: add/edit/delete, preferences & constraints
pages/2_Portfolio_Builder.py  Generate / compare strategies, save a recommendation
pages/3_Client_History.py     Every saved portfolio for a client, with CSV export

core/data_providers/
  base.py                     MarketDataProvider interface (swap the data source here)
  universe.py                 The curated ~17-ETF investable universe
  sample_provider.py          Synthetic demo data (default)
  yfinance_provider.py        Real data via yfinance (needs open internet)
  factory.py                  DATA_PROVIDER env var picks which one to use
  cache.py                    On-disk price cache (also a fallback if a live fetch fails)

core/optimization/engine.py   PyPortfolioOpt-backed optimizer: min variance, max
                               Sharpe, max return (linear program under the
                               diversification cap), target-risk frontier point,
                               plus efficient-frontier sampling for the chart

core/db/                      SQLAlchemy models + helpers: Consultant, Client,
                               Portfolio, PortfolioHolding (SQLite by default —
                               change the URL in session.py for Postgres/MySQL)

core/auth/auth.py             Minimal bcrypt + session_state login (see caveats below)

scripts/
  seed_demo_data.py           Demo consultant + sample clients
  refresh_market_data.py      Pull real prices (run where the internet is open)
```

## Strategies

- **Minimum Variance** — lowest-volatility portfolio available.
- **Maximum Sharpe Ratio** — best risk-adjusted return; the default recommendation for "moderate" clients.
- **Maximum Return** — highest return subject to the same per-position diversification cap as everything else (an unconstrained max-return portfolio is degenerate — 100% into one asset — so this isn't that).
- **Target Risk** — a specific point on the efficient frontier, for clients with a custom risk mandate.

Each client's `risk_tolerance` field (conservative / moderate / aggressive /
custom) picks a sensible default strategy; a consultant can override it or use
"Compare all strategies" to see all four side-by-side before a client meeting.

## Known limitations / where to go next

This is a working demo scoped to validate the idea with a handful of
consultants, not a production launch. Before selling it for real, you'd want to
work through, roughly in priority order:

1. **Real, licensed market data** (see above) — the single biggest blocker to charging money for this.
2. **Real auth** — the current login is bcrypt + Streamlit session state, fine for a handful of trusted users, not for a public signup flow. No password reset, no MFA, no rate limiting.
3. **A real ESG screen** — `esg_focus` currently just excludes commodities/gold/high-yield as a rough placeholder, not a real ESG score. Fine to disclose as "in development," not fine to imply it's a compliant ESG screen.
4. **Compliance review** — this generates model output, not personalized investment advice; the in-app disclaimer says so, but you (or your consultants' compliance teams) should sign off on this before it's used with actual client money.
5. **Multi-tenant hardening** if you go the "sell to many firms" route — data isolation between firms, admin tooling to manage consultant accounts, etc.
6. **Deployment** — Streamlit Community Cloud is the fastest path to a shareable demo link; a real launch would likely move to a proper host with Postgres instead of SQLite.
