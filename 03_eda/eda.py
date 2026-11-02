"""
Milestone 3: exploratory data analysis for the Kenya Retail Sales Intelligence project.

Run from the repo root (after the Milestone 2 pipeline):
    python 03_eda/eda.py

Reads only from data/clean/. Writes to 03_eda/:
    figures/*.png      the charts
    tables/*.csv       every number behind the charts
    eda_findings.md    findings written from the computed numbers
Re-running rebuilds everything.

Business questions covered (from Milestone 1):
    Q1 holiday and calendar effects     Q2 category, store and concentration
    Q3 nominal versus real growth       Q4 customer value (descriptive)
Because the data is synthetic, the calendar effects the generator built in are listed next to
what the analysis recovers, as a check that the pipeline and method work.
"""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CLEAN = Path("data/clean")
OUT = Path("03_eda")
FIG = OUT / "figures"
TAB = OUT / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

INK, MID, SOFT = "#111111", "#6b6b6b", "#c8c8c8"
plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "font.size": 10, "axes.edgecolor": MID,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.titleweight": "bold", "axes.titlesize": 11, "axes.titlelocation": "left",
    "lines.linewidth": 1.6, "text.color": INK, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, facecolor="white")
    plt.close(fig)


def m(x):  # KES millions label
    return f"{x / 1e6:,.1f}M"


# ================================================================== LOAD
df = pd.read_csv(CLEAN / "sales_clean.csv", parse_dates=["date"])
customers = pd.read_csv(CLEAN / "customers_clean.csv")
products = pd.read_csv(CLEAN / "products_clean.csv")
stores = pd.read_csv(CLEAN / "stores_clean.csv")
rfm = pd.read_csv(CLEAN / "customer_rfm.csv", parse_dates=["first_purchase", "last_purchase"])
hol = pd.read_csv(CLEAN / "holiday_calendar.csv", parse_dates=["date"])
has_real = "real_revenue_kes" in df.columns
print(f"Loaded {len(df):,} clean sales rows, {df['date'].min().date()} to {df['date'].max().date()}")

total_rev = df["revenue_kes"].sum()
F = {}  # facts used in the written findings

# =================================================== OVERVIEW AND QUALITY
F["rows"] = len(df)
F["revenue_total"] = total_rev
F["avg_basket_line"] = df["revenue_kes"].mean()
F["median_line"] = df["revenue_kes"].median()
F["anon_share_rows"] = 1 - df["customer_known"].mean()
F["anon_share_rev"] = df.loc[~df["customer_known"], "revenue_kes"].sum() / total_rev
F["imputed_price_rows"] = int(df["price_was_imputed"].sum())
pay = df.groupby("payment_method")["revenue_kes"].sum().sort_values(ascending=False)
pay_share = (pay / total_rev).round(4)
pay_share.to_csv(TAB / "payment_method_share.csv", header=["revenue_share"])
F["pay_share"] = pay_share.to_dict()
desc = df[["quantity", "unit_price_kes", "discount_kes", "revenue_kes"]].describe().T
desc.to_csv(TAB / "summary_statistics.csv")

# ======================================== Q2: CATEGORY, STORE, CONCENTRATION
cat = df.groupby("category").agg(revenue=("revenue_kes", "sum"), lines=("transaction_id", "count"),
                                 units=("quantity", "sum")).sort_values("revenue", ascending=False)
cat["revenue_share"] = cat["revenue"] / total_rev
cat.to_csv(TAB / "revenue_by_category.csv")

st = df.groupby("store_id").agg(revenue=("revenue_kes", "sum"), lines=("transaction_id", "count"))
st = st.join(stores.set_index("store_id")[["store_name", "format"]]).sort_values("revenue", ascending=False)
st["revenue_share"] = st["revenue"] / total_rev
st.to_csv(TAB / "revenue_by_store.csv")

prod_rev = df.groupby("product_id")["revenue_kes"].sum().sort_values(ascending=False)
cust_rev = df[df["customer_known"]].groupby("customer_id")["revenue_kes"].sum().sort_values(ascending=False)


