import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.app_common import disclaimer, page_setup
from core.data_providers.universe import UNIVERSE
from core.db import crud
from core.db.session import get_session

ASSET_CLASSES = sorted({a.asset_class for a in UNIVERSE}) + ["Unclassified"]

consultant = page_setup("Holdings")
st.title("Holdings")
st.caption("Record what a client actually holds today — this is what Rebalancing compares against their saved target.")

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)
    if not clients:
        st.info("Add a client first on the **Clients** page.")
        st.stop()

    client = st.selectbox("Client", clients, format_func=lambda c: c.name)
    snapshots = crud.list_holdings_snapshots_for_client(db, client.id)

    tab_record, tab_history = st.tabs(["Record new snapshot", "History"])

    with tab_record:
        st.write(
            "Enter each position's ticker, asset class, and current dollar value — positions don't need to "
            "match the model universe exactly, since asset class is what's compared to the target on Rebalancing. "
            "Add or remove rows as needed."
        )
        default_rows = pd.DataFrame([{"Ticker": "", "Asset Class": ASSET_CLASSES[0], "Value": 0.0}])
        if snapshots and st.checkbox("Pre-fill from most recent snapshot", value=False):
            latest = snapshots[0]
            default_rows = pd.DataFrame(
                [{"Ticker": p.ticker, "Asset Class": p.asset_class, "Value": p.value} for p in latest.positions]
            )

        edited = st.data_editor(
            default_rows,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", required=True),
                "Asset Class": st.column_config.SelectboxColumn("Asset Class", options=ASSET_CLASSES, required=True),
                "Value": st.column_config.NumberColumn("Value ($)", min_value=0.0, step=1000.0, format="$%.2f"),
            },
            key=f"editor_{client.id}",
        )

        total = float(edited["Value"].fillna(0).sum()) if not edited.empty else 0.0
        st.metric("Total value", f"${total:,.0f}")

        label = st.text_input("Label for this snapshot", value="", placeholder="e.g. Q3 review")
        if st.button("Save snapshot", type="primary"):
            rows = edited.dropna(subset=["Ticker"])
            rows = rows[rows["Ticker"].astype(str).str.strip() != ""]
            if rows.empty:
                st.error("Add at least one position with a ticker and value.")
            else:
                positions = [
                    {
                        "ticker": str(r["Ticker"]).strip().upper(),
                        "name": str(r["Ticker"]).strip().upper(),
                        "asset_class": r["Asset Class"],
                        "value": float(r["Value"] or 0),
                    }
                    for _, r in rows.iterrows()
                ]
                crud.save_holdings_snapshot(db, client.id, label or "Holdings snapshot", positions)
                st.success("Saved.")
                st.rerun()

    with tab_history:
        if not snapshots:
            st.info(f"No recorded holdings for {client.name} yet — use the **Record new snapshot** tab.")
        else:
            hist_rows = [
                {
                    "Date": s.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Label": s.label or "Holdings snapshot",
                    "Total value": f"${s.total_value():,.0f}",
                    "Positions": len(s.positions),
                }
                for s in snapshots
            ]
            st.dataframe(hist_rows, use_container_width=True, hide_index=True)

            if len(snapshots) > 1:
                trend = go.Figure()
                trend.add_trace(
                    go.Scatter(
                        x=[s.created_at for s in reversed(snapshots)],
                        y=[s.total_value() for s in reversed(snapshots)],
                        mode="lines+markers",
                    )
                )
                trend.update_layout(height=280, yaxis_title="Total value ($)", margin=dict(t=10))
                st.plotly_chart(trend, use_container_width=True)

            st.divider()
            chosen = st.selectbox(
                "Inspect a snapshot",
                snapshots,
                format_func=lambda s: f"{s.created_at:%Y-%m-%d %H:%M} — {s.label or 'Holdings snapshot'}",
            )
            total_value = chosen.total_value()
            c1, c2 = st.columns([1, 1])
            with c1:
                table = [
                    {
                        "Ticker": p.ticker,
                        "Asset class": p.asset_class,
                        "Value": f"${p.value:,.0f}",
                        "Weight": f"{(p.value / total_value if total_value else 0):.1%}",
                    }
                    for p in sorted(chosen.positions, key=lambda p: -p.value)
                ]
                st.dataframe(table, use_container_width=True, hide_index=True)
            with c2:
                if chosen.positions:
                    by_class: dict[str, float] = {}
                    for p in chosen.positions:
                        by_class[p.asset_class] = by_class.get(p.asset_class, 0.0) + p.value
                    pie = go.Figure(data=[go.Pie(labels=list(by_class.keys()), values=list(by_class.values()), hole=0.4)])
                    pie.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(pie, use_container_width=True)

            if st.button("Delete this snapshot", type="secondary"):
                crud.delete_holdings_snapshot(db, chosen)
                st.success("Deleted.")
                st.rerun()

finally:
    db.close()

st.divider()
disclaimer()
