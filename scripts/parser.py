import re
from datetime import datetime
from typing import List, Optional

# JavaScript evaluated inside the browser to read VA web components.

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


def extract_ratings_from_headers(headers: List[str]) -> List[Optional[int]]:
    """Extract percentage ratings (10, 20, etc.) from header strings."""
    ratings: List[Optional[int]] = []
    for h in headers:
        m = re.search(r"(\d+)\s*%", h)
        ratings.append(int(m.group(1)) if m else None)
    return ratings


def looks_like_10_20_table(headers: List[str], ncols: int) -> bool:
    """Check if table appears to be the 10-20% specific table."""
    # 10–20% table has exactly two columns, and headers are not percentages
    return ncols == 2 and not any(re.search(r"\d+\s*%", h) for h in headers)


def format_effective_line(raw_text: Optional[str], rates_year: int) -> str:
    """Format the effective date line for the README."""
    if not raw_text:
        return f"Effective date: Unknown (see source) for {rates_year} rates"

    match = re.search(
        r"Effective\s+([A-Za-z]+)\s+(\d{1,2})(?:,)?\s+(\d{4})",
        raw_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return f"{raw_text.strip()} for {rates_year} rates"

    month_name, day_str, year_str = match.groups()
    try:
        parsed = datetime.strptime(f"{month_name} {day_str} {year_str}", "%B %d %Y")
    except ValueError:
        return f"{raw_text.strip()} for {rates_year} rates"

    month_abbr = parsed.strftime("%b")
    return f"Effective {month_abbr} {parsed.day}, {parsed.year} for {rates_year} rates"