def top_share(s, frac):
    k = max(1, int(round(len(s) * frac)))
    return s.iloc[:k].sum() / s.sum()


F["top20_products"] = top_share(prod_rev, 0.2)
F["top20_customers"] = top_share(cust_rev, 0.2)
F["n_products"], F["n_customers"] = len(prod_rev), len(cust_rev)
pd.DataFrame({"measure": ["top 20% of products", "top 20% of known customers"],
              "revenue_share": [F["top20_products"], F["top20_customers"]]}).to_csv(TAB / "concentration.csv", index=False)

# ===================================================== Q3: NOMINAL VS REAL
monthly = df.groupby("year_month").agg(revenue=("revenue_kes", "sum"), txns=("transaction_id", "count"))
if has_real:
    monthly["real_revenue"] = df.groupby("year_month")["real_revenue_kes"].sum()
    monthly["cpi"] = df.groupby("year_month")["cpi"].first()
monthly.to_csv(TAB / "monthly_summary.csv")
yr = df.groupby("year").agg(revenue=("revenue_kes", "sum"), txns=("transaction_id", "count"))
F["nominal_growth"] = yr.loc[2025, "revenue"] / yr.loc[2024, "revenue"] - 1
F["txn_growth"] = yr.loc[2025, "txns"] / yr.loc[2024, "txns"] - 1
if has_real:
    yr["real_revenue"] = df.groupby("year")["real_revenue_kes"].sum()
    F["real_growth"] = yr.loc[2025, "real_revenue"] / yr.loc[2024, "real_revenue"] - 1
    cpi_y = monthly["cpi"].groupby(monthly.index.str[:4]).mean()
    F["cpi_growth"] = cpi_y["2025"] / cpi_y["2024"] - 1
yr.to_csv(TAB / "yearly_summary.csv")

# ================================== Q1: DAILY MODEL OF CALENDAR EFFECTS
daily = df.groupby("date").agg(txns=("transaction_id", "count"), revenue=("revenue_kes", "sum"))
daily = daily.reindex(pd.date_range(df["date"].min(), df["date"].max()))
daily["txns"] = daily["txns"].fillna(0)
daily = daily[daily["txns"] > 0].copy()
daily["weekend"] = (daily.index.weekday >= 5).astype(int)
daily["payday"] = ((daily.index.day >= 25) | (daily.index.day <= 2)).astype(int)
hol_map = hol.assign(base=hol["holiday_name"].str.replace(" (observed)", "", regex=False)).set_index("date")["base"]
daily["holiday"] = daily.index.map(hol_map)
pre = df.groupby("date")["is_pre_festive_window"].first()
daily["prefest"] = (pre.reindex(daily.index).fillna(False).astype(bool) & daily["holiday"].isna()).astype(int)
daily["t"] = (daily.index - daily.index[0]).days / 365.0

cols, names = [np.ones(len(daily)), daily["t"].values], ["intercept", "trend_per_year"]
for mth in range(1, 13):
    if mth == 6:
        continue  # June is the reference month
    cols.append((daily.index.month == mth).astype(int)); names.append(f"month_{mth}")
for c in ["weekend", "payday", "prefest"]:
    cols.append(daily[c].values); names.append(c)
hol_names = sorted(daily["holiday"].dropna().unique())
for h in hol_names:
    cols.append((daily["holiday"] == h).astype(int).values); names.append(f"hol_{h}")
X = np.column_stack(cols).astype(float)
y = np.log(daily["txns"].values)
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
resid = y - X @ beta
sigma2 = resid @ resid / (len(y) - X.shape[1])
se = np.sqrt(np.diag(sigma2 * np.linalg.inv(X.T @ X)))
eff = pd.DataFrame({"term": names, "coef": beta, "se": se})
eff["effect_pct"] = (np.exp(eff["coef"]) - 1) * 100
eff["ci_low_pct"] = (np.exp(eff["coef"] - 1.96 * eff["se"]) - 1) * 100
eff["ci_high_pct"] = (np.exp(eff["coef"] + 1.96 * eff["se"]) - 1) * 100
rsq = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
F["model_r2"], F["model_days"] = rsq, len(y)

