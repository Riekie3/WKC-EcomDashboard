# Unified Data Model

**As of:** 2026-09-17 · Companion to `DIRECT_MARKETPLACE_DASHBOARD_PLAN.md`

---

## 1. Design principles

1. **Store transactions, derive metrics.** The current system stores pre-aggregated daily/product summaries, which is why every "wrong number" bug in this project has been unfixable without a re-upload. The new model stores **orders and order items**; every headline metric becomes a query, not a stored figure.
2. **Never invent a field a platform does not provide.** Nullable beats fabricated. A column that is null for Lazada and populated for Shopee is honest; a column silently defaulted to 0 is a future bug.
3. **Keep the raw payload.** Every synced record keeps the platform's original JSON. Re-deriving a metric after a mapping bug must never require re-hitting the API.
4. **Idempotency is a schema property, not application logic.** Every platform-sourced row carries a natural key `(platform, shop_id, platform_*_id)` with a UNIQUE constraint, so a duplicate webhook is a no-op upsert rather than a double-count.
5. **One database per brand, unchanged.** The existing isolation decision (Sony → its own Neon project, Tefal → its own) is preserved. `shops` allows N shops per brand DB, which is the correct grain: one brand, three marketplace shops.
6. **Data minimisation by default.** Buyer PII is not stored unless a named feature requires it. See §6.

---

## 2. Entities

```
platform_accounts ──< shops ──< orders ──< order_items
                        │         │
                        │         ├──< refunds
                        │         └──< shipments
                        │
                        ├──< products ──< product_variants
                        ├──< transactions          (fees, commission, settlement)
                        ├──< sync_jobs
                        ├──< sync_cursors
                        └──< webhook_events

legacy_*  (existing Excel-sourced fact tables, retained read-only for funnel metrics)
```

---

## 3. Table definitions

Types shown as PostgreSQL. Every table gets `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` and `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` unless noted.

### 3.1 `platform_accounts` — one row per developer app registration

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `platform` | TEXT NOT NULL | `shopee` / `tiktok_shop` / `lazada` |
| `app_identifier` | TEXT NOT NULL | Shopee `partner_id`, TikTok/Lazada `app_key`. **Not secret.** |
| `app_secret_enc` | BYTEA NOT NULL | Encrypted at rest — see plan §14 |
| `environment` | TEXT NOT NULL | `production` / `sandbox` |
| `status` | TEXT NOT NULL | `active` / `disabled` |

UNIQUE `(platform, app_identifier, environment)`

### 3.2 `shops` — one row per authorized marketplace shop

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal shop id used everywhere downstream |
| `platform_account_id` | UUID FK → platform_accounts | |
| `platform` | TEXT NOT NULL | Denormalised for query convenience |
| `platform_shop_id` | TEXT NOT NULL | Shopee `shop_id`, Lazada seller id, TikTok `shop_id` |
| `shop_cipher` | TEXT NULL | **TikTok only** — required on every TikTok call |
| `display_name` | TEXT | e.g. "Sony Official Store MY" |
| `region` | TEXT NOT NULL | `MY` |
| `currency` | TEXT NOT NULL | `MYR` — stored, never hard-coded |
| `timezone` | TEXT NOT NULL | `Asia/Kuala_Lumpur` |
| `access_token_enc` | BYTEA | Encrypted |
| `refresh_token_enc` | BYTEA | Encrypted |
| `access_token_expires_at` | TIMESTAMPTZ | Shopee: +4h. Drives the refresh scheduler. |
| `refresh_token_expires_at` | TIMESTAMPTZ | Shopee: +30d. **Drives re-authorization alerts.** |
| `connection_status` | TEXT NOT NULL | `connected` / `token_expired` / `revoked` / `error` |
| `last_synced_at` | TIMESTAMPTZ NULL | |

UNIQUE `(platform, platform_shop_id)` · INDEX `(connection_status)` · INDEX `(access_token_expires_at)`

