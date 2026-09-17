# Implementation Tasks

**As of:** 2026-09-17 · Companion to `DIRECT_MARKETPLACE_DASHBOARD_PLAN.md`

Phases 0–2 are specified in full because they are the next work. Phases 3–10 are outlined at lower granularity and will be expanded once Phase 0 replaces the research document's `[U]` marks with verified facts.

**Proposed location for new code:** `SyncService/` as a sibling of `Portal/` and `SonyDashboard/` in the existing monorepo — a separately deployable service, consistent with the current structure.

---

## PHASE 0 — Access and verification (blocks all API coding)

### TASK-001 — Register developer accounts on all three platforms
**Purpose:** Approval lead time is the longest pole in the project and costs nothing to start.
**Dependencies:** None. **Start immediately.**
**Files affected:** None (external).
**Expected result:** Approved developer accounts with credentials issued.
**Acceptance criteria:**
- Shopee: `partner_id` + `partner_key` issued
- TikTok Shop: **custom app** on the **Global** Partner Portal; `app_key` + `app_secret` issued
- Lazada: app created; `app_key` + `app_secret` issued
- Redirect URIs registered for all three
- Sandbox/test access confirmed where offered

### TASK-002 — Verify Shopee API surface against official docs
**Purpose:** Replace `[U]` marks with verified facts before any adapter is written.
**Dependencies:** TASK-001
**Files affected:** `docs/marketplace-api-research.md`
**Expected result:** §1 of the research doc is fully `[V]`.
**Acceptance criteria:** Confirmed and recorded — exact order list/detail endpoint paths and parameters; max date window per query; pagination; `escrow_detail` request/response shape; push event types and signature scheme; **actual rate limits**; historical depth; regional host for MY.

### TASK-003 — Verify TikTok Shop API surface, incl. Malaysia finance
**Purpose:** Resolve the project's highest-impact unknown (OQ-4 / R2).
**Dependencies:** TASK-001
**Files affected:** `docs/marketplace-api-research.md`, `docs/MALAYSIA_API_LIMITATIONS.md`
**Expected result:** §2 fully `[V]`; MY finance availability answered yes/no.
**Acceptance criteria:**
- **Confirmed whether `/finance/202309/statements` returns data for a MY shop** ← critical
- Current API version per endpoint recorded (do not assume `202309` everywhere)
- `access_token` lifetime settled (24h vs 7d conflict resolved)
- `shop_cipher` acquisition and usage confirmed
- Affiliate **Seller** API scope for a brand's own shop confirmed
- Webhook event types, signature scheme, retry behaviour confirmed

### TASK-004 — Verify Lazada API surface
**Purpose:** Same, plus avoid the decommissioned-docs trap.
**Dependencies:** TASK-001
**Files affected:** `docs/marketplace-api-research.md`
**Expected result:** §3 fully `[V]`.
**Acceptance criteria:** TOP signing spec captured with a **known-good test vector**; `/orders/get` parameters and page limits; finance endpoint shapes; MY gateway host; push availability answered definitively; **zero reliance on `lazada-sellercenter.readme.io`**.

### TASK-005 — Complete the Malaysia verification checklist
**Purpose:** Prevent market-specific assumptions from reaching code.
**Dependencies:** TASK-002/003/004
**Files affected:** `docs/MALAYSIA_API_LIMITATIONS.md`
**Expected result:** MY-1…MY-10 all answered.
**Acceptance criteria:** Every row resolved; **MY-10 (per-endpoint timestamp timezone) documented per endpoint**, since it silently corrupts day-bucketed metrics.

### TASK-006 — Resolve OQ-1 and OQ-2 with the business
**Purpose:** These change what the product is; engineering cannot decide them.
**Dependencies:** None (parallel with TASK-001)
**Files affected:** `docs/DIRECT_MARKETPLACE_DASHBOARD_PLAN.md` §27, `docs/METRIC_DEFINITIONS.md` §3
**Expected result:** Written decisions.
**Acceptance criteria:**
- **OQ-1:** keep a narrow Excel import for traffic metrics, or drop those metrics — decided
- **OQ-2:** Shopee gross vs net at switchover — decided **with the staff who own that number**, before go-live

---

## PHASE 1 — Foundations (needs no credentials; run in parallel with Phase 0)

### TASK-010 — Scaffold the sync service
**Purpose:** A deployable skeleton to build into.
**Dependencies:** None
**Files affected:** `SyncService/` (new): `main.py`, `requirements.txt`, `README.md`, `config/`
**Expected result:** FastAPI app with `/health`, config loading, structured logging.
**Acceptance criteria:** Runs locally; `/health` returns 200; no secrets in the repo; `.gitignore` covers local env files.

