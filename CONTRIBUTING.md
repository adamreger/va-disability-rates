# Contributing to VA Disability Rates

Thanks for your interest in contributing! This project publishes **normalized datasets of VA disability compensation rates** along with scraping and validation scripts.  
We welcome pull requests for **new years of data, bug fixes, or improvements to the tooling**.

---

## How to Contribute

### 1. Fork and Clone
```bash
git clone https://github.com/YOUR_USERNAME/va-disability-rates.git
cd va-disability-rates
```

### 2. Add a New Year of Data
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

### 3. Validate

Run the schema validation before committing:
```bash
pip install frictionless
frictionless validate data/2026/rates_normalized.csv --schema schemas/rates_schema.json
```

All files must pass validation (correct columns, no malformed data).

### 4. Update Documentation
* Add the new year the **root README.md** coverage list.
* Update the CHANGELOG.md with a new entry

### 5. Submit a Pull Request
* Use a clear title (e.g., `Add 2026 rates`).
* Reference the source VA URL in your PR description.
* Confirm validation passes in CI.

---

## Coding Style
* Python scripts should follow [PEP 8](https://peps.python.org/pep-0008/).
* Use descriptive commit messages (imperative style: “Add 2026 dataset”).
* Keep CSVs clean: UTF-8 encoding, no extra BOM, header row required.

---

## License
* Data: CC0 1.0 (public domain)
* Code: MIT

By contributing, you agree that your work will be released under these licenses.