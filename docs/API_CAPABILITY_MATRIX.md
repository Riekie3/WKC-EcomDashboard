# API Capability Matrix

**As of:** 2026-09-17 · **Market:** Malaysia · Sources and confidence marks: see `marketplace-api-research.md`

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Fully available via official API |
| 🟡 | Partially available / derivable with work |
| 🔴 | Not available via official API |
| ⚠️ | Requires approval or special access |
| ❓ | Not confirmed — must be verified against official docs before it is designed against |

Confidence marks in brackets — **[V]** verified · **[P]** probable · **[U]** unconfirmed.

---

## 1. Core capability matrix

| Capability | Shopee | TikTok Shop | Lazada |
|---|---|---|---|
| Seller authentication (OAuth) | ✅ [V] | ✅ [V] | ✅ [V] |
| Request signing | ✅ HMAC-SHA256 [V] | ✅ app_key/secret [V] | ✅ HMAC-SHA256, TOP scheme [V] |
| Multi-shop addressing | shop_id [V] | **shop_cipher** [V] | seller-scoped token [P] |
| Orders — list | ✅ [V] | ✅ `/order/202309/...` [V] | ✅ `/orders/get` [V] |
| Orders — detail | ✅ [V] | ✅ [V] | ✅ `/order/get` [V] |
| Order items / line items | ✅ [V] | ✅ [V] | ✅ [P] |
| Order status | ✅ [V] | ✅ [V] | ✅ [V] |
| Products | ✅ [V] | ✅ [V] | ✅ [V] |
| SKU / variants | ✅ [V] | ✅ [V] | ✅ [V] |
| Inventory / stock | ✅ [V] | ✅ [V] | ✅ [V] |
| Pricing | ✅ [V] | ✅ [V] | ✅ [V] |
| Discounts / vouchers | ✅ [P] | 🟡 order-level [P] | ✅ Marketing API [P] |
| Shipping / logistics | ✅ [V] | ✅ [V] | ✅ [V] |
| Tracking | ✅ [V] | ✅ [V] | ✅ [V] |
| Returns | ✅ [V] | ✅ [P] | ✅ [V] |
| Refunds | ✅ [V] | ✅ [P] | ✅ [V] |
| **Finance — transactions** | ✅ billing/wallet transactions [P] | ✅ statements `/finance/202309/statements` [V] | ✅ `/finance/transaction/details/get` [V] |
| **Finance — settlement** | ✅ **escrow detail** [P] | ✅ statements [V] | ✅ `accountTransactions/query` [V] |
| Finance — commission / platform fees | 🟡 within escrow detail [P] | 🟡 within statements [P] | 🟡 within transactions [P] |
| Finance — payouts / withdrawals | ✅ payout [P] | ✅ `/finance/202309/withdrawals` [V] | 🟡 [U] |
| Taxes | ❓ [U] | ❓ [U] | ❓ [U] |
| **Marketing / ads performance** | ⚠️ Product Ads API exists, **needs Shopee Partner Support to enable** [P] | 🔴 not in Shop API (paid ads live in TikTok Ads, a separate product) [P] | ⚠️ Sponsored Solutions API exists, scope/approval ❓ [U] |
| **Affiliate data** | ❓ no Open Platform endpoint found [U] | ✅ **Affiliate Seller API** [V] | ❓ [U] |
| Creator-level attributed GMV | 🔴 n/a | 🟡 likely in Affiliate Seller domain [U] | 🔴 n/a |
| **Shop traffic — visitors / page views** | 🔴 Seller Centre only [X] | 🔴 [U→X] | 🔴 Business Advisor only [U→X] |
| **Product impressions / clicks / CTR** | 🔴 except inside gated ads API [X] | 🔴 [U→X] | 🔴 [U→X] |
| **Conversion rate** | 🔴 depends on traffic data [X] | 🔴 [U→X] | 🔴 [U→X] |
| Traffic-source breakdown | 🔴 [X] | 🔴 n/a | 🔴 n/a |
| Webhooks / push | ✅ order, return, logistics, payment, item [P] | ✅ order status [P] | ❓ weak/unconfirmed [U] |
| Historical backfill | ❓ window limits [U] | ❓ [U] | ❓ [U] |
| Rate limits | ❓ conflicting: 10 rps vs 100 rpm [U] | ❓ [U] | ❓ [U] |
| Malaysia support | ✅ [P] | ✅ Global Partner Portal [P] | ✅ [P] |

---

## 2. The same matrix, re-cut by what the dashboard actually shows today

This is the cut that matters for scoping. Each row is a field the current app renders.

| Current field | Current source | API replacement | Verdict |
|---|---|---|---|
| `revenue` (net) | Spreadsheet column, platform-specific gross/net rules | Sum of order line items by status, minus refunds | ✅ **Better than today** |
| `gross_revenue` | Spreadsheet column | Sum of order line items | ✅ Better |
| `refund_amount` | Spreadsheet column | Refund/return records | ✅ Better |
| `orders` | Spreadsheet column | Count of orders | ✅ Better |
| `units_sold` | Spreadsheet column | Sum of line-item quantities | ✅ Better |
| `buyers` | Spreadsheet column | Distinct buyer count from orders | 🟡 Derivable; buyer identity is PII — see `DATA_MODEL.md` §6 |
| `visitors` | Spreadsheet column | — | 🔴 **No API source** |
| `funnel_stage` (Shopee Placed/Confirmed/Paid) | Three sheets in one workbook | Order status field | ✅ Better — and removes the triple-count bug class |
| `sales` (per product) | Spreadsheet column | Sum of line items grouped by SKU | ✅ Better |
| `impressions` / `clicks` / `ctr` (per product) | Spreadsheet column | — | 🔴 **No API source** (⚠️ partially inside gated ads APIs) |
| `conversion_rate` (per product) | Spreadsheet column | — | 🔴 No API source |
| Ads `spend` / `roas` / `cpc` / `cost_per_order` | Spreadsheet column | ⚠️ Shopee ads API (gated), Lazada Sponsored Solutions (❓), TikTok n/a | ⚠️ **Per-platform, approval-gated** |
| Affiliate `commission` / `sales` / `roi` | Spreadsheet column | TikTok Affiliate Seller ✅; Shopee ❓ | 🟡 **Partial — TikTok only** |
| Creator `affiliate_gmv` / `followers` | Spreadsheet column | TikTok Affiliate Seller 🟡 | 🟡 Unconfirmed |
| Traffic-source `sales_ratio` | Spreadsheet column | — | 🔴 No API source |
| **New:** platform fees, commission, settlement, payout | **Not available today at all** | ✅ All three platforms | ✅ **Net new capability** |

### Reading of this table

Three distinct groups emerge:

1. **Gets strictly better (and is the bulk of the value):** all revenue, order, unit, refund and product-sales figures. These become more accurate, not merely more automated.
2. **Net new:** true fee/commission/settlement visibility — the dashboard cannot show this today at all, because the exports do not carry it. This is arguably the single biggest upside of the project and was not in the original brief's metric list.
3. **Cannot be replaced:** the traffic/funnel layer — visitors, impressions, clicks, CTR, conversion rate, traffic-source ratio.

Group 3 is the reason "no Excel at all" is not achievable without a deliberate product decision to drop those metrics. See **OQ-1** in the main plan.