### 3.3 `orders`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `shop_id` | UUID FK → shops, NOT NULL | |
| `platform` | TEXT NOT NULL | |
| `platform_order_id` | TEXT NOT NULL | |
| `order_status` | TEXT NOT NULL | **Normalised** — see §5 |
| `platform_order_status` | TEXT NOT NULL | Raw, unmapped |
| `ordered_at` | TIMESTAMPTZ NOT NULL | UTC |
| `paid_at` | TIMESTAMPTZ NULL | |
| `shipped_at` | TIMESTAMPTZ NULL | |
| `delivered_at` | TIMESTAMPTZ NULL | |
| `cancelled_at` | TIMESTAMPTZ NULL | |
| `platform_updated_at` | TIMESTAMPTZ NULL | Drives incremental sync cursors |
| `currency` | TEXT NOT NULL | |
| `item_subtotal` | NUMERIC(14,2) NULL | Sum of line items before order-level adjustments |
| `shipping_fee_buyer` | NUMERIC(14,2) NULL | Paid by buyer |
| `shipping_fee_seller` | NUMERIC(14,2) NULL | Borne by seller |
| `seller_discount` | NUMERIC(14,2) NULL | Seller-funded |
| `platform_discount` | NUMERIC(14,2) NULL | Platform-funded |
| `tax_amount` | NUMERIC(14,2) NULL | **Stored, not used** until MY tax semantics confirmed |
| `buyer_paid_total` | NUMERIC(14,2) NULL | What the buyer paid |
| `buyer_ref` | TEXT NULL | **Pseudonymous** buyer key — see §6 |
| `raw_payload` | JSONB NOT NULL | Original API response |
| `first_seen_at` | TIMESTAMPTZ NOT NULL | |

UNIQUE `(platform, platform_order_id)` — **the idempotency anchor**
INDEX `(shop_id, ordered_at)` · `(shop_id, platform_updated_at)` · `(order_status)`

### 3.4 `order_items`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `order_id` | UUID FK → orders, NOT NULL | |
| `shop_id` | UUID FK → shops, NOT NULL | Denormalised for direct aggregation |
| `platform_item_id` | TEXT NULL | Line id where the platform provides one |
| `platform_product_id` | TEXT NULL | |
| `platform_sku_id` | TEXT NULL | |
| `seller_sku` | TEXT NULL | |
| `product_name` | TEXT NULL | Snapshot at order time |
| `variation_name` | TEXT NULL | |
| `quantity` | INTEGER NOT NULL | |
| `unit_price` | NUMERIC(14,2) NULL | |
| `item_discount` | NUMERIC(14,2) NULL | |
| `item_gross` | NUMERIC(14,2) NULL | quantity × unit_price |
| `item_net` | NUMERIC(14,2) NULL | after item-level discounts |
| `raw_payload` | JSONB NOT NULL | |

UNIQUE `(order_id, platform_item_id)` where `platform_item_id` is not null
INDEX `(shop_id, platform_sku_id)` · `(platform_product_id)`

### 3.5 `refunds`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `shop_id` | UUID FK, NOT NULL | |
| `order_id` | UUID FK NULL | Null if the platform reports a refund not resolvable to a synced order |
| `platform_refund_id` | TEXT NOT NULL | |
| `refund_type` | TEXT NOT NULL | `cancellation` / `return` / `refund_only` / `adjustment` |
| `refund_status` | TEXT NOT NULL | Normalised |
| `refund_amount` | NUMERIC(14,2) NOT NULL | **Always a currency amount, never a unit count** |
| `refund_quantity` | INTEGER NULL | Units — kept strictly separate from amount |
| `refunded_at` | TIMESTAMPTZ NULL | |
| `reason` | TEXT NULL | |
| `raw_payload` | JSONB NOT NULL | |

UNIQUE `(platform, platform_refund_id)` · INDEX `(shop_id, refunded_at)`

> The split between `refund_amount` and `refund_quantity` is deliberate and non-negotiable. The single worst data bug in this project's history came from a TikTok spreadsheet exposing a monetary `Refunds` column next to a unit-count `Items refunded` column with confusingly parallel names. Encoding the distinction in the schema makes that class of error a type error rather than a silent miscalculation.

### 3.6 `transactions` — fees, commission, settlement

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `shop_id` | UUID FK, NOT NULL | |
| `order_id` | UUID FK NULL | Where attributable |
| `platform_transaction_id` | TEXT NOT NULL | |
| `transaction_type` | TEXT NOT NULL | `settlement` / `platform_fee` / `commission` / `affiliate_fee` / `shipping_fee` / `adjustment` / `payout` / `tax` |
| `amount` | NUMERIC(14,2) NOT NULL | **Signed** — negative for deductions |
| `currency` | TEXT NOT NULL | |
| `occurred_at` | TIMESTAMPTZ NOT NULL | |
| `statement_id` | TEXT NULL | TikTok statement, Shopee payout batch, Lazada statement |
| `raw_payload` | JSONB NOT NULL | |

