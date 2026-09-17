# Metric Definitions

**As of:** 2026-09-17 · Companion to `DATA_MODEL.md`

Different marketplaces define "sales" differently. This document fixes **one** definition per metric, computed identically across platforms, and states exactly which records feed it.

---

## 1. Classification of every metric the dashboard shows today

| Metric | Class | API-era source |
|---|---|---|
| Total Revenue | **Derived** | Sum over order items, status-filtered, minus refunds |
| Gross Revenue | **Derived** | Sum over order items, status-filtered |
| Refunded / Cancelled amount | **Derived** | Sum over `refunds.refund_amount` |
| Total Orders | **Derived** | Count of qualifying orders |
| Units Sold | **Derived** | Sum of `order_items.quantity` |
| Total Buyers | **Derived** | Distinct `orders.buyer_ref` |
| Visitors | **Unavailable** | 🔴 No API source — Excel-only or dropped |
| Product sales / units / orders | **Derived** | Order items grouped by SKU |
| Product impressions / clicks / CTR | **Unavailable** | 🔴 No API source (⚠️ partial inside gated ads APIs) |
| Conversion rate | **Unavailable** | 🔴 Depends on visitors/clicks |
| Ads spend / ROAS / CPC / cost-per-order | **Platform-specific, gated** | ⚠️ Shopee ads API (approval), Lazada Sponsored Solutions (❓), TikTok n/a |
| Affiliate commission / sales / ROI | **Platform-specific** | 🟡 TikTok Affiliate Seller only |
| Creator affiliate GMV / followers | **Platform-specific** | 🟡 TikTok, unconfirmed |
| Traffic-source sales ratio | **Unavailable** | 🔴 No API source |
| **Platform fees** | **Net new** | ✅ `transactions` — not available today at all |
| **Commission** | **Net new** | ✅ `transactions` |
| **Net settlement / payout** | **Net new** | ✅ `transactions` |

---

## 2. Canonical formulas

All monetary values in the shop's `currency`; all date bucketing in `Asia/Kuala_Lumpur`; all timestamps stored UTC.

### 2.1 Revenue-qualifying orders

```
qualifying_orders :=
    orders
    WHERE order_status IN ('paid', 'shipped', 'delivered', 'returned')
      AND ordered_at BETWEEN :start AND :end
```

`pending`, `cancelled` and `failed` are excluded. `returned` is **included** here and netted out via refunds — so a return reduces revenue by its actual refunded amount rather than erasing the whole order.

### 2.2 Gross Sales

```
gross_sales := Σ order_items.item_net   over qualifying_orders
```

Line-item level, after item-level discounts, before order-level adjustments, refunds and fees. This is the closest analogue to the marketplaces' own "GMV".

### 2.3 Refunded Revenue

```
refunded_revenue := Σ refunds.refund_amount
                    WHERE refund_status = 'completed'
                      AND refunded_at BETWEEN :start AND :end
```

**Bucketed by refund date, not order date.** A refund in September against a June order reduces September. This matches how the business experiences cash, and it is why the figure can exceed a low-volume day's gross sales — a legitimate negative, not a bug. (This behaviour was already observed in the current Lazada data, where single days show negative net revenue.)

### 2.4 Net Sales — **the headline number**

```
net_sales := gross_sales − refunded_revenue
```

Deliberately **excludes** platform fees and commission. Net Sales answers "what did we sell?"; Net Settlement (§2.8) answers "what did we get paid?". Collapsing the two into one figure is the mistake that makes marketplace dashboards untrustworthy.

### 2.5 Orders / Units / Buyers

```
orders_count := COUNT(DISTINCT qualifying_orders.id)
units_sold   := Σ order_items.quantity        over qualifying_orders
buyers_count := COUNT(DISTINCT orders.buyer_ref) over qualifying_orders
average_order_value := net_sales / NULLIF(orders_count, 0)
```

### 2.6 Platform Fees / Commission

```
platform_fees := −Σ transactions.amount WHERE transaction_type = 'platform_fee'
commission    := −Σ transactions.amount WHERE transaction_type IN ('commission','affiliate_fee')
```

Sign-flipped to positive-for-display, since `transactions.amount` stores deductions as negative.

