# Malaysia-Specific API Considerations

**As of:** 2026-09-17 · Confidence marks: **[V]** verified · **[P]** probable · **[U]** unconfirmed

The brief asked specifically not to assume that US / UK / SG / ID API behaviour applies to Malaysia. This document records what was established, and — more importantly — exactly what must be confirmed by a human with portal access before any Malaysia-dependent code is written.

---

## 1. Why this document exists

One concrete piece of evidence proves the concern is real rather than theoretical:

> TikTok Shop publishes a **separate Indonesia / Tokopedia Open API integration one-pager**. **[V]**

A platform does not publish market-specific integration documents unless the integration genuinely differs by market. That single artifact invalidates any reasoning of the form *"the global docs say X, therefore Malaysia has X"*.

Applied consistently, this means **every** capability in `API_CAPABILITY_MATRIX.md` that is marked from global documentation carries an implicit Malaysia asterisk until checked with a MY-authorized shop.

---

## 2. Platform-by-platform

### 2.1 Shopee Malaysia

| Aspect | Finding | Conf. |
|---|---|---|
| Market supported | Shopee MY is a first-class Shopee market | [P] |
| MY-specific API gate | None found | [U] |
| Regional API host | Shopee uses region-specific hosts; the MY host must be confirmed | [U] |
| Currency | MYR | [P] |
| Escrow / payout semantics in MY | **Unconfirmed** — payout timing and fee composition are market-specific commercially, even where the endpoint is global | [U] |
| Ads API in MY | Gated globally; MY-specific availability unknown | [U] |

**Must verify:** correct regional host, `escrow_detail` field composition for MY, and whether the ads enablement process differs for MY sellers.

### 2.2 TikTok Shop Malaysia

| Aspect | Finding | Conf. |
|---|---|---|
| Portal to use | **Global Partner Portal** (`partner.tiktokshop.com`) — the separate US Partner Portal is only for US-registered companies targeting US shops | [P] |
| Market supported | TikTok Shop MY is an active market | [P] |
| **Finance API in MY** | **UNCONFIRMED — highest-priority unknown in this project** | [U] |
| Affiliate Seller API in MY | Unconfirmed | [U] |
| API version | `202309` family documented; MY parity unknown | [U] |
| Currency | MYR | [P] |

**This is the single largest Malaysia risk.** TikTok Shop's finance endpoints (`/finance/202309/statements`, `/finance/202309/withdrawals`) are documented globally, but the Indonesia precedent shows market divergence is real. If MY is excluded:

- TikTok settlement / fee / commission reporting cannot be automated.
- TikTok net revenue must be derived from order and refund records only — still workable, but **fees and commission become invisible for TikTok**, while remaining visible for Shopee and Lazada.
- The unified "Net Settlement" metric would then be **not comparable across platforms**, which is worse than not showing it. The metric layer must handle this explicitly rather than silently summing a partial figure (see `METRIC_DEFINITIONS.md` §5).

### 2.3 Lazada Malaysia

| Aspect | Finding | Conf. |
|---|---|---|
| Market supported | Lazada MY is a first-class market | [P] |
| Regional gateway | Lazada uses region-specific API gateways; the MY gateway must be confirmed | [P] |
| Finance endpoints in MY | Documented globally; MY availability unconfirmed | [U] |
| Sponsored Solutions (ads) in MY | Family exists; MY scope and approval unknown | [U] |
| Currency | MYR | [P] |

**Note:** the legacy dead docs used country-specific hosts (e.g. `api.sellercenter.lazada.sg`). The live Open Platform equivalent for MY must be taken from the current portal, **not** inferred from that pattern.

---

## 3. Currency and timezone

| Decision | Value | Rationale |
|---|---|---|
| Business currency | **MYR** | All three MY marketplaces settle in MYR |
| Business timezone | **Asia/Kuala_Lumpur** (UTC+8) | Matches how staff read "a day" |
| Storage of timestamps | **UTC**, always | Avoids DST/offset ambiguity; converted at query time |
| Storage of currency | **Per-shop `currency` column, not hard-coded** | Brief explicitly requires supporting other markets later |

**A real, non-obvious risk here:** marketplace APIs return timestamps in a mix of UTC epoch seconds and local-market times depending on the endpoint. A day-boundary error of 8 hours will silently misattribute up to a third of a day's orders to the wrong date — and this would be **invisible** in the dashboard, showing up only as "the numbers don't quite match Seller Centre".

Mitigation, mandatory: every adapter converts to UTC at the boundary, stores UTC, and **daily aggregates are computed in `Asia/Kuala_Lumpur`** — never by truncating a UTC timestamp. This must have a unit test with a fixture order timed at 23:30 MYT (= 15:30 UTC same day) and one at 07:30 MYT (= 23:30 UTC *previous* day).

---

## 4. Tax handling

Malaysia applies **SST** (Sales and Service Tax), and marketplace-collected tax treatment varies by platform and by seller registration status. **[U]** across all three platforms.

Do **not** design tax logic from the API field names alone. Until confirmed:
- Store whatever tax field the API returns, unmodified, per order.
- Do **not** surface a "tax" metric in the dashboard.
- Do **not** subtract tax in any net-revenue formula.

Rationale: a wrong tax figure in a finance dashboard is worse than an absent one, because it will be trusted.

---

## 5. Malaysia verification checklist

To be completed by a human with developer-portal access and a MY-authorized test shop, **before Phase 2**. Every row blocks the adapter work for that platform.

| # | Item | Platform | Blocks |
|---|---|---|---|
| MY-1 | Confirm correct regional API host | All 3 | All API work |
| MY-2 | Confirm finance endpoints return data for a MY shop | **TikTok** | Settlement metrics |
| MY-3 | Confirm finance endpoints return data for a MY shop | Shopee, Lazada | Settlement metrics |
| MY-4 | Confirm order history window / max backfill depth | All 3 | Initial sync design |
| MY-5 | Confirm actual rate limits observed for a MY shop | All 3 | Backfill concurrency |
| MY-6 | Confirm webhook/push availability for MY | Shopee, TikTok | Sync architecture |
| MY-7 | Confirm affiliate endpoints return data for a MY shop | TikTok | Affiliate page |
| MY-8 | Confirm ads API enablement path and metrics for MY | Shopee, Lazada | Ads page |
| MY-9 | Confirm currency field values and tax field semantics | All 3 | Metric layer |
| MY-10 | Confirm timestamp timezone per endpoint | All 3 | **All date-bucketed metrics** |

MY-10 is the quietest and most dangerous of these — it produces plausible-looking wrong numbers rather than errors.
