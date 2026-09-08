"""Cached price loading shared by every page (avoids re-fetching /
re-generating on every Streamlit rerun)."""

import streamlit as st

from core.data_providers.factory import get_provider
from core.data_providers.universe import TICKERS


@st.cache_data(ttl=3600, show_spinner="Loading market data...")
def load_prices():
    provider = get_provider()
    prices = provider.get_price_history(TICKERS, years=5)
    return prices, provider.as_of()
