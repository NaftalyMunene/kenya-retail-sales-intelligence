-- Milestone 4: SQL analysis for the Kenya Retail Sales Intelligence project (SQLite).
-- Run with: python 04_sql/run_queries.py
-- Each query starts with a name line and a purpose line. The runner saves every result to 04_sql/results/<name>.csv.
-- Techniques used: joins, GROUP BY, CASE, CTEs, window functions (LAG, RANK, NTILE, ROW_NUMBER, running SUM).

-- name: q01_reconciliation
-- purpose: Check the database holds the same totals as the clean CSV (business question: data trust)
SELECT COUNT(*)                         AS sales_lines,
       COUNT(DISTINCT transaction_id)   AS distinct_transactions,
       COUNT(DISTINCT customer_id)      AS known_customers,
       ROUND(SUM(revenue_kes), 2)       AS revenue_kes,
       ROUND(SUM(real_revenue_kes), 2)  AS real_revenue_kes,
       MIN(date)                        AS first_date,
       MAX(date)                        AS last_date
FROM sales;

-- name: q02_category_share
-- purpose: Q2 which categories drive revenue, with each share of the total
SELECT p.category,
       ROUND(SUM(s.revenue_kes), 0)                                         AS revenue_kes,
       ROUND(100.0 * SUM(s.revenue_kes) / SUM(SUM(s.revenue_kes)) OVER (), 1) AS revenue_share_pct,
       SUM(s.quantity)                                                      AS units_sold
FROM sales s
JOIN products p USING (product_id)
GROUP BY p.category
ORDER BY revenue_kes DESC;

-- name: q03_store_ranking
-- purpose: Q2 rank stores by revenue and show share and average line value
SELECT RANK() OVER (ORDER BY SUM(s.revenue_kes) DESC)                        AS revenue_rank,
       st.store_name, st.format, st.county,
       ROUND(SUM(s.revenue_kes), 0)                                          AS revenue_kes,
       ROUND(100.0 * SUM(s.revenue_kes) / SUM(SUM(s.revenue_kes)) OVER (), 1) AS revenue_share_pct,
       ROUND(AVG(s.revenue_kes), 0)                                          AS avg_line_value_kes
FROM sales s
JOIN stores st USING (store_id)
GROUP BY st.store_id
ORDER BY revenue_rank;

-- name: q04_monthly_growth
-- purpose: Q3 monthly nominal and real revenue with month-on-month and year-on-year growth (LAG)
WITH m AS (
    SELECT year_month,
           SUM(revenue_kes)       AS revenue,
           SUM(real_revenue_kes)  AS real_revenue,
           COUNT(*)               AS txns
    FROM sales
    GROUP BY year_month
)
SELECT year_month,
       ROUND(revenue, 0)       AS revenue_kes,
       ROUND(real_revenue, 0)  AS real_revenue_kes,
       txns,
       ROUND(100.0 * (revenue / LAG(revenue) OVER (ORDER BY year_month) - 1), 1)              AS mom_nominal_pct,
       ROUND(100.0 * (revenue / LAG(revenue, 12) OVER (ORDER BY year_month) - 1), 1)          AS yoy_nominal_pct,
       ROUND(100.0 * (real_revenue / LAG(real_revenue, 12) OVER (ORDER BY year_month) - 1), 1) AS yoy_real_pct
FROM m
ORDER BY year_month;

-- name: q05_category_yoy
-- purpose: Q3 growth by category, 2025 versus 2024, nominal and real (conditional aggregation)
SELECT p.category,
       ROUND(SUM(CASE WHEN s.year = 2024 THEN s.revenue_kes END), 0) AS revenue_2024,
       ROUND(SUM(CASE WHEN s.year = 2025 THEN s.revenue_kes END), 0) AS revenue_2025,
       ROUND(100.0 * (SUM(CASE WHEN s.year = 2025 THEN s.revenue_kes END)
                    / SUM(CASE WHEN s.year = 2024 THEN s.revenue_kes END) - 1), 1)           AS nominal_growth_pct,
       ROUND(100.0 * (SUM(CASE WHEN s.year = 2025 THEN s.real_revenue_kes END)
                    / SUM(CASE WHEN s.year = 2024 THEN s.real_revenue_kes END) - 1), 1)      AS real_growth_pct
FROM sales s
JOIN products p USING (product_id)
GROUP BY p.category
ORDER BY nominal_growth_pct DESC;

