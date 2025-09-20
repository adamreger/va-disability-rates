# VA Disability Compensation Rates (Normalized)

This repository provides **normalized datasets** of U.S. Department of Veterans Affairs (VA) disability compensation rates, along with the **scraping and normalization scripts** used to generate them.

- **Coverage:** 2020 – 2025 (effective December 1 of the prior year)
- **Format:** CSV (UTF-8, RFC 4180 compliant) with one row per (Year, Rating, Category, Dependent_Status / Added_Item)
- **Extras:** Python scripts for scraping, normalization, and validation
- **Source:** [VA Disability Compensation Rates](https://www.va.gov/disability/compensation-rates/veteran-rates/)

> ⚠️ This project is **not affiliated with the VA**. It republishes publicly available information in a developer-friendly format.

## Why this repo?

The VA publishes rates in multiple HTML tables, which can be cumbersome to work with programmatically.  
This repo normalizes those tables into a consistent schema across years, so you can:

- Import into Google Sheets, Excel, or BI tools
- Load into Python/R data pipelines
- Compare rates across years with a single dataset

## Repo Structure
```
va-disability-rates/
├─ data/
│  ├─ 2025/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
│  ├─ 2024/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
│  └─ 2023/
│     ├─ rates_normalized.csv
│     └─ README.md
├─ docs/
│  └─ index.md                 # Optional: GitHub Pages docs
├─ scripts/
│  ├─ fetch_2025.py
│  └─ validate.py              # schema/quality checks
├─ schemas/
│  └─ rates_schema.json        # column types, required fields
├─ tests/
│  └─ test_validate.py
├─ .gitattributes              # LFS rules (if needed)
├─ .github/workflows/ci.yml    # automatic validation on PRs
├─ CHANGELOG.md
├─ LICENSE
└─ README.md
```

## Schema

| Column            | Type    | Description |
|-------------------|---------|-------------|
| `Year`            | int     | Effective year of the rate table |
| `Rating`          | int     | Disability rating (10–100) |
| `Category`        | string  | "Basic" or "Added" |
| `Dependent_Group` | string  | "No children", "With children", or `null` for added items |
| `Dependent_Status`| string  | Dependency description (varies by group) |
| `Has_Spouse`      | boolean | Boolean flag to indicate if the rate incldues a dependent spouse |
| `Parent_Count`    | int     | Number of dependent parents in the rate (0, 1, or 2) |
| `Child_Count`     | int     | Number of dependent children in the rate (0 or 1) |
| `Added_Item`      | string  | Description of the added amount (if applicable) |
| `Monthly_Rate_USD`| float   | Monthly compensation in U.S. dollars |

## License

- **Data:** [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — public domain  
- **Code:** [MIT](https://opensource.org/licenses/MIT)

---

## Getting started

```bash
git clone https://github.com/YOUR_USERNAME/va-disability-rates.git
cd va-disability-rates

# Install dependencies
pip install -r requirements.txt

# Rebuild normalized 2025 dataset
python scripts/fetch_2025.py

## Contributing

Issues and pull requests welcome! Please see the CONTRIBUTING.md for guidelines.

## Versioning & releases
- Tag releases (v1.0.0, v1.1.0).
  - **PATCH:** corrected values, no schema change.
  - **MINOR:** new columns/years.
  - **MAJOR:** breaking schema changes.
- Publish GitHub Releases; attach the exact CSV/Parquet so consumers can pin.

## Validation & CI
Add basic QA so every PR keeps data clean.

**schemas/rates_schema.json** (Frictionless example):
```json
{
  "fields": [
    {"name": "Year", "type": "integer"},
    {"name": "Rating", "type": "integer", "constraints": {"minimum": 10, "maximum": 100}},
    {"name": "Dependent_Group", "type": "string", "missingValues": [""]},
    {"name": "Dependent_Status", "type": "string", "missingValues": [""]},
    {"name": "Category", "type": "string", "constraints": {"enum": ["Basic","Added"]}},
    {"name": "Added_Item", "type": "string", "missingValues": [""]},
    {"name": "Monthly_Rate_USD", "type": "number"}
  ],
  "primaryKey": ["Year","Rating","Category","Dependent_Group","Dependent_Status","Added_Item"]
}
```

**.github/workflows/ci.yml:**
```yaml
name: Validate data
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pipx install frictionless
      - run: |
          frictionless validate data/**/rates_normalized.csv \
            --schema schemas/rates_schema.json
```

## Data Dictionary (per-year README)
Inside each data/<year>/README.md:
- Effective date (e.g., “Effective Dec 1, 2024 for 2025 rates”).
- Source URL(s).
- Any manual adjustments or known caveats.
- Row counts, quick summary stats, checksum (optional sha256).

## Reproducibility
- Put scraping/cleaning in scripts/.
- A simple Makefile or justfile to rebuild:

## Discoverability
- Use good repo name & description (e.g., va-disability-rates-dataset).
- Add topics: `dataset`, `csv`, `va`, `benefits`, `public-data`, etc.
- Optional docs site with GitHub Pages (from docs/).

## Licensing & ethics
- For public gov data, CC0 (public domain) is common; if you require attribution, CC-BY 4.0.
- Include NOTICE about the original VA source and that your repo is not affiliated with the VA.
- Confirm no PII/PHI; keep data aggregate and public.
