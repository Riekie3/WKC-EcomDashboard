# SonyDashboard

A consolidated performance dashboard for **Shopee**, **Lazada**, and **TikTok Shop** built with
Python (pandas + Streamlit). No platform APIs are used -- it ingests the Excel/CSV reports staff
already export manually from each platform's seller center, normalizes them into a shared
schema, and keeps a running history in a local SQLite database.

Part of the [WKC-EcomDashboard](https://github.com/Riekie3/WKC-EcomDashboard) monorepo -- see
`../Portal` for the multi-brand landing page this dashboard is linked from.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Running

```bash
streamlit run Info.py
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
| Ads performance (paid CPC) | `ads_data_SHP.csv` | `ads_data_LZD.xlsx` | *(not currently exported)* |
| Affiliate / commission marketing | `AMS_SHP.csv` | *(not currently exported)* | `AMS_TT.xlsx` |
| Traffic-source breakdown by product | `sales_source_SHP.xlsx` | *(not currently exported)* | *(not currently exported)* |
| Creator / affiliate leaderboard | *(not currently exported)* | *(not currently exported)* | `AMS_TT_Aff.xlsx` |

TikTok's product performance report has ~176 columns; only the core metrics (name, GMV, units
sold, impressions/clicks/CTR) are ingested in this version -- the remaining ~166 columns
(LIVE/video/affiliate segment breakdowns) are intentionally not captured at all yet (not even in
`extra_metrics`), per the approved "core metrics only" scoping decision. Other parsers' unmapped
columns (Shopee, Lazada, TikTok's other report types) are captured in each row's `extra_metrics`
JSON field even though most aren't surfaced on a chart yet.

## Dashboard pages

- **Sales Overview** -- revenue/orders/buyers KPIs and trend, filterable by date range and
  platform. Shopee's headline numbers use the Confirmed Order funnel stage (Placed/Paid are still
  stored and viewable in an expander).
- **Product Performance** -- top sellers by revenue per platform, from the latest uploaded batch.
- **Ads Performance** -- daily spend/ROAS for platforms that report it as a time series (Lazada),
  and campaign-level tables for platforms that report it per campaign (Shopee).
- **Affiliate & Marketing** -- commission-based / creator-driven performance, separate from paid
  CPC ads: per-product affiliate commission (Shopee, TikTok), Shopee's traffic-source-by-product
  breakdown, and TikTok's creator/affiliate leaderboard.
- **Data Management** -- delete a specific upload batch, delete by date range, download a backup
  of the database file, restore from a previously downloaded backup (replaces all current data --
  requires confirmation), or erase everything (requires typing "ERASE" to confirm). Data is kept
  indefinitely by default (no automatic deletion).

## Project layout

```
Info.py                         # landing page (sidebar nav label: "Info")
pages/                          # Streamlit pages (Upload, Sales, Product, Ads, Affiliate & Marketing, Data Management)
src/
  config/schema.py              # canonical field names per fact table
  ingestion/
    transforms.py               # shared number/date/extras parsing helpers
    router.py                   # filename -> (platform, report_type) detection + parser lookup
    pipeline.py                 # zip expansion, parsing, validation for the Upload page
    parsers/{shopee,lazada,tiktok}.py   # one parser per platform, per real report structure
  storage/
    models.py                   # SQLAlchemy models (daily_sales, product_performance, ads_performance,
                                 #   affiliate_marketing, traffic_source_performance, creator_performance, upload_batches)
    db.py                       # SQLite engine/session
    repository.py                # insert/query/delete helpers
data/app.db                     # SQLite database (created on first run, not committed)
```

## Notes

- Data is retained indefinitely; there is no automatic cleanup. Use the Data Management page's
  backup button periodically, especially before large deletes.
- Hosting (local vs. Streamlit Community Cloud vs. an office server) is not yet decided -- nothing
  in the current design assumes one or the other.