-- name: q06_holiday_days
-- purpose: Q1 each public holiday day against a baseline of similar ordinary days in the same month
WITH daily AS (
    SELECT date, year_month, is_weekend, is_payday_window,
           MAX(is_public_holiday)      AS is_holiday,
           MAX(holiday_name)           AS holiday_name,
           MAX(is_pre_festive_window)  AS is_prefest,
           COUNT(*)                    AS txns,
           SUM(revenue_kes)            AS revenue
    FROM sales
    GROUP BY date
),
base AS (
    SELECT year_month, is_weekend, is_payday_window, AVG(txns) AS base_txns
    FROM daily
    WHERE is_holiday = 0 AND is_prefest = 0
    GROUP BY year_month, is_weekend, is_payday_window
)
SELECT d.date, d.holiday_name, d.txns,
       ROUND(b.base_txns, 1)                          AS baseline_txns,
       ROUND(100.0 * (d.txns / b.base_txns - 1), 1)   AS uplift_pct
FROM daily d
LEFT JOIN base b USING (year_month, is_weekend, is_payday_window)
WHERE d.is_holiday = 1
ORDER BY d.date;

-- name: q07_holiday_uplift_by_name
-- purpose: Q1 average uplift per holiday (two observed days each, so treat as indicative)
WITH daily AS (
    SELECT date, year_month, is_weekend, is_payday_window,
           MAX(is_public_holiday) AS is_holiday, MAX(holiday_name) AS holiday_name,
           MAX(is_pre_festive_window) AS is_prefest, COUNT(*) AS txns
    FROM sales
    GROUP BY date
),
base AS (
    SELECT year_month, is_weekend, is_payday_window, AVG(txns) AS base_txns
    FROM daily
    WHERE is_holiday = 0 AND is_prefest = 0
    GROUP BY year_month, is_weekend, is_payday_window
),
h AS (
    SELECT REPLACE(d.holiday_name, ' (observed)', '') AS holiday, d.txns, b.base_txns
    FROM daily d
    LEFT JOIN base b USING (year_month, is_weekend, is_payday_window)
    WHERE d.is_holiday = 1
)
SELECT holiday,
       COUNT(*)                                      AS days_observed,
       ROUND(100.0 * (SUM(txns) / SUM(base_txns) - 1), 1) AS uplift_pct
FROM h
WHERE base_txns IS NOT NULL
GROUP BY holiday
ORDER BY uplift_pct DESC;

-- name: q08_payday_effect
-- purpose: Q1 payday window (25th to 2nd) against other days, split by weekday and weekend, excluding holidays and December
WITH daily AS (
    SELECT date, month, is_weekend, is_payday_window,
           MAX(is_public_holiday) AS is_holiday, MAX(is_pre_festive_window) AS is_prefest,
           COUNT(*) AS txns, SUM(revenue_kes) AS revenue
    FROM sales
    GROUP BY date
)
SELECT CASE is_weekend WHEN 1 THEN 'weekend' ELSE 'weekday' END                       AS day_type,
       COUNT(CASE WHEN is_payday_window = 1 THEN 1 END)                                 AS payday_days,
       COUNT(CASE WHEN is_payday_window = 0 THEN 1 END)                                 AS other_days,
       ROUND(AVG(CASE WHEN is_payday_window = 1 THEN txns END), 1)                      AS payday_avg_txns,
       ROUND(AVG(CASE WHEN is_payday_window = 0 THEN txns END), 1)                      AS other_avg_txns,
       ROUND(100.0 * (AVG(CASE WHEN is_payday_window = 1 THEN txns END)
                    / AVG(CASE WHEN is_payday_window = 0 THEN txns END) - 1), 1)        AS payday_lift_pct
FROM daily
WHERE is_holiday = 0 AND is_prefest = 0 AND month <> 12
GROUP BY is_weekend;

-- name: q09_customer_deciles
-- purpose: Q2 revenue concentration by customer decile (NTILE) with cumulative share
WITH c AS (
    SELECT customer_id, SUM(revenue_kes) AS rev
    FROM sales
    WHERE customer_known = 1
    GROUP BY customer_id
),
r AS (
    SELECT rev, NTILE(10) OVER (ORDER BY rev DESC, customer_id) AS decile
    FROM c
)
SELECT decile,
       COUNT(*)                                                              AS customers,
       ROUND(SUM(rev), 0)                                                    AS revenue_kes,
       ROUND(100.0 * SUM(rev) / SUM(SUM(rev)) OVER (), 1)                    AS revenue_share_pct,
       ROUND(100.0 * SUM(SUM(rev)) OVER (ORDER BY decile) / SUM(SUM(rev)) OVER (), 1) AS cumulative_share_pct
FROM r
GROUP BY decile
ORDER BY decile;

