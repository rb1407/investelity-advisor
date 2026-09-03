import streamlit as st

from core.app_common import disclaimer, page_setup, sample_data_banner
from core.db import crud
from core.db.session import get_session
from core.market_data import load_prices

consultant = page_setup("Home")

st.title("Investelity Advisor")
st.caption("Portfolio construction & client organizer for investment consultants")
sample_data_banner()

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)
    total_portfolios = sum(len(c.portfolios) for c in clients)
finally:
    db.close()

col1, col2, col3 = st.columns(3)
col1.metric("Clients", len(clients))
col2.metric("Saved portfolios", total_portfolios)
prices, as_of = load_prices()
col3.metric("Assets in universe", prices.shape[1])

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
                "Saved portfolios": len(c.portfolios),
                "Last updated": c.portfolios[0].created_at.strftime("%Y-%m-%d") if c.portfolios else "—",
            }
            for c in sorted(clients, key=lambda c: c.name)
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

with right:
    st.subheader("Get started")
    st.markdown(
        "1. Add a client and their risk preferences on **Clients**\n"
        "2. Generate and compare portfolio strategies on **Portfolio Builder**\n"
        "3. Save the recommendation and track it over time on **Client History**"
    )

st.divider()
disclaimer()
