"""
Milestone 2: cleaning and preparation pipeline for the Kenya Retail Sales Intelligence project.

Run from the repo root:
    python 02_cleaning/clean_pipeline.py
Optional: python 02_cleaning/clean_pipeline.py path/to/raw/folder

Reads only from data/raw/ and writes only to data/clean/ and 02_cleaning/cleaning_log.csv.
Raw files are never edited. Re-running rebuilds everything from scratch.

Outputs (data/clean/):
    sales_clean.csv, customers_clean.csv, products_clean.csv, stores_clean.csv,
    customer_rfm.csv, holiday_calendar.csv, rejected_rows.csv
Evidence:
    02_cleaning/cleaning_log.csv   (before/after counts for every step)
    02_cleaning/defect_recovery.csv (what the pipeline found vs what the generator injected)
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- config
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/synthetic")
CONTEXT = Path("data/raw/context")
CLEAN = Path("data/clean")
LOG_DIR = Path("02_cleaning")
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")
PRICE_RATIO_LIMIT = 3.0        # price more than 3x (or under 1/3) of the product median = error
IQR_K = 3.0                    # outlier fence for quantity (flag only, never deleted)
PAYMENT_CANON = {"m-pesa": "M-Pesa", "cash": "Cash", "card": "Card"}

CLEAN.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_rows, rejected, found = [], [], {}


def log(step, before, after, note=""):
    log_rows.append({"step": step, "rows_before": before, "rows_after": after,
                     "rows_removed": before - after, "note": note})
    print(f"{step:<42} before={before:>7} after={after:>7}  {note}")


def reject(df, mask, reason):
    """Move rows matching mask to the rejected list (never silently dropped)."""
    if mask.sum():
        rejected.append(df[mask].assign(reject_reason=reason))
    return df[~mask].copy()


# ------------------------------------------------------- holiday calendar
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


def build_holiday_calendar():
    """Public Holidays Act fixed dates + Sunday rule, computed Easter (third-party
    assumption), and Idd dates from Gazette Notices 4339 (2024) and 3861 (2025)."""
    rows = []
    fixed = [(1, 1, "New Year"), (5, 1, "Labour Day"), (6, 1, "Madaraka Day"),
             (10, 10, "Mazingira Day"), (10, 20, "Mashujaa Day"), (12, 12, "Jamhuri Day"),
             (12, 25, "Christmas"), (12, 26, "Boxing Day")]
    for y in (2024, 2025):
        for m, d, name in fixed:
            dt = date(y, m, d)
            rows.append((dt, name, "Public Holidays Act Cap 110"))
            if dt.weekday() == 6:  # Sunday rule
                rows.append((dt + timedelta(days=1), name + " (observed)", "Cap 110 Sunday rule"))
        e = easter(y)
        rows.append((e - timedelta(days=2), "Good Friday", "Computed Easter (third-party assumption)"))
        rows.append((e + timedelta(days=1), "Easter Monday", "Computed Easter (third-party assumption)"))
    rows.append((date(2024, 4, 10), "Idd-ul-Fitr", "Gazette Notice 4339"))
    rows.append((date(2025, 3, 31), "Idd-ul-Fitr", "Gazette Notice 3861"))
    cal = pd.DataFrame(rows, columns=["date", "holiday_name", "source"])
    cal["date"] = pd.to_datetime(cal["date"])
    return cal.drop_duplicates("date").sort_values("date").reset_index(drop=True)


# =================================================================== LOAD
print("=== LOAD AND PROFILE ===")
sales_raw = pd.read_csv(RAW / "sales.csv", dtype=str)
customers = pd.read_csv(RAW / "customers.csv", dtype=str)
products = pd.read_csv(RAW / "products.csv", dtype=str)
stores = pd.read_csv(RAW / "stores.csv", dtype=str)
n_raw = len(sales_raw)
print(f"raw sales rows: {n_raw}, customers: {len(customers)}, products: {len(products)}, stores: {len(stores)}")
print("missing per column (raw sales):")
print(sales_raw.isna().sum().to_string())
log("0 raw load", n_raw, n_raw, "starting point")

sales = sales_raw.copy()

# ======================================================= 1. EXACT DUPLICATES
mask = sales.duplicated(keep="first")
found["exact_duplicate_rows"] = int(mask.sum())
before = len(sales)
sales = reject(sales, mask, "exact_duplicate_row")
log("1 remove exact duplicate rows", before, len(sales), f"{found['exact_duplicate_rows']} removed")

mask = sales.duplicated(subset="transaction_id", keep="first")
before = len(sales)
sales = reject(sales, mask, "duplicate_transaction_id")
log("2 remove duplicate transaction IDs", before, len(sales), f"{int(mask.sum())} removed (kept first)")

# ============================================================ 3. KEY FIELDS
before = len(sales)
mask = sales[["transaction_id", "store_id", "product_id"]].isna().any(axis=1)
sales = reject(sales, mask, "missing_key_field")
log("3 drop rows missing key fields", before, len(sales), f"{int(mask.sum())} removed")

# ================================================================= 4. TYPES
print("\n=== TYPES ===")
sales["date_parsed"] = pd.to_datetime(sales["date"], format="%Y-%m-%d", errors="coerce")
found["bad_dates"] = int(sales["date_parsed"].isna().sum())
before = len(sales)
sales = reject(sales, sales["date_parsed"].isna(), "invalid_date")
sales["date"] = sales["date_parsed"]
sales = sales.drop(columns="date_parsed")
log("4a parse dates, drop invalid", before, len(sales), f"{found['bad_dates']} unparseable dates")

for col in ["quantity", "unit_price_kes", "discount_kes"]:
    num = pd.to_numeric(sales[col], errors="coerce")
    coerced = int((num.isna() & sales[col].notna()).sum())
    sales[col] = num
    print(f"   {col}: {coerced} values could not be converted")
log("4b numeric columns converted", len(sales), len(sales), "quantity, unit_price_kes, discount_kes")

sales["quantity"] = sales["quantity"].astype("Int64")
for col in ["transaction_id", "store_id", "product_id"]:
    sales[col] = sales[col].str.strip()

# ============================================ 5. TEXT STANDARDISATION
before_case = (sales["payment_method"] != sales["payment_method"].str.strip().str.lower().map(PAYMENT_CANON)).sum()
sales["payment_method"] = sales["payment_method"].str.strip().str.lower().map(PAYMENT_CANON).fillna("Unknown")
found["payment_method_case_issues"] = int(before_case)
log("5 standardise payment_method text", len(sales), len(sales), f"{int(before_case)} values re-cased")

# ===================================== 6. REFERENTIAL CHECKS (store, product)
before = len(sales)
bad = ~sales["store_id"].isin(stores["store_id"]) | ~sales["product_id"].isin(products["product_id"])
sales = reject(sales, bad, "unknown_store_or_product")
log("6 store and product IDs exist", before, len(sales), f"{int(bad.sum())} removed")

# ================================================ 7. DATE RANGE CHECK
before = len(sales)
bad = (sales["date"] < START) | (sales["date"] > END)
sales = reject(sales, bad, "date_out_of_range")
log("7 dates inside 2024-01-01 to 2025-12-31", before, len(sales), f"{int(bad.sum())} removed")

# ============================================================ 8. QUANTITY
before = len(sales)
neg = sales["quantity"] < 0
found["negative_quantity"] = int(neg.sum())
sales.loc[neg, "quantity"] = -sales.loc[neg, "quantity"]       # sign-entry error, corrected
zero = sales["quantity"].fillna(0) == 0
sales = reject(sales, zero, "zero_or_missing_quantity")
log("8 fix negative quantity, drop zero", before, len(sales),
    f"{found['negative_quantity']} sign-corrected (assumed entry error, no return flag exists), {int(zero.sum())} dropped")

# ================================================ 9. PRICE OUTLIERS + MISSING
print("\n=== PRICES ===")
prod_med = sales.groupby("product_id")["unit_price_kes"].median()
ratio = sales["unit_price_kes"] / sales["product_id"].map(prod_med)
bad_price = (ratio > PRICE_RATIO_LIMIT) | (ratio < 1 / PRICE_RATIO_LIMIT)
found["price_outliers_x10"] = int(bad_price.sum())
sales["price_was_outlier"] = bad_price
sales.loc[bad_price, "unit_price_kes"] = np.nan                # blank out, then impute below
log("9a flag price outliers (ratio to product median)", len(sales), len(sales),
    f"{found['price_outliers_x10']} flagged and blanked for imputation")

found["missing_unit_price"] = int((sales["unit_price_kes"].isna() & ~bad_price).sum())
sales["price_was_imputed"] = sales["unit_price_kes"].isna()
sales["ym"] = sales["date"].dt.to_period("M")
grp = sales.groupby(["product_id", "ym"])["unit_price_kes"].transform("median")
sales["unit_price_kes"] = sales["unit_price_kes"].fillna(grp)
sales["unit_price_kes"] = sales["unit_price_kes"].fillna(sales["product_id"].map(prod_med))
still = sales["unit_price_kes"].isna()
before = len(sales)
sales = reject(sales, still, "price_could_not_be_imputed")
log("9b impute missing or outlier prices", before, len(sales),
    f"{int(sales['price_was_imputed'].sum())} imputed from product-month median")
sales = sales.drop(columns="ym")

# =============================================================== 10. DISCOUNT
gross = sales["quantity"].astype(float) * sales["unit_price_kes"]
bad_disc = (sales["discount_kes"] < 0) | (sales["discount_kes"] > gross) | sales["discount_kes"].isna()
n_bad = int(bad_disc.sum())
sales.loc[bad_disc, "discount_kes"] = 0.0
log("10 discount between 0 and gross value", len(sales), len(sales), f"{n_bad} reset to 0")

# =============================================================== 11. CUSTOMERS
print("\n=== CUSTOMERS ===")
customers["signup_date"] = pd.to_datetime(customers["signup_date"], errors="coerce")
customers["loyalty_member"] = customers["loyalty_member"].str.lower().eq("true")
dup_c = customers.duplicated("customer_id").sum()
customers = customers.drop_duplicates("customer_id")
log("11a customers: duplicate IDs removed", len(customers) + dup_c, len(customers), f"{dup_c} removed")

found["missing_customer_id"] = int(sales["customer_id"].isna().sum())
unknown = sales["customer_id"].notna() & ~sales["customer_id"].isin(customers["customer_id"])
found["orphan_customer_ids"] = int(unknown.sum())
sales["customer_known"] = sales["customer_id"].isin(customers["customer_id"])
sales.loc[~sales["customer_known"], "customer_id"] = np.nan
log("11b customer IDs checked against customers", len(sales), len(sales),
    f"{found['missing_customer_id']} missing + {found['orphan_customer_ids']} orphan kept as anonymous sales (customer_known=False)")

first_buy = sales.dropna(subset=["customer_id"]).groupby("customer_id")["date"].min()
cust_signup = customers.set_index("customer_id")["signup_date"]
early = first_buy < cust_signup.reindex(first_buy.index)
print(f"   customers whose first purchase is before their signup date: {int(early.sum())} (flagged, not removed)")
customers["first_purchase_before_signup"] = customers["customer_id"].map(early).fillna(False).astype(bool)

# =============================================================== 12. OUTLIERS
print("\n=== OUTLIERS (flag only) ===")
sales = sales.merge(products[["product_id", "category"]], on="product_id", how="left")
q1 = sales.groupby("category")["quantity"].transform(lambda s: s.astype(float).quantile(0.25))
q3 = sales.groupby("category")["quantity"].transform(lambda s: s.astype(float).quantile(0.75))
sales["is_quantity_outlier"] = sales["quantity"].astype(float) > (q3 + IQR_K * (q3 - q1))
log("12 flag quantity outliers (IQR, per category)", len(sales), len(sales),
    f"{int(sales['is_quantity_outlier'].sum())} flagged, kept: large baskets are plausible")

# ============================================================== 13. FEATURES
print("\n=== FEATURES ===")
sales["revenue_kes"] = (sales["quantity"].astype(float) * sales["unit_price_kes"] - sales["discount_kes"]).round(2)
sales["year"] = sales["date"].dt.year
sales["month"] = sales["date"].dt.month
sales["year_month"] = sales["date"].dt.to_period("M").astype(str)
sales["day_of_week"] = sales["date"].dt.day_name()
sales["is_weekend"] = sales["date"].dt.weekday >= 5
sales["is_payday_window"] = (sales["date"].dt.day >= 25) | (sales["date"].dt.day <= 2)

cal = build_holiday_calendar()
sales = sales.merge(cal[["date", "holiday_name"]], on="date", how="left")
sales["is_public_holiday"] = sales["holiday_name"].notna()
hol_dates = cal["date"].values
idx = np.searchsorted(hol_dates, sales["date"].values)
nxt = np.where(idx < len(hol_dates), hol_dates[np.minimum(idx, len(hol_dates) - 1)], np.datetime64("NaT", "ns"))
sales["days_to_next_holiday"] = ((pd.to_datetime(nxt) - sales["date"]).dt.days)
big = cal[cal["holiday_name"].isin(["Christmas", "Idd-ul-Fitr", "Good Friday"])]["date"].values
idx2 = np.searchsorted(big, sales["date"].values)
nb = np.where(idx2 < len(big), big[np.minimum(idx2, len(big) - 1)], np.datetime64("NaT", "ns"))
gap = (pd.to_datetime(nb) - sales["date"]).dt.days
sales["is_pre_festive_window"] = (gap >= 1) & (gap <= 3)
log("13a calendar and holiday features", len(sales), len(sales),
    f"{int(sales['is_public_holiday'].sum())} rows on public holidays")

cpi_file = CONTEXT / "cpi_monthly.csv"
if cpi_file.exists():
    cpi = pd.read_csv(cpi_file)
    cpi = cpi.dropna(subset=["cpi"])
    if len(cpi) >= 24:
        sales = sales.merge(cpi.rename(columns={"month": "year_month"}), on="year_month", how="left")
        sales["real_revenue_kes"] = (sales["revenue_kes"] / sales["cpi"] * 100).round(2)
        log("13b CPI join and real revenue", len(sales), len(sales), "real_revenue_kes added")
    else:
        print(f"   cpi_monthly.csv has {len(cpi)} of 24 months filled in: real revenue skipped until complete")
else:
    print("   data/raw/context/cpi_monthly.csv not found: real revenue skipped")

# ================================================================== RFM
snapshot = sales["date"].max() + pd.Timedelta(days=1)
known = sales[sales["customer_known"]]
rfm = known.groupby("customer_id").agg(
    recency_days=("date", lambda s: (snapshot - s.max()).days),
    frequency=("transaction_id", "nunique"),
    monetary_kes=("revenue_kes", "sum"),
    first_purchase=("date", "min"), last_purchase=("date", "max")).reset_index()
rfm["tenure_days"] = (rfm["last_purchase"] - rfm["first_purchase"]).dt.days
log("13c customer RFM table", len(rfm), len(rfm), "one row per known customer")

# ================================================================== SAVE
print("\n=== SAVE ===")
sales = sales.sort_values(["date", "transaction_id"]).reset_index(drop=True)
sales.to_csv(CLEAN / "sales_clean.csv", index=False)
customers.to_csv(CLEAN / "customers_clean.csv", index=False)
products.to_csv(CLEAN / "products_clean.csv", index=False)
stores.to_csv(CLEAN / "stores_clean.csv", index=False)
rfm.to_csv(CLEAN / "customer_rfm.csv", index=False)
cal.to_csv(CLEAN / "holiday_calendar.csv", index=False)
rej = pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame()
rej.to_csv(CLEAN / "rejected_rows.csv", index=False)
log("14 final clean sales saved", n_raw, len(sales), f"{len(rej)} rows in rejected_rows.csv, each with a reason")

pd.DataFrame(log_rows).to_csv(LOG_DIR / "cleaning_log.csv", index=False)

# ====================================================== DEFECT RECOVERY CHECK
inj_file = RAW / "injected_defects.json"
if inj_file.exists():
    inj = json.loads(inj_file.read_text())
    rows = []
    for k, v in found.items():
        rows.append({"defect": k, "injected_by_generator": inj.get(k), "found_by_pipeline": v})
    rec = pd.DataFrame(rows)
    rec["difference"] = rec["found_by_pipeline"] - rec["injected_by_generator"]
    rec.to_csv(LOG_DIR / "defect_recovery.csv", index=False)
    print("\n=== DEFECT RECOVERY (small differences come from overlapping defects on the same row) ===")
    print(rec.to_string(index=False))
print(f"\nDone. Clean sales rows: {len(sales)} of {n_raw} raw.")
