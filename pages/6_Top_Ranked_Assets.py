import pandas as pd
import streamlit as st

from core.app_common import disclaimer, page_setup
from core.data_providers.investelity_rankings import (
    data_available,
    list_countries,
    load_market_overview,
    load_rankings,
    period_label,
)

page_setup("Top Ranked Assets")
st.title("Top Ranked Assets")
st.caption(
    "Individual stocks and funds ranked by risk-adjusted return (Sharpe ratio), by country -- "
    "straight from the investelity data pipeline, not the model-portfolio universe used elsewhere in this app."
)

if not data_available():
    st.info(
        "No investelity ranking data is bundled with this deployment yet. Copy the pipeline's "
        "`final/1y/<month>_<year>/` and `final/3y/<month>_<year>/` CSVs into `data/investelity/1y/` "
        "and `data/investelity/3y/`, set `data/investelity/meta.txt`, and redeploy."
    )
    st.stop()

st.caption(f"Pipeline data as of: **{period_label()}**")

col_period, col_country, col_search = st.columns([1, 2, 2])
with col_period:
    period = st.radio("Trailing period", ["3y", "1y"], horizontal=True)
with col_country:
    countries = list_countries(period)
    if not countries:
        st.warning(f"No countries found for period {period}.")
        st.stop()
    default_idx = next((i for i, (code, _) in enumerate(countries) if code == "us"), 0)
    code, name = st.selectbox(
        "Country / bucket",
        countries,
        index=default_idx,
        format_func=lambda pair: pair[1],
    )
with col_search:
    query = st.text_input("Filter by name or ticker", placeholder="e.g. Apple, or AAPL")

df = load_rankings(period, code)

if df.empty:
    st.info(f"No ranked assets available for {name} ({period}).")
    st.stop()

if query:
    mask = df["Name"].str.contains(query, case=False, na=False) | df["Ticker"].str.contains(query, case=False, na=False)
    view = df[mask]
    if view.empty:
        st.warning(f"No name or ticker matches \"{query}\" in {name} ({period}).")
else:
    view = df

m1, m2, m3, m4 = st.columns(4)
m1.metric("Ranked assets", f"{len(df):,}")
m2.metric("Top annualized return", f"{df['Return (%)'].max():.1f}%" if not df.empty else "—")
m3.metric("Median risk (ann. std dev)", f"{df['Risk'].median():.3f}" if not df.empty else "—")
have_beta = df["Volatility"].notna().sum()
m4.metric("With beta vs. index", f"{have_beta:,} / {len(df):,}")

st.caption(
    "**Volatility** here is beta vs. the country's own market index (not annualized risk — that's the "
    "**Risk** column). It's blank for a given ticker when there wasn't enough overlapping history against "
    "the index to compute a meaningful beta, and blank for every ticker in a country when the index itself "
    "wasn't available in the pipeline's price data — either way, not missing data on our end."
)

n_view = len(view)
if n_view <= 10:
    # st.slider requires min_value != max_value -- with 10 or fewer matching
    # rows (a narrow search, or a small country) there's nothing meaningful
    # to adjust, so just show all of them without a slider.
    top_n = n_view
else:
    top_n = st.slider("Rows to show", min_value=10, max_value=min(2000, n_view), value=min(50, n_view), step=10)

st.dataframe(
    view.head(top_n),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Rank": st.column_config.NumberColumn("Rank", width="small"),
        "Return (%)": st.column_config.NumberColumn("Return (%)", format="%.2f%%"),
        "Risk": st.column_config.NumberColumn("Risk", format="%.3f"),
        "Volatility": st.column_config.NumberColumn("Beta vs. index", format="%.3f"),
    },
)
if len(view) > top_n:
    st.caption(f"Showing {top_n:,} of {len(view):,} matching rows — raise the slider above to see more.")

with st.expander("Country market index performance (all countries, this period)"):
    overview = load_market_overview(period)
    if overview.empty:
        st.caption("No market index overview available for this period.")
    else:
        st.dataframe(
            overview,
            use_container_width=True,
            hide_index=True,
            column_config={"Return (%)": st.column_config.NumberColumn("Return (%)", format="%.2f%%")},
        )
        if code != "usf":
            row = overview[overview["ISO Code"] == code]
            if not row.empty:
                r = row.iloc[0]
                # A country's index can itself be un-rankable for the period
                # (e.g. too little Sharpe-ratio data to place it), leaving
                # Rank/Return/Risk blank in markets.csv for that row -- guard
                # each field rather than assume they're always populated.
                rank_part = f"ranked #{int(r['Rank'])} of {len(overview)}" if pd.notna(r["Rank"]) else "wasn't ranked"
                return_part = f", return {r['Return (%)']:.2f}%" if pd.notna(r["Return (%)"]) else ""
                st.caption(f"**{name}**'s index ({r['Market Index Name']}) {rank_part} this period{return_part}.")

st.divider()
disclaimer()
