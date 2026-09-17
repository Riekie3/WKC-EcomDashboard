# Direct Marketplace Analytics Dashboard

**Version:** 1.0 (planning — no production code written) · **Date:** 2026-09-17
**Companions:** `marketplace-api-research.md` · `API_CAPABILITY_MATRIX.md` · `DATA_MODEL.md` · `METRIC_DEFINITIONS.md` · `MALAYSIA_API_LIMITATIONS.md` · `IMPLEMENTATION_TASKS.md`

---

## 1. Project objective

Replace Excel upload as the **data source** of the WKC ecommerce analytics dashboard with direct, automated ingestion from Shopee, TikTok Shop and Lazada official APIs — keeping Excel only as an optional export format and as a narrow import path for data no API exposes.

Success is not "no more uploading". Success is:

1. The dashboard is **current without human action**.
2. Revenue figures are **derived from transaction records**, so they are correct by construction rather than by careful spreadsheet-column archaeology.
3. Fee, commission and settlement data — **invisible today** — becomes visible.
4. Adding a fourth marketplace, or a fourth brand, does not require touching the analytics engine.

---

## 2. Current system

Inspected 2026-09-17 at `D:\Rie\Claude\EcommerceDashboard`.

### 2.1 Stack

| Aspect | Current |
|---|---|
| Language | Python 3 |
| UI framework | Streamlit (multipage) |
| Data | pandas |
| ORM | SQLAlchemy 2.x declarative |
| DB | SQLite locally; **Neon Postgres** in production (was Supabase, migrated 2026-09) |
| Charts | Plotly |
| Excel | openpyxl (xlsx), xlrd (xls) |
| Hosting | Streamlit Community Cloud, public, no auth |
| Repo | Monorepo `WKC-EcomDashboard` — `Portal/` + `SonyDashboard/` |
| Size | ~2,180 lines of Python |

### 2.2 Architecture

```
Excel/CSV upload → router.detect(filename) → per-platform parser
    → normalized DataFrame → repository.insert_batch → fact table
    → pages query via repository.query_df → pandas aggregation → Plotly
```

### 2.3 Components worth keeping

| Component | Verdict | Why |
|---|---|---|
| `src/config/schema.py` | **Keep, extend** | Already a single source of truth for canonical fields — exactly the right instinct |
| `src/storage/db.py` | **Keep** | Contains two hard-won production fixes: `prepare_threshold=None` for pooled Postgres, and `_add_missing_columns` additive migrations |
| `src/storage/repository.py` | **Refactor** | Query patterns survive; must gain order-level aggregation |
| `src/storage/backup.py` | **Keep** | Backend-agnostic JSON backup/restore — still valuable |
| `src/ingestion/transforms.py` | **Keep** | `to_number`, `parse_date` handle real-world messiness; `require_columns` stays for the Excel side |
| `src/ingestion/parsers/*` | **Keep, demote** | Still needed for the funnel metrics no API provides |
| `src/dashboard/*` | **Keep** | Filters and branding are orthogonal to data source |
| Streamlit pages | **Refactor** | Same charts, new queries |
| `metrics`/aggregation logic in pages | **Replace** | Currently inline in page files; must move to a shared analytics layer |

### 2.4 The one structural problem in the current design

Metric logic lives **inside page files**. `pages/2_Sales_Overview.py` knows that Shopee must be filtered to `funnel_stage == 'confirmed'`; `pages/6_Returns_Refunds.py` had to learn the same rule separately — and the fact that it *didn't* is precisely what caused the Shopee triple-count bug (fixed in `74aa399`).

That bug is a design signal, not bad luck: **platform-specific rules embedded in presentation code will diverge.** The new architecture must make it impossible for a page to compute a metric its own way.

### 2.5 Excel coupling to be removed

The parsers hard-code Excel structure: sheet names (`"Key Metrics"`, `"Top Performing Products"`, `"Sheet 1"`), header row offsets (`header=3`, `header=5`, `header=6`), exact column labels (`"Sales (MYR)"`, `"# of buyers"`, `"Est.Commission(RM)"`), and — worst — **positional column indices** for TikTok product performance (`gmv` at index 4, `Refunds` at 40). Filename-pattern routing requires staff to rename every export before upload.

