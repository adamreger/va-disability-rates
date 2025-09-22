#!/usr/bin/env python3
import argparse
import asyncio
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
from playwright.async_api import async_playwright

# ---------- Setup helpers ----------


def ensure_playwright_browsers() -> None:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _parse_rate_to_float(s: str) -> float:
    clean = s.replace("$", "").replace(",", "").replace("\u00a0", " ").strip()
    return float(clean)


# Grab slotted/distributed text from cells/headers living under <slot> inside shadow DOM
JS_GET_DISTRIBUTED_TEXT = """
(cell) => {
  const getText = (node) => {
    if (!node) return '';
    if (node.nodeType === Node.TEXT_NODE) return node.textContent || '';
    if (node.tagName && node.tagName.toLowerCase() === 'slot') {
      const assigned = node.assignedNodes({flatten: true});
      return assigned.map(getText).join(' ');
    }
    const slot = node.querySelector && node.querySelector('slot');
    if (slot) {
      const assigned = slot.assignedNodes({flatten: true});
      if (assigned && assigned.length) return assigned.map(getText).join(' ');
    }
    return Array.from(node.childNodes || []).map(getText).join(' ');
  };
  return getText(cell).replace(/\\s+/g, ' ').trim();
}
"""

# Find closest preceding H3 in light DOM for the <va-table> hosting this <table>
JS_FIND_PRECEDING_H3 = """
(tableEl) => {
  const innerHost = tableEl.getRootNode()?.host || null; // <va-table-inner>
  const vaTable = innerHost ? innerHost.closest('va-table') : null;
  if (!vaTable) return null;

  let node = vaTable;
  while (node) {
    let p = node.previousElementSibling;
    while (p) {
      const h3s = p.querySelectorAll ? p.querySelectorAll('h3') : [];
      if (h3s && h3s.length) {
        const h3 = h3s[h3s.length - 1];
        return { id: h3.id || '', text: (h3.textContent || '').trim() };
      }
      if (p.tagName && p.tagName.toLowerCase() === 'h3') {
        return { id: p.id || '', text: (p.textContent || '').trim() };
      }
      p = p.previousElementSibling;
    }
    node = node.parentElement;
  }
  return null;
}
"""


def _extract_ratings_from_headers(headers: List[str]) -> List[Optional[int]]:
    ratings: List[Optional[int]] = []
    for h in headers:
        m = re.search(r"(\d+)\s*%", h)
        ratings.append(int(m.group(1)) if m else None)
    return ratings


def _looks_like_10_20_table(headers: List[str], ncols: int) -> bool:
    # 10–20% table has exactly two columns, and headers are not percentages
    return ncols == 2 and not any(re.search(r"\d+\\s*%", h) for h in headers)


def _dep_group_from_h3_id(h3_id: str) -> Optional[str]:
    id_lower = (h3_id or "").lower()
    if id_lower.startswith("with-a-dependent-spouse-or-par"):
        return "No children"
    if id_lower.startswith("with-dependents-including-chil"):
        return "With children"
    return None


def _debug_table_log(
    idx: int,
    caption: str,
    category: Optional[str],
    headers: List[str],
    body_rows: int,
    section: Optional[Dict[str, Any]],
) -> None:
    # Pretty-print to match your requested format
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


# ---------- Main scrape ----------


