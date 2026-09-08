import streamlit as st

from core.app_common import disclaimer, page_setup, sample_data_banner
from core.db import crud
from core.db.session import get_session
from core.market_data import load_prices
from core.rebalancing.engine import compute_drift, needs_rebalancing

consultant = page_setup("Home")

st.title("Investelity Organizer")
st.caption("Portfolio recommendations, holdings tracking, and rebalancing for investment consultants")
sample_data_banner()

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)
    total_portfolios = sum(len(c.portfolios) for c in clients)
    total_snapshots = sum(len(c.holdings_snapshots) for c in clients)
    total_aum = sum(
        (max(c.holdings_snapshots, key=lambda s: s.created_at).total_value() if c.holdings_snapshots else 0.0)
        for c in clients
    )

    alerts = []
    for c in clients:
        if not c.holdings_snapshots or not c.portfolios:
            continue
        latest_snapshot = max(c.holdings_snapshots, key=lambda s: s.created_at)
        latest_target = max(c.portfolios, key=lambda p: p.created_at)
        rows = compute_drift(latest_snapshot, latest_target)
        if needs_rebalancing(rows, c.rebalance_threshold):
            alerts.append(c.name)
finally:
    db.close()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Clients", len(clients))
col2.metric("Tracked AUM", f"${total_aum:,.0f}")
col3.metric("Saved recommendations", total_portfolios)
col4.metric("Needs rebalancing", len(alerts), delta=None if not alerts else f"{len(alerts)} client(s)", delta_color="inverse")

st.divider()

left, right = st.columns([2, 1])
with left:
    st.subheader("Your clients")
    if not clients:
        st.info("No clients yet — add your first one on the **Clients** page.")
    else:
        rows = [
            {
                "Client": c.name,
                "Risk tolerance": c.risk_tolerance.title(),
                "Tracked value": f"${max(c.holdings_snapshots, key=lambda s: s.created_at).total_value():,.0f}" if c.holdings_snapshots else "—",
                "Recommendations": len(c.portfolios),
                "Needs rebalancing": "⚠️ Yes" if c.name in alerts else "—",
            }
            for c in sorted(clients, key=lambda c: c.name)
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if alerts:
        st.warning(f"**Rebalancing flagged for:** {', '.join(alerts)} — see the Rebalancing page.", icon="⚖️")

with right:
    st.subheader("Get started")
    st.markdown(
        "1. Add a client and their risk preferences on **Clients**\n"
        "2. Generate and save a model recommendation on **Portfolio Builder**\n"
        "3. Record what they actually hold on **Holdings**\n"
        "4. Check drift and rebalancing needs on **Rebalancing**\n"
        "5. Review recommendation history on **Client History**"
    )
    prices, as_of = load_prices()
    st.caption(f"Model universe: {prices.shape[1]} assets · {as_of}")

st.divider()
disclaimer()