Every one of these disappears for API-sourced data.

---

## 3. Proposed system

```
Shopee API      TikTok Shop API      Lazada API
     │                 │                  │
ShopeeAdapter    TikTokAdapter      LazadaAdapter      ← only these know platform specifics
     └─────────────────┼──────────────────┘
                       ▼
              Sync Engine (workers)
        backfill · incremental · webhooks · reconciliation
                       ▼
            Normalized Postgres (Neon)
       shops · orders · order_items · refunds · transactions
                       ▼
              Analytics Layer  ← the ONLY place metrics are defined
                       ▼
              Streamlit Dashboard
                       │
              ┌────────┴────────┐
         Excel export      PDF/CSV export   (optional outputs)

        Excel import ──► funnel metrics only (visitors/impressions/CTR),
                          clearly labelled, optional
```

---

## 4. Architecture

### 4.1 The hosting problem — the most consequential finding in this document

**Streamlit Community Cloud cannot host this system.** Three independent reasons, each sufficient on its own:

1. **Token refresh.** Shopee access tokens live **4 hours**; refresh tokens **30 days**. A Streamlit app executes only while someone has the page open. Miss 30 days and the seller must manually re-authorize every shop.
2. **Webhooks need an always-on inbound HTTPS endpoint.** Streamlit has no request-handler model.
3. **Backfill is long-running.** Importing years of orders under rate limits takes far longer than a page render, and must survive the browser closing.

**Therefore the system splits in two:**

| Service | Responsibility | Hosting |
|---|---|---|
| **Sync service** (new) | Adapters, scheduler, workers, webhook receiver, token refresher | Always-on host with public HTTPS |
| **Dashboard** (existing) | Read-only UI over Postgres | Streamlit Cloud, **unchanged** |

This is deliberately incremental: the existing Streamlit app survives as the read layer, and the new work is additive. No UI rewrite is required to get value.

### 4.2 Sync service internals

```
FastAPI app
 ├── /webhooks/{platform}      signature-verified, writes webhook_events, returns 200 fast
 ├── /health, /metrics
 └── /admin/sync/{shop_id}     manual trigger
Scheduler (APScheduler)
 ├── token_refresh        every 30 min   ← well inside Shopee's 4h window
 ├── incremental_orders   every 15 min
 ├── webhook_drain        every 1 min
 ├── finance_sync         hourly
 └── reconciliation       every 6 hours + nightly deep pass
Worker
 └── processes sync_jobs with retry/backoff, writes through adapters
```

Recommendation: **one process** running FastAPI + APScheduler + in-process worker, backed by Postgres for job state. Redis/Celery is not justified at this volume (three shops per brand, low thousands of orders/month) and would add an operational dependency for no gain. Revisit only if multi-brand load grows.

### 4.3 Adapter interface

```python
class MarketplaceAdapter(Protocol):
    platform: str
    def build_authorize_url(self, redirect_uri: str, state: str) -> str: ...
    def exchange_code(self, code: str, **kw) -> ShopCredentials: ...
    def refresh_token(self, creds: ShopCredentials) -> ShopCredentials: ...
    def get_shop(self, creds) -> ShopInfo: ...
    def iter_orders(self, creds, since, until) -> Iterator[RawOrder]: ...
    def get_order(self, creds, platform_order_id) -> RawOrder: ...
    def iter_refunds(self, creds, since, until) -> Iterator[RawRefund]: ...
    def iter_transactions(self, creds, since, until) -> Iterator[RawTransaction]: ...
    def iter_products(self, creds) -> Iterator[RawProduct]: ...
    def verify_webhook(self, headers, body: bytes) -> WebhookVerification: ...
    def parse_webhook(self, payload: dict) -> list[WebhookFact]: ...
    def capabilities(self) -> set[Capability]: ...
```

