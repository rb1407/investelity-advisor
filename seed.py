"""Demo data seeding — creates a demo consultant login, a few sample
clients, a saved model recommendation for most of them, and a recorded
holdings snapshot for some of them (one deliberately drifted, so the
Rebalancing page and the Home dashboard alert have something to show on
first login).

Called both from the CLI (`scripts/seed_demo_data.py`, for local use) and
automatically from `Home.py` / `core/app_common.py` on startup. This matters
for hosted deployments (e.g. Railway, Streamlit Community Cloud) where
there's no shell access to run a one-off script before the app starts — the
app has to seed itself. Safe to call on every startup: it only creates
records that don't already exist.
"""

from core.auth.auth import hash_password
from core.data_providers.factory import get_provider
from core.data_providers.universe import ASSET_BY_TICKER, TICKERS, esg_excluded_tickers
from core.db import crud
from core.db.session import get_session, init_db
from core.optimization.engine import STRATEGY_FOR_RISK_TOLERANCE, OptimizationInputs, PortfolioOptimizer

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"

SAMPLE_CLIENTS = [
    dict(
        name="Priya Shah",
        email="priya@example.com",
        risk_tolerance="conservative",
        investment_horizon_years=6,
        initial_investment=250_000,
        max_position_weight=0.30,
        esg_focus=False,
        excluded_tickers="",
        notes="Nearing retirement; prioritizes capital preservation.",
    ),
    dict(
        name="Daniel Okafor",
        email="daniel@example.com",
        risk_tolerance="moderate",
        investment_horizon_years=15,
        initial_investment=500_000,
        max_position_weight=0.35,
        esg_focus=True,
        excluded_tickers="",
        notes="Wants an ESG-screened core allocation.",
    ),
    dict(
        name="Wei Chen",
        email="wei@example.com",
        risk_tolerance="aggressive",
        investment_horizon_years=25,
        initial_investment=100_000,
        max_position_weight=0.40,
        esg_focus=False,
        excluded_tickers="HYG",
        notes="Long horizon, comfortable with volatility. No high-yield credit exposure per mandate.",
    ),
    dict(
        name="Amara Bello",
        email="amara@example.com",
        risk_tolerance="custom",
        target_risk=0.09,
        investment_horizon_years=10,
        initial_investment=350_000,
        max_position_weight=0.30,
        esg_focus=False,
        excluded_tickers="",
        notes="Targeting a specific volatility band agreed with the client.",
    ),
]


def _build_recommendation(db, client, prices):
    """Runs this client's default strategy and saves it as their target."""
    exclusions = set(client.excluded_tickers_list())
    if client.esg_focus:
        exclusions |= set(esg_excluded_tickers())

    optimizer = PortfolioOptimizer(
        OptimizationInputs(prices=prices, excluded_tickers=list(exclusions), max_weight=client.max_position_weight)
    )
    strategy = STRATEGY_FOR_RISK_TOLERANCE.get(client.risk_tolerance, "maximum_sharpe")
    if strategy == "minimum_variance":
        result = optimizer.minimum_variance()
    elif strategy == "maximum_return":
        result = optimizer.maximum_return()
    elif strategy == "target_risk":
        min_r, max_r = optimizer.risk_bounds()
        target = client.target_risk or (min_r + max_r) / 2
        result = optimizer.target_risk(target)
    else:
        result = optimizer.maximum_sharpe()

    return crud.save_portfolio(
        db, client.id, result, data_as_of=provider_as_of(), label=f"{result.strategy} — initial", asset_meta=ASSET_BY_TICKER
    )


def provider_as_of() -> str:
    return get_provider().as_of()


def _weights_to_holdings_positions(weights: dict[str, float], total_value: float) -> list[dict]:
    return [
        {
            "ticker": ticker,
            "name": ASSET_BY_TICKER[ticker].name if ticker in ASSET_BY_TICKER else ticker,
            "asset_class": ASSET_BY_TICKER[ticker].asset_class if ticker in ASSET_BY_TICKER else "Unclassified",
            "value": round(weight * total_value, 2),
        }
        for ticker, weight in weights.items()
    ]


def seed(verbose: bool = False) -> None:
    init_db()
    db = get_session()
    try:
        consultant = crud.get_consultant_by_username(db, DEMO_USERNAME)
        if consultant is None:
            consultant = crud.create_consultant(
                db, DEMO_USERNAME, "Demo Consultant", hash_password(DEMO_PASSWORD),
                email="demo@investelity.app", firm_name="Investelity Advisory (Demo)",
            )
            if verbose:
                print(f"Created consultant '{DEMO_USERNAME}' / password '{DEMO_PASSWORD}'")
        elif verbose:
            print(f"Consultant '{DEMO_USERNAME}' already exists — skipping.")

        existing = {c.name: c for c in crud.list_clients(db, consultant.id)}
        newly_created = []
        for fields in SAMPLE_CLIENTS:
            if fields["name"] in existing:
                if verbose:
                    print(f"Client '{fields['name']}' already exists — skipping.")
                continue
            client = crud.create_client(db, consultant.id, **fields)
            existing[client.name] = client
            newly_created.append(client)
            if verbose:
                print(f"Created client '{client.name}'")

        if not newly_created:
            return

        # Everything below only runs the very first time this app starts
        # (i.e. only for clients we just created), so re-seeding never
        # clobbers a consultant's real saved recommendations or holdings.
        provider = get_provider()
        prices = provider.get_price_history(TICKERS, years=5)

        priya = existing.get("Priya Shah")
        daniel = existing.get("Daniel Okafor")
        wei = existing.get("Wei Chen")
        # Amara is deliberately left with no recommendation/holdings yet —
        # a useful "empty state" to show a first-time viewer of the app.

        for client in [c for c in (priya, daniel, wei) if c in newly_created]:
            portfolio = _build_recommendation(db, client, prices)
            if verbose:
                print(f"Saved recommendation for {client.name}: {portfolio.strategy}")

            target_weights = {h.ticker: h.weight for h in portfolio.holdings}
            if client is priya:
                # Tracks her target closely (small, sub-threshold drift) —
                # shows a "no action needed" client on the dashboard.
                positions = _weights_to_holdings_positions(target_weights, client.initial_investment)
                if positions:
                    # nudge the largest position a couple of points, still under her 5% default threshold
                    positions[0]["value"] = round(positions[0]["value"] * 1.03, 2)
                crud.save_holdings_snapshot(db, client.id, "Initial review", positions)
            elif client is daniel:
                # Deliberately drifted well past his rebalance threshold —
                # a strong equity rally since his last review left him
                # overweight equities and underweight bonds/cash. This is
                # the client the Home dashboard alert and Rebalancing page
                # are meant to catch.
                drifted = {}
                for ticker, weight in target_weights.items():
                    asset_class = ASSET_BY_TICKER.get(ticker).asset_class if ticker in ASSET_BY_TICKER else ""
                    if "Equity" in asset_class:
                        drifted[ticker] = weight * 1.35
                    elif "Bond" in asset_class or "Treasur" in asset_class or "Cash" in asset_class:
                        drifted[ticker] = weight * 0.55
                    else:
                        drifted[ticker] = weight
                total_w = sum(drifted.values()) or 1.0
                drifted = {t: w / total_w for t, w in drifted.items()}
                positions = _weights_to_holdings_positions(drifted, client.initial_investment)
                crud.save_holdings_snapshot(db, client.id, "Q2 review — equities ran ahead of plan", positions)
            elif client is wei:
                # No holdings snapshot yet for Wei — shows the "record
                # holdings to enable rebalancing" empty state on that page.
                pass

    finally:
        db.close()