# Effects the generator built in (known truth, percent change in transaction volume)
TRUTH = {"weekend": 25, "payday": 18, "prefest": 20, "month_12": 30, "month_1": -12, "month_2": -5, "month_8": 5,
         "hol_Christmas": 45, "hol_Boxing Day": -15, "hol_New Year": -20, "hol_Idd-ul-Fitr": 35,
         "hol_Good Friday": -25, "hol_Easter Monday": 15, "hol_Labour Day": -10, "hol_Madaraka Day": 10,
         "hol_Mashujaa Day": 10, "hol_Jamhuri Day": 10, "hol_Mazingira Day": 5}
eff["built_in_truth_pct"] = eff["term"].map(TRUTH)
eff["truth_inside_ci"] = (eff["built_in_truth_pct"] >= eff["ci_low_pct"]) & (eff["built_in_truth_pct"] <= eff["ci_high_pct"])
eff.to_csv(TAB / "calendar_effects_model.csv", index=False)
chk = eff.dropna(subset=["built_in_truth_pct"])
F["truth_inside"], F["truth_total"] = int(chk["truth_inside_ci"].sum()), len(chk)
F["trend_pct"] = float(eff.loc[eff["term"] == "trend_per_year", "effect_pct"].iloc[0])

# raw descriptive profiles
dow = daily.groupby(daily.index.day_name())["txns"].mean().reindex(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
dom = daily.groupby(daily.index.day)["txns"].mean()
dow.to_csv(TAB / "avg_daily_transactions_by_weekday.csv", header=["avg_transactions"])
dom.to_csv(TAB / "avg_daily_transactions_by_day_of_month.csv", header=["avg_transactions"])
F["weekend_raw"] = daily.loc[daily["weekend"] == 1, "txns"].mean() / daily.loc[daily["weekend"] == 0, "txns"].mean() - 1
F["payday_raw"] = daily.loc[daily["payday"] == 1, "txns"].mean() / daily.loc[daily["payday"] == 0, "txns"].mean() - 1

# =================================================== Q4: CUSTOMERS (RFM)
rfm["r"] = pd.qcut(rfm["recency_days"].rank(method="first"), 4, labels=[4, 3, 2, 1]).astype(int)
rfm["f"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
rfm["mo"] = pd.qcut(rfm["monetary_kes"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)


def label(row):
    if row.r >= 3 and row.f >= 3:
        return "Champions"
    if row.r <= 2 and row.f >= 3:
        return "At risk"
    if row.r >= 3:
        return "New or developing"
    return "Low value or lapsed"


rfm["rfm_segment"] = rfm.apply(label, axis=1)
seg = rfm.groupby("rfm_segment").agg(customers=("customer_id", "count"), revenue=("monetary_kes", "sum"),
                                     avg_frequency=("frequency", "mean"), avg_recency_days=("recency_days", "mean"))
seg["customer_share"] = seg["customers"] / seg["customers"].sum()
seg["revenue_share"] = seg["revenue"] / seg["revenue"].sum()
seg = seg.sort_values("revenue", ascending=False)
seg.to_csv(TAB / "rfm_segments.csv")
rfm.to_csv(TAB / "customer_rfm_scored.csv", index=False)
F["rfm"] = seg

tier = rfm.merge(customers[["customer_id", "segment"]], on="customer_id").groupby("segment").agg(
    customers=("customer_id", "count"), avg_revenue=("monetary_kes", "mean"), avg_visits=("frequency", "mean"))
tier.to_csv(TAB / "revenue_per_customer_by_tier.csv")
F["tier"] = tier

# ========================================================== FIGURES
# 1 monthly index: nominal, real, transactions (one axis, Jan 2024 = 100)
fig, ax = plt.subplots(figsize=(8, 4.2))
idx = monthly.copy()
series = [("Nominal revenue", idx["revenue"], "-", INK), ("Transactions", idx["txns"], ":", MID)]
if has_real:
    series.insert(1, ("Real revenue (CPI-adjusted)", idx["real_revenue"], "--", MID))
for lab, s, ls, col in series:
    v = s / s.iloc[0] * 100
    ax.plot(range(len(v)), v.values, ls, color=col, label=lab)
ax.set_xticks(range(0, len(idx), 3)); ax.set_xticklabels(idx.index[::3], rotation=0, fontsize=8.5)
ax.set_xlim(-0.5, len(idx) - 0.5); ax.set_ylabel("Index, January 2024 = 100")
ax.set_title("Monthly sales: nominal, real and volume (index)")
ax.legend(frameon=False, loc="upper left", fontsize=8.5)
save(fig, "01_monthly_index.png")

# 2 revenue by category, 3 revenue by store
for name, tbl, lab_col, title, fn in [("category", cat, cat.index, "Revenue by category (KES)", "02_revenue_by_category.png"),
                                      ("store", st, st["store_name"], "Revenue by store (KES)", "03_revenue_by_store.png")]:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    vals = tbl["revenue"].values[::-1]
    labs = list(lab_col)[::-1]
    ax.barh(labs, vals, color=INK, height=0.55)
    for i, v in enumerate(vals):
        ax.text(v, i, f"  {m(v)}  ({v / total_rev:.0%})", va="center", fontsize=8.5)
    ax.set_xlim(0, vals.max() * 1.28); ax.grid(axis="y", visible=False)
    ax.set_xlabel("Revenue, KES"); ax.xaxis.set_major_formatter(lambda x, _: f"{x / 1e6:.0f}M")
    ax.set_title(title)
    save(fig, fn)

# 4 concentration curves
fig, ax = plt.subplots(figsize=(6.5, 4.5))
for lab, s, ls, col in [("Customers (known)", cust_rev, "-", INK), ("Products", prod_rev, "--", MID)]:
    cum = s.cumsum() / s.sum()
    xs = np.arange(1, len(s) + 1) / len(s)
    ax.plot(np.r_[0, xs] * 100, np.r_[0, cum.values] * 100, ls, color=col, label=lab)
ax.axvline(20, color=SOFT, lw=1)
ax.set_xlabel("Share of customers or products, ranked by revenue (%)"); ax.set_ylabel("Share of revenue (%)")
ax.set_title("Revenue concentration"); ax.legend(frameon=False, loc="lower right")
ax.text(21, 6, f"Top 20%: customers {F['top20_customers']:.0%}, products {F['top20_products']:.0%}", fontsize=8.5)
save(fig, "04_concentration.png")

# 5 weekday and day-of-month rhythm
fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.9))
a.bar([d[:3] for d in dow.index], dow.values, color=[MID] * 5 + [INK] * 2, width=0.6)
a.set_ylabel("Avg transactions per day"); a.grid(axis="x", visible=False); a.set_title("By weekday")
b.plot(dom.index, dom.values, "-", color=INK, marker="o", ms=3.5)
b.axvspan(24.5, 31.5, color="#eeeeee"); b.axvspan(0.5, 2.5, color="#eeeeee")
b.set_xlabel("Day of month (shaded: payday window)"); b.set_title("By day of month")
save(fig, "05_weekday_and_payday_rhythm.png")

# 6 recovered effects with intervals and built-in truth
order = ["weekend", "payday", "prefest", "month_12", "month_1", "month_2", "month_8"] + \
        [f"hol_{h}" for h in ["Christmas", "Idd-ul-Fitr", "Easter Monday", "Madaraka Day", "Mashujaa Day", "Jamhuri Day",
                              "Mazingira Day", "Labour Day", "Boxing Day", "New Year", "Good Friday"]]
pretty = {"weekend": "Weekend", "payday": "Payday window", "prefest": "Pre-festive run-up (3 days)",
          "month_12": "December (vs June)", "month_1": "January (vs June)", "month_2": "February (vs June)",
          "month_8": "August (vs June)"}
e = eff.set_index("term").loc[order]
fig, ax = plt.subplots(figsize=(8, 7))
ypos = np.arange(len(e))[::-1]
for yv, (term, r) in zip(ypos, e.iterrows()):
    ax.plot([r.ci_low_pct, r.ci_high_pct], [yv, yv], "-", color=MID, lw=1.4)
    ax.plot(r.effect_pct, yv, "o", color=INK, ms=6)
    ax.plot(r.built_in_truth_pct, yv, "D", mfc="white", mec=INK, ms=6, mew=1.3)
ax.set_yticks(ypos)
ax.set_yticklabels([pretty.get(t, t.replace("hol_", "") + " (holiday)") for t in e.index], fontsize=9)
ax.axvline(0, color=INK, lw=0.8)
ax.set_xlabel("Effect on daily transactions (%), 95% interval")
ax.set_title("Calendar effects recovered from the data")
ax.plot([], [], "o", color=INK, label="Estimated"); ax.plot([], [], "D", mfc="white", mec=INK, label="Built into generator")
ax.legend(frameon=False, loc="lower right"); ax.grid(axis="y", visible=False)
save(fig, "06_calendar_effects.png")

# 7 customer distributions
fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.9))
a.hist(rfm["frequency"], bins=40, color=INK); a.set_xlabel("Purchase lines per customer"); a.set_ylabel("Customers")
a.set_title("Purchase frequency")
b.hist(np.log10(rfm["monetary_kes"].clip(lower=1)), bins=40, color=INK)
b.set_xlabel("Total spend per customer, KES (log10 scale)"); b.set_title("Customer spend")
save(fig, "07_customer_distributions.png")

