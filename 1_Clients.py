import streamlit as st

from core.app_common import disclaimer, page_setup
from core.data_providers.universe import UNIVERSE
from core.db import crud
from core.db.session import get_session

consultant = page_setup("Clients")
st.title("Clients")
st.caption("Your roster — preferences and constraints saved here drive recommendations and rebalancing checks.")

db = get_session()
try:
    clients = crud.list_clients(db, consultant.id)

    tab_roster, tab_new = st.tabs(["Roster", "Add new client"])

    with tab_roster:
        if not clients:
            st.info("No clients yet. Use the **Add new client** tab.")
        for client in clients:
            with st.expander(f"**{client.name}** — {client.risk_tolerance.title()}"):
                with st.form(f"edit_{client.id}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Name", value=client.name)
                        email = st.text_input("Email", value=client.email)
                        horizon = st.number_input(
                            "Investment horizon (years)", min_value=1, max_value=50,
                            value=client.investment_horizon_years,
                        )
                        initial = st.number_input(
                            "Initial investment ($)", min_value=0.0, value=client.initial_investment, step=1000.0
                        )
                    with c2:
                        risk_tolerance = st.selectbox(
                            "Risk tolerance",
                            ["conservative", "moderate", "aggressive", "custom"],
                            index=["conservative", "moderate", "aggressive", "custom"].index(client.risk_tolerance),
                        )
                        target_risk = st.slider(
                            "Target annualized risk (if custom)", 0.01, 0.30,
                            value=client.target_risk or 0.10, step=0.01,
                            disabled=risk_tolerance != "custom",
                        )
                        max_weight = st.slider(
                            "Max weight per position", 0.10, 1.0, value=client.max_position_weight, step=0.05
                        )
                        rebalance_threshold = st.slider(
                            "Rebalancing alert threshold (asset-class drift)", 0.02, 0.20,
                            value=client.rebalance_threshold, step=0.01,
                            help="Flag this client for rebalancing when any asset class drifts from target by more than this.",
                        )
                        esg_focus = st.checkbox("ESG focus (excludes commodities/high-yield)", value=client.esg_focus)

                    exclude_options = [a.ticker for a in UNIVERSE]
                    excluded = st.multiselect(
                        "Additional exclusions (model universe)", exclude_options, default=client.excluded_tickers_list(),
                        format_func=lambda t: f"{t} — {next(a.name for a in UNIVERSE if a.ticker == t)}",
                    )
                    notes = st.text_area("Notes", value=client.notes)

                    save_col, delete_col = st.columns([1, 1])
                    saved = save_col.form_submit_button("Save changes", use_container_width=True)
                    deleted = delete_col.form_submit_button("Delete client", use_container_width=True, type="secondary")

                if saved:
                    crud.update_client(
                        db, client,
                        name=name, email=email, investment_horizon_years=horizon,
                        initial_investment=initial, risk_tolerance=risk_tolerance,
                        target_risk=target_risk, max_position_weight=max_weight,
                        rebalance_threshold=rebalance_threshold,
                        esg_focus=esg_focus, excluded_tickers=",".join(excluded), notes=notes,
                    )
                    st.success("Saved.")
                    st.rerun()
                if deleted:
                    crud.delete_client(db, client)
                    st.success("Deleted.")
                    st.rerun()

    with tab_new:
        with st.form("new_client"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name*")
                email = st.text_input("Email")
                horizon = st.number_input("Investment horizon (years)", min_value=1, max_value=50, value=10)
                initial = st.number_input("Initial investment ($)", min_value=0.0, value=0.0, step=1000.0)
            with c2:
                risk_tolerance = st.selectbox("Risk tolerance", ["conservative", "moderate", "aggressive", "custom"])
                target_risk = st.slider("Target annualized risk (if custom)", 0.01, 0.30, value=0.10, step=0.01)
                max_weight = st.slider("Max weight per position", 0.10, 1.0, value=0.35, step=0.05)
                rebalance_threshold = st.slider(
                    "Rebalancing alert threshold (asset-class drift)", 0.02, 0.20, value=0.05, step=0.01
                )
                esg_focus = st.checkbox("ESG focus (excludes commodities/high-yield)", value=False)

            excluded = st.multiselect(
                "Additional exclusions (model universe)", [a.ticker for a in UNIVERSE],
                format_func=lambda t: f"{t} — {next(a.name for a in UNIVERSE if a.ticker == t)}",
            )
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add client", use_container_width=True)

        if submitted:
            if not name.strip():
                st.error("Name is required.")
            else:
                crud.create_client(
                    db, consultant.id,
                    name=name.strip(), email=email, investment_horizon_years=horizon,
                    initial_investment=initial, risk_tolerance=risk_tolerance,
                    target_risk=target_risk, max_position_weight=max_weight,
                    rebalance_threshold=rebalance_threshold,
                    esg_focus=esg_focus, excluded_tickers=",".join(excluded), notes=notes,
                )
                st.success(f"Added {name}.")
                st.rerun()
finally:
    db.close()

st.divider()
disclaimer()
