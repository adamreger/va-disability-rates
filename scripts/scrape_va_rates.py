#!/usr/bin/env python3
import argparse
import asyncio
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

# Support both `python scripts/scrape_va_rates.py` and package imports in tests.
if __package__:
    from .parser import (
        JS_FIND_PRECEDING_H3,
        JS_GET_DISTRIBUTED_TEXT,
        extract_ratings_from_headers,
        format_effective_line,
        looks_like_10_20_table,
    )

    from .normalizer import (
        dep_group_from_heading,
        normalize_rows,
        parse_rate_to_float,
    )
else:
    from parser import (
        JS_FIND_PRECEDING_H3,
        JS_GET_DISTRIBUTED_TEXT,
        extract_ratings_from_headers,
        format_effective_line,
        looks_like_10_20_table,
    )

    from normalizer import (
        dep_group_from_heading,
        normalize_rows,
        parse_rate_to_float,
    )

# ---------- Setup helpers ----------


def ensure_playwright_browsers() -> None:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


async def _extract_effective_text(page: Any, debug: bool = False) -> Optional[str]:
    try:
        locator = page.locator("strong", has_text="Effective")
        if await locator.count() == 0:
            return None
        text = (await locator.first.inner_text()).strip()
        if debug:
            print(f"[DEBUG] Found effective date text: {text}")
        return text
    except Exception:
        return None


def _extract_existing_general_notes(readme_path: Path) -> List[str]:
    if not readme_path.exists():
        return []

    notes: List[str] = []
    in_notes_section = False
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower() == "## general notes":
            in_notes_section = True
            continue
        if in_notes_section:
            if stripped.startswith("## "):
                break
            if stripped.startswith("- "):
                notes.append(stripped)
    return notes


def _generate_summary_lines(df: pd.DataFrame, duplicates_removed: int) -> List[str]:
    total_rows = len(df)
    category_counts = df["Category"].value_counts().to_dict()
    basic_rows = int(category_counts.get("Basic", 0))
    added_rows = int(category_counts.get("Added", 0))

    ratings = sorted(df["Rating"].unique())
    rating_min = ratings[0] if ratings else "n/a"
    rating_max = ratings[-1] if ratings else "n/a"

    monthly = df["Monthly_Rate_USD"]
    monthly_min = monthly.min()
    monthly_max = monthly.max()
    monthly_mean = monthly.mean()

    return [
        f"- Total rows: {total_rows}",
        f"- Basic rows: {basic_rows}; Added rows: {added_rows}",
        f"- Ratings covered: {rating_min}-{rating_max} ({len(ratings)} unique)",
        f"- Monthly rate (USD): min ${monthly_min:,.2f}, max ${monthly_max:,.2f}, mean ${monthly_mean:,.2f}",
        f"- Duplicates removed during normalization: {duplicates_removed}",
    ]


def _write_dataset_readme(
    output_csv: Path,
    df: pd.DataFrame,
    url: str,
    year: int,
    effective_text: Optional[str],
    duplicates_removed: int,
) -> None:
    directory = output_csv.parent
    readme_path = directory / "README.md"

    existing_notes = _extract_existing_general_notes(readme_path)

    checksum = hashlib.sha256(output_csv.read_bytes()).hexdigest()

    lines: List[str] = []
    lines.append(f"# VA Disability Compensation Rates – {year}")
    lines.append("")
    lines.append(f"- {format_effective_line(effective_text, year)}")
    lines.append(f"- Source: {url}")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.extend(_generate_summary_lines(df, duplicates_removed))
    lines.append("")
    lines.append("## Checksum")
    lines.append(f"- SHA256: `{checksum}`")
    lines.append("")
    lines.append("## General Notes")

    note_lines = existing_notes or ["- _None recorded._"]
    lines.extend(note_lines)
    lines.append("")

    directory.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved dataset README to {readme_path}")