# 8 RFM segments
fig, ax = plt.subplots(figsize=(7.5, 3.8))
s2 = seg.sort_values("revenue_share")
yy = np.arange(len(s2))
ax.barh(yy - 0.18, s2["customer_share"] * 100, height=0.34, color=SOFT, label="Share of customers")
ax.barh(yy + 0.18, s2["revenue_share"] * 100, height=0.34, color=INK, label="Share of revenue")
ax.set_yticks(yy); ax.set_yticklabels(s2.index); ax.set_xlabel("%"); ax.grid(axis="y", visible=False)
ax.set_title("RFM segments: customers versus revenue"); ax.legend(frameon=False, loc="lower right")
save(fig, "08_rfm_segments.png")

# ====================================================== WRITTEN FINDINGS
def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def g(term):
    r = eff.set_index("term").loc[term]
    return f"{r.effect_pct:+.1f}% (95% interval {r.ci_low_pct:+.1f}% to {r.ci_high_pct:+.1f}%; built in: {r.built_in_truth_pct:+.0f}%)"


top_cat = cat.index[0]; top_store = st["store_name"].iloc[0]
lines = []
A = lines.append
A("**MILESTONE 3: EXPLORATORY DATA ANALYSIS, FINDINGS**")
A("Generated by 03_eda/eda.py from data/clean/. Every number below is in 03_eda/tables/ and every chart is in 03_eda/figures/.\n")
A("**Scope and data used**")
A(f"- {F['rows']:,} clean sales lines, {df['date'].min().date()} to {df['date'].max().date()}, total revenue KES {F['revenue_total'] / 1e6:,.1f} million.")
A(f"- Typical sales line: median KES {F['median_line']:,.0f}, mean KES {F['avg_basket_line']:,.0f} (right-skewed, driven by electronics and clothing).")
A(f"- {pct(F['anon_share_rows'])} of lines ({pct(F['anon_share_rev'])} of revenue) have no usable customer ID. They are kept for sales analysis and excluded from customer analysis.")
A(f"- {F['imputed_price_rows']:,} unit prices were imputed in Milestone 2 and are flagged price_was_imputed.")
A("- Payment mix by revenue: " + ", ".join(f"{k} {pct(v, 0)}" for k, v in F["pay_share"].items()) + ".\n")

