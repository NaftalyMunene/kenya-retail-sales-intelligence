## 2026-11-02 (Milestone 3)
- Saved `03_eda/eda.py` and ran it on `data/clean/sales_clean.csv`.
- Outputs: 8 figures in `03_eda/figures/`, 13 tables in `03_eda/tables/`, findings in `03_eda/eda_findings.md`.
- Key findings: total revenue KES 163.8M; Groceries 54% of revenue; Thika Road 20%; top 20% of products 51% of revenue; top 20% of known customers 54%; 2025 nominal revenue +9.6%, transactions +5.6%, real revenue +5.3% after CPI; all 18 generator-built calendar effects recovered inside 95% intervals (weekend ~+26%, payday ~+17%, December ~+28% vs June, Christmas ~+52%, Good Friday ~-21%).
- Limitations stated in findings: data is synthetic; holiday effects rest on two days each (wide intervals); 1,653 customers purchase before signup (generator flaw, flagged).## 2026-10-29
- Ran `01_framing/generate_data.py` (SEED=42) → 5 output files in `data/raw/synthetic/`.
- Defect counts recorded in `data/raw/synthetic/injected_defects.json`.
- Changed generator output path from `data/raw/generated/` to `data/raw/synthetic/`.
- Wrote `01_framing/problem_statement.md` and `01_framing/data_inventory.md`.
- Milestone 1 documents ready for commit.# Daily Log

## 2026-10-27
- Created repository skeleton and pushed to GitHub.
- Downloaded and placed five source PDFs in data/raw/context/.
- Wrote 01_framing/source_register.md with five sources and Easter-date note.