-- name: q10_rfm_segments
-- purpose: Q4 RFM scoring in SQL (NTILE quartiles) and segment summary
WITH snap AS (
    SELECT DATE(MAX(date), '+1 day') AS d FROM sales
),
base AS (
    SELECT customer_id,
           CAST(JULIANDAY((SELECT d FROM snap)) - JULIANDAY(MAX(date)) AS INTEGER) AS recency_days,
           COUNT(*)            AS frequency,
           SUM(revenue_kes)    AS monetary
    FROM sales
    WHERE customer_known = 1
    GROUP BY customer_id
),
scored AS (
    SELECT customer_id, recency_days, frequency, monetary,
           NTILE(4) OVER (ORDER BY recency_days DESC, customer_id) AS r,
           NTILE(4) OVER (ORDER BY frequency, customer_id)         AS f,
           NTILE(4) OVER (ORDER BY monetary, customer_id)          AS m
    FROM base
),
labeled AS (
    SELECT *,
           CASE WHEN r >= 3 AND f >= 3 THEN 'Champions'
                WHEN r <= 2 AND f >= 3 THEN 'At risk'
                WHEN r >= 3             THEN 'New or developing'
                ELSE 'Low value or lapsed' END AS segment
    FROM scored
)
SELECT segment,
       COUNT(*)                                                      AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)            AS customer_share_pct,
       ROUND(SUM(monetary), 0)                                       AS revenue_kes,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 1)  AS revenue_share_pct,
       ROUND(AVG(frequency), 0)                                      AS avg_purchase_lines,
       ROUND(AVG(recency_days), 0)                                   AS avg_recency_days
FROM labeled
GROUP BY segment
ORDER BY revenue_kes DESC;

-- name: q11_monthly_retention
-- purpose: Q4 share of each month's active customers who are also active the next month (self join)
WITH active AS (
    SELECT DISTINCT year_month, customer_id
    FROM sales
    WHERE customer_known = 1
),
nxt AS (
    SELECT year_month, customer_id,
           SUBSTR(DATE(year_month || '-01', '+1 month'), 1, 7) AS next_month
    FROM active
)
SELECT n.year_month,
       COUNT(*)                                                       AS active_customers,
       SUM(CASE WHEN b.customer_id IS NOT NULL THEN 1 ELSE 0 END)     AS active_next_month,
       ROUND(100.0 * SUM(CASE WHEN b.customer_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS retention_pct
FROM nxt n
LEFT JOIN active b ON b.customer_id = n.customer_id AND b.year_month = n.next_month
WHERE n.next_month <= (SELECT MAX(year_month) FROM sales)
GROUP BY n.year_month
ORDER BY n.year_month;

-- name: q12_store_cumulative_revenue
-- purpose: Q2 running total of revenue per store by month (window SUM)
WITH m AS (
    SELECT st.store_name, s.year_month, SUM(s.revenue_kes) AS revenue
    FROM sales s
    JOIN stores st USING (store_id)
    GROUP BY st.store_name, s.year_month
)
SELECT store_name, year_month,
       ROUND(revenue, 0) AS revenue_kes,
       ROUND(SUM(revenue) OVER (PARTITION BY store_name ORDER BY year_month), 0) AS cumulative_revenue_kes
FROM m
ORDER BY store_name, year_month;

-- name: q13_category_mix_by_store
-- purpose: Q2 category share inside each store (window SUM by partition)
SELECT st.store_name, p.category,
       ROUND(SUM(s.revenue_kes), 0) AS revenue_kes,
       ROUND(100.0 * SUM(s.revenue_kes) / SUM(SUM(s.revenue_kes)) OVER (PARTITION BY st.store_name), 1) AS share_of_store_pct
FROM sales s
JOIN stores st USING (store_id)
JOIN products p USING (product_id)
GROUP BY st.store_name, p.category
ORDER BY st.store_name, revenue_kes DESC;

-- name: q14_top_products_per_category
-- purpose: Q2 the three best products in each category (ROW_NUMBER)
WITH pr AS (
    SELECT p.category, p.product_id, p.product_name,
           SUM(s.revenue_kes) AS revenue, SUM(s.quantity) AS units
    FROM sales s
    JOIN products p USING (product_id)
    GROUP BY p.product_id
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC) AS rn
    FROM pr
)
SELECT category, rn AS rank_in_category, product_id, product_name,
       ROUND(revenue, 0) AS revenue_kes, units
FROM ranked
WHERE rn <= 3
ORDER BY category, rn;

-- name: q15_top_revenue_days
-- purpose: Q1 the ten highest-revenue days with their calendar context
SELECT date, day_of_week,
       MAX(holiday_name)       AS holiday,
       MAX(is_payday_window)   AS payday_window,
       COUNT(*)                AS txns,
       ROUND(SUM(revenue_kes), 0) AS revenue_kes
FROM sales
GROUP BY date
ORDER BY SUM(revenue_kes) DESC
LIMIT 10;

-- name: q16_data_quality_by_month
-- purpose: Data trust, share of imputed prices and anonymous sales by month
SELECT year_month,
       COUNT(*)                                                  AS lines,
       ROUND(100.0 * SUM(price_was_imputed) / COUNT(*), 2)       AS imputed_price_pct,
       ROUND(100.0 * SUM(1 - customer_known) / COUNT(*), 2)      AS anonymous_sales_pct,
       SUM(is_quantity_outlier)                                  AS quantity_outliers
FROM sales
GROUP BY year_month
ORDER BY year_month;