`capabilities()` is what keeps unavailable data honest: `LazadaAdapter` simply does not advertise `AFFILIATE`, and the analytics layer renders "—" rather than `0`. Absence is modelled, not improvised.

Normalization (`RawOrder` → `orders` rows) lives in a **separate mapper per platform**, not inside the client. Clients do HTTP + auth + pagination; mappers do field translation. Mixing them is what makes marketplace integrations unmaintainable.

---

## 5. Shopee integration

| Item | Plan |
|---|---|
| Credentials | `partner_id` + `partner_key`; HMAC-SHA256 signing |
| Auth | Shop authorization → `access_token` (4h) + `refresh_token` (30d) |
| Refresh | Every 30 min, well inside the window |
| Orders | Windowed pagination by `create_time`; assume a max window per call (commonly 15 days) — confirm |
| Detail | Batch order-detail calls; respect max-IDs-per-request |
| Refunds | Returns API + cancellation status |
| **Finance** | **`escrow_detail` is the priority endpoint** — the authoritative settlement breakdown |
| Webhooks | Push for order/return/logistics/payment/item; HMAC-verified |
| Ads | **Deferred** — requires Shopee Partner Support enablement; also note the Auto Product Ads family is being deprecated |
| Risks | Rate limit unknown (10 rps vs 100 rpm conflict); 30-day refresh expiry is a real operational cliff |

## 6. TikTok Shop integration

| Item | Plan |
|---|---|
| Portal | Global Partner Portal (non-US markets incl. MY) |
| App type | **Custom app** — no App Store listing needed; no reported data-access difference vs public |
| Credentials | `app_key` + `app_secret` |
| Auth | Code exchange → `access_token` + `refresh_token` + **`shop_cipher`** |
| `shop_cipher` | Stored per shop; required on every call — **unique to TikTok, must not leak into the generic interface** |
| Versioning | Date-stamped (`202309`); **pin the version per endpoint in config**, never float |
| Orders | `/order/202309/...` |
| **Finance** | `/finance/202309/statements`, `/finance/202309/withdrawals` — **MY availability is the top project unknown** |
| Affiliate | **Affiliate Seller API** — the brand-side family; partner/agency families are out of scope |
| Webhooks | Order-status webhooks with documented retry |
| Risks | MY finance availability ❓; token lifetime conflicting (24h vs 7d) ❓; version deprecation is a standing maintenance cost |

## 7. Lazada integration

| Item | Plan |
|---|---|
| Credentials | `app_key` + `app_secret` |
| Auth | OAuth 2.0 — `/auth/token/create`, `/auth/token/refresh` |
| Signing | **HMAC-SHA256 TOP scheme** over sorted parameter string — build and unit-test this first; it is the most error-prone piece on this platform |
| Orders | `/orders/get` (list), `/order/get` (single), order-items endpoints |
| **Finance** | `/finance/transaction/details/get`, `/finance/transaction/accountTransactions/query` |
| Returns | Return/Refund API family |
| Ads | Sponsored Solutions family exists — scope/approval ❓, deferred |
| Webhooks | **Assume none** — design Lazada as polling-first; treat any push as a bonus |
| Risks | **Do not follow `lazada-sellercenter.readme.io`** — decommissioned 2018, still highly ranked in search |

---

## 8. Unified data model

See `DATA_MODEL.md`. Summary: `platform_accounts`, `shops`, `orders`, `order_items`, `refunds`, `transactions`, `products`, `product_variants`, `shipments`, `sync_jobs`, `sync_cursors`, `webhook_events`; existing Excel fact tables retained for funnel metrics.

Two decisions carry the most weight:

1. **`refund_amount` (money) and `refund_quantity` (units) are separate columns.** The worst historical bug in this project came from a spreadsheet exposing a monetary `Refunds` column beside a unit-count `Items refunded`. The schema now makes conflating them a type error.
2. **Natural keys with UNIQUE constraints on every platform-sourced table.** Idempotency is enforced by the database, not by hopeful application code — which is what makes duplicate webhooks a non-event.

