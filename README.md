# WKC-EcomDashboard

Multi-brand ecommerce performance dashboards for Wah Kong Corporation. Each brand gets its own
Streamlit app and its own database, kept fully isolated from the others; a small landing page
ties them together.

```
EcommerceDashboard/
├── Portal/         # Landing page -- brand tiles, click through to a brand's dashboard
├── SonyDashboard/  # Sony: Shopee / Lazada / TikTok Shop performance dashboard
└── <Brand>/        # Future brands (e.g. Tefal) go here as their own sibling folder
```

Each subfolder is a self-contained Streamlit project with its own `requirements.txt`, `.venv`,
and README -- see the folder for setup/run instructions.

## Adding a new brand

1. Copy `SonyDashboard/` as a starting point (the ingestion parsers are keyed to the
   **platform** export format -- Shopee/Lazada/TikTok -- not the brand, so they're reusable as-is
   unless the new brand's actual export files turn out to have their own quirks).
2. Swap the branding (logo, page title) and point it at a fresh, empty database.
3. Add one entry to `Portal/brands.py` with the new brand's logo and hosted URL.
