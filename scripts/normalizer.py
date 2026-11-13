import re
from typing import Any, Dict, Optional

import pandas as pd


def parse_rate_to_float(s: str) -> float:
    """Clean and parse a rate string (e.g. '$3,100.00') to float."""
    clean = s.replace("$", "").replace(",", "").replace("\u00a0", " ").strip()
    return float(clean)


def normalize_status_text(status: str) -> str:
    """Normalize status text for easier regex matching."""
    text = re.sub(r"[^a-z0-9\s]", " ", (status or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def has_negated_term(text: str, term_pattern: str) -> bool:
    """Check if a term is present but negated (e.g. 'no spouse')."""
    pattern = rf"(?:no|without)\s+(?:[a-z]+\s+){{0,3}}{term_pattern}"
    return bool(re.search(pattern, text))


def infer_basic_dependents(status: str) -> Dict[str, Any]:
    """
    Infer Has_Spouse / Parent_Count / Has_Child structure from a description string.
    """
    normalized = normalize_status_text(status)

    has_spouse = False
    if "spouse" in normalized and not has_negated_term(normalized, r"spouse"):
        has_spouse = True

    parent_count = 0
    if "parent" in normalized:
        if not has_negated_term(normalized, r"parents?"):
            if (
                re.search(r"\b(2|two)\s+(?:dependent\s+)?parents?\b", normalized)
                or "both parents" in normalized
            ):
                parent_count = 2
            elif re.search(r"\b(1|one)\s+(?:dependent\s+)?parent\b", normalized):
                parent_count = 1
            elif "parents" in normalized:
                parent_count = 2
            else:
                parent_count = 1

    has_child = False
    if re.search(r"\bchild(?:ren)?\b", normalized) and not has_negated_term(
        normalized, r"child(?:ren)?"
    ):
        if re.search(r"with\s+(?:one|two|three|\d+)?\s*child", normalized):
            has_child = True
        elif re.search(r"child\s+only", normalized):
            has_child = True
        elif re.search(r"with\s+children", normalized):
            has_child = True
        else:
            has_child = True

    return {
        "Has_Spouse": has_spouse,
        "Parent_Count": parent_count,
        "Has_Child": has_child,
    }


def dep_group_from_heading(heading_id: str, heading_text: str) -> Optional[str]:
    """Identify a section's dependent group, including headings without IDs."""
    id_lower = (heading_id or "").lower()
    if id_lower.startswith("with-a-dependent-spouse-or-par"):
        return "No children"
    if id_lower.startswith("with-dependents-including-chil"):
        return "With children"
    text = normalize_status_text(heading_text)
    if "no children" in text:
        return "No children"
    if "including children" in text:
        return "With children"
    return None


def normalize_rows(rows: list[Dict[str, Any]]) -> tuple[pd.DataFrame, int]:
    """Deduplicate scraped rows and enrich Basic rows with dependent flags."""
    df = pd.DataFrame(rows)
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

    df["Has_Spouse"] = pd.NA
    df["Parent_Count"] = pd.NA
    df["Has_Child"] = pd.NA

    basic_mask = df["Category"] == "Basic"
    if basic_mask.any():
        inferred = df.loc[basic_mask, "Dependent_Status"].apply(infer_basic_dependents)
        inferred_df = pd.DataFrame(list(inferred), index=df.index[basic_mask])
        df.loc[basic_mask, ["Has_Spouse", "Parent_Count", "Has_Child"]] = inferred_df

    df["Has_Spouse"] = df["Has_Spouse"].astype("boolean")
    df["Has_Child"] = df["Has_Child"].astype("boolean")
    df["Parent_Count"] = df["Parent_Count"].astype("Int64")
    return df, before - len(df)
