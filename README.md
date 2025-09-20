# VA Disability Compensation Rates (Normalized)

Sample, versioned datasets of VA disability compensation rates by year.

- **Coverage:** 2020–2025
- **Grain:** One row per (Year, Rating, Category, Dependent_Status / Added_Item)
- **Source:** https://www.va.gov/disability/compensation-rates/veteran-rates/

## Repo Layout
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

## README Essentials
- **What & why** (1–2 sentences).
- **Source & provenance** (original URLs, effective dates, any manual steps).
- **Schema** (columns, types, allowed values, units, null policy).
- **Versioning** (semantic versioning; how you bump versions when schema/values change).
- **How to use** (quick examples in Python/R/Sheets).
- **License** (data: CC0 or CC-BY 4.0; code: MIT/Apache-2.0).
- **Cite this** (how you want credit + link to DOI if you mint one).
- **Limitations** (known gaps, rounding, update cadence).

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