## 9. Authentication (system-level)

The dashboard is currently **public with no login** — a deliberate past decision when it held only aggregate sales figures.

That decision must be revisited, because this system will hold **marketplace access tokens and settlement data**. Recommendation: the sync service is never publicly routable except `/webhooks/*` and `/health`; the dashboard gains authentication before it displays settlement data. Escalated as **OQ-3**.

## 10. Synchronization

### 10.1 Initial sync

```
authorize → store credentials → discover shop → products
         → historical orders (windowed, oldest→newest, resumable)
         → refunds → transactions → build analytics → mark ready
```

Backfill runs as resumable `sync_jobs` with a persisted cursor. Interrupting it must never corrupt state or force a restart from zero.

### 10.2 Incremental sync

```
webhook (fast path) ─┐
polling every 15min ─┼─► sync_jobs queue ─► adapter ─► mapper ─► upsert ─► analytics
manual trigger ──────┘
```

Polling uses `platform_updated_at` cursors with a **deliberate overlap** (re-query the last 60 minutes) — cheap insurance against clock skew and late-arriving updates, made safe by upsert idempotency.

### 10.3 Failure modes and handling

| Failure | Handling |
|---|---|
| Duplicate webhook | UNIQUE `dedupe_key` → no-op |
| Missed webhook | Reconciliation sweep catches it |
| API 5xx / network | Exponential backoff, capped retries |
| Rate limited | Adaptive limiter + `Retry-After`; job re-queued, not failed |
| Access token expired | Refresh, retry once |
| **Refresh token expired** | Mark shop `token_expired`, **alert a human**, stop retrying |
| Partial sync | `sync_jobs.status = 'partial'`, resume from cursor |
| Clock skew | All comparisons in UTC; overlap window absorbs drift |
| Pagination drift | Sort by stable key; overlap + upsert make re-reads harmless |

## 11. Webhooks and reconciliation

**Webhook = speed. Polling = correctness. Database = source of truth.** Webhooks are never trusted as complete.

Reconciliation job (every 6h, plus a nightly deeper pass):

```
for each connected shop:
    re-list orders updated in the last 48h
    compare platform state against local rows
    upsert differences; log drift_count to sync_jobs
```

A persistently non-zero `drift_count` is the early-warning signal that webhook processing has broken — the kind of silent failure that otherwise goes unnoticed until someone questions a number.

Webhook handler contract: verify signature → persist raw → return 200 **immediately** → process asynchronously. Never process inline; slow handlers cause vendor-side retry storms.

## 12. Analytics engine

One module owns every metric definition (`METRIC_DEFINITIONS.md`). Pages call `analytics.net_sales(shops, start, end)`; pages never write aggregation logic. This directly fixes §2.4.

Platform-specific rules live in the **status map**, not in query code. Availability is explicit: a metric unavailable for a selected platform returns `Unavailable(reason)` — a real value the UI must render — rather than `0` or a silently missing row.

## 13. Dashboard

Overview (Gross Sales, Net Sales, Refunds, Orders, Units, AOV, **Fees**, **Commission**, **Net Settlement**), platform comparison, trends, product analytics, order analytics, financial analytics, and Returns & Refunds — filtered by date range, platform, shop, product/SKU, order status.

New, and important: a **data-freshness indicator** ("Shopee synced 4 min ago · Lazada 12 min ago · TikTok ⚠️ token expired"). A dashboard that syncs itself must show whether it actually did.

## 14. Security

| Concern | Decision |
|---|---|
| App secrets | Environment variables / secret manager — **never** in the repo |
| Tokens | **Encrypted at rest** (`*_enc` columns, AES-GCM via a KMS/env-held key) |
| Key rotation | Versioned key id per row; re-encrypt on rotation |
| Webhook auth | Signature verification mandatory; reject and log failures |
| Logging | Tokens/secrets **masked**; buyer PII never logged |
| PII | Not stored — pseudonymous `buyer_ref` only (`DATA_MODEL.md` §6) |
| Audit | `sync_jobs` + `webhook_events` retain who/what/when |
| Dashboard access | See **OQ-3** |