UNIQUE `(platform, platform_transaction_id)` · INDEX `(shop_id, occurred_at, transaction_type)`

### 3.7 `products` / `product_variants`

`products`: `id`, `shop_id`, `platform_product_id`, `name`, `status`, `category_id`, `category_name`, `created_at_platform`, `raw_payload`. UNIQUE `(shop_id, platform_product_id)`.

`product_variants`: `id`, `product_id`, `shop_id`, `platform_sku_id`, `seller_sku`, `variation_name`, `price`, `stock`, `status`, `raw_payload`. UNIQUE `(shop_id, platform_sku_id)`.

### 3.8 `shipments`

`id`, `shop_id`, `order_id`, `platform_package_id`, `tracking_number`, `carrier`, `shipment_status`, `shipped_at`, `delivered_at`, `raw_payload`. UNIQUE `(platform, platform_package_id)`.

### 3.9 `sync_jobs` — observability for every sync run

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `shop_id` | UUID FK NULL | Null for global jobs |
| `job_type` | TEXT NOT NULL | `initial_backfill` / `incremental_orders` / `finance_sync` / `product_sync` / `reconciliation` / `token_refresh` |
| `status` | TEXT NOT NULL | `queued` / `running` / `succeeded` / `failed` / `partial` |
| `window_start` / `window_end` | TIMESTAMPTZ NULL | Data window covered |
| `records_seen` / `records_written` | INTEGER | |
| `error_code` | TEXT NULL | From the taxonomy in plan §16 |
| `error_detail` | TEXT NULL | **Secret-masked** |
| `started_at` / `finished_at` | TIMESTAMPTZ | |
| `attempt` | INTEGER NOT NULL DEFAULT 1 | |

INDEX `(shop_id, job_type, started_at DESC)` · `(status)`

This table is what makes "is the dashboard's data actually current?" answerable — which the current system cannot answer at all.

### 3.10 `sync_cursors` — incremental sync position

`shop_id` + `resource` (`orders`/`refunds`/`transactions`/`products`) PK, plus `cursor_value` (TIMESTAMPTZ or opaque token), `updated_at`.

### 3.11 `webhook_events` — raw inbound events

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `platform` | TEXT NOT NULL | |
| `shop_id` | UUID FK NULL | Resolved where possible |
| `event_type` | TEXT NOT NULL | |
| `platform_event_id` | TEXT NULL | |
| `signature_valid` | BOOLEAN NOT NULL | |
| `payload` | JSONB NOT NULL | |
| `received_at` | TIMESTAMPTZ NOT NULL | |
| `processed_at` | TIMESTAMPTZ NULL | |
| `process_status` | TEXT NOT NULL | `pending` / `processed` / `ignored` / `failed` |
| `dedupe_key` | TEXT NOT NULL | UNIQUE — makes duplicate delivery a no-op |

UNIQUE `(dedupe_key)` · INDEX `(process_status, received_at)`

---

## 4. Field mapping — orders

Per the brief's requested format. **Every "source" cell below is [U] until portal verification** (`marketplace-api-research.md` §0).