A("**Q2: What drives revenue, and how concentrated is it?**")
A(f"- {top_cat} is the largest category at {pct(cat['revenue_share'].iloc[0], 0)} of revenue; " +
  "; ".join(f"{i} {pct(r, 0)}" for i, r in cat["revenue_share"].iloc[1:].items()) + ".")
A(f"- {top_store} is the largest store at {pct(st['revenue_share'].iloc[0], 0)}; the smallest is {st['store_name'].iloc[-1]} at {pct(st['revenue_share'].iloc[-1], 0)}.")
A(f"- The top 20% of products bring {pct(F['top20_products'], 0)} of revenue and the top 20% of known customers bring {pct(F['top20_customers'], 0)}.")
A("- Figures: 02_revenue_by_category, 03_revenue_by_store, 04_concentration.\n")

A("**Q3: How much growth is real?**")
A(f"- 2025 nominal revenue grew {pct(F['nominal_growth'])} on 2024, while transaction count grew {pct(F['txn_growth'])}.")
if has_real:
    A(f"- Average CPI rose {pct(F['cpi_growth'])} between 2024 and 2025 (KNBS, base February 2019 = 100), so real revenue grew {pct(F['real_growth'])}.")
    A("- Roughly, growth splits into price inflation and real volume. Real growth is lower than nominal growth by about the CPI change.")
