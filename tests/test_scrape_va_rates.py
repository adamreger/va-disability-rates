import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
from frictionless import Resource, Schema, validate
from playwright.async_api import Error as PlaywrightError

from scripts import scrape_va_rates as scraper
from scripts.normalizer import (
    dep_group_from_heading,
    infer_basic_dependents,
    normalize_rows,
)
from scripts.parser import looks_like_10_20_table

SOURCE_URL = "https://example.com/rates/"
SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "rates_schema.json"


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
    result = infer_basic_dependents(status)
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
    result = infer_basic_dependents(status)
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
    result, duplicates_removed = normalize_rows(rows)
    assert duplicates_removed == 0

    assert result.loc[0, "Has_Spouse"]
    assert result.loc[0, "Parent_Count"] == 1
    assert not result.loc[0, "Has_Child"]

    assert pd.isna(result.loc[1, "Has_Spouse"])
    assert pd.isna(result.loc[1, "Parent_Count"])
    assert pd.isna(result.loc[1, "Has_Child"])
    assert str(result["Has_Spouse"].dtype) == "boolean"
    assert str(result["Has_Child"].dtype) == "boolean"
    assert str(result["Parent_Count"].dtype) == "Int64"


@pytest.mark.parametrize(
    "headers, expected",
    [
        (["Disability rating", "Monthly payment"], True),
        (["Dependent status", "30%"], False),
        (["Dependent status", "30 %"], False),
        (["Dependent status", "30%", "40%"], False),
    ],
)
def test_parser_looks_like_10_20(headers, expected):
    assert looks_like_10_20_table(headers, len(headers)) is expected


@pytest.mark.parametrize(
    "heading_id, text, expected",
    [
        ("with-a-dependent-spouse-or-parent", "", "No children"),
        ("with-dependents-including-children", "", "With children"),
        ("", "With a dependent spouse or parent, but no children", "No children"),
        ("", "With dependents, including children", "With children"),
        ("", "", None),
    ],
)
def test_dependent_group_from_heading(heading_id, text, expected):
    assert dep_group_from_heading(heading_id, text) == expected


@pytest.fixture
def browser_session(monkeypatch):
    """Replace browser I/O while exercising extraction and file generation."""
    installer = Mock()
    monkeypatch.setattr(scraper, "ensure_playwright_browsers", installer)
    page = AsyncMock()
    effective_date = Mock()
    effective_date.count = AsyncMock(return_value=1)
    effective_date.first.inner_text = AsyncMock(
        return_value="Effective December 1, 2025"
    )
    page.locator = Mock(return_value=effective_date)
    browser = AsyncMock()
    browser.new_page.return_value = page
    context = AsyncMock()
    context.__aenter__.return_value.chromium.launch = AsyncMock(return_value=browser)
    monkeypatch.setattr(scraper, "async_playwright", Mock(return_value=context))
    return page, browser, installer


def table_handle(headers, rows, caption="", section=None):
    def cell(text):
        return Mock(evaluate=AsyncMock(return_value=text))

    table = Mock()
    table.query_selector = AsyncMock(return_value=cell(caption) if caption else None)
    selectors = {
        "thead tr th": [cell(text) for text in headers],
        "tbody tr": [
            Mock(
                query_selector_all=AsyncMock(return_value=[cell(text) for text in row])
            )
            for row in rows
        ],
    }
    table.query_selector_all = AsyncMock(
        side_effect=lambda selector: selectors[selector]
    )
    table.evaluate = AsyncMock(return_value=section)
    handle = Mock()
    handle.as_element.return_value = table
    return Mock(evaluate_handle=AsyncMock(return_value=handle))


@pytest.fixture
def representative_page(browser_session):
    page, browser, installer = browser_session
    tables = [
        table_handle(
            ["Disability rating", "Monthly payment"],
            [["10%", "$180.42"], ["20%", "$356.66"]],
        ),
        table_handle(
            ["Dependent status", "30%"],
            [
                ["With spouse and 1 parent (no children)", "$680.00"],
                ["With spouse and 1 parent (no children)", "$680.00"],
            ],
            "Basic monthly rates",
            {"id": "", "text": "With a dependent spouse or parent, but no children"},
        ),
        table_handle(
            ["Dependent status", "30%", "40%"],
            [["Veteran with child only (no spouse or parents)", "$600.00", "$850.00"]],
            "Basic monthly rates",
            {"id": "", "text": "With dependents, including children"},
        ),
        table_handle(
            ["Added amounts", "30%", "40%"],
            [["Each additional schoolchild", "$1,100.00", "$1,200.00"]],
            "Added amounts",
        ),
    ]
    page.query_selector_all.side_effect = lambda selector: (
        tables if selector == "va-table-inner.hydrated" else []
    )
    return page, browser, installer