Explicitly ruled out by the brief and agreed: no scraping, no browser automation, no undocumented/private endpoints.

## 15. Database

**PostgreSQL — already in use (Neon), no change.** SQLite cannot support concurrent sync workers plus dashboard readers, and this workload has genuine concurrency. MySQL offers nothing Postgres doesn't here, and would discard the existing investment.

Keep: one database per brand (existing isolation decision), `JSONB` for `raw_payload`, the `prepare_threshold=None` pooling fix, and additive migrations. Add: Alembic, once the schema stops being a moving target — `_add_missing_columns` is a good stopgap but cannot express renames, backfills or constraint changes, all of which this project will need.

## 16. Error handling

Taxonomy: `AUTH_ERROR`, `TOKEN_EXPIRED`, `REFRESH_TOKEN_EXPIRED`, `RATE_LIMIT`, `NETWORK_ERROR`, `API_ERROR`, `INVALID_SIGNATURE`, `INVALID_RESPONSE`, `PERMISSION_DENIED`, `SHOP_DISCONNECTED`, `SYNC_FAILED`, `MAPPING_ERROR`.

| Class | Policy |
|---|---|
| `NETWORK_ERROR`, `API_ERROR` (5xx) | Exponential backoff, ~5 attempts |
| `RATE_LIMIT` | Honour `Retry-After`, re-queue |
| `TOKEN_EXPIRED` | Refresh, retry once |
| `REFRESH_TOKEN_EXPIRED`, `AUTH_ERROR`, `PERMISSION_DENIED` | **Do not retry** — alert a human |
| `INVALID_SIGNATURE` | Reject, log, never process |
| `MAPPING_ERROR` | Fail that record, quarantine raw payload, continue the batch |

`MAPPING_ERROR` handling is deliberate: one unmappable order must not stop a 10,000-order backfill, but it must not be silently dropped either.

## 17. Logging and monitoring

Structured JSON logs with `shop_id`, `job_id`, `platform`, `error_code`. Track: sync success rate, records/run, API latency and error rate per platform, webhook lag, reconciliation drift, token expiry countdown. Alert on: refresh token expiring within 7 days, shop disconnected, reconciliation drift above threshold, sync failure streak.

## 18. API limits

All three platforms' limits are **unconfirmed** (`marketplace-api-research.md`). Therefore: a per-platform adaptive token-bucket limiter, conservative defaults, config-driven, that backs off on 429 and records observed ceilings. **Never hard-code a rate from a blog post.**

## 19. Malaysia-specific considerations

See `MALAYSIA_API_LIMITATIONS.md`. Headline: TikTok Shop MY finance availability is the single biggest unknown; MY-10 (per-endpoint timestamp timezone) is the most dangerous because it produces plausible wrong numbers rather than errors.

## 20. Capability matrix

See `API_CAPABILITY_MATRIX.md`.

## 21. Cost analysis and build-vs-buy

### Recurring cost, Option A (build ourselves)

| Item | Cost |
|---|---|
| Developer accounts (all 3) | **Free** |
| API calls | **Free** (rate-limited, not metered) |
| Postgres (Neon free) | **Free** at this volume |
| **Sync service host** (always-on, public HTTPS) | **~USD 5–10/month** — the one genuinely new cost |
| Dashboard (Streamlit Cloud) | Free |

The financial cost of this project is negligible. **The real cost is engineering time and ongoing maintenance** — API versions deprecate, and that maintenance never ends.

### Options

| | A — Build all three | B — Unified provider (e.g. API2Cart) | C — Hybrid |
|---|---|---|---|
| Dev effort | High (~8–12 wks) | Low–medium | Medium |
| Running cost | ~USD 5–10/mo | Subscription (often USD 100+/mo) | Between |
| API coverage | Full — incl. finance, settlement, affiliate | **Typically products/orders/inventory only** | Full where it matters |
| Control | Total | Limited by their model | High |
| Reliability | Ours to own | Their uptime + their lag | Mixed |
| Vendor dependency | None | **High** | Moderate |
| Maintenance | Ours | Theirs | Shared |

