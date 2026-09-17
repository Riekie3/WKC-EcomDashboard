# Marketplace API Research

**Research date:** 2026-09-17
**Researcher:** Claude Code (Opus 5)
**Scope:** Shopee, TikTok Shop, Lazada — Malaysia market — for replacing Excel-upload ingestion in the WKC Ecommerce Dashboard with direct API ingestion.

---

## 0. READ THIS FIRST — research integrity statement

This document separates what was **verified**, what is **probable**, and what is **unconfirmed**. That distinction is load-bearing: designing an adapter against a guessed endpoint signature wastes more time than not building it at all.

### 0.1 A hard constraint hit during this research

**All three vendors' official documentation portals are not machine-readable from this environment.** Specifically, on 2026-09-17:

| Portal | URL | Result |
|---|---|---|
| Shopee Open Platform | `open.shopee.com/documents/v2/Introduction` | Fetch **blocked** by the host |
| TikTok Shop Partner Center | `partner.tiktokshop.com/docv2/page/...` | Returns a JS shell; body content truncated/empty |
| Lazada Open Platform | `open.lazada.com/apps/doc/...` | Returns a JS shell; only the page header resolves |

Consequence: the endpoint names, parameters and limits below come from **search-engine summaries of those official pages**, from **official-adjacent artifacts** (vendor Postman workspaces, vendor SDK documentation), and from **third-party integrator documentation**. They are good enough to *plan and budget* against. They are **not** good enough to *code against without verification*.

**Mandatory gate before Phase 2 coding:** a human with a registered developer account must open each portal, confirm every endpoint this plan depends on, and correct this document. See `TASK-002`, `TASK-003`, `TASK-004` in `IMPLEMENTATION_TASKS.md`.

### 0.2 Confidence legend used throughout

| Mark | Meaning |
|---|---|
| **[V]** | Verified — consistent across 2+ independent sources, or from a vendor-controlled artifact |
| **[P]** | Probable — single credible source, or strong consensus among third-party integrators |
| **[U]** | Unconfirmed — could not establish; must be checked against official docs before use |
| **[X]** | Established as **not available** via official API |

### 0.3 A trap found during this research (worth recording)

`lazada-sellercenter.readme.io` still ranks highly in search and still serves complete, confident-looking API documentation (`GetOrders`, `Signing requests`, etc. against `api.sellercenter.lazada.sg`). **That documentation is decommissioned.** Its own announcement page states the docs were decommissioned from **2018-12-20**, and the Seller Center API itself from **2018-06-28**, with users directed to `open.lazada.com`. **[V]**

Any tutorial, SDK or AI answer describing Lazada's API in terms of `Action=GetOrders` + `UserID` + `Version=1.0` is describing a **dead API**. The live Lazada API is the Open Platform one (`/orders/get`, TOP-style HMAC-SHA256 signing). This is exactly the "obsolete API version" failure mode the brief warned about — and it is live and well-indexed right now.

---

## 1. SHOPEE — Shopee Open Platform

### 1.1 Access and authentication

| Item | Finding | Conf. |
|---|---|---|
| Portal | `open.shopee.com` — developer registration + verification required | [V] |
| Credentials | `partner_id` + `partner_key` issued per app | [V] |
| Model | Per-shop authorization; seller grants app access, app receives shop-scoped tokens | [V] |
| Request signing | HMAC-SHA256 over partner key + API path + timestamp + token | [V] |
| `access_token` lifetime | **4 hours** | [V] |
| `refresh_token` lifetime | **30 days** | [V] |
| Token refresh | `RefreshAccessToken` before expiry | [V] |
| Redirect URL | Required, registered per app | [P] |
| Sandbox | A test/sandbox environment is referenced | [P] |
| Malaysia | Shopee MY is a supported market; no MY-specific API gate found | [U] |

**Operational consequence of the 4h / 30d token pair:** the system *must* run an unattended token-refresh job. A 4-hour access token means a dashboard opened once a week will **always** find its token dead. A 30-day refresh token means that if the refresher is down for 30 days, the seller must **manually re-authorize from scratch**.

This single fact rules out the current hosting model (a Streamlit app that only executes while someone has the page open). See plan §10.

### 1.2 Data domains

