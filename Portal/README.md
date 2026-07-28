# Portal

Landing page listing every brand's ecommerce dashboard. Click a brand's logo to open its
dedicated dashboard (each brand is its own separate Streamlit app + database, living as a
sibling folder in this repo -- see `../SonyDashboard` for the pattern).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Running

```bash
streamlit run Home.py
```

## Adding a new brand

Edit `brands.py` -- add one entry to the `BRANDS` list:

```python
{
    "name": "Tefal",
    "logo": "assets/tefal_logo.png",   # drop the logo file in assets/
    "url": "https://tefal-dashboard-url",
    "status": "live",
},
```

Until a brand's dashboard is ready, leave `"status": "coming_soon"` (and `logo`/`url` as
`None`) -- it'll show as a greyed-out placeholder tile instead of a link.

## Updating the Sony URL

`brands.py` currently points Sony at `http://localhost:8501` as a placeholder. Update it to
the real hosted URL once the Sony dashboard is published (e.g. a Tailscale Funnel URL).