def _debug_table_log(
    idx: int,
    caption: str,
    category: Optional[str],
    headers: List[str],
    body_rows: int,
    section: Optional[Dict[str, Any]],
) -> None:
    cat = category or "UNKNOWN"
    hdrs = ", \n\t\t".join([f"'{h}'" for h in headers])
    section_line = ""
    if section:
        section_line = (
            f"\n\t\tsection_h3_id='{section.get('id', '')}', "
            f"section_h3_text='{section.get('text', '')}', "
        )
    print(
        f"[DEBUG] Table {idx}: \n"
        f"\t\tcaption='{caption}', \n"
        f"\t\tcategory={cat},{section_line}\n"
        f"\t\theaders=[\n\t\t\t{hdrs}\n\t\t], \n"
        f"\t\tbody_rows={body_rows}"
    )


async def _scrape_rows(
    page: Any,
    url: str,
    year: int,
    debug: bool,
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    print(f"Processing year {year} from {url}...")

    if debug:
        print(f"[DEBUG] Navigating to: {url}")

    await page.goto(url, wait_until="networkidle")

    effective_text = await _extract_effective_text(page, debug)

    # Expand accordions
    buttons = await page.query_selector_all(
        'va-accordion button[data-testid="expand-all-accordions"]'
    )
    for b in buttons:
        try:
            await b.click()
        except Exception:
            pass

    # Collect tables
    await page.wait_for_selector("va-table-inner.hydrated", timeout=15000)
    inners = await page.query_selector_all("va-table-inner.hydrated")
    tables = []
    for inner in inners:
        handle = await inner.evaluate_handle(
            'el => el.shadowRoot ? el.shadowRoot.querySelector("table") : null'
        )
        table_el = handle.as_element() if handle else None
        if table_el:
            tables.append(table_el)

    rows_out = []

    for idx, t in enumerate(tables, start=1):
        caption_el = await t.query_selector("caption")
        caption_text = (
            await caption_el.evaluate(JS_GET_DISTRIBUTED_TEXT) if caption_el else ""
        )
        category = (
            "Basic"
            if "Basic" in caption_text
            else ("Added" if "Added" in caption_text else None)
        )

        header_els = await t.query_selector_all("thead tr th")
        headers = [await h.evaluate(JS_GET_DISTRIBUTED_TEXT) for h in header_els]
        headers = [h.strip() for h in headers]
        ratings_from_headers = extract_ratings_from_headers(headers)

        section_meta = await t.evaluate(JS_FIND_PRECEDING_H3)
        dep_group_override = (
            dep_group_from_heading(
                section_meta.get("id", ""), section_meta.get("text", "")
            )
            if section_meta
            else None
        )

        body_rows = await t.query_selector_all("tbody tr")

        if debug:
            _debug_table_log(
                idx,
                caption_text or "",
                category,
                headers,
                len(body_rows),
                section_meta,
            )

        if category is None:
            if looks_like_10_20_table(
                headers, len(headers)
            ) or "Dependent status" in " ".join(headers):
                category = "Basic"
            else:
                category = "Added" if any("Added" in h for h in headers) else "Basic"

        # 10-20% table special case
        if looks_like_10_20_table(headers, len(headers)):
            for br in body_rows:
                cells = await br.query_selector_all("th, td")
                values = [await c.evaluate(JS_GET_DISTRIBUTED_TEXT) for c in cells]
                if len(values) < 2:
                    continue
                m = re.search(r"(\d+)\s*%", values[0])
                if not m:
                    continue
                rating = int(m.group(1))
                try:
                    rate = parse_rate_to_float(values[1])
                except ValueError:
                    continue
                rows_out.append(
                    {
                        "Year": year,
                        "Rating": rating,
                        "Dependent_Group": dep_group_override or "All",
                        "Dependent_Status": "All",
                        "Category": "Basic",
                        "Added_Item": None,
                        "Monthly_Rate_USD": rate,
                    }
                )
            continue

        # Standard table
        for br in body_rows:
            cells = await br.query_selector_all("th, td")
            values = [await c.evaluate(JS_GET_DISTRIBUTED_TEXT) for c in cells]
            if not values:
                continue

            dependent_status_raw = values[0].strip()
            added_item = None

            if category == "Added":
                added_item = dependent_status_raw
                dependent_group = ""
                dependent_status = ""
            else:
                dependent_status = dependent_status_raw
                if dep_group_override:
                    dependent_group = dep_group_override
                else:
                    lower = dependent_status.lower()
                    if "child" in lower:
                        dependent_group = "With children"
                    elif "spouse" in lower or "parent" in lower:
                        dependent_group = "No children"
                    else:
                        dependent_group = "All"

            for col_idx, val in enumerate(values[1:], start=1):
                if not val:
                    continue
                rating = (
                    ratings_from_headers[col_idx]
                    if col_idx < len(ratings_from_headers)
                    else None
                )
                if rating is None and col_idx < len(headers):
                    m = re.search(r"(\d+)\s*%", headers[col_idx])
                    if m:
                        rating = int(m.group(1))
                if rating is None:
                    continue
                try:
                    rate = parse_rate_to_float(val)
                except ValueError:
                    continue

                rows_out.append(
                    {
                        "Year": year,
                        "Rating": rating,
                        "Dependent_Group": dependent_group,
                        "Dependent_Status": dependent_status,
                        "Category": category,
                        "Added_Item": added_item,
                        "Monthly_Rate_USD": rate,
                    }
                )

    return rows_out, effective_text


async def scrape(
    url: str,
    year: int,
    output_file: Optional[Path],
    preview: Optional[int] = None,
    debug: bool = False,
    write_readme: bool = False,
) -> None:
    """Scrape one source page for one rate year."""
    ensure_playwright_browsers()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            rows_out, effective_text = await _scrape_rows(page, url, year, debug)
        finally:
            await browser.close()

    if not rows_out:
        raise RuntimeError(f"No rows were scraped for {year} from {url}.")

    df, duplicates_removed = normalize_rows(rows_out)
    if debug:
        print(f"[DEBUG] Deduplication removed {duplicates_removed} duplicate rows")
        print(f"[DEBUG] Final row count after dedup: {len(df)}")

    if preview is not None:
        print(df.head(preview).to_string(index=False))
        print("[INFO] Preview mode: skipped writing CSV and README.")
    else:
        if not output_file:
            raise ValueError("Provide --out/--output or run with --preview.")

        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} rows to {output_file}")

        if write_readme:
            _write_dataset_readme(
                output_file,
                df,
                url,
                year,
                effective_text,
                duplicates_removed,
            )


# ---------- CLI ----------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scrape one year of VA disability rates into CSV."
    )
    parser.add_argument("--url", required=True, help="VA.gov disability rates page URL")
    parser.add_argument(
        "--year",
        required=True,
        type=int,
        help="Single rate year (e.g., 2026)",
    )
    parser.add_argument(
        "--out", "--output", dest="output_file", type=Path, help="Output CSV path"
    )
    parser.add_argument(
        "--preview", type=int, help="Preview first N rows; no file written"
    )
    parser.add_argument("--debug", action="store_true", help="Verbose debug logging")
    parser.add_argument(
        "--write-readme",
        action="store_true",
        help="Generate a README.md alongside the output CSV",
    )
    args = parser.parse_args(argv)

    if args.preview is not None and args.preview < 1:
        parser.error("--preview must be a positive integer")
    if args.write_readme and not args.output_file:
        parser.error("--write-readme requires --out/--output")
    if not args.output_file and args.preview is None:
        parser.error("provide --out/--output or run with --preview")

    try:
        asyncio.run(
            scrape(
                args.url,
                args.year,
                args.output_file,
                args.preview,
                args.debug,
                args.write_readme,
            )
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
        PlaywrightError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
