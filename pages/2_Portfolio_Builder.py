import plotly.graph_objects as go
import streamlit as st

from core.app_common import disclaimer, page_setup, sample_data_banner
from core.data_providers.universe import ASSET_BY_TICKER, esg_excluded_tickers
from core.data_providers.investelity_universe import (
    TOP_N,
    asset_meta_for,
    list_countries,
    load_top_prices,
    period_label,
    top_assets,
    universe_available,
)
from core.db import crud
from core.db.session import get_session
from core.market_data import load_prices
from core.optimization.engine import STRATEGY_FOR_RISK_TOLERANCE, OptimizationInputs, PortfolioOptimizer

STRATEGY_LABELS = {
    "minimum_variance": "Minimum Variance",
    "maximum_sharpe": "Maximum Sharpe Ratio",
    "maximum_return": "Maximum Return",
    "target_risk": "Target Risk (custom)",
}

consultant = page_setup("Portfolio Builder")
st.title("Portfolio Builder")
st.caption("Generate a MODEL recommendation — the target you'll compare actual holdings against on the Rebalancing page.")

st.subheader("Universe")
universe_options = ["Model ETFs"]
if universe_available():
    universe_options.append("Investelity Top Picks")
universe_choice = st.radio(
    "Build this recommendation from",
    universe_options,
    horizontal=True,
    help=(
        "**Model ETFs** — the curated 17-fund asset-allocation universe used elsewhere in this app. "
        f"**Investelity Top Picks** — individual stocks/funds from the investelity pipeline's own "
        f"Sharpe-ratio ranking, top {TOP_N} per country/bucket (kept small so the optimizer stays as "
        "stable as it is on the ETF universe — see core/data_providers/investelity_universe.py)."
    ),
)

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)
    if not clients:
        st.info("Add a client first on the **Clients** page.")
        st.stop()

    client = st.selectbox("Client", clients, format_func=lambda c: c.name)

    if universe_choice == "Investelity Top Picks":
        col_period, col_country = st.columns(2)
        with col_period:
            inv_period = st.radio("Trailing period", ["3y", "1y"], horizontal=True, key="inv_period")
        with col_country:
            countries = list_countries(inv_period)
            default_idx = next((i for i, (c, _) in enumerate(countries) if c == "us"), 0)
            inv_code, inv_name = st.selectbox(
                "Country / bucket", countries, index=default_idx, format_func=lambda p: p[1], key="inv_country",
            )
        prices = load_top_prices(inv_period, inv_code)
        if prices.empty or prices.shape[1] < 2:
            st.warning(
                f"Not enough price history for {inv_name} ({inv_period}) to build a portfolio -- "
                "pick another country or period."
            )
            st.stop()
        as_of = (
            f"Investelity pipeline — {period_label()}, top {prices.shape[1]} by Sharpe in "
            f"{inv_name} ({inv_period} lookback)"
        )
        asset_meta = asset_meta_for(inv_period, inv_code)
        # The ESG bucket in universe.py is a placeholder screen defined for the
        # 17 model ETFs specifically (see its docstring) -- it doesn't apply to
        # investelity's individual stocks, so only per-ticker exclusions carry
        # over to this universe.
        exclusions = set(client.excluded_tickers_list())
        st.caption(f"Building from {prices.shape[1]} tickers in {inv_name} — {as_of}.")
        st.warning(
            "These tickers are investelity's own top performers **by trailing Sharpe ratio** over "
            f"just the last {inv_period[0]} year{'s' if inv_period[0] != '1' else ''} of monthly prices. "
            "Building a portfolio out of an already Sharpe-ranked shortlist means the return/Sharpe "
            "numbers below will look unusually strong on paper — that's the ranking's selection bias "
            "showing up, not a forecast of what these picks will do going forward. Treat this universe "
            "as illustrative, and prefer the Model ETF universe for numbers you'd put in front of a client.",
            icon="⚠️",
        )
    else:
        sample_data_banner()
        prices, as_of = load_prices()
        asset_meta = ASSET_BY_TICKER
        exclusions = set(client.excluded_tickers_list())
        if client.esg_focus:
            exclusions |= set(esg_excluded_tickers())

    with st.expander("Effective constraints for this client", expanded=False):
        st.write(f"**Risk tolerance:** {client.risk_tolerance.title()}")
        st.write(f"**Max position weight:** {client.max_position_weight:.0%}")
        st.write(f"**Excluded assets:** {', '.join(sorted(exclusions)) or 'none'}")

    optimizer = PortfolioOptimizer(
        OptimizationInputs(prices=prices, excluded_tickers=list(exclusions), max_weight=client.max_position_weight)
    )
    min_risk, max_risk = optimizer.risk_bounds()

    default_strategy = STRATEGY_FOR_RISK_TOLERANCE.get(client.risk_tolerance, "maximum_sharpe")

    st.subheader("Strategy")
    mode = st.radio("View", ["Recommended strategy", "Compare all strategies"], horizontal=True)

    target_vol = None
    if default_strategy == "target_risk" or mode == "Compare all strategies":
        target_vol = st.slider(
            "Target annualized risk", min_value=float(min_risk), max_value=float(max_risk),
            value=float(min(max(client.target_risk or (min_risk + max_risk) / 2, min_risk), max_risk)),
            step=0.005,
        )

    def run_strategy(key: str):
        if key == "minimum_variance":
            return optimizer.minimum_variance()
        if key == "maximum_sharpe":
            return optimizer.maximum_sharpe()
        if key == "maximum_return":
            return optimizer.maximum_return()
        return optimizer.target_risk(target_vol if target_vol is not None else (min_risk + max_risk) / 2)

    if mode == "Recommended strategy":
        strategy_key = st.selectbox(
            "Strategy", list(STRATEGY_LABELS.keys()), index=list(STRATEGY_LABELS.keys()).index(default_strategy),
            format_func=lambda k: STRATEGY_LABELS[k] + ("  (recommended)" if k == default_strategy else ""),
        )
        results = [run_strategy(strategy_key)]
    else:
        results = optimizer.compare_all(target_volatility=target_vol)

    curve = optimizer.efficient_frontier_curve()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["risk"], y=curve["return"], mode="lines", name="Efficient frontier"))
    for r in results:
        fig.add_trace(
            go.Scatter(
                x=[r.expected_risk], y=[r.expected_return], mode="markers+text",
                marker=dict(size=14), text=[r.strategy], textposition="top center", name=r.strategy,
            )
        )
    fig.update_layout(
        xaxis_title="Expected annualized risk (volatility)", yaxis_title="Expected annualized return",
        xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=420, legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # A real, diversified portfolio's Sharpe ratio essentially never holds
    # above ~3-4 out of sample. Above that, the number is reflecting
    # estimation noise (a short history) or, for the investelity universe,
    # the fact that the tickers were themselves pre-selected by trailing
    # Sharpe -- so it's flagged inline rather than presented at face value.
    UNSTABLE_SHARPE = 5.0

    for r in results:
        st.markdown(f"### {r.strategy}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Expected return", f"{r.expected_return:.1%}")
        m2.metric("Expected risk", f"{r.expected_risk:.1%}")
        m3.metric("Sharpe ratio", f"{r.sharpe_ratio:.2f}")
        if r.sharpe_ratio > UNSTABLE_SHARPE:
            m3.caption("⚠️ Unusually high — treat as an unstable estimate, not a forecast.")

        c1, c2 = st.columns([1, 1])
        with c1:
            table = r.as_table()
            table["Asset class"] = table["Ticker"].map(lambda t: asset_meta[t].asset_class)
            table["Name"] = table["Ticker"].map(lambda t: asset_meta[t].name)
            table["Weight"] = table["Weight"].map(lambda w: f"{w:.1%}")
            st.dataframe(table[["Ticker", "Name", "Asset class", "Weight"]], use_container_width=True, hide_index=True)
        with c2:
            pie = go.Figure(data=[go.Pie(labels=list(r.weights.keys()), values=list(r.weights.values()), hole=0.4)])
            pie.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(pie, use_container_width=True)

        with st.form(f"save_{r.strategy}_{client.id}"):
            label = st.text_input("Label for this recommendation", value=f"{r.strategy} — {client.name}", key=f"label_{r.strategy}")
            save = st.form_submit_button(f"Save this as {client.name}'s target")
        if save:
            crud.save_portfolio(db, client.id, r, data_as_of=as_of, label=label, asset_meta=asset_meta)
            st.success("Saved — this becomes the target used on the Rebalancing page (most recent recommendation wins).")

finally:
    db.close()

st.divider()
disclaimer()
