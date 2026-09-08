"""Drift / rebalancing analysis.

Compares a client's ACTUAL holdings (a HoldingsSnapshot: dollar value per
position) against a TARGET model recommendation (a Portfolio: weights per
ticker), at the ASSET-CLASS level. Asset class is the common currency
because a client's real positions won't always be the exact tickers in the
house model universe (legacy positions, a fund from a previous advisor,
etc.) -- but "how much US equity vs. bonds vs. cash" is always comparable.

This is the core "organizing software" payoff: not just generating a
recommendation once, but being able to tell a consultant, at a glance,
which of their clients have drifted enough from plan to need a
conversation.
"""

from dataclasses import dataclass

from core.db.models import HoldingsSnapshot, Portfolio


@dataclass
class DriftRow:
    asset_class: str
    target_weight: float
    actual_weight: float

    @property
    def drift(self) -> float:
        """actual - target. Positive = overweight, negative = underweight."""
        return self.actual_weight - self.target_weight

    def suggested_trade(self, total_value: float) -> float:
        """Dollar amount to trade to close the gap. Positive = sell this
        much of the asset class, negative = buy this much."""
        return self.drift * total_value


def actual_weights_by_asset_class(snapshot: HoldingsSnapshot) -> dict[str, float]:
    total = snapshot.total_value()
    if total <= 0:
        return {}
    weights: dict[str, float] = {}
    for p in snapshot.positions:
        weights[p.asset_class] = weights.get(p.asset_class, 0.0) + p.value / total
    return weights


def target_weights_by_asset_class(portfolio: Portfolio) -> dict[str, float]:
    weights: dict[str, float] = {}
    for h in portfolio.holdings:
        cls = h.asset_class or "Unclassified"
        weights[cls] = weights.get(cls, 0.0) + h.weight
    return weights


def compute_drift(snapshot: HoldingsSnapshot, target: Portfolio) -> list[DriftRow]:
    actual = actual_weights_by_asset_class(snapshot)
    target_w = target_weights_by_asset_class(target)
    all_classes = sorted(set(actual) | set(target_w))
    return [
        DriftRow(asset_class=cls, target_weight=target_w.get(cls, 0.0), actual_weight=actual.get(cls, 0.0))
        for cls in all_classes
    ]


def needs_rebalancing(rows: list[DriftRow], threshold: float) -> bool:
    return any(abs(r.drift) > threshold for r in rows)


def max_drift(rows: list[DriftRow]) -> float:
    return max((abs(r.drift) for r in rows), default=0.0)