@pytest.mark.parametrize("output_flag", ["--out", "--output"])
def test_scrape_writes_normalized_csv_and_preserves_readme_notes(
    representative_page, tmp_path, capsys, output_flag
):
    output = tmp_path / "2026" / "rates_normalized.csv"
    output.parent.mkdir()
    readme = output.with_name("README.md")
    readme.write_text(
        "## General Notes\n- Reviewed manually.\n\n## Other\n- Unrelated bullet.\n"
    )
    assert (
        scraper.main(
            [
                "--url",
                SOURCE_URL,
                "--year",
                "2026",
                output_flag,
                str(output),
                "--write-readme",
                "--debug",
            ]
        )
        == 0
    )

    df = pd.read_csv(output)
    assert len(df) == 7
    assert df["Year"].unique().tolist() == [2026]
    assert df["Rating"].tolist() == [10, 20, 30, 30, 40, 30, 40]
    assert df["Monthly_Rate_USD"].tolist() == [
        180.42,
        356.66,
        680,
        600,
        850,
        1100,
        1200,
    ]
    assert df.loc[2, "Dependent_Group"] == "No children"
    assert df.loc[2, "Has_Spouse"]
    assert df.loc[2, "Parent_Count"] == 1
    assert not df.loc[2, "Has_Child"]
    assert df.loc[3, "Dependent_Group"] == "With children"
    assert df.loc[3, "Has_Child"]
    assert not df.loc[3, "Has_Spouse"]
    added = df[df["Category"] == "Added"]
    assert added["Added_Item"].tolist() == ["Each additional schoolchild"] * 2
    assert (
        added[
            [
                "Dependent_Group",
                "Dependent_Status",
                "Has_Spouse",
                "Parent_Count",
                "Has_Child",
            ]
        ]
        .isna()
        .all()
        .all()
    )
    report = validate(
        Resource(
            path=output.name,
            basepath=str(output.parent),
            schema=Schema.from_descriptor(json.loads(SCHEMA.read_text())),
        )
    )
    assert report.valid, report.flatten(["type", "message"])

    text = readme.read_text()
    assert "Effective Dec 1, 2025 for 2026 rates" in text
    assert f"- Source: {SOURCE_URL}" in text
    assert "- Total rows: 7" in text
    assert "Duplicates removed during normalization: 1" in text
    assert hashlib.sha256(output.read_bytes()).hexdigest() in text
    assert "- Reviewed manually." in text
    assert "Unrelated bullet" not in text
    assert "Deduplication removed 1 duplicate rows" in capsys.readouterr().out
    page, browser, _ = representative_page
    page.goto.assert_awaited_once_with(SOURCE_URL, wait_until="networkidle")
    browser.close.assert_awaited_once()


@pytest.mark.parametrize("with_output", [False, True])
def test_preview_writes_no_files(representative_page, tmp_path, capsys, with_output):
    args = ["--url", SOURCE_URL, "--year", "2026", "--preview", "2"]
    output = tmp_path / "rates.csv"
    readme = tmp_path / "README.md"
    if with_output:
        output.write_text("existing CSV\n")
        readme.write_text("existing README\n")
        args.extend(["--out", str(output), "--write-readme"])
    assert scraper.main(args) == 0
    assert "Preview mode" in capsys.readouterr().out
    if with_output:
        assert output.read_text() == "existing CSV\n"
        assert readme.read_text() == "existing README\n"
    else:
        assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "args, message",
    [
        (["--year", "2024-2026", "--preview", "1"], "invalid int value"),
        (["--year", "invalid", "--preview", "1"], "invalid int value"),
        (["--year", "2026"], "provide --out/--output or run with --preview"),
        (["--year", "2026", "--preview", "0"], "positive integer"),
        (["--year", "2026", "--preview", "-1"], "positive integer"),
        (
            ["--year", "2026", "--preview", "1", "--write-readme"],
            "--write-readme requires",
        ),
    ],
)
def test_invalid_arguments_fail_before_starting_browser(
    browser_session, capsys, args, message
):
    with pytest.raises(SystemExit) as exc:
        scraper.main(["--url", SOURCE_URL, *args])
    assert exc.value.code == 2
    assert message in capsys.readouterr().err
    page, browser, installer = browser_session
    installer.assert_not_called()
    browser.new_page.assert_not_awaited()


@pytest.mark.parametrize("navigation_error", [False, True])
def test_scrape_failure_returns_nonzero_and_closes_browser(
    browser_session, tmp_path, capsys, navigation_error
):
    page, browser, _ = browser_session
    page.query_selector_all.return_value = []
    if navigation_error:
        page.goto.side_effect = PlaywrightError("Navigation failed")
    output = tmp_path / "rates.csv"
    assert (
        scraper.main(["--url", SOURCE_URL, "--year", "2026", "--out", str(output)]) == 1
    )
    assert not output.exists()
    assert not output.with_name("README.md").exists()
    assert (
        "Navigation failed" if navigation_error else "No rows were scraped"
    ) in capsys.readouterr().err
    browser.close.assert_awaited_once()
