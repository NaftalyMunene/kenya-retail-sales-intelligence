# Data Inventory

## Source tables (raw)

| Table | Grain | Primary key | Location |
|---|---|---|---|
| stores | one store | store_id | data/raw/synthetic/stores.csv |
| products | one SKU | product_id | data/raw/synthetic/products.csv |
| customers | one customer | customer_id | data/raw/synthetic/customers.csv |
| sales | one line item | transaction_id | data/raw/synthetic/sales.csv |

## Context files

| File | Purpose |
|---|---|
| Public_Holidays_Act_Cap110.pdf | Fixed holidays + Sunday rule |
| Gazette_Notice_3861_2025.pdf | 2025 Idd-ul-Fitr date (31 Mar) |
| Gazette_Notice_4339_2024.pdf | 2024 Idd-ul-Fitr date (10 Apr) |
| KNBS_CPI_Dec2024.pdf | 2024 monthly CPI (base Feb 2019 = 100) |
| KNBS_CPI_Dec2025.pdf | 2025 monthly CPI |

## Generator

- **File:** `01_framing/generate_data.py`
- **Run:** `python 01_framing/generate_data.py`
- **Output:** `data/raw/synthetic/` (stores, products, customers, sales, injected_defects.json)
- **Seed:** 42 — re-running reproduces identical output.

## Fields and where they live

- **customer_id, payment_method, promo/discount flag:** in `sales.csv` (customer_id also in `customers.csv`).
- **promo flag:** represented by `discount_kes` > 0 in `sales.csv`.
- **store / category identifiers:** `sales.store_id` → `stores.store_id`; `sales.product_id` → `products.product_id` → `products.category`.

## Planned clean outputs

| File | Contents |
|---|---|
| data/clean/sales_clean.csv | cleaned sales with features |
| data/clean/customers_clean.csv | cleaned customers |
| data/clean/products_clean.csv | cleaned products |
| data/clean/stores_clean.csv | cleaned stores |
| data/clean/holiday_calendar.csv | built from Act + Gazette + computed Easter |
| data/clean/cpi.csv | monthly CPI (base Feb 2019 = 100) |
| data/clean/rejected_rows.csv | dropped rows + reason |
| 02_cleaning/cleaning_log.csv | before/after row counts per step |
