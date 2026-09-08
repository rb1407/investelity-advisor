"""SQLAlchemy models — the practice-management layer.

Two distinct kinds of "portfolio" live here, and keeping them separate is
the key design decision of this app:

- Portfolio / PortfolioHolding: a MODEL recommendation the optimizer
  produced (target weights from the curated universe) — what Portfolio
  Builder generates and saves.
- HoldingsSnapshot / HoldingsPosition: what a client ACTUALLY holds, as the
  consultant records it (dollar value per position, tagged with an asset
  class) — a dated snapshot, so a client can have many over time.

Rebalancing compares the two at the asset-class level (see
core/rebalancing/engine.py) — that's the "organizing" payoff: not just
generating a recommendation once, but tracking whether reality has drifted
away from it.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Consultant(Base):
    __tablename__ = "consultants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    firm_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    clients: Mapped[list["Client"]] = relationship(back_populates="consultant", cascade="all, delete-orphan")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consultant_id: Mapped[int] = mapped_column(ForeignKey("consultants.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Preferences / constraints used to generate recommendations
    risk_tolerance: Mapped[str] = mapped_column(String(32), default="moderate")  # conservative/moderate/aggressive/custom
    target_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    investment_horizon_years: Mapped[int] = mapped_column(Integer, default=10)
    initial_investment: Mapped[float] = mapped_column(Float, default=0.0)
    max_position_weight: Mapped[float] = mapped_column(Float, default=0.35)
    esg_focus: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded_tickers: Mapped[str] = mapped_column(Text, default="")  # comma-separated
    rebalance_threshold: Mapped[float] = mapped_column(Float, default=0.05)  # abs. asset-class drift that triggers a flag
    notes: Mapped[str] = mapped_column(Text, default="")

    consultant: Mapped["Consultant"] = relationship(back_populates="clients")
    portfolios: Mapped[list["Portfolio"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    holdings_snapshots: Mapped[list["HoldingsSnapshot"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )

    def excluded_tickers_list(self) -> list[str]:
        return [t.strip().upper() for t in self.excluded_tickers.split(",") if t.strip()]


class Portfolio(Base):
    """A saved MODEL recommendation (target weights), not actual holdings."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    label: Mapped[str] = mapped_column(String(128), default="")
    strategy: Mapped[str] = mapped_column(String(64))
    data_as_of: Mapped[str] = mapped_column(String(128), default="")

    expected_return: Mapped[float] = mapped_column(Float)
    expected_risk: Mapped[float] = mapped_column(Float)
    sharpe_ratio: Mapped[float] = mapped_column(Float)

    client: Mapped["Client"] = relationship(back_populates="portfolios")
    holdings: Mapped[list["PortfolioHolding"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioHolding(Base):
    """One target position (ticker + weight) within a saved recommendation."""

    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(128), default="")
    asset_class: Mapped[str] = mapped_column(String(64), default="")
    weight: Mapped[float] = mapped_column(Float)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")


class HoldingsSnapshot(Base):
    """What a client ACTUALLY held, as of a point in time. A client
    accumulates many of these over successive reviews."""

    __tablename__ = "holdings_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    label: Mapped[str] = mapped_column(String(128), default="")

    client: Mapped["Client"] = relationship(back_populates="holdings_snapshots")
    positions: Mapped[list["HoldingsPosition"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )

    def total_value(self) -> float:
        return sum(p.value for p in self.positions)


class HoldingsPosition(Base):
    """One actual position within a holdings snapshot: a ticker, the dollar
    value held, and the asset class it's tagged with (the common currency
    used to compare actual holdings against a model recommendation, since
    a client's real positions won't always be exactly the tickers in the
    house model universe)."""

    __tablename__ = "holdings_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("holdings_snapshots.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(128), default="")
    asset_class: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)

    snapshot: Mapped["HoldingsSnapshot"] = relationship(back_populates="positions")