### TASK-011 — Define the marketplace adapter interface
**Purpose:** Keep platform specifics out of the analytics layer (plan §4.3).
**Dependencies:** TASK-010
**Files affected:** `SyncService/adapters/base.py`, `SyncService/adapters/types.py`
**Expected result:** `MarketplaceAdapter` Protocol + `RawOrder`/`RawRefund`/`RawTransaction`/`ShopCredentials`/`Capability` dataclasses.
**Acceptance criteria:**
- All three platform adapters can implement it **without changing analytics code**
- `capabilities()` can express "this platform has no affiliate data"
- TikTok's `shop_cipher` is carried in `ShopCredentials` **without appearing in the generic interface**

### TASK-012 — Implement the unified data model
**Purpose:** The normalized store.
**Dependencies:** TASK-010
**Files affected:** `SyncService/models/*.py`, Alembic migrations
**Expected result:** All tables from `DATA_MODEL.md` §3.
**Acceptance criteria:**
- Every platform-sourced table has a UNIQUE natural key
- `refund_amount` and `refund_quantity` are **separate columns**
- `raw_payload` is JSONB
- Existing Excel fact tables untouched
- Migrations run clean on an empty DB **and** on a copy of the current production DB

### TASK-013 — Configuration system
**Purpose:** No hard-coded platform field mappings or limits (brief §17).
**Dependencies:** TASK-010
**Files affected:** `SyncService/config/platforms/{shopee,tiktok,lazada}.yaml`, `config/loader.py`
**Expected result:** Endpoints, API versions, status maps, rate limits, currency/timezone defaults, field mappings — all declarative.
**Acceptance criteria:** Changing a status mapping or pinned API version requires **no code change**; an unmapped platform status **raises** rather than defaulting.

### TASK-014 — Sync job framework
**Purpose:** Resumable, observable, retryable work.
**Dependencies:** TASK-012
**Files affected:** `SyncService/sync/jobs.py`, `sync/worker.py`, `sync/scheduler.py`
**Expected result:** Jobs persisted to `sync_jobs`, worker with backoff, APScheduler wiring.
**Acceptance criteria:** A killed job resumes from its cursor without duplicating or losing rows; failures record an `error_code` from the taxonomy; retries follow the plan §16 policy.

### TASK-015 — Error taxonomy and retry policies
**Dependencies:** TASK-010
**Files affected:** `SyncService/errors.py`
**Expected result:** Exception classes per plan §16 with declared retry policy.
**Acceptance criteria:** `AUTH_ERROR` / `REFRESH_TOKEN_EXPIRED` are **never retried in a loop**; `MAPPING_ERROR` quarantines one record without aborting the batch.

### TASK-016 — Credential encryption
**Purpose:** Tokens must not sit in plaintext (plan §14).
**Dependencies:** TASK-012
**Files affected:** `SyncService/security/crypto.py`
**Expected result:** AES-GCM encrypt/decrypt for `*_enc` columns, key from env/secret manager, versioned key id.
**Acceptance criteria:** No plaintext token is ever written to DB or logs; log masking verified by test; key rotation re-encrypts without downtime.

### TASK-017 — Mock adapter + end-to-end pipeline test
**Purpose:** Prove the architecture before any real API exists. **This is the Phase 1 exit gate.**
**Dependencies:** TASK-011…TASK-015
**Files affected:** `SyncService/adapters/mock.py`, `tests/test_pipeline_e2e.py`
**Expected result:** A fake platform flows through adapter → mapper → upsert → analytics.
**Acceptance criteria:**
- Full pipeline runs with zero network access
- **Running the same batch twice produces identical row counts and sums** (idempotency)
- Metrics computed from mock data match hand-calculated expected values

### TASK-018 — Analytics layer
**Purpose:** One home for every metric definition (fixes plan §2.4).
**Dependencies:** TASK-012
**Files affected:** `SyncService/analytics/metrics.py` (importable by the dashboard)
**Expected result:** Functions implementing `METRIC_DEFINITIONS.md` §2.
**Acceptance criteria:**
- Golden-dataset tests assert exact figures
- **Timezone tests** with orders at 23:30 MYT and 07:30 MYT bucket to the correct MY day
- Unavailable metrics return `Unavailable(reason)` — never `0`
- Net Settlement **refuses to sum** across a platform set with incomplete finance coverage

---

## PHASE 2 — Shopee MVP

