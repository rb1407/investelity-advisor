"""Minimal auth for a handful of consultant accounts.

Deliberately simple (bcrypt password hashing + a Streamlit session_state
flag) -- this is a demo for a handful of consultants, not a public-facing
product yet. Before a real launch, put this behind proper session/cookie
handling and add password-reset flows.
"""

import bcrypt
import streamlit as st
from sqlalchemy.orm import Session

from core.db.crud import get_consultant_by_username
from core.db.models import Consultant


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def current_consultant() -> Consultant | None:
    return st.session_state.get("consultant")


def login(db: Session, username: str, password: str) -> Consultant | None:
    consultant = get_consultant_by_username(db, username.strip())
    if consultant and verify_password(password, consultant.password_hash):
        st.session_state["consultant"] = consultant
        return consultant
    return None


def logout() -> None:
    st.session_state.pop("consultant", None)


def require_login() -> Consultant:
    consultant = current_consultant()
    if consultant is not None:
        return consultant

    st.title("Investelity Organizer — Sign in")
    st.caption("Portfolio recommendations, holdings tracking, and rebalancing for investment consultants")

    from core.db.session import get_session

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        db = get_session()
        try:
            consultant = login(db, username, password)
        finally:
            db.close()
        if consultant is not None:
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.info("Demo login — username: **demo**, password: **demo1234**")
    st.stop()
