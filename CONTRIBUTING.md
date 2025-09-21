# Contributing to VA Disability Rates

Thanks for your interest in contributing! This project publishes **normalized datasets of VA disability compensation rates** along with scraping and validation scripts.
We welcome pull requests for **new years of data, bug fixes, or improvements to the tooling**.

---

## Development Setup

### 1. Clone the repo:
```bash
git clone git@github.com:YOUR_USERNAME/va-disability-rates.git
cd va-disability-rates
```

### 2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

### 3. Run tests
```bash
pytest
```

## Adding a New Year of Data
1. Scrape rates from the official VA page (e.g. for 2026: https://www.va.gov/disability/compensation-rates/veteran-rates/). Past years live under /past-rates-YYYY/.

2. Normalize the tables into the schema used in:
```bash
data/<year>/rates_normalized.csv
```

3. Place the file in a new folder:
```bash
data/2026/rates_normalized.csv
```

4. Add a short `README.md` in that folder with:
* Source URL(s)
* Effective date
* Notes about any manual cleanup

## Validation

Run the schema validation before committing:
```bash
frictionless validate data/2026/rates_normalized.csv --schema schemas/rates_schema.json
```

All files must pass validation (correct columns, no malformed data).

## Updating Documentation
* Add the new year the **root README.md** coverage list
* Update the CHANGELOG.md with a new entry

## Pull Request Guidelines
* Use a clear title (e.g., `Add 2026 rates`)
* Reference the source VA URL in your PR description
* Confirm validation passes in CI
* Ensure your changes follow coding style and linting (Ruff will auto-run via pre-commit)

### PR Checklist
- [ ] Data validates with schema
- [ ] README.md updated (coverage list)
- [ ] CHANGELOG.md updated
- [ ] Tests pass locally

## Coding Style
* Python scripts should follow [PEP 8](https://peps.python.org/pep-0008/)
* Use descriptive commit messages (imperative style: “Add 2026 dataset”)
* Keep CSVs clean: UTF-8 encoding, no extra BOM, header row required

## License
* Data: CC0 1.0 (public domain)
* Code: MIT

By contributing, you agree that your work will be released under these licenses.
