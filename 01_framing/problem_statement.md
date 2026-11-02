# Problem Statement

**Role:** Analyst for a Kenyan retail chain.

**Stakeholder:** Operations Manager for 5 stores — Nairobi (2), Kisumu, Mombasa, Nakuru.

**Decision the stakeholder makes differently:** sets monthly replenishment quantities per store × category at the start of each month, replacing the assumed current practice of repeating last week's sales.

**Prediction target:** units sold, at store × category × day grain.

**Forecast horizon:** 30 days from month end (e.g. 31 October origin → forecast 1–30 November).

**Success measure:** MAPE on the final 61-day holdout (Nov–Dec 2025) below 15%, and at least 2 percentage points better than the seasonal-naïve baseline (repeat the last observed week). The 2-point margin is my judgment.

**Out of scope:**
- Staffing / queue length (baskets would be the right target, not units).
- Orders (converting demand to orders needs stock-on-hand and lead times, not modelled).
- Customer churn (not the target).

**Assumptions stated honestly:**
- The retailer's current ordering rule is *assumed* to be repeat-last-week; I do not know it.
- CPI is a descriptive covariate only, not a model feature — no leakage.
- Easter dates come from a third-party calendar (no Kenyan official gazette located).
- 2 years of synthetic data (2024–2025, 731 days) with known injected defects.