**Recommendation: Option A.** The decisive factor is not cost — it is that unified providers are built for *catalog and order synchronisation* (the storefront-integration use case), and this project's highest-value data is **finance: settlements, fees, commissions**. That is precisely the area unified providers cover least well, and it is the area where this dashboard has the most to gain.

Option B would buy a slower path to the part that is already easy, while not delivering the part that matters. Option C is worth revisiting only if a fourth and fifth marketplace appear.

## 22. MVP

**Goal: one platform, end to end, proving the whole chain.**

```
Connect ONE Shopee shop (OAuth)
   → backfill 90 days of orders + refunds
   → normalize into orders/order_items/refunds
   → analytics layer computes Gross/Net Sales, Orders, Units, AOV
   → existing Streamlit Sales Overview reads API-sourced data
   → reconcile against the same period's Excel figures
```

**Shopee first**, not all three — because the sole purpose of the MVP is to validate the *architecture* (auth, token refresh, pagination, normalization, idempotency, metrics) and one platform validates all of it. Adding Lazada and TikTok afterwards is repetition, not discovery. Shopee is chosen because it is the largest revenue contributor and has the strongest webhook support.

**Explicitly deferred past MVP:** webhooks (polling is enough to prove correctness), finance/settlement, ads, affiliate, products/inventory, multi-shop UI, dashboard auth.

**The MVP's real deliverable is the reconciliation table**, not the pretty page: if API-derived June numbers do not reconcile with the Excel-derived June numbers (allowing for the known Shopee gross/net discontinuity in `METRIC_DEFINITIONS.md` §3), the mapping is wrong and no amount of further building will fix it.

## 23. Development phases

| Phase | Scope | Gate to exit |
|---|---|---|
| **0 — Access & verification** | Register developer accounts; **verify every [U] in the research doc**; complete the MY checklist | Research doc updated with [V] marks; no unknowns remain on the MVP path |
| **1 — Foundations** *(no credentials needed)* | Adapter interface, data model + migrations, config system, sync-job framework, logging, error taxonomy, **mock adapter** | Mock adapter passes the full pipeline into the DB |
| **2 — Shopee (MVP)** | Auth, token refresh, orders, refunds, backfill, incremental polling, analytics, reconciliation | June reconciliation explained to the cent |
| **3 — Lazada** | TOP signing, auth, orders, refunds, polling | Reconciles |
| **4 — TikTok Shop** | Auth + `shop_cipher`, orders, refunds; finance **if MY-available** | Reconciles |
| **5 — Unified analytics** | Cross-platform metrics, availability handling, provenance labels | Combined view correct with mixed availability |
| **6 — Dashboard** | Refactor pages onto the analytics layer; freshness indicators; Excel demoted | Feature parity minus known-unavailable metrics |
| **7 — Webhooks** | Receiver, signatures, dedupe, drain worker | Drift ≈ 0 over 7 days |
| **8 — Reliability** | Retries, reconciliation tuning, alerting, monitoring | Survives an induced 24h outage |
| **9 — Security** | Encryption at rest, rotation, masking, dashboard auth | Review passed |
| **10 — Production** | Deploy, backup, runbook, parallel run vs Excel | One clean month in parallel |

Deviation from the brief's suggested order: **Phase 0 is expanded and made a hard gate**, because ~60% of research claims are `[U]`. Building adapters against unverified endpoints is the main way this project could waste weeks.

## 24. Testing strategy

| Layer | Approach |
|---|---|
| Signing | **Unit tests with known-good vectors** — especially Lazada TOP |
| Adapters | Mocked HTTP fixtures — **no production credentials in tests** |
| Pagination | Fixtures with multi-page and boundary cases |
| Token refresh | Simulated expiry/clock skew |
| Webhooks | Valid, invalid-signature, duplicate, out-of-order fixtures |
| Normalization | Real (PII-scrubbed) payload fixtures per platform |
| **Metrics** | Golden-dataset tests asserting exact expected figures |
| **Timezone** | Fixtures at 23:30 MYT and 07:30 MYT proving correct day bucketing |
| Idempotency | Ingest the same batch twice; assert identical row counts and sums |
| Reconciliation | Injected drift is detected and corrected |

