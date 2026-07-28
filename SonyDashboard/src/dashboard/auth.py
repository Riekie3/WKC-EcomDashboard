import streamlit as st


def require_login():
    """Gate the whole app behind a single shared password stored in
    .streamlit/secrets.toml (never committed -- see secrets.toml.example).
    Call this first thing on every page, since Streamlit's multipage nav lets
    someone navigate straight to a page URL, bypassing checks only on Info.py.
    """
    if st.session_state.get("authenticated"):
        return

    try:
        correct_password = st.secrets.get("password")
    except Exception:
        correct_password = None

    if not correct_password:
        st.error(
            "No password configured. Create `.streamlit/secrets.toml` with "
            '`password = "..."` before running this app (see secrets.toml.example).'
        )
        st.stop()

    st.title("🔒 Sign in")
    password = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        if password == correct_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
