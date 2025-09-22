#!/usr/bin/env python3
import argparse
import asyncio
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

import pandas as pd
from playwright.async_api import async_playwright


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

# Find the closest preceding H3 in the light DOM for a given <table> inside <va-table-inner>'s shadowRoot
JS_FIND_PRECEDING_H3 = """
(tableEl) => {
  // climb out of shadow DOM to the host and then to its <va-table>
  const innerHost = tableEl.getRootNode()?.host || null; // <va-table-inner>
  const vaTable = innerHost ? innerHost.closest('va-table') : null;
  if (!vaTable) return null;

  // Walk previous siblings/ancestors to find the nearest preceding <h3>
  let node = vaTable;
  while (node) {
    // scan previous siblings
    let p = node.previousElementSibling;
    while (p) {
      // prefer the last <h3> found in this sibling (if any)
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
    // climb to parent and continue
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
    # 10–20% table: 2 columns, headers aren't percentages
    return ncols == 2 and not any(re.search(r"\d+\s*%", h) for h in headers)


def _debug_table_log(
    idx: int,
    caption: str,
    category: str,
    headers: List[str],
    body_rows: int,
    section: Optional[Dict[str, Any]],
) -> None:
    headers_str = ", \n\t\t".join([f"'{h}'" for h in headers])
    section_line = ""
    if section:
        section_line = f"\n\tsection_h3_id='{section.get('id', '')}', section_h3_text='{section.get('text', '')}', "
    print(
        f"[DEBUG] Table {idx}: \n"
        f"\tcaption='{caption}', \n"
        f"\tcategory={category},{section_line}\n"
        f"\theaders=[\n\t\t{headers_str}\n\t], \n"
        f"\tbody_rows={body_rows}"
    )


async def _expand_all_accordions(page) -> int:
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
    return clicked


async def _collect_tables(page) -> List:
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
    return tables


async def _text(el) -> str:
    if not el:
        return ""
    return await el.evaluate(JS_GET_DISTRIBUTED_TEXT)


def _dep_group_from_h3_id(h3_id: str) -> Optional[str]:
    id_lower = (h3_id or "").lower()
    if id_lower.startswith("with-a-dependent-spouse-or-par"):
        return "No children"
    if id_lower.startswith("with-dependents-including-chil"):
        return "With children"
    return None  # unknown/none → fall back


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
        expanded = await _expand_all_accordions(page)
        if debug:
            print(f"[DEBUG] Clicked 'Expand all' on {expanded} accordion(s)")

        await page.wait_for_timeout(300)  # let content hydrate
        tables = await _collect_tables(page)

        if debug:
            print(
                f"[DEBUG] Found {len(tables)} table(s) inside va-table-inner (shadow DOM)"
            )

        rows_out = []

        for idx, t in enumerate(tables, start=1):
            caption_el = await t.query_selector("caption")
            caption_text = await _text(caption_el)
            category = (
                "Basic"
                if ("Basic" in caption_text)
                else ("Added" if "Added" in caption_text else None)
            )

            # headers via slotted text
            header_els = await t.query_selector_all("thead tr th")
            headers = [await _text(h) for h in header_els]
            headers = [h.strip() for h in headers]
            ratings_from_headers = _extract_ratings_from_headers(headers)

            # detect nearest preceding H3 to determine Dependent_Group override
            section_meta = await t.evaluate(JS_FIND_PRECEDING_H3)
            dep_group_override = (
                _dep_group_from_h3_id(section_meta["id"]) if section_meta else None
            )

            body_rows = await t.query_selector_all("tbody tr")
            if debug:
                _debug_table_log(
                    idx,
                    caption_text or "",
                    category or "UNKNOWN",
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

            # Special case: 10–20% table (ratings in first column)
            if _looks_like_10_20_table(headers, len(headers)):
                for br in body_rows:
                    cells = await br.query_selector_all("th, td")
                    values = [await _text(c) for c in cells]
                    if len(values) < 2:
                        continue
                    left = values[0]
                    m = re.search(r"(\d+)\s*%", left)
                    if not m:
                        continue
                    rating = int(m.group(1))
                    try:
                        rate = _parse_rate_to_float(values[1])
                    except ValueError:
                        if debug:
                            print(
                                f"[DEBUG] Skipping unparsable rate '{values[1]}' in 10–20 row '{left}'"
                            )
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
                continue  # done with this table

            # General case (ratings appear in header columns 2..N)
            for br in body_rows:
                cells = await br.query_selector_all("th, td")
                values = [await _text(c) for c in cells]
                if not values:
                    continue

                dependent_status = values[0].strip()
                added_item = None

                if category == "Added":
                    added_item = dependent_status
                    dependent_group = dep_group_override or "N/A"
                else:
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

                    header_rating = (
                        ratings_from_headers[col_idx]
                        if col_idx < len(ratings_from_headers)
                        else None
                    )
                    rating = header_rating
                    if rating is None:
                        htxt = headers[col_idx] if col_idx < len(headers) else ""
                        m = re.search(r"(\d+)\s*%", htxt)
                        if m:
                            rating = int(m.group(1))
                    if rating is None:
                        continue

                    try:
                        rate = _parse_rate_to_float(val)
                    except ValueError:
                        if debug:
                            print(
                                f"[DEBUG] Skipping unparsable rate '{val}' (row '{dependent_status}', col {col_idx})"
                            )
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
        raise SystemExit(
            "No rows were scraped. Run again with --debug to see diagnostics."
        )

    df = pd.DataFrame(rows_out)

    if preview is not None and preview > 0:
        print(df.head(preview).to_string(index=False))
        print("[INFO] Preview mode: skipped writing CSV.")
    else:
        if not output_file:
            raise SystemExit(
                "Error: provide --out (or --output), or run with --preview for preview-only mode."
            )
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} rows to {output_file}")


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
        "--preview",
        type=int,
        help="Preview the first N rows in the terminal (no file written)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable verbose debug logging"
    )
    args = parser.parse_args()

    out_path = args.out or args.output
    asyncio.run(scrape(args.url, args.year, out_path, args.preview, args.debug))
