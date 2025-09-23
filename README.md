# VA Disability Compensation Rates (Normalized)

This repository provides **normalized datasets** of U.S. Department of Veterans Affairs (VA) disability compensation rates, along with the **scraping and normalization scripts** used to generate them.

- **Coverage:** 2020 – 2025 (effective December 1 of the prior year)
- **Format:** CSV (UTF-8, RFC 4180 compliant) with one row per (Year, Rating, Category, Dependent_Status / Added_Item)
- **Extras:** Python scripts for scraping, normalization, and validation
- **Source:** [VA Disability Compensation Rates](https://www.va.gov/disability/compensation-rates/veteran-rates/)

> ⚠️ This project is **not affiliated with the VA**. It republishes publicly available information in a developer-friendly format.

## Why this repo?

The VA publishes rates in multiple HTML tables, which can be cumbersome to work with programmatically. This repo normalizes those tables into a consistent schema across years, so you can:

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
│  ├─ 2023/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
│  ├─ 2022/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
│  ├─ 2021/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
│  ├─ 2020/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
├─ schemas/
│  └─ rates_schema.json
├─ scripts/
│  ├─ scrape_va_rates.py
├─ tests/
│  └─ test_scrape_va_rates.py
├─ .github/workflows/validate-data.yml
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ LICENSE
└─ README.md
```

## Schema

| Column             | Type    | Description                                                      |
| ------------------ | ------- | ---------------------------------------------------------------- |
| `Year`             | int     | Effective year of the rate table                                 |
| `Rating`           | int     | Disability rating (10–100)                                       |
| `Category`         | string  | "Basic" or "Added"                                               |
| `Dependent_Group`  | string  | "No children", "With children", or `null` for added items        |
| `Dependent_Status` | string  | Dependency description (varies by group)                         |
| `Has_Spouse`       | boolean | Boolean flag to indicate if the rate incldues a dependent spouse |
| `Parent_Count`     | int     | Number of dependent parents in the rate (0, 1, or 2)             |
| `Has_Child`        | boolean | Boolean flag to indicate if the rate incldues a dependent child  |
| `Added_Item`       | string  | Description of the added amount (if applicable)                  |
| `Monthly_Rate_USD` | float   | Monthly compensation in U.S. dollars                             |

## License

- **Data:** [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — public domain
- **Code:** [MIT](https://opensource.org/licenses/MIT)

---

## Getting started

```bash
git clone https://github.com/YOUR_USERNAME/va-disability-rates.git
cd va-disability-rates

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
pre-commit install
```

### Rebuild normalized dataset:
```bash
python scrape_va_rates.py \
  --url "https://www.va.gov/disability/compensation-rates/veteran-rates" \
  --year 2025 \
  --out ../data/2025/rates_normalized.csv \
  --debug \
  --write-readme
```

### Parameters:
```python
"--url", required=True, help="VA.gov disability rates page URL")
"--year", required=True, type=int, help="Rates year (e.g., 2024)"
"--out", help="Output CSV path")
"--output", help="Output CSV path (alias for --out)")
"--preview", type=int, help="Preview first N rows; no file written"
"--debug", action="store_true", help="Verbose debug logging")
"--write-readme", action="store_true", help="Generate a README.md alongside the output CSV. Merges in any previous bullets under "General Notes""
```

## Usage Example
Load dataset into pandas and query 100% ratings:
```bash
import pandas as pd

df = pd.read_csv("data/2025/rates_normalized.csv")
print(df[df["Rating"] == 100])
```


## Contributing
Issues and pull requests welcome!
Please see the [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## Versioning & releases
- **PATCH:** corrected values, no schema change.
- **MINOR:** new columns/years.
- **MAJOR:** breaking schema changes.
Releases are tagged (v1.0.0, v1.1.0) and published with attached CSVs/Parquet so consumers can pin to exact versions.

## Validation & CI
Every PR is automatically validated against the schema in GitHub CI

**schemas/rates_schema.json**:
```yaml
name: Validate data

on:
  push:
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install frictionless
      - name: Validate data files
        run: |
          frictionless validate data/**/rates_normalized.csv --schema schemas/rates_schema.json
```

## Data Dictionary (per-year README)
Inside each data/<year>/README.md:
- Effective date (e.g., “Effective Dec 1, 2024 for 2025 rates”).
- Source URL(s).
- Any manual adjustments or known caveats.
- Row counts, quick summary stats, checksum (sha256).

## License
- **Data:** [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — public domain
- **Code:** [MIT](https://opensource.org/licenses/MIT)