| Domain | Availability | Conf. |
|---|---|---|
| Orders (list + detail, items, status, timestamps, SKU, qty, buyer, shipping) | Available | [V] |
| Products / SKU / stock / variation / category / status | Available | [V] |
| Logistics / tracking / shipment / fulfilment status | Available | [V] |
| Returns and refunds | Available | [V] |
| Payments — payout, **escrow detail**, billing transactions, wallet transactions | Available | [P] |
| Discounts / vouchers / promotions | Available | [P] |
| **Product Ads performance** (incl. CTR, conversion rate, direct vs broad attribution) | Available **but gated** — "requires special permissions… contact Shopee Partner Support to enable advertising features" | [P] |
| **Shop traffic analytics** — visitors, page views, product impressions, click-through | **Not available** — the Open API covers shop *operations*; traffic and market-intelligence data is Seller Centre only | [X] |
| Affiliate / AMS commission data | No Open Platform endpoint identified | [U] |

**`escrow_detail` is the most valuable single endpoint for this project.** It is the platform's own settlement breakdown — the authoritative answer to "what were we actually paid, after which fees" — which is exactly the question the current Excel pipeline answers badly.

Note the ads caveat: Shopee's ads endpoints reportedly include an **Auto Product Ads family that is being deprecated**, so any ads work must target the current family. **[P]**

### 1.3 Push / webhooks

Shopee provides a **push mechanism** delivering order, return, logistics, payment and item events to a partner-registered endpoint, signed with HMAC-SHA256. **[P]**

Retry semantics, ordering guarantees and delivery SLA: **[U]**. Design assumes at-least-once delivery with possible gaps (plan §11).

### 1.4 Rate limits

Sources conflict: one reports **10 requests/second per shop** for most endpoints; another reports **100 requests/minute**. **[U]** — treat as *unknown*, implement an adaptive limiter, and confirm before any bulk backfill. Do not hard-code either number.

### 1.5 Historical data

Retrievable history depth, and whether a full historical backfill is permitted: **[U]**. Most marketplace order APIs cap the queryable window per request (commonly a 15-day `create_time` range); assume windowed pagination will be required and design the backfill worker for it regardless.

---

## 2. TIKTOK SHOP — Partner Center / Open API

### 2.1 Access and authentication

| Item | Finding | Conf. |
|---|---|---|
| Portal | `partner.tiktokshop.com` — Global Partner Portal serves non-US markets incl. **Malaysia**; a separate US Partner Portal exists for US-registered companies targeting US shops | [P] |
| App types | **Custom app** (own shop / direct distribution to named sellers) vs **Public app** (listed on the TikTok Shop App Store) | [V] |
| App type for this project | **Custom app** — WKC operates its own shops; no App Store listing needed | — |
| Data-access difference between app types | **None reported** — "no differences in data access level or API call rate limitations between public and custom apps" | [P] |
| Credentials | `app_key` + `app_secret` | [V] |
| Authorization | OAuth-style: authorization code exchanged for tokens | [V] |
| **`shop_cipher`** | Returned at token exchange; identifies *which shop's* data a call addresses; required on subsequent calls | [V] |
| `access_token` lifetime | **Conflicting** — "24 hours" reported by multiple third parties; a 7-day figure was not corroborated | [U] |
| `refresh_token` lifetime | Reported **365 days** | [P] |
| App approval time | 2–3 business days typically reported | [P] |
| API versioning | Date-stamped versions in the path, e.g. **`202309`**; breaking changes ship as new version strings | [V] |

**The `shop_cipher` concept is architecturally significant** and has no analogue on the other two platforms — the adapter interface must not assume "one token implies one shop".

### 2.2 Data domains

