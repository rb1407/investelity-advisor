# Investelity Organizer

A practice-management tool for investment consultants: keep a client roster with
saved risk preferences, generate minimum-variance / maximum-Sharpe /
maximum-return / target-risk model recommendations across a curated set of
asset-class ETFs, **and** record what each client actually holds — so the app
can tell you, at a glance, which clients have drifted from plan and need a
rebalancing conversation.

This is the "organizing software" idea from the
[`investelity`](https://github.com/rb1407/investelity) data project, rebuilt
as a proper multi-client tool rather than a one-off ranking script. Two kinds
of "portfolio" live side by side here, deliberately kept separate:

- **Target** (`Portfolio` / `PortfolioHolding`) — a model recommendation the
  optimizer produced, generated and saved on **Portfolio Builder**.
- **Actual** (`HoldingsSnapshot` / `HoldingsPosition`) — what a client really
  holds, as a dated snapshot you record on **Holdings**.

**Rebalancing** compares the two at the asset-class level (not the exact
ticker level, since real positions rarely match the house model universe
exactly) and flags any client whose drift exceeds their configured threshold.

## Quick start

```bash
pip install -r requirements.txt
python scripts/seed_demo_data.py   # creates a demo login + sample clients/data
streamlit run Home.py
```

Open the URL Streamlit prints and log in with **username: `demo`, password:
`demo1234`**. The demo seeds four sample clients — one (Daniel Okafor) is
seeded with a deliberately drifted holdings snapshot so the Home dashboard
alert and Rebalancing page have something to show immediately.

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
Home.py                       Dashboard: roster summary, tracked AUM, rebalancing alerts
pages/1_Clients.py            Client roster: add/edit/delete, preferences & constraints
pages/2_Portfolio_Builder.py  Generate / compare strategies, save a client's target
pages/3_Holdings.py           Record a dated snapshot of a client's actual holdings
pages/4_Rebalancing.py        Target vs. actual drift by asset class, suggested trades
pages/5_Client_History.py     Every saved recommendation for a client, with CSV export

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

core/rebalancing/engine.py    Asset-class-level drift analysis: compares a
                               HoldingsSnapshot's actual weights against a
                               Portfolio's target weights, flags clients past
                               their configured drift threshold

core/db/                      SQLAlchemy models + helpers: Consultant, Client,
                               Portfolio, PortfolioHolding, HoldingsSnapshot,
                               HoldingsPosition (SQLite by default — change the
                               URL in session.py for Postgres/MySQL)

core/auth/auth.py             Minimal bcrypt + session_state login (see caveats below)
core/seed.py                  Demo consultant + sample clients + sample recommendations
                               and holdings (runs automatically on first startup)

scripts/
  seed_demo_data.py           CLI entrypoint for seed.py (not required — see above)
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

## Rebalancing

Each client has a `rebalance_threshold` (default 5%, editable on the Clients
page). Rebalancing takes their most recently recorded `HoldingsSnapshot` and
most recently saved `Portfolio` target, aggregates both to weights per asset
class, and flags the client if any asset class has drifted (actual − target)
by more than the threshold — surfaced both on the Rebalancing page (with a
target-vs-actual chart and suggested buy/sell dollar amounts per asset class)
and as an alert banner on the Home dashboard.

## Known limitations / where to go next

This is a working demo scoped to validate the idea with a handful of
consultants, not a production launch. Before selling it for real, you'd want to
work through, roughly in priority order:

1. **Real, licensed market data** (see above) — the single biggest blocker to charging money for this.
2. **Real auth** — the current login is bcrypt + Streamlit session state, fine for a handful of trusted users, not for a public signup flow. No password reset, no MFA, no rate limiting.
3. **A real ESG screen** — `esg_focus` currently just excludes commodities/gold/high-yield as a rough placeholder, not a real ESG score. Fine to disclose as "in development," not fine to imply it's a compliant ESG screen.
4. **Compliance review** — this generates model output, not personalized investment advice; the in-app disclaimer says so, but you (or your consultants' compliance teams) should sign off on this before it's used with actual client money.
5. **Multi-tenant hardening** if you go the "sell to many firms" route — data isolation between firms, admin tooling to manage consultant accounts, etc.
6. **Ticker-level drift**, not just asset-class-level, once holdings are consistently recorded against the model universe.
7. **Deployment** — this repo includes a `Procfile` for Railway/Heroku-style hosts; a real launch would likely move to a proper host with Postgres instead of SQLite.
