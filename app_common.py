"""Shared UI chrome used by every page: sidebar identity/logout, the data
source banner, and the compliance disclaimer."""

import streamlit as st

from core.auth.auth import current_consultant, logout, require_login
from core.data_providers.cache import read_cache_meta
from core.data_providers.factory import get_provider
from core.db.session import init_db
from core.seed import seed


DISCLAIMER = (
    "For illustrative and internal-research purposes only. Model output is not "
    "personalized investment advice and does not account for a client's complete "
    "financial situation, tax position, or account-level restrictions. Review with "
    "your firm's compliance requirements before presenting to a client."
)


@st.cache_resource
def _ensure_db_ready() -> bool:
    """Runs once per running app process — initializes tables and seeds the
    demo account. Doing this here (rather than a separate setup script)
    means a hosted deployment with no shell access still comes up ready to
    use."""
    init_db()
    seed()
    return True


def page_setup(title: str) -> "Consultant":  # noqa: F821
    st.set_page_config(page_title=f"{title} · Investelity Organizer", layout="wide")
    _ensure_db_ready()
    consultant = require_login()

    with st.sidebar:
        st.markdown(f"**{consultant.name}**")
        if consultant.firm_name:
            st.caption(consultant.firm_name)
        if st.button("Log out", use_container_width=True):
            logout()
            st.rerun()
        st.divider()
        st.caption(f"Market data: {_data_freshness_label()}")

    return consultant


def disclaimer() -> None:
    st.caption(f"⚠️ {DISCLAIMER}")


def _data_freshness_label() -> str:
    cached = read_cache_meta()
    if cached and cached != "No cached data yet":
        return cached.splitlines()[0]
    return get_provider().as_of()


def sample_data_banner() -> None:
    label = _data_freshness_label()
    if label and "sample" in label.lower():
        st.warning(
            "This workspace is running on **sample/synthetic market data** "
            "(no real prices) — see the sidebar and README. Run "
            "`scripts/refresh_market_data.py` on a machine with normal internet "
            "access to pull real prices before using this with an actual client.",
            icon="🧪",
        )
