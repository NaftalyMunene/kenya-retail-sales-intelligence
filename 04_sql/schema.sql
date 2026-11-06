-- Schema for the Kenya Retail Sales Intelligence database (SQLite).
-- Built by 04_sql/build_db.py from data/clean/. Dates are stored as ISO text (YYYY-MM-DD).
-- Booleans are stored as 0 or 1.

PRAGMA foreign_keys = ON;

CREATE TABLE stores (
    store_id    TEXT PRIMARY KEY,
    store_name  TEXT NOT NULL,
    county      TEXT,
    format      TEXT
);

CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    base_price_kes  REAL
);

CREATE TABLE customers (
    customer_id                   TEXT PRIMARY KEY,
    signup_date                   TEXT,
    county                        TEXT,
    segment                       TEXT,      -- Budget, Regular, Premium
    loyalty_member                INTEGER,
    first_purchase_before_signup  INTEGER    -- generator flaw, flagged in Milestone 2
);

CREATE TABLE holidays (
    date          TEXT PRIMARY KEY,
    holiday_name  TEXT NOT NULL,
    source        TEXT
);

CREATE TABLE cpi (
    month  TEXT PRIMARY KEY,                 -- YYYY-MM
    cpi    REAL                              -- KNBS overall CPI, base February 2019 = 100
);

CREATE TABLE sales (
    transaction_id         TEXT PRIMARY KEY,
    date                   TEXT NOT NULL,
    store_id               TEXT NOT NULL REFERENCES stores (store_id),
    customer_id            TEXT REFERENCES customers (customer_id),   -- NULL = anonymous sale
    product_id             TEXT NOT NULL REFERENCES products (product_id),
    quantity               INTEGER NOT NULL,
    unit_price_kes         REAL NOT NULL,
    discount_kes           REAL NOT NULL,
    payment_method         TEXT,
    price_was_outlier      INTEGER,
    price_was_imputed      INTEGER,
    customer_known         INTEGER,
    is_quantity_outlier    INTEGER,
    revenue_kes            REAL NOT NULL,
    real_revenue_kes       REAL,
    cpi                    REAL,
    year                   INTEGER,
    month                  INTEGER,
    year_month             TEXT,
    day_of_week            TEXT,
    is_weekend             INTEGER,
    is_payday_window       INTEGER,
    holiday_name           TEXT,
    is_public_holiday      INTEGER,
    days_to_next_holiday   REAL,
    is_pre_festive_window  INTEGER
);

CREATE INDEX idx_sales_date        ON sales (date);
CREATE INDEX idx_sales_year_month  ON sales (year_month);
CREATE INDEX idx_sales_store       ON sales (store_id);
CREATE INDEX idx_sales_product     ON sales (product_id);
CREATE INDEX idx_sales_customer    ON sales (customer_id);