| Domain | Availability | Conf. |
|---|---|---|
| Orders — list, detail, items, SKU, qty, price, discount, shipping, status, recipient | Available (`/order/202309/...`) | [V] |
| Products / inventory / variations / price / status / category | Available | [V] |
| Fulfilment / packages / tracking / logistics | Available | [V] |
| Returns / refunds / cancellations | Available | [P] |
| **Finance — statements** | `GET /finance/202309/statements` | [V] |
| **Finance — withdrawals** | `GET /finance/202309/withdrawals` | [V] |
| Finance — settlement composition (item revenue − platform fee − affiliate commission − shipping adjustments) | Exposed via statements / transactions | [P] |
| **Affiliate — Seller API** | Exists as its own API family. Three families total: **Affiliate Seller** (brand's own programme), **Affiliate Partner** (agencies/TSPs), **Affiliate Creator** (creator tools) | [V] |
| Affiliate — which family applies here | **Affiliate Seller** — partner endpoints require separate agency approval that WKC does not need | [P] |
| Creator-level attributed GMV / commission for own shop | Likely within the Affiliate Seller domain | [U] |
| **Product-page traffic analytics** (impressions, clicks, CTR, conversion rate as shown in Seller Center) | No open endpoint identified | [U] → treat as **[X]** until proven otherwise |

### 2.3 Finance × Malaysia — the specific risk the brief flagged

The brief correctly warns that finance endpoints can be market-specific. Result:

| API | Market documented | Available to Malaysia? | Notes |
|---|---|---|---|
| `/finance/202309/statements` | Global docs | **[U]** | Documented globally; MY availability not separately confirmed |
| `/finance/202309/withdrawals` | Global docs | **[U]** | Same |
| Settlement / transaction detail | Global docs | **[U]** | Same |
| Tokopedia-specific finance flows | **Indonesia only** | Not applicable to MY | A separate ID-market integration one-pager exists **[V]** |

The existence of an Indonesia/Tokopedia-specific integration document **confirms that TikTok Shop's API surface genuinely varies by market**, which means MY availability cannot be inferred from global docs.

**This is a Phase-0 blocker, not a Phase-4 detail.** If MY finance endpoints turn out to be unavailable, TikTok net-settlement reporting stays manual and the MVP scope shrinks accordingly.

### 2.4 Webhooks

Order-status webhooks are documented, with retry behaviour. **[P]** Duplicate delivery, ordering guarantees and the signature scheme: **[U]**.

Design stance (mandated by the brief and adopted here): **webhooks are the fast path, polling reconciliation is the correctness path.** Never treat webhook delivery as complete.

### 2.5 Rate limits

**[U]** — not established. Reported as identical between custom and public apps. Must be confirmed before designing backfill concurrency.

---

## 3. LAZADA — Lazada Open Platform

### 3.1 Access and authentication

| Item | Finding | Conf. |
|---|---|---|
| Portal | `open.lazada.com` | [V] |
| Credentials | `app_key` + `app_secret` | [V] |
| Authorization | OAuth 2.0 — seller authorizes, code exchanged at **`/auth/token/create`** | [V] |
| Refresh | **`/auth/token/refresh`** | [V] |
| Signing | **HMAC-SHA256, Alibaba TOP scheme** — signature over the sorted parameter string using the app secret | [V] |
| Common params | `app_key`, `timestamp`, `access_token`, `sign_method=sha256`, `sign` | [V] |
| Roles | A distinct **Service Provider / ISV** role exists in the platform model | [P] |
| Malaysia | Lazada MY is a first-class market; region-specific gateway endpoints are used | [P] |

Lazada's TOP signing scheme is the fiddliest of the three (sorted-parameter canonical string). Well-trodden, but also the most common source of silent signature failures — budget real time for it and build a signing unit test from day one.

### 3.2 Data domains

| Domain | Endpoint / note | Conf. |
|---|---|---|
| Orders — list | **`/orders/get`** | [V] |
| Orders — single | **`/order/get`** | [V] |
| Order items | `/order/items/get`, multi-order variant | [P] |
| Products / SKU / price / stock / status | Product API family | [V] |
| **Finance — transaction details** | **`/finance/transaction/details/get`** | [V] |
| **Finance — account transactions** | **`/finance/transaction/accountTransactions/query`** | [V] |
| Returns and refunds | Return/Refund API family | [V] |
| Fulfilment / logistics / shipping documents | Fulfilment + Logistics API families | [V] |
| Marketing — vouchers / campaigns / promotions | Marketing API family | [P] |
| **Advertising — Sponsored Solutions** | A **Sponsored Solutions API** family exists | [P] — scope, metrics and approval requirements **[U]** |
| Membership / Service Market | Exist; not relevant here | [V] |
| **Shop traffic analytics** (visitors, page views, conversion rate as in Business Advisor) | No endpoint identified — Business Advisor appears to be a Seller Centre surface | [U] → treat as **[X]** until proven otherwise |

Note: the current dashboard's Lazada daily-sales file is literally a **Business Advisor** export (its header row reads `Data Source: Lazada - Business Advisor - Dashboard`). That is the strongest single indicator that today's Lazada numbers come from an analytics surface that has **no documented API equivalent** — the API path would have to rebuild those figures from orders instead of reading them off a report.

### 3.3 Webhooks / notifications

Lazada push/notification coverage for orders, products, inventory and fulfilment: **[U]**. Historically Lazada's push support has been weaker and less uniform than Shopee's.

**Plan for polling as the primary mechanism on Lazada**, and treat any push support found as a bonus optimisation rather than a dependency.

### 3.4 Rate limits and pagination

**[U]** for current limits. The legacy (dead) docs capped `GetOrders` at **100 per page** — a plausible order of magnitude for the live endpoint's page size, but **not citable as fact** for the current API.

---

## 4. THE FINDING THAT DRIVES THE WHOLE ARCHITECTURE

Cross-referencing the three platforms against **what the existing dashboard actually displays today** produces a clean and consequential split.

### 4.1 API-reachable — the transactional and financial core

Orders, order items, SKUs, quantities, prices, discounts, shipping fees, taxes, cancellations, returns, refunds, platform fees, commissions, settlements, payouts.

**All three platforms expose this.** This is the majority of the dashboard's *value* and **100% of its accuracy pain to date**. Every correctness bug fought in this project so far was a symptom of consuming **pre-aggregated spreadsheet summaries instead of transaction records**:

| Past bug | Root cause | Would it exist with order-level API data? |
|---|---|---|
| Lazada revenue too high | `Revenue` column was gross; cancellations/returns sat in separate columns | **No** — cancelled/returned orders carry a status |
| TikTok revenue too high | Needed `GMV − Items refunded` | **No** — same reason |
| TikTok product/affiliate/creator reports wrong | Monetary `Refunds` vs unit-count `Items refunded` look-alike columns | **No** — no ambiguous spreadsheet columns to confuse |
| Shopee triple-counted | Three funnel-stage rows per day summed together | **No** — one row per order, status is a field |
| Schema-drift risk | Platform renames a spreadsheet column | **Largely no** — versioned API contracts instead |

Moving to order-level API data does not merely automate the current numbers — **it makes a whole class of bug structurally impossible**, because net revenue stops being a guess about which spreadsheet column means what and becomes a sum over records with known statuses.

That is the strongest argument for this project, and it is stronger than the "no more manual uploads" argument.

### 4.2 NOT API-reachable — the traffic / funnel layer

| Metric | Currently shown on | API status |
|---|---|---|
| `visitors` | Sales Overview | **[X] / [U]** — no endpoint on any of the three |
| `impressions`, `clicks`, `ctr` | Product Performance | **[X] / [U]** except inside gated **ads** APIs |
| `conversion_rate` | Product Performance | Derivable *only if* visitors/clicks exist — so no |
| `sales_ratio` + traffic-source split | Affiliate & Marketing (Shopee) | **[X]** — pure Seller Centre analytics |
| Shopee funnel stages (Placed / Confirmed / Paid) | Sales Overview expander | **Reconstructable** from order status instead |

These are **Seller Centre / Business Advisor analytics surfaces**, not commerce APIs. Marketplaces deliberately do not expose shop-traffic telemetry through partner APIs.

### 4.3 Therefore

> **Excel cannot be removed completely — but it can stop being the data source.**

The defensible target state is a **hybrid**, which is also what the brief's own preferred diagram implies:

- **APIs become the source of truth** for everything transactional and financial — automatic, continuous, no human step.
- **Excel import survives as a narrow, optional, clearly-labelled side-channel** for the funnel/traffic metrics no API exposes — or those metrics are consciously dropped.
- **Excel / CSV / PDF export** becomes an output format, as intended.

Recommending "remove Excel entirely" would require silently deleting Product Performance's impressions/clicks/CTR and Sales Overview's visitors. That is a **product decision, not a technical one**, and it is escalated as Open Question **OQ-1** in the main plan.

---

## 5. Sources

### Official portals
Not machine-fetchable on 2026-09-17 — these are the required human-verification targets.

- Shopee Open Platform — https://open.shopee.com/documents/v2/Introduction
- TikTok Shop — API concepts overview — https://partner.tiktokshop.com/docv2/page/tts-api-concepts-overview
- TikTok Shop — Finance API overview — https://partner.tiktokshop.com/docv2/page/finance-api-overview
- TikTok Shop — Authorization guide (202309) — https://partner.tiktokshop.com/docv2/page/authorization-guide-202309
- TikTok Shop — Affiliate Seller API overview — https://partner.tiktokshop.com/docv2/page/affiliate-seller-api-overview
- TikTok Shop — Affiliate Creator API overview — https://partner.tiktokshop.com/docv2/page/affiliate-creator-api-overview
- TikTok Shop — publish a public app — https://partner.tiktokshop.com/docv2/page/publish-and-list-public-app
- TikTok Shop — ID/Tokopedia market one-pager (evidence markets diverge) — https://partner.tiktokshop.com/docv2/page/id-market-tokopedia-shop-open-api-integration-one-pager
- TikTok Shop — Node.js SDK integration — https://partner.tiktokshop.com/docv2/page/integrate-node-js-sdk
- Lazada Open Platform — https://open.lazada.com/ · API list — https://open.lazada.com/apps/doc/api
- Lazada — `finance/transaction/details/get` — https://open.lazada.com/apps/doc/api?path=%2Ffinance%2Ftransaction%2Fdetails%2Fget
- Lazada — `finance/transaction/accountTransactions/query` — https://open.lazada.com/apps/doc/api?path=/finance/transaction/accountTransactions/query
- Lazada — `order/document/get` — https://open.lazada.com/apps/doc/api?path=%2Forder%2Fdocument%2Fget
- TikTok Shop Open Platform Postman workspace — https://www.postman.com/tiktok-shop-open
- TikTok for Developers — affiliate API launch announcement — https://developers.tiktok.com/blog/2024-tiktok-shop-affiliate-apis-launch-developer-opportunity

### Decommissioned — do not use
Recorded so they are not mistakenly re-adopted by a future search.

- https://lazada-sellercenter.readme.io/docs/announcement (decommission notice, 2018-12-20)
- https://lazada-sellercenter.readme.io/docs/getorders (dead Seller Center API)

### Supporting / third-party
Used only where official pages were unreachable; treated as corroboration, never as the sole basis for a design decision.

- api2cart — Shopee API guide — https://api2cart.com/api-technology/shopee-api/
- api2cart — Shopee API documentation 2026 — https://api2cart.com/news/shopee-api-documentation/
- api2cart — Lazada developer and affiliate API guide — https://api2cart.com/api-technology/lazada-developer-api/
- publicapis.io — Shopee Open Platform key setup, auth, endpoints — https://publicapis.io/shopee-api
- Rollout — Shopee API essentials — https://rollout.com/integration-guides/shopee/api-essentials
- easydata.io.vn — what Shopee's official API can and cannot access — https://easydata.io.vn/blog/shopee-data-collection-with-api/
- congminh1254/shopee-sdk — Ads manager docs (ads gating and metrics) — https://github.com/congminh1254/shopee-sdk/blob/main/docs/managers/ads.md
- bemomentiq — TikTok Shop Finance API (statements, payouts, settlement) — https://bemomentiq.com/blog/tiktok-shop-finance-api-settlement-guide
- bemomentiq — TikTok Shop affiliate APIs explained — https://bemomentiq.com/blog/tiktok-shop-affiliate-apis-explained
- keyapi.ai — TikTok Shop API integration guide — https://www.keyapi.ai/blog/tiktok-shop-api-integration-guide-sellers/
- unified.to — setting up a TikTok Shop application — https://unified.to/blog/how_to_setup_a_tiktok_shop_application
- singaporeapi.com — Lazada Open Platform endpoints and auth — https://singaporeapi.com/apis/lazada-open-platform
- branch8/lazada-open-platform-sdk — https://github.com/branch8/lazada-open-platform-sdk
- EcomPHP/tiktokshop-php — https://github.com/EcomPHP/tiktokshop-php