else:
    A("- Real revenue was not computed because the CPI series is incomplete.")
A("- Figure: 01_monthly_index. The December peak and January dip repeat in both years, so compare same months across years, never December with January.\n")

A("**Q1: Do holidays and the calendar change sales?**")
A(f"- Raw averages: weekend days have {pct(F['weekend_raw'], 0)} more transactions than weekdays, and the payday window (25th to 2nd) has {pct(F['payday_raw'], 0)} more than other days.")
A(f"- A regression of log daily transactions on trend, month, weekend, payday, pre-festive and holiday terms ({F['model_days']} days, R-squared {F['model_r2']:.2f}) gives:")
for term, lab in [("weekend", "Weekend"), ("payday", "Payday window"), ("prefest", "Pre-festive run-up"),
                  ("month_12", "December versus June"), ("month_1", "January versus June"),
                  ("hol_Christmas", "Christmas Day"), ("hol_Idd-ul-Fitr", "Idd-ul-Fitr"), ("hol_Good Friday", "Good Friday"),
                  ("hol_Easter Monday", "Easter Monday"), ("hol_New Year", "New Year")]:
    A(f"  - {lab}: {g(term)}")
A(f"- Underlying growth trend: about {F['trend_pct']:.1f}% a year in transaction volume.")
A(f"- {F['truth_inside']} of {F['truth_total']} built-in effects fall inside the 95% interval. A miss or two would be normal (about 1 in 20 by chance), mostly for holidays, which have only two observed days each.")
A("- Figures: 05_weekday_and_payday_rhythm, 06_calendar_effects.\n")

A("**Q4: Which customers matter?**")
for name, r in F["rfm"].iterrows():
    A(f"- {name}: {int(r['customers']):,} customers ({pct(r['customer_share'], 0)}), {pct(r['revenue_share'], 0)} of customer revenue, average {r['avg_frequency']:.0f} purchase lines, last seen {r['avg_recency_days']:.0f} days before the data ends.")
A("- Average total spend per customer by customer tier (Budget, Regular, Premium): " + ", ".join(f"{i} KES {r['avg_revenue']:,.0f}" for i, r in F["tier"].iterrows()) + ".")
A("- Figures: 07_customer_distributions, 08_rfm_segments. Churn modelling and forecasting are left to later milestones.\n")

A("**Limitations and checks**")
A("- The data is synthetic. These findings show that the method recovers known effects, not how a real retailer behaves.")
A("- The holiday effects rest on two days per holiday, so their intervals are wide.")
A("- 1,653 customers have purchases before their recorded signup date, a flaw in the generator. They are flagged and kept.")
A("- The RFM segments use quartile scores on the 2024 to 2025 window, so recency is measured against the last date in the data.")
(OUT / "eda_findings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nSaved {len(list(FIG.glob('*.png')))} figures, {len(list(TAB.glob('*.csv')))} tables and eda_findings.md in {OUT}/")
