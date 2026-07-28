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
        # TODO: replace with the real hosted URL once the Sony dashboard is published
        # (e.g. a Tailscale Funnel URL like https://your-desktop.your-tailnet.ts.net)
        "url": "http://localhost:8501",
        "status": "live",
    },
    {
        "name": "Tefal",
        "logo": None,
        "url": None,
        "status": "coming_soon",
    },
]
