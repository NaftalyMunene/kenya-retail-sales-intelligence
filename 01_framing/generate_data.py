"""
Synthetic data generator for the Kenya Retail Sales Intelligence project.

Run from the repo root:
    python 01_framing/generate_data.py

Writes to data/raw/generated/:
    stores.csv, products.csv, customers.csv, sales.csv, injected_defects.json

Everything is driven by SEED, so the output is reproducible.
Demand effects built in (the "known truth" you should recover in EDA and stats):
    - weekend lift, payday lift (25th to 2nd), December peak, January dip
    - public holiday effect (varies by holiday), Easter and Idd effects
    - gradual price inflation over 2024 to 2025
Defects injected on purpose (counts logged in injected_defects.json):
    duplicates, missing values, bad dates, negative quantities, price outliers,
    inconsistent text casing, orphan customer IDs.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START, END = date(2024, 1, 1), date(2025, 12, 31)
N_CUSTOMERS = 3000
OUT = Path("data/raw/synthetic")
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(SEED)
# ---------------------------------------------------------------- holidays
def easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)

def holiday_calendar():
    """Fixed holidays, Sunday rule, Easter (computed), Idd (gazetted dates)."""
    cal = {}
    fixed = [(1, 1, "New Year"), (5, 1, "Labour Day"), (6, 1, "Madaraka Day"),
             (10, 10, "Mazingira Day"), (10, 20, "Mashujaa Day"),
             (12, 12, "Jamhuri Day"), (12, 25, "Christmas"), (12, 26, "Boxing Day")]
    for y in (2024, 2025):
        for m, d, name in fixed:
            dt = date(y, m, d)
            cal[dt] = name
            if dt.weekday() == 6:  # Sunday rule: following Monday is a holiday
                cal[dt + timedelta(days=1)] = name + " (observed)"
        e = easter(y)
        cal[e - timedelta(days=2)] = "Good Friday"
        cal[e + timedelta(days=1)] = "Easter Monday"
    cal[date(2024, 4, 10)] = "Idd-ul-Fitr"   # Gazette Notice 4339
    cal[date(2025, 3, 31)] = "Idd-ul-Fitr"   # Gazette Notice 3861
    return cal

HOLIDAYS = holiday_calendar()
# demand multiplier per holiday (retail: shopping peaks before and on festive days)
HOL_EFFECT = {"Christmas": 1.45, "Boxing Day": 0.85, "New Year": 0.80,
              "Idd-ul-Fitr": 1.35, "Good Friday": 0.75, "Easter Monday": 1.15,
              "Labour Day": 0.90, "Madaraka Day": 1.10, "Mashujaa Day": 1.10,
              "Jamhuri Day": 1.10, "Mazingira Day": 1.05}

def holiday_multiplier(d):
    name = HOLIDAYS.get(d)
    if name:
        return HOL_EFFECT.get(name.replace(" (observed)", ""), 1.05)
    # pre-festive shopping run-up (3 days before Christmas, Idd, Easter weekend)
    for k, dt in HOLIDAYS.items():
        base = dt if True else None
        if 1 <= (k - d).days <= 3 and HOLIDAYS[k] in ("Christmas", "Idd-ul-Fitr", "Good Friday"):
            return 1.20
    return 1.0

# ------------------------------------------------------------------ stores
stores = pd.DataFrame({
    "store_id": [f"S{i:02d}" for i in range(1, 9)],
    "store_name": ["Nairobi CBD", "Westlands", "Thika Road", "Mombasa Nyali",
                   "Kisumu Central", "Nakuru Town", "Eldoret Town", "Nyeri Town"],
    "county": ["Nairobi", "Nairobi", "Kiambu", "Mombasa", "Kisumu", "Nakuru", "Uasin Gishu", "Nyeri"],
    "format": ["Supermarket", "Supermarket", "Hypermarket", "Supermarket",
               "Mini-mart", "Supermarket", "Mini-mart", "Mini-mart"],
    "size_factor": [1.6, 1.3, 1.8, 1.2, 0.8, 1.0, 0.8, 0.6],
})

# ---------------------------------------------------------------- products
cats = {  # category: (n_products, price_low, price_high, popularity)
    "Groceries": (18, 60, 900, 3.0), "Beverages": (10, 40, 400, 2.0),
    "Household": (10, 120, 1500, 1.2), "Personal Care": (8, 100, 1200, 1.0),
    "Electronics": (6, 800, 25000, 0.25), "Clothing": (8, 400, 4500, 0.5),
}
rows = []
for c, (n, lo, hi, pop) in cats.items():
    prices = np.round(np.exp(rng.uniform(np.log(lo), np.log(hi), n)) / 5) * 5
    for i, p in enumerate(prices, 1):
        rows.append((f"{c[:3].upper()}{i:03d}", f"{c} item {i}", c, float(p), pop))
products = pd.DataFrame(rows, columns=["product_id", "product_name", "category", "base_price_kes", "popularity"])

# --------------------------------------------------------------- customers
towns = stores["county"].tolist()
cust_ids = [f"C{i:05d}" for i in range(1, N_CUSTOMERS + 1)]
segment = rng.choice(["Budget", "Regular", "Premium"], N_CUSTOMERS, p=[0.45, 0.40, 0.15])
customers = pd.DataFrame({
    "customer_id": cust_ids,
    "signup_date": [START + timedelta(days=int(x)) for x in rng.integers(-400, 600, N_CUSTOMERS)],
    "county": rng.choice(towns, N_CUSTOMERS, p=stores["size_factor"] / stores["size_factor"].sum()),
    "segment": segment,
    "loyalty_member": rng.random(N_CUSTOMERS) < 0.55,
})
seg_spend = {"Budget": 0.8, "Regular": 1.0, "Premium": 1.8}
# heavy-tailed visit propensity: a few frequent shoppers, many occasional ones
propensity = rng.gamma(1.2, 1.0, N_CUSTOMERS) * customers["segment"].map({"Budget": 0.8, "Regular": 1.0, "Premium": 1.3}).values
propensity = propensity / propensity.sum()

# ------------------------------------------------------------------- sales
def inflation_index(d):  # about 4.5% a year, smooth
    return 1 + 0.045 * ((d - START).days / 365)

records, tid = [], 1
pop = products["popularity"].values / products["popularity"].sum()
pay_methods = ["M-Pesa", "Cash", "Card"]
pay_p = [0.62, 0.23, 0.15]

d = START
while d <= END:
    month_mult = {12: 1.30, 1: 0.88, 2: 0.95, 8: 1.05}.get(d.month, 1.0)
    dow_mult = 1.25 if d.weekday() >= 5 else 1.0
    pay_mult = 1.18 if (d.day >= 25 or d.day <= 2) else 1.0
    hol = holiday_multiplier(d)
    growth = 1 + 0.06 * ((d - START).days / 365)
    for _, s in stores.iterrows():
        lam = 22 * s["size_factor"] * month_mult * dow_mult * pay_mult * hol * growth
        n = rng.poisson(lam)
        if n == 0:
            continue
        cust_idx = rng.choice(N_CUSTOMERS, n, p=propensity)
        prod_idx = rng.choice(len(products), n, p=pop)
        for ci, pi in zip(cust_idx, prod_idx):
            seg_name = segment[ci]
            base = products.at[pi, "base_price_kes"]
            price = round(base * inflation_index(d) * rng.uniform(0.97, 1.03) / 5) * 5
            qty_mean = 2.2 * seg_spend[seg_name] if products.at[pi, "category"] in ("Groceries", "Beverages") else 1.2
            qty = max(1, int(rng.poisson(qty_mean)))
            disc = round(price * qty * rng.choice([0, 0.05, 0.10, 0.20], p=[0.72, 0.15, 0.09, 0.04]), 2)
            records.append((f"T{tid:07d}", d.isoformat(), s["store_id"], cust_ids[ci],
                            products.at[pi, "product_id"], qty, float(price), disc,
                            rng.choice(pay_methods, p=pay_p)))
            tid += 1
    d += timedelta(days=1)

sales = pd.DataFrame(records, columns=["transaction_id", "date", "store_id", "customer_id",
                                       "product_id", "quantity", "unit_price_kes", "discount_kes", "payment_method"])
clean_rows = len(sales)

# ---------------------------------------------------------- inject defects
log = {"seed": SEED, "clean_rows_before_defects": clean_rows}
def pick(frac):
    return rng.choice(sales.index, int(len(sales) * frac), replace=False)

idx = pick(0.004); sales.loc[idx, "customer_id"] = None;               log["missing_customer_id"] = len(idx)
idx = pick(0.002); sales.loc[idx, "unit_price_kes"] = np.nan;           log["missing_unit_price"] = len(idx)
idx = pick(0.001); sales.loc[idx, "date"] = rng.choice(["31/02/2024", "2024-13-05", "not available", "00-00-0000"], len(idx)); log["bad_dates"] = len(idx)
idx = pick(0.001); sales.loc[idx, "quantity"] = -sales.loc[idx, "quantity"]; log["negative_quantity"] = len(idx)
idx = pick(0.0015); sales.loc[idx, "unit_price_kes"] = sales.loc[idx, "unit_price_kes"] * 10; log["price_outliers_x10"] = len(idx)
idx = pick(0.05); sales.loc[idx, "payment_method"] = sales.loc[idx, "payment_method"].str.upper(); log["payment_method_case_issues"] = len(idx)
idx = pick(0.003); sales.loc[idx, "customer_id"] = "C99999";            log["orphan_customer_ids"] = len(idx)
dup = sales.sample(int(len(sales) * 0.003), random_state=SEED)
sales = pd.concat([sales, dup], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)
log["exact_duplicate_rows"] = len(dup)
log["final_rows"] = len(sales)

# ------------------------------------------------------------------ write
stores.drop(columns=["size_factor"]).to_csv(OUT / "stores.csv", index=False)
products.drop(columns=["popularity"]).to_csv(OUT / "products.csv", index=False)
customers.to_csv(OUT / "customers.csv", index=False)
sales.to_csv(OUT / "sales.csv", index=False)
(OUT / "injected_defects.json").write_text(json.dumps(log, indent=2))
print(json.dumps(log, indent=2))
