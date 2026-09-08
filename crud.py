"""Helper functions around the ORM models -- keeps the Streamlit pages free
of raw SQLAlchemy query boilerplate."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from core.optimization.engine import PortfolioResult
from .models import Client, Consultant, HoldingsPosition, HoldingsSnapshot, Portfolio, PortfolioHolding


# --- Consultants -----------------------------------------------------------

def get_consultant_by_username(db: Session, username: str) -> Consultant | None:
    return db.scalar(select(Consultant).where(Consultant.username == username))


def create_consultant(
    db: Session, username: str, name: str, password_hash: str, email: str = "", firm_name: str = ""
) -> Consultant:
    consultant = Consultant(username=username, name=name, password_hash=password_hash, email=email, firm_name=firm_name)
    db.add(consultant)
    db.commit()
    db.refresh(consultant)
    return consultant


# --- Clients -----------------------------------------------------------

def list_clients(db: Session, consultant_id: int) -> list[Client]:
    # Eager-load relationships accessed on the dashboard/roster views so a
    # later lazy load never has to depend on this short-lived session still
    # being open (Streamlit reruns the whole script per interaction).
    return list(
        db.scalars(
            select(Client)
            .options(selectinload(Client.portfolios), selectinload(Client.holdings_snapshots))
            .where(Client.consultant_id == consultant_id)
            .order_by(Client.name)
        )
    )


def get_client(db: Session, client_id: int) -> Client | None:
    return db.get(Client, client_id)


def create_client(db: Session, consultant_id: int, **fields) -> Client:
    client = Client(consultant_id=consultant_id, **fields)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update_client(db: Session, client: Client, **fields) -> Client:
    for k, v in fields.items():
        setattr(client, k, v)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client) -> None:
    db.delete(client)
    db.commit()


# --- Portfolios (model recommendations) -------------------------------------

def save_portfolio(
    db: Session,
    client_id: int,
    result: PortfolioResult,
    data_as_of: str,
    label: str = "",
    asset_meta: dict | None = None,
) -> Portfolio:
    asset_meta = asset_meta or {}
    portfolio = Portfolio(
        client_id=client_id,
        label=label,
        strategy=result.strategy,
        data_as_of=data_as_of,
        expected_return=result.expected_return,
        expected_risk=result.expected_risk,
        sharpe_ratio=result.sharpe_ratio,
    )
    db.add(portfolio)
    db.flush()

    for ticker, weight in result.weights.items():
        meta = asset_meta.get(ticker)
        db.add(
            PortfolioHolding(
                portfolio_id=portfolio.id,
                ticker=ticker,
                weight=weight,
                name=meta.name if meta else ticker,
                asset_class=meta.asset_class if meta else "",
            )
        )

    db.commit()
    db.refresh(portfolio)
    return portfolio


def list_portfolios_for_client(db: Session, client_id: int) -> list[Portfolio]:
    return list(
        db.scalars(
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .where(Portfolio.client_id == client_id)
            .order_by(Portfolio.created_at.desc())
        )
    )


# --- Holdings snapshots (actual positions) ----------------------------------

def save_holdings_snapshot(
    db: Session, client_id: int, label: str, positions: list[dict]
) -> HoldingsSnapshot:
    """positions: list of {ticker, name, asset_class, value}"""
    snapshot = HoldingsSnapshot(client_id=client_id, label=label)
    db.add(snapshot)
    db.flush()

    for p in positions:
        db.add(
            HoldingsPosition(
                snapshot_id=snapshot.id,
                ticker=p["ticker"],
                name=p.get("name", p["ticker"]),
                asset_class=p["asset_class"],
                value=p["value"],
            )
        )

    db.commit()
    db.refresh(snapshot)
    return snapshot


def list_holdings_snapshots_for_client(db: Session, client_id: int) -> list[HoldingsSnapshot]:
    return list(
        db.scalars(
            select(HoldingsSnapshot)
            .options(selectinload(HoldingsSnapshot.positions))
            .where(HoldingsSnapshot.client_id == client_id)
            .order_by(HoldingsSnapshot.created_at.desc())
        )
    )


def latest_holdings_snapshot(db: Session, client_id: int) -> HoldingsSnapshot | None:
    return db.scalar(
        select(HoldingsSnapshot)
        .options(selectinload(HoldingsSnapshot.positions))
        .where(HoldingsSnapshot.client_id == client_id)
        .order_by(HoldingsSnapshot.created_at.desc())
        .limit(1)
    )


def delete_holdings_snapshot(db: Session, snapshot: HoldingsSnapshot) -> None:
    db.delete(snapshot)
    db.commit()
