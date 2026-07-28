"""Brand registry for the portal. Add a new brand by adding one entry here --
nothing else in the app needs to change.

status: "live" shows the logo as a clickable tile linking to the brand's dashboard.
        "coming_soon" shows a greyed-out placeholder tile (no link).

url_local / url_public: the Portal picks whichever matches how *it* was accessed
(see resolve_url() in Home.py, via st.context.url) -- so clicking a tile from
localhost stays on localhost (fast, no Tailscale round-trip needed), while
clicking it from the public Tailscale URL goes to the brand's public URL.
"""
import os

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def _asset(filename: str) -> str:
    # Absolute path, independent of the process's working directory (which varies
    # depending on how `streamlit run` is invoked -- relative paths broke this before).
    return os.path.join(_ASSETS_DIR, filename)


BRANDS = [
    {
        "name": "Sony",
        "logo": _asset("sony_logo.webp"),
        "url_local": "http://localhost:8501",
        # Published via Tailscale Funnel from the desktop, on port 8443 (the Portal itself
        # uses the default 443) -- requires the desktop on, `streamlit run Info.py`
        # (SonyDashboard) running, and `tailscale funnel --bg --https=8443 8501` active.
        # Password-gated (see SonyDashboard/.streamlit/secrets.toml).
        "url_public": "https://user20.tail672847.ts.net:8443",
        "status": "live",
    },
    {
        "name": "Tefal",
        "logo": None,
        "url_local": None,
        "url_public": None,
        "status": "coming_soon",
    },
]