| internal_field | type | description | Shopee source | TikTok source | Lazada source | nullable | transformation |
|---|---|---|---|---|---|---|---|
| `platform_order_id` | TEXT | Platform's order id | `order_sn` | `order_id` | `order_id` | no | cast to text |
| `order_status` | TEXT | Normalised status | `order_status` | `order_status` | `statuses[]` | no | via §5 map |
| `platform_order_status` | TEXT | Raw status | same | same | same | no | verbatim |
| `ordered_at` | TIMESTAMPTZ | Creation | `create_time` (epoch) | `create_time` (epoch) | `created_at` | no | → UTC |
| `paid_at` | TIMESTAMPTZ | Payment | `pay_time` | payment info | `updated_at` + status | yes | → UTC |
| `platform_updated_at` | TIMESTAMPTZ | Last change | `update_time` | `update_time` | `updated_at` | yes | → UTC; cursor source |
| `currency` | TEXT | Currency | `currency` | `currency` | order currency | no | fallback: shop currency |
| `item_subtotal` | NUMERIC | Pre-adjustment | derive from items | derive from items | derive from items | yes | Σ `item_net` |
| `shipping_fee_buyer` | NUMERIC | Buyer-paid shipping | `estimated_shipping_fee` / escrow | shipping fields | `shipping_fee` | yes | — |
| `seller_discount` | NUMERIC | Seller-funded | voucher fields | seller discount | `voucher_seller` | yes | — |
| `platform_discount` | NUMERIC | Platform-funded | voucher fields | platform discount | `voucher_platform` | yes | — |
| `tax_amount` | NUMERIC | Tax | ❓ | ❓ | `tax_amount`? | yes | **stored, unused** |
| `buyer_paid_total` | NUMERIC | Buyer total | `total_amount` | `payment.total` | `price` | yes | — |
| `buyer_ref` | TEXT | Pseudonymous buyer | hash(`buyer_user_id`) | hash(buyer id) | hash(customer id) | yes | **HMAC, see §6** |

**Fields deliberately absent from the model:** `visitors`, `impressions`, `clicks`, `ctr`, `conversion_rate`. No platform provides them via API; adding nullable columns for them would invite a future contributor to "fill them in" from an unreliable source.

---

## 5. Status normalisation

Platform statuses differ in both vocabulary and granularity. The normalised set is intentionally small, because metrics depend on it:

| Normalised | Meaning | Counts toward revenue? |
|---|---|---|
| `pending` | Created, not yet paid | **No** |
| `paid` | Paid, not yet fulfilled | Yes |
| `shipped` | In fulfilment | Yes |
| `delivered` | Completed | Yes |
| `cancelled` | Cancelled before fulfilment | **No** |
| `returned` | Returned after delivery | Yes, **less** the refund |
| `failed` | Failed/expired | **No** |

Each adapter owns a `STATUS_MAP` from its raw statuses to this set, defined in configuration (plan §17), never inline in query code. Any unmapped raw status **raises**, rather than defaulting — an unknown status silently mapping to `paid` would inflate revenue exactly the way the old spreadsheet bugs did.

**This replaces Shopee's Placed/Confirmed/Paid funnel-stage hack.** Instead of three duplicate row sets per day (the cause of the triple-count bug), there is one order row with one status.

---

## 6. PII and data minimisation

The APIs return buyer names, phone numbers, email addresses and full delivery addresses. **The analytics dashboard needs none of them.**

| Category | Examples | Decision |
|---|---|---|
| Analytics data | amounts, quantities, SKUs, statuses, timestamps | **Store** |
| Operational data | tracking number, carrier, package status | **Store** (needed for fulfilment views) |
| Sensitive PII | buyer name, phone, email, address | **Do not store** |

For distinct-buyer counts, store `buyer_ref` = `HMAC-SHA256(buyer_id, per-shop salt)` — stable enough to count distinct buyers and identify repeat purchase, while not being a usable identifier if the database leaks.

`raw_payload` is the one place PII could leak back in. Adapters therefore **strip PII fields from the payload before persisting** it. This is a scrubbing step in the adapter, unit-tested with a fixture containing every PII field.

---

## 7. Relationship to the existing schema

The current six fact tables (`daily_sales`, `product_performance`, `ads_performance`, `affiliate_marketing`, `traffic_source_performance`, `creator_performance`) plus `upload_batches` are **not dropped**.

| Existing table | Fate |
|---|---|
| `daily_sales` | **Superseded** by `orders` + `order_items`. Retained read-only for historical periods predating API connection. |
| `product_performance` | **Partially superseded** — sales/units/orders come from order items; impressions/clicks/CTR remain Excel-only. |
| `ads_performance` | **Retained** — API replacement is approval-gated and may never arrive. |
| `affiliate_marketing` | **Partially superseded** (TikTok only). |
| `traffic_source_performance` | **Retained** — no API equivalent exists. |
| `creator_performance` | **Partially superseded** (TikTok, unconfirmed). |
| `upload_batches` | **Retained** — still the provenance record for Excel imports. |

Coexistence rule: every metric declares whether it is served from `api` or `excel` provenance, and the UI labels any Excel-derived figure. Users must never be left guessing whether a number is live or from a stale upload — that ambiguity would be a step backwards from today, where at least everything is uniformly manual.