The idempotency and timezone tests are the two that would have caught this project's historical bug classes before users did.

## 25. Deployment strategy

Sync service on an always-on host with public HTTPS; dashboard stays on Streamlit Cloud; Neon Postgres per brand. Secrets in the host's secret store. Nightly `pg_dump` in addition to Neon's own backups.

**Cutover: parallel run.** API pipeline runs alongside Excel for one full month, with a weekly reconciliation report. Excel upload is demoted to optional only after a month of matching figures.

## 26. Risks

| # | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R1 | **Developer account / app approval rejected or slow** | Blocks everything | Medium | Start Phase 0 immediately — it is pure waiting |
| R2 | **TikTok MY finance API unavailable** | No TikTok settlement data | Medium | Verify in Phase 0; degrade to order-derived net |
| R3 | **Traffic metrics unavailable** (confirmed) | Product Performance loses impressions/CTR | **Certain** | Hybrid Excel, or drop the metrics — **OQ-1** |
| R4 | Rate limits tighter than assumed | Slow backfill | Medium | Adaptive limiter; backfill runs for days if needed |
| R5 | **Shopee 30-day refresh expiry** | Shop silently disconnects | Medium | Monitoring + alert at 7 days; re-auth runbook |
| R6 | API version deprecation | Breakage | **Certain over time** | Pin versions; watch changelogs; budget maintenance |
| R7 | Ads data stays gated | Ads page stays manual | High | Keep Excel for ads |
| R8 | **Shopee gross→net discontinuity alarms stakeholders** | Trust lost at go-live | **High if unmanaged** | Show both; parallel run; agree definition first — **OQ-2** |
| R9 | Historical depth insufficient | Old data only in Excel | Medium | Keep Excel-era rows read-only |
| R10 | Timezone bug misattributes days | Silent wrong numbers | Medium | Mandatory timezone tests (MY-10) |
| R11 | Scope creep into a full ERP | Never ships | Medium | MVP discipline — one platform, one metric set |

## 27. Open questions

| # | Question | Owner | Blocks |
|---|---|---|---|
| **OQ-1** | Traffic metrics (visitors, impressions, CTR, conversion, traffic-source) have **no API source**. Keep a small Excel import for them, or drop them from the product? | **Business** | Phase 6 scope |
| **OQ-2** | Shopee revenue is deliberately gross today. Switch to net (≈15.6% lower for June 2026) or keep gross as a second metric? | **Business + staff who own the number** | Metric layer |
| **OQ-3** | Dashboard is public and unauthenticated. Does it get auth before it shows settlement data? | **Business** | Phase 9 |
| OQ-4 | Is TikTok Shop MY finance API available? | Engineering, Phase 0 | R2 |
| OQ-5 | Pursue Shopee ads API enablement, or keep ads on Excel? | Business | Phase 7+ |
| OQ-6 | How far back should the backfill go? | Business | Phase 2 |
| OQ-7 | Does this apply to Tefal/3M/etc. too, or Sony first? | Business | Roadmap |

OQ-1, OQ-2 and OQ-3 are **business decisions that engineering cannot make**, and two of them change what the product *is*.

## 28. Recommended next steps

1. **Answer OQ-1 and OQ-2** — they determine scope and prevent a go-live credibility failure.
2. **Start Phase 0 registration today** — approval waiting time is the longest pole and costs nothing to start.
3. **Verify the `[U]` claims** — especially TikTok MY finance.
4. **Build Phase 1 foundations in parallel** — the interface, data model, config, job framework, logging and mock adapter need no credentials, so this work is not blocked by approvals.
5. **Do not write a single production API call** until that endpoint is verified against official documentation.
