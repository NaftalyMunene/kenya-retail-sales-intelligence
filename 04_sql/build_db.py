"""
Milestone 4, step 1: build the SQLite database from the clean data.

Run from the repo root:
    python 04_sql/build_db.py

Reads data/clean/*.csv and data/raw/context/cpi_monthly.csv.
Writes 04_sql/kenya_retail.db (rebuilt from scratch each run, so it is not committed to git).
"""
import sqlite3
from pathlib import Path

import pandas as pd

CLEAN = Path("data/clean")
CPI_FILE = Path("data/raw/context/cpi_monthly.csv")
SQL_DIR = Path("04_sql")
DB = SQL_DIR / "kenya_retail.db"

SALES_COLS = ["transaction_id", "date", "store_id", "customer_id", "product_id", "quantity", "unit_price_kes",
              "discount_kes", "payment_method", "price_was_outlier", "price_was_imputed", "customer_known",
              "is_quantity_outlier", "revenue_kes", "real_revenue_kes", "cpi", "year", "month", "year_month",
              "day_of_week", "is_weekend", "is_payday_window", "holiday_name", "is_public_holiday",
              "days_to_next_holiday", "is_pre_festive_window"]
BOOL_COLS = ["price_was_outlier", "price_was_imputed", "customer_known", "is_quantity_outlier",
             "is_weekend", "is_payday_window", "is_public_holiday", "is_pre_festive_window"]


def to_int_flags(df, cols):
    for c in cols:
        df[c] = df[c].astype(str).str.lower().map({"true": 1, "false": 0, "1": 1, "0": 0}).fillna(0).astype(int)
    return df


if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
con.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))

stores = pd.read_csv(CLEAN / "stores_clean.csv")
products = pd.read_csv(CLEAN / "products_clean.csv")
customers = to_int_flags(pd.read_csv(CLEAN / "customers_clean.csv"), ["loyalty_member", "first_purchase_before_signup"])
holidays = pd.read_csv(CLEAN / "holiday_calendar.csv")
sales = pd.read_csv(CLEAN / "sales_clean.csv")

for col in SALES_COLS:  # CPI columns are missing if the CPI series was incomplete in Milestone 2
    if col not in sales.columns:
        sales[col] = None
sales = to_int_flags(sales[SALES_COLS].copy(), BOOL_COLS)
sales["date"] = pd.to_datetime(sales["date"]).dt.strftime("%Y-%m-%d")
sales["customer_id"] = sales["customer_id"].where(sales["customer_known"] == 1, None)
sales["holiday_name"] = sales["holiday_name"].where(sales["holiday_name"].notna(), None)

stores.to_sql("stores", con, if_exists="append", index=False)
products.to_sql("products", con, if_exists="append", index=False)
customers.to_sql("customers", con, if_exists="append", index=False)
holidays["date"] = pd.to_datetime(holidays["date"]).dt.strftime("%Y-%m-%d")
holidays.to_sql("holidays", con, if_exists="append", index=False)
if CPI_FILE.exists():
    cpi = pd.read_csv(CPI_FILE).dropna(subset=["cpi"])
    cpi.to_sql("cpi", con, if_exists="append", index=False)
sales.to_sql("sales", con, if_exists="append", index=False, chunksize=5000)
con.commit()

print(f"Built {DB}")
for t in ["stores", "products", "customers", "holidays", "cpi", "sales"]:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:<10} {n:>8} rows")
bad = con.execute("PRAGMA foreign_key_check").fetchall()
print(f"Foreign key violations: {len(bad)}")
con.close()
