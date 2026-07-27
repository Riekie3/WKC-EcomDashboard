# EcommerceSonyDashboard

A consolidated performance dashboard for **Shopee**, **Lazada**, and **TikTok Shop** built with
Python (pandas + Streamlit). No platform APIs are used -- it ingests the Excel/CSV reports staff
already export manually from each platform's seller center, normalizes them into a shared
schema, and keeps a running history in a local SQLite database.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Running

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Uploading data

Go to the **Upload Data** page and drop in either:

- The whole export bundle as a `.zip` (the shape staff already produce, e.g. `marketplace export.zip`
  with `Shopee/`, `Lazada/`, `Tiktok/` folders inside), or
- Individual report files.

Files are matched to a platform and report type automatically by filename (e.g.
`net_data_daily_SHP.xlsx`, `product_performance_LZD.xls`, `ads_data_LZD.xlsx`). Unrecognized
files are skipped and listed, not silently ignored. Recognized files are parsed and shown as a
preview -- review the row counts and any warnings, then click **Confirm & Save to Dashboard** to
commit them. Data accumulates across uploads (nothing is overwritten), so re-uploading a fresh
export just adds the latest period to the history.

### Supported report types (per platform)

| Report type | Shopee | Lazada | TikTok Shop |
|---|---|---|---|
| Daily sales | `net_data_daily_SHP.xlsx` | `net_data_daily_LZD.xls` | `net_data_daily_TT.xlsx` |
| Product performance | `product_performance_SHP.xlsx` | `product_performance_LZD.xls` | `product_performance_TT.xlsx` |
| Ads performance | `ads_data_SHP.csv` | `ads_data_LZD.xlsx` | *(not currently exported)* |

TikTok's product performance report has ~176 columns; only the core metrics (name, GMV, units
sold, impressions/clicks/CTR) are ingested in this version -- the rest is intentionally out of
scope for now. Other platform-specific files (e.g. `AMS_*`, `sales_source_SHP.xlsx`) aren't wired
up yet.

## Dashboard pages

- **Sales Overview** -- revenue/orders/buyers KPIs and trend, filterable by date range and
  platform. Shopee's headline numbers use the Confirmed Order funnel stage (Placed/Paid are still
  stored and viewable in an expander).
- **Product Performance** -- top sellers by revenue per platform, from the latest uploaded batch.
- **Ads Performance** -- daily spend/ROAS for platforms that report it as a time series (Lazada),
  and campaign-level tables for platforms that report it per campaign (Shopee).
- **Data Management** -- delete a specific upload batch, delete by date range, or download a
  backup of the database file. Data is kept indefinitely by default (no automatic deletion) --
  use this page to correct a bad upload.

## Project layout

```
app.py                          # landing page
pages/                          # Streamlit pages (Upload, Sales, Product, Ads, Data Management)
src/
  config/schema.py              # canonical field names per fact table
  ingestion/
    transforms.py               # shared number/date/extras parsing helpers
    router.py                   # filename -> (platform, report_type) detection + parser lookup
    pipeline.py                 # zip expansion, parsing, validation for the Upload page
    parsers/{shopee,lazada,tiktok}.py   # one parser per platform, per real report structure
  storage/
    models.py                   # SQLAlchemy models (daily_sales, product_performance, ads_performance, upload_batches)
    db.py                       # SQLite engine/session
    repository.py                # insert/query/delete helpers
data/app.db                     # SQLite database (created on first run, not committed)
```

## Notes

- Data is retained indefinitely; there is no automatic cleanup. Use the Data Management page's
  backup button periodically, especially before large deletes.
- Hosting (local vs. Streamlit Community Cloud vs. an office server) is not yet decided -- nothing
  in the current design assumes one or the other.
