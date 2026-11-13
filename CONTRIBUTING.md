# Contributing to VA Disability Rates

Thanks for your interest in contributing! This project publishes **normalized datasets of VA disability compensation rates** along with scraping and validation scripts.
We welcome pull requests for **new years of data, bug fixes, or improvements to the tooling**.

---

## Development Setup

### 1. Clone the repo:
```bash
git clone git@github.com:{GITHUB_USERNAME}/va-disability-rates.git
cd va-disability-rates
```

### 2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pre-commit install
```

### 3. Run code checks
```bash
python -m pytest
ruff check scripts tests
ruff format --check scripts tests
```

Tests replace browser I/O, so they run without downloading Chromium or accessing the VA website.

## Adding or Correcting a Year of Data

Run these commands from the repository root. Updates normally affect one rate year. Use the same process for a historical correction, leaving other years unchanged.

1. Select the official VA source page for the year being updated. Check the page's effective date: `--year` labels the output and must match the rate year on that page.

2. Preview the extraction. For example, when the source page covers 2026:

```bash
python scripts/scrape_va_rates.py \
  --url "https://www.va.gov/disability/compensation-rates/veteran-rates/" \
  --year 2026 \
  --preview 5 \
  --debug
```

3. Generate the CSV and its README. Change the URL, year, and output directory together for a different year:

```bash
python scripts/scrape_va_rates.py \
  --url "https://www.va.gov/disability/compensation-rates/veteran-rates/" \
  --year 2026 \
  --out data/2026/rates_normalized.csv \
  --write-readme
```

The scraper installs Chromium through Playwright on first use. It replaces the selected CSV and preserves existing bullets in the README's `General Notes` section.

4. Validate the CSV using the command below. Review the source URL, effective date, row counts, ratings, and representative Basic and Added amounts against the source page. Schema validation checks structure and types; the source comparison checks the values.

5. Review `git diff -- data/2026/` and `git status --short` to confirm the intended year's files changed. Newly created files appear in status and need to be reviewed directly before staging. Record any manual corrections in that year's `General Notes`.

6. Update the root README's coverage and directory list when adding a new year. Run code checks, then include the source URL and validation results in the commit or pull request.

## Validation

Run the schema validation before committing:
```bash
frictionless validate data/2026/rates_normalized.csv --schema schemas/rates_schema.json
```

All files must pass validation (correct columns, no malformed data).

## Pull Request Guidelines
* Use a clear title (e.g., `Add 2026 rates`)
* Reference the source VA URL in your PR description
* Confirm validation passes in CI
* Ensure tests, lint, formatting, and schema validation pass locally and in CI

### PR Checklist
- [ ] Data validates with schema
- [ ] README.md updated (coverage list)
- [ ] Per-year README reviewed (source, effective date, summary, checksum, and notes)
- [ ] Tests pass locally

## Coding Style
* Python scripts should follow [PEP 8](https://peps.python.org/pep-0008/)
* Use descriptive commit messages (imperative style: “Add 2026 dataset”)
* Keep CSVs clean: UTF-8 encoding, no extra BOM, header row required

## License
* Data: CC0 1.0 (public domain)
* Code: MIT

By contributing, you agree that your work will be released under these licenses.
