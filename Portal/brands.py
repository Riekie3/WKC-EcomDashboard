"""Brand registry for the portal. Add a new brand by adding one entry here --
nothing else in the app needs to change.

status: "live" shows the logo as a clickable tile linking to `url`.
        "coming_soon" shows a greyed-out placeholder tile (no link).
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
        # Published via Tailscale Funnel from the desktop -- requires the desktop to be on
        # and both `streamlit run Info.py` (SonyDashboard) and `tailscale funnel --bg 8501`
        # to be running. Password-gated (see SonyDashboard/.streamlit/secrets.toml).
        "url": "https://user20.tail672847.ts.net",
        "status": "live",
    },
    {
        "name": "Tefal",
        "logo": None,
        "url": None,
        "status": "coming_soon",
    },
]