async def scrape(
    url: str,
    year: int,
    output_file: Optional[str],
    preview: Optional[int] = None,
    debug: bool = False,
) -> None:
    ensure_playwright_browsers()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        if debug:
            print(f"[DEBUG] Navigating to: {url}")

        await page.goto(url, wait_until="networkidle")

        # Expand all accordions
        buttons = await page.query_selector_all(
            'va-accordion button[data-testid="expand-all-accordions"]'
        )
        clicked = 0
        for b in buttons:
            try:
                await b.click()
                clicked += 1
            except Exception:
                pass
        if debug:
            print(f"[DEBUG] Clicked 'Expand all' on {clicked} accordion(s)")

        # Collect tables by piercing shadow roots
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

        if debug:
            print(
                f"[DEBUG] Found {len(tables)} table(s) inside va-table-inner (shadow DOM)"
            )

        rows_out = []

        for idx, t in enumerate(tables, start=1):
            # Caption → category detection
            caption_el = await t.query_selector("caption")
            caption_text = (
                await caption_el.evaluate(JS_GET_DISTRIBUTED_TEXT) if caption_el else ""
            )
            category = (
                "Basic"
                if "Basic" in caption_text
                else ("Added" if "Added" in caption_text else None)
            )

            # Headers via slotted text
            header_els = await t.query_selector_all("thead tr th")
            headers = [await h.evaluate(JS_GET_DISTRIBUTED_TEXT) for h in header_els]
            headers = [h.strip() for h in headers]
            ratings_from_headers = _extract_ratings_from_headers(headers)

            # Section H3 used to override dependent group for Basic tables
            section_meta = await t.evaluate(JS_FIND_PRECEDING_H3)
            dep_group_override = (
                _dep_group_from_h3_id(section_meta["id"]) if section_meta else None
            )

            # Body rows
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

            # Fallback category detection if caption missing
            if category is None:
                if _looks_like_10_20_table(
                    headers, len(headers)
                ) or "Dependent status" in " ".join(headers):
                    category = "Basic"
                else:
                    category = (
                        "Added" if any("Added" in h for h in headers) else "Basic"
                    )

            # Special case: 10–20% table (ratings are first-column values)
            if _looks_like_10_20_table(headers, len(headers)):
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
                        rate = _parse_rate_to_float(values[1])
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

            # General case: headers[1..] are ratings columns
            for br in body_rows:
                cells = await br.query_selector_all("th, td")
                values = [await c.evaluate(JS_GET_DISTRIBUTED_TEXT) for c in cells]
                if not values:
                    continue

                dependent_status_raw = values[0].strip()
                added_item = None

                if category == "Added":
                    # Your rule: empty Dependent_Group and Dependent_Status; use label as Added_Item
                    added_item = dependent_status_raw
                    dependent_group = ""
                    dependent_status = ""
                else:
                    # Basic tables: infer/override dependent group
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
                        rate = _parse_rate_to_float(val)
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

        await browser.close()

    if not rows_out:
        raise SystemExit("No rows were scraped.")

    # Build DataFrame and de-duplicate on the full identity
    df = pd.DataFrame(rows_out)
    before = len(df)
    df = df.drop_duplicates(
        subset=[
            "Year",
            "Rating",
            "Dependent_Group",
            "Dependent_Status",
            "Category",
            "Added_Item",
            "Monthly_Rate_USD",
        ],
        keep="first",
    ).reset_index(drop=True)
    after = len(df)

    # Print dedup summary and final count in debug mode
    if debug:
        removed = before - after
        print(f"[DEBUG] Deduplication removed {removed} duplicate rows")
        print(f"[DEBUG] Final row count after dedup: {after}")

    if preview:
        print(df.head(preview).to_string(index=False))
        print("[INFO] Preview mode: skipped writing CSV.")
    else:
        if not output_file:
            raise SystemExit("Error: provide --out/--output or run with --preview.")
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} rows to {output_file}")


# ---------- CLI ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape VA disability rates (single year) into CSV."
    )
    parser.add_argument("--url", required=True, help="VA.gov disability rates page URL")
    parser.add_argument(
        "--year", required=True, type=int, help="Rates year (e.g., 2024)"
    )
    parser.add_argument("--out", help="Output CSV path")
    parser.add_argument("--output", help="Output CSV path (alias for --out)")
    parser.add_argument(
        "--preview", type=int, help="Preview first N rows; no file written"
    )
    parser.add_argument("--debug", action="store_true", help="Verbose debug logging")
    args = parser.parse_args()

    out_path = args.out or args.output
    asyncio.run(scrape(args.url, args.year, out_path, args.preview, args.debug))
