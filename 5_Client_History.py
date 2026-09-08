import plotly.graph_objects as go
import streamlit as st

from core.app_common import disclaimer, page_setup
from core.db import crud
from core.db.session import get_session

consultant = page_setup("Client History")
st.title("Client History")
st.caption("Every model recommendation you've saved for a client, in one place — the record you can pull up before a review meeting.")

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)
    if not clients:
        st.info("Add a client first on the **Clients** page.")
        st.stop()

    client = st.selectbox("Client", clients, format_func=lambda c: c.name)
    portfolios = crud.list_portfolios_for_client(db, client.id)

    if not portfolios:
        st.info(f"No saved recommendations for {client.name} yet — build one on **Portfolio Builder**.")
        st.stop()

    st.subheader("History")
    rows = [
        {
            "Date": p.created_at.strftime("%Y-%m-%d %H:%M"),
            "Label": p.label or p.strategy,
            "Strategy": p.strategy,
            "Return": f"{p.expected_return:.1%}",
            "Risk": f"{p.expected_risk:.1%}",
            "Sharpe": f"{p.sharpe_ratio:.2f}",
        }
        for p in portfolios
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Inspect a saved recommendation")
    chosen = st.selectbox(
        "Recommendation",
        portfolios,
        format_func=lambda p: f"{p.created_at:%Y-%m-%d %H:%M} — {p.label or p.strategy}",
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Expected return", f"{chosen.expected_return:.1%}")
    m2.metric("Expected risk", f"{chosen.expected_risk:.1%}")
    m3.metric("Sharpe ratio", f"{chosen.sharpe_ratio:.2f}")
    st.caption(f"Data source: {chosen.data_as_of}")

    c1, c2 = st.columns([1, 1])
    with c1:
        table = [
            {"Ticker": h.ticker, "Name": h.name, "Asset class": h.asset_class, "Weight": f"{h.weight:.1%}"}
            for h in sorted(chosen.holdings, key=lambda h: -h.weight)
        ]
        st.dataframe(table, use_container_width=True, hide_index=True)
    with c2:
        pie = go.Figure(
            data=[go.Pie(labels=[h.ticker for h in chosen.holdings], values=[h.weight for h in chosen.holdings], hole=0.4)]
        )
        pie.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(pie, use_container_width=True)

    csv = "\n".join(
        ["Ticker,Name,Asset Class,Weight"]
        + [f"{h.ticker},{h.name},{h.asset_class},{h.weight:.4f}" for h in chosen.holdings]
    )
    st.download_button(
        "Download as CSV",
        data=csv,
        file_name=f"{client.name.replace(' ', '_')}_{chosen.strategy.replace(' ', '_')}.csv",
        mime="text/csv",
    )

finally:
    db.close()

st.divider()
disclaimer()
