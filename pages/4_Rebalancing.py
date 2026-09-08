import plotly.graph_objects as go
import streamlit as st

from core.app_common import disclaimer, page_setup
from core.db import crud
from core.db.session import get_session
from core.rebalancing.engine import compute_drift, max_drift, needs_rebalancing

consultant = page_setup("Rebalancing")
st.title("Rebalancing")
st.caption("Compares each client's most recent recorded holdings against their most recent saved target, by asset class.")

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)
    if not clients:
        st.info("Add a client first on the **Clients** page.")
        st.stop()

    client = st.selectbox("Client", clients, format_func=lambda c: c.name)

    portfolios = crud.list_portfolios_for_client(db, client.id)
    snapshots = crud.list_holdings_snapshots_for_client(db, client.id)

    if not portfolios:
        st.info(f"No saved target for {client.name} yet — generate one on **Portfolio Builder**.")
        st.stop()
    if not snapshots:
        st.info(f"No recorded holdings for {client.name} yet — record one on **Holdings**.")
        st.stop()

    target = portfolios[0]  # list_portfolios_for_client is ordered most-recent-first
    snapshot = snapshots[0]  # list_holdings_snapshots_for_client is ordered most-recent-first

    st.caption(
        f"Target: **{target.label or target.strategy}** (saved {target.created_at:%Y-%m-%d}) · "
        f"Holdings: **{snapshot.label or 'Holdings snapshot'}** (recorded {snapshot.created_at:%Y-%m-%d}, "
        f"${snapshot.total_value():,.0f})"
    )

    rows = compute_drift(snapshot, target)
    flagged = needs_rebalancing(rows, client.rebalance_threshold)
    worst = max_drift(rows)

    m1, m2, m3 = st.columns(3)
    m1.metric("Largest drift", f"{worst:.1%}")
    m2.metric("Alert threshold", f"{client.rebalance_threshold:.0%}")
    m3.metric("Status", "⚠️ Rebalance" if flagged else "✅ On target")

    if flagged:
        st.warning(
            f"One or more asset classes have drifted more than {client.rebalance_threshold:.0%} from target — "
            "consider a rebalancing trade.",
            icon="⚖️",
        )
    else:
        st.success("All asset classes are within the alert threshold of target.", icon="✅")

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Target", x=[r.asset_class for r in rows], y=[r.target_weight for r in rows]))
    fig.add_trace(go.Bar(name="Actual", x=[r.asset_class for r in rows], y=[r.actual_weight for r in rows]))
    fig.update_layout(barmode="group", yaxis_tickformat=".0%", height=380, legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Drift detail")
    total_value = snapshot.total_value()
    table = [
        {
            "Asset class": r.asset_class,
            "Target": f"{r.target_weight:.1%}",
            "Actual": f"{r.actual_weight:.1%}",
            "Drift": f"{r.drift:+.1%}",
            "Suggested trade": (
                f"Sell ${r.suggested_trade(total_value):,.0f}"
                if r.drift > 0.001
                else (f"Buy ${-r.suggested_trade(total_value):,.0f}" if r.drift < -0.001 else "—")
            ),
            "Flagged": "⚠️" if abs(r.drift) > client.rebalance_threshold else "",
        }
        for r in sorted(rows, key=lambda r: -abs(r.drift))
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)

    if len(snapshots) > 1:
        with st.expander("Compare against an earlier holdings snapshot instead"):
            alt_snapshot = st.selectbox(
                "Snapshot",
                snapshots,
                format_func=lambda s: f"{s.created_at:%Y-%m-%d %H:%M} — {s.label or 'Holdings snapshot'}",
                key="alt_snapshot",
            )
            if alt_snapshot.id != snapshot.id:
                alt_rows = compute_drift(alt_snapshot, target)
                alt_table = [
                    {
                        "Asset class": r.asset_class,
                        "Target": f"{r.target_weight:.1%}",
                        "Actual": f"{r.actual_weight:.1%}",
                        "Drift": f"{r.drift:+.1%}",
                    }
                    for r in sorted(alt_rows, key=lambda r: -abs(r.drift))
                ]
                st.dataframe(alt_table, use_container_width=True, hide_index=True)

finally:
    db.close()

st.divider()
disclaimer()
