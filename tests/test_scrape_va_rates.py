import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

# Stub the playwright import used by the scraper so we can load the module without the dependency
playwright_module = types.ModuleType("playwright")
async_api_module = types.ModuleType("async_api")
setattr(async_api_module, "async_playwright", object())  # placeholder
setattr(playwright_module, "async_api", async_api_module)
sys.modules.setdefault("playwright", playwright_module)
sys.modules.setdefault("playwright.async_api", async_api_module)

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scrape_va_rates.py"
SPEC = importlib.util.spec_from_file_location("scrape_va_rates", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load scrape_va_rates module spec")
svr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(svr)  # type: ignore[misc]


@pytest.mark.parametrize(
    "status, expected",
    [
        (
            "With spouse (no parents or children)",
            {"Has_Spouse": True, "Parent_Count": 0, "Has_Child": False},
        ),
        (
            "With spouse and 1 parent (no children)",
            {"Has_Spouse": True, "Parent_Count": 1, "Has_Child": False},
        ),
        (
            "With spouse and 2 parents (no children)",
            {"Has_Spouse": True, "Parent_Count": 2, "Has_Child": False},
        ),
        (
            "VetERan alone (no dependents)",
            {"Has_Spouse": False, "Parent_Count": 0, "Has_Child": False},
        ),
        (
            "Veteran with child only (no spouse or parents)",
            {"Has_Spouse": False, "Parent_Count": 0, "Has_Child": True},
        ),
        (
            "With 1 child, spouse, and 1 parent",
            {"Has_Spouse": True, "Parent_Count": 1, "Has_Child": True},
        ),
    ],
)
def test_infer_basic_dependents_variants(status, expected):
    result = svr._infer_basic_dependents(status)
    assert result["Has_Spouse"] == expected["Has_Spouse"]
    assert result["Parent_Count"] == expected["Parent_Count"]
    assert result["Has_Child"] == expected["Has_Child"]


@pytest.mark.parametrize(
    "status",
    [
        "With 1 parent (no spouse or children)",
        "With 2 parents (no spouse or children)",
        "Without spouse, with one parent",
    ],
)
def test_infer_basic_dependents_handles_negations(status):
    result = svr._infer_basic_dependents(status)
    assert result["Has_Spouse"] is False
    assert result["Has_Child"] is False


def test_dataframe_enrichment_assigns_only_basic_rows():
    rows = [
        {
            "Year": 2024,
            "Rating": 70,
            "Dependent_Group": "No children",
            "Dependent_Status": "With spouse and 1 parent (no children)",
            "Category": "Basic",
            "Added_Item": None,
            "Monthly_Rate_USD": 1737.20,
        },
        {
            "Year": 2024,
            "Rating": 70,
            "Dependent_Group": "",
            "Dependent_Status": "",
            "Category": "Added",
            "Added_Item": "Aid and attendance",
            "Monthly_Rate_USD": 150.00,
        },
    ]
    df = pd.DataFrame(rows)

    result = df.copy()
    result["Has_Spouse"] = pd.NA
    result["Parent_Count"] = pd.NA
    result["Has_Child"] = pd.NA

    mask = result["Category"] == "Basic"
    inferred = result.loc[mask, "Dependent_Status"].apply(svr._infer_basic_dependents)
    inferred_df = pd.DataFrame(list(inferred), index=result.index[mask])
    result.loc[mask, ["Has_Spouse", "Parent_Count", "Has_Child"]] = inferred_df

    result["Has_Spouse"] = result["Has_Spouse"].astype("boolean")
    result["Has_Child"] = result["Has_Child"].astype("boolean")
    result["Parent_Count"] = result["Parent_Count"].astype("Int64")

    assert result.loc[0, "Has_Spouse"]
    assert result.loc[0, "Parent_Count"] == 1
    assert not result.loc[0, "Has_Child"]

    assert pd.isna(result.loc[1, "Has_Spouse"])
    assert pd.isna(result.loc[1, "Parent_Count"])
    assert pd.isna(result.loc[1, "Has_Child"])

    assert str(result["Has_Spouse"].dtype) == "boolean"
    assert str(result["Has_Child"].dtype) == "boolean"
    assert str(result["Parent_Count"].dtype) == "Int64"
