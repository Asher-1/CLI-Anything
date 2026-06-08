"""Core tests for cli-anything-web-yu-pri."""

import json

from click.testing import CliRunner
import pytest

from cli_anything.web_yu_pri.core.browser import ADD_ITEM_COMMAND, SELECTORS, build_dry_run, selector_report
from cli_anything.web_yu_pri.core.items import (
    ItemLine,
    build_contents_plan,
    load_items,
    parse_item_mapping,
)
from cli_anything.web_yu_pri.web_yu_pri_cli import cli


def test_parse_item_mapping_aliases():
    item = parse_item_mapping(
        {
            "pkg": "Award plaque",
            "cost": "8,000",
            "num": "2",
            "couCd": "kr",
            "hsCode": "4901.99",
        }
    )
    assert item.description == "Award plaque"
    assert item.value == 8000
    assert item.quantity == 2
    assert item.country == "KR"
    assert item.hs_code == "4901.99"


def test_parse_item_rejects_bad_country():
    with pytest.raises(ValueError, match="country"):
        parse_item_mapping({"description": "x", "value": 1, "country": "KOR"})


def test_load_json_object_payload(tmp_path):
    path = tmp_path / "items.json"
    path.write_text(
        json.dumps({"items": [{"description": "Certificate", "value": 9000}]}),
        encoding="utf-8",
    )
    items = load_items(path, default_country="KR")
    assert items == [ItemLine(description="Certificate", value=9000, quantity=1, country="KR")]


def test_load_csv_aliases(tmp_path):
    path = tmp_path / "items.csv"
    path.write_text("name,amount,qty,origin\nMedal,1000,3,US\n", encoding="utf-8")
    items = load_items(path)
    assert items[0].description == "Medal"
    assert items[0].value == 1000
    assert items[0].quantity == 3
    assert items[0].country == "US"


def test_plan_line_value_mode():
    plan = build_contents_plan(
        [
            ItemLine(description="A", value=8000, quantity=2),
            ItemLine(description="B", value=9000, quantity=1),
        ],
        value_mode="line",
    )
    assert plan["computed_total"] == 17000
    assert plan["items"][0]["line_total"] == 8000


def test_plan_unit_value_mode():
    plan = build_contents_plan(
        [
            ItemLine(description="A", value=4000, quantity=2),
            ItemLine(description="B", value=9000, quantity=1),
        ],
        value_mode="unit",
    )
    assert plan["computed_total"] == 17000
    assert plan["items"][0]["line_total"] == 8000


def test_plan_warns_declared_total_mismatch():
    plan = build_contents_plan([ItemLine(description="A", value=100)], total_value=200)
    assert plan["total_matches"] is False
    assert plan["warnings"]


def test_selector_report_contains_contents_controls():
    report = selector_report()
    assert report["selectors"]["item_description"] == SELECTORS["item_description"]
    assert report["add_item_command"] == ADD_ITEM_COMMAND


def test_build_dry_run_has_safety_metadata():
    dry = build_dry_run([ItemLine(description="A", value=100)])
    assert dry["dry_run"] is True
    assert dry["safety"]["browser_launched"] is False
    assert dry["safety"]["final_submit_clicked"] is False


def test_cli_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "contents" in result.output


def test_cli_plan_json(tmp_path):
    path = tmp_path / "items.json"
    path.write_text(json.dumps([{"description": "A", "value": 100}]), encoding="utf-8")
    result = CliRunner().invoke(cli, ["--json", "plan", str(path)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["computed_total"] == 100


def test_cli_contents_fill_dry_run_json(tmp_path):
    path = tmp_path / "items.json"
    path.write_text(json.dumps([{"description": "A", "value": 100}]), encoding="utf-8")
    result = CliRunner().invoke(cli, ["--json", "contents", "fill", str(path), "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["dry_run"] is True
    assert data["plan"]["declared_total"] == 100