### TASK-020 — Shopee request signing
**Dependencies:** TASK-002, TASK-011
**Files:** `SyncService/adapters/shopee/signing.py`
**Acceptance:** Unit tests pass against a **known-good vector**; signature correct for both token and non-token calls.

### TASK-021 — Shopee OAuth + token lifecycle
**Dependencies:** TASK-020, TASK-016
**Files:** `adapters/shopee/auth.py`, `api/routes/oauth.py`
**Acceptance:** Full authorize → callback → encrypted persist; **refresh runs every 30 min** (inside the 4h window); refresh-token expiry raises an alert at **7 days remaining** and does not retry-loop.

### TASK-022 — Shopee order ingestion
**Dependencies:** TASK-021
**Files:** `adapters/shopee/orders.py`, `mappers/shopee_order.py`
**Acceptance:** Windowed pagination respects the documented max window; maps to `orders` + `order_items` per `DATA_MODEL.md` §4; unknown status **raises**; re-running yields no duplicates; PII stripped from `raw_payload`.

### TASK-023 — Shopee refunds/returns ingestion
**Dependencies:** TASK-022
**Acceptance:** `refund_amount` is always currency; `refund_quantity` always units; refunds bucket by refund date.

### TASK-024 — Historical backfill worker
**Dependencies:** TASK-022, TASK-014
**Acceptance:** Backfills a configurable window oldest→newest; resumable after kill; respects the adaptive rate limiter; progress visible in `sync_jobs`.

### TASK-025 — Incremental polling
**Dependencies:** TASK-024
**Acceptance:** Runs every 15 min using `platform_updated_at` cursors with a **60-minute overlap**; overlap causes no duplicates.

### TASK-026 — Adaptive rate limiter
**Dependencies:** TASK-010
**Acceptance:** Per-platform token bucket, config-driven; honours `Retry-After`; records observed ceilings; **no rate hard-coded from an unverified source**.

### TASK-027 — Reconciliation job
**Dependencies:** TASK-025
**Acceptance:** Re-lists the last 48h, upserts differences, records `drift_count`; injected drift is detected and corrected.

### TASK-028 — **Reconciliation against Excel — the MVP gate**
**Purpose:** Prove the API numbers are right before anything is built on them.
**Dependencies:** TASK-022…TASK-027, TASK-018
**Files:** `tests/reconciliation/shopee_june_2026.md`
**Expected result:** A written comparison of API-derived vs Excel-derived figures for the same period.
**Acceptance criteria:**
- Gross Sales, Orders, Units reconcile **to the cent**, or every difference is explained
- The **Shopee gross-vs-net discontinuity** (`METRIC_DEFINITIONS.md` §3) is quantified, not hand-waved
- Result reviewed with the business before Phase 3 starts

### TASK-029 — Point one dashboard page at API data
**Dependencies:** TASK-028
**Files:** `SonyDashboard/pages/2_Sales_Overview.py`
**Acceptance:** Sales Overview reads through the analytics layer; **page contains no aggregation logic of its own**; a freshness indicator shows last sync time; Excel-era history still renders with an `excel` provenance badge.

---

## PHASE 3+ — Outline

| Task | Phase | Summary |
|---|---|---|
| TASK-030…039 | 3 — Lazada | TOP signing (+ test vector), auth, orders, refunds, polling, reconciliation |
| TASK-040…049 | 4 — TikTok | Auth + `shop_cipher`, orders, refunds, **finance if MY-available**, affiliate (seller) |
| TASK-050…059 | 5 — Unified analytics | Cross-platform metrics, availability handling, provenance labels |
| TASK-060…069 | 6 — Dashboard | All pages onto the analytics layer; Excel demoted to optional; exports |
| TASK-070…079 | 7 — Webhooks | Receiver, signature verification, dedupe, drain worker, drift monitoring |
| TASK-080…089 | 8 — Reliability | Alerting, monitoring, induced-outage drill |
| TASK-090…099 | 9 — Security | Rotation, audit logging, **dashboard authentication (OQ-3)** |
| TASK-100…109 | 10 — Production | Deploy, backups, runbook, one-month parallel run |

---

## Critical path

```
TASK-001 (register) ──► TASK-002/003/004 (verify) ──► TASK-020+ (Shopee adapter)
                                                            │
TASK-010…018 (foundations, no credentials) ─────────────────┘
                                                            ▼
                                                    TASK-028 (reconcile) ──► Phase 3
```

**TASK-001 is the only thing that cannot be started sooner, and everything API-shaped waits on it.** Phase 1 (TASK-010…018) is fully unblocked today — which is why the plan recommends starting there while approvals are pending.
