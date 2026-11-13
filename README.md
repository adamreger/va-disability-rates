# VA Disability Compensation Rates (Normalized)

This repository provides **normalized datasets** of U.S. Department of Veterans Affairs (VA) disability compensation rates, along with the **scraping and normalization scripts** used to generate them.

- **Coverage:** 2020 – 2026 (effective December 1 of the prior year)
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
│  ├─ 2026/
│  │  ├─ rates_normalized.csv
│  │  └─ README.md
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
│  ├─ parser.py
│  ├─ normalizer.py
│  └─ requirements.txt
├─ tests/
│  └─ test_scrape_va_rates.py
├─ .github/workflows/validate-data.yml
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
| `Has_Spouse`       | boolean | Boolean flag to indicate if the rate includes a dependent spouse |
| `Parent_Count`     | int     | Number of dependent parents in the rate (0, 1, or 2)             |
| `Has_Child`        | boolean | Boolean flag to indicate if the rate includes a dependent child  |
| `Added_Item`       | string  | Description of the added amount (if applicable)                  |
| `Monthly_Rate_USD` | float   | Monthly compensation in U.S. dollars                             |

## License

- **Data:** [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — public domain
- **Code:** [MIT](https://opensource.org/licenses/MIT)

---

## Getting started

```bash
git clone git@github.com:adamreger/va-disability-rates.git
cd va-disability-rates

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
pre-commit install
```

### Scrape one year

Run commands from the repository root. Each invocation scrapes one explicit source URL for one rate year. Confirm that the source page covers the year supplied with `--year`.

```bash
python scripts/scrape_va_rates.py \
  --url "https://www.va.gov/disability/compensation-rates/veteran-rates/" \
  --year 2026 \
  --out data/2026/rates_normalized.csv \
  --debug \
  --write-readme
```

The scraper installs Chromium through Playwright on first use. The output CSV is replaced if it already exists. Generated READMEs preserve existing bullets under `General Notes`.

To preview the first five rows without writing files:

```bash
python scripts/scrape_va_rates.py \
  --url "https://www.va.gov/disability/compensation-rates/veteran-rates/" \
  --year 2026 \
  --preview 5
```

| Parameter | Purpose |
| --- | --- |
| `--url` | Required source page URL |
| `--year` | Required single integer rate year |
| `--out`, `--output` | Output CSV path; required unless previewing |
| `--preview N` | Preview a positive number of rows; writes no CSV or README |
| `--debug` | Print table extraction and deduplication details |
| `--write-readme` | Generate a README alongside the CSV; requires an output path |

Invalid arguments and scrape failures exit with a nonzero status.

## Usage Example
Load dataset into pandas and query 100% ratings:
```python
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

Every push and pull request runs tests, Ruff lint and formatting checks, and schema validation for every dataset through [the CI workflow](.github/workflows/validate-data.yml). Tests replace browser I/O and do not contact the VA or download Chromium.

Run the same code checks locally:

```bash
python -m pytest
ruff check scripts tests
ruff format --check scripts tests
frictionless validate data/2026/rates_normalized.csv --schema schemas/rates_schema.json
```

For the annual data update and review process, see [CONTRIBUTING.md](CONTRIBUTING.md#adding-or-correcting-a-year-of-data).

## Data Dictionary (per-year README)
Inside each data/<year>/README.md:
- Effective date (e.g., “Effective Dec 1, 2024 for 2025 rates”).
- Source URL(s).
- Any manual adjustments or known caveats.
- Row counts, quick summary stats, checksum (sha256).

## License
- **Data:** [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) — public domain
- **Code:** [MIT](https://opensource.org/licenses/MIT)