### 2.7 Shipping

```
shipping_income := Σ orders.shipping_fee_buyer
shipping_cost   := Σ orders.shipping_fee_seller
                   + (−Σ transactions.amount WHERE transaction_type = 'shipping_fee')
```

### 2.8 Net Settlement

```
net_settlement := Σ transactions.amount
                  WHERE transaction_type IN
                        ('settlement','platform_fee','commission',
                         'affiliate_fee','shipping_fee','adjustment')
```

**Availability caveat — must be enforced in code, not just documented.** This metric requires working finance endpoints. If TikTok Shop MY finance access is unavailable (see `MALAYSIA_API_LIMITATIONS.md` §2.2), then a combined cross-platform Net Settlement would silently mean "Shopee + Lazada only", which is worse than showing nothing.

Rule: **the analytics layer must refuse to sum this metric across a platform set where any selected platform lacks finance coverage**, and instead render it per-platform with an explicit "not available for X" marker.

---

## 3. The Shopee discontinuity — read before switching over

The existing system was explicitly confirmed with the user (2026-07-30) to keep **Shopee revenue gross**, because staff's own Shopee dashboard does not subtract Cancelled/Returned Sales. Lazada and TikTok are net.

So today's system applies **three different revenue definitions** across three platforms, and the combined total is a sum of incomparable quantities.

The API rebuild fixes that — one definition everywhere. But the consequence must be stated plainly:

> **When the API version goes live, Shopee's revenue figure will drop** relative to what staff report, because it will finally net out returns. For the June 2026 reference period, Shopee's gross was RM768,434.60 with RM120,025.40 of cancellations/returns — so a net figure would be roughly **RM648,409**, about **15.6% lower**.

This is not a regression. It is the correct number appearing for the first time. But if it appears without warning, it will read as "the new system is broken", and trust in the rebuild will be lost on day one.

**Required mitigations:**
1. Show **both** Gross Sales and Net Sales on the overview — never Net alone.
2. Run both systems in parallel for one full month and publish a reconciliation table (old vs new, per platform, with the delta explained).
3. Agree the switchover definition with the staff who own the Shopee number **before** go-live, not after.

This is `OQ-2` in the main plan and it is a stakeholder task, not an engineering one.

---

## 4. Metric availability by platform

| Metric | Shopee | TikTok | Lazada | Combined? |
|---|---|---|---|---|
| Gross Sales | ✅ | ✅ | ✅ | ✅ |
| Refunded Revenue | ✅ | ✅ | ✅ | ✅ |
| Net Sales | ✅ | ✅ | ✅ | ✅ |
| Orders / Units | ✅ | ✅ | ✅ | ✅ |
| Buyers | 🟡 | 🟡 | 🟡 | 🟡 pseudonymous |
| AOV | ✅ | ✅ | ✅ | ✅ |
| Platform Fees | ✅ [U] | ❓ MY | ✅ [U] | ⚠️ only if all three |
| Commission | ✅ [U] | ❓ MY | ✅ [U] | ⚠️ |
| Net Settlement | ✅ [U] | ❓ MY | ✅ [U] | ⚠️ |
| Ads spend / ROAS | ⚠️ gated | 🔴 | ⚠️ ❓ | 🔴 |
| Affiliate commission | ❓ | ✅ | ❓ | 🔴 |
| Visitors / impressions / CTR / conversion | 🔴 | 🔴 | 🔴 | 🔴 |

Rendering rule for the UI: a metric that is unavailable for a selected platform renders as **"—" with a tooltip naming the reason**. It never renders as `0`, and it is never silently omitted from a sum.

---

## 5. Provenance labelling

Every figure carries a provenance tag:

| Tag | Meaning | UI treatment |
|---|---|---|
| `api` | Derived from synced API records | Normal, with "synced N minutes ago" |
| `excel` | From a manual upload | Badge: "from upload — DD Mon YYYY" |
| `mixed` | Period spans both | Badge + a link to the breakdown |
| `unavailable` | No source for this platform selection | "—" + reason |

This matters most during the transition, when a date range will genuinely straddle Excel-era and API-era data. Without it, a user comparing June (Excel) to October (API) would be comparing two different definitions and would have no way to know.
