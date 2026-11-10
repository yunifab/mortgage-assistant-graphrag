"""Tests of the collateral taxonomy (ontology/taxonomy_collateral.ttl + rules/35_taxonomy.dlog).
Needs RDFox running; skipped otherwise. Run: uv run pytest tests/test_taxonomy.py

Each test is a small case that exercises one part of the taxonomy: inheritance from a parent class,
combining dimensions (building type + use + construction + legal right), and limits stored as data.
"""

import json
from pathlib import Path

import pytest
from rdflib.namespace import RDFS

from mortgage_assistant.rules import rdfox
from mortgage_assistant.rules.case import COLLATERAL_TYPES, Case
from mortgage_assistant.rules.engine import RABO, check_case, ontology_graph

pytestmark = pytest.mark.skipif(not rdfox.is_available(), reason="RDFox is not running (docs/RDFOX_SETUP.md)")
SECTIONS = {json.loads(line)["id"] for line in
            open(Path(__file__).resolve().parents[1] / "data" / "processed" / "sections.jsonl", encoding="utf-8")}


def check(collateral: dict, loan: dict | None = None, **app) -> tuple[set[str], set[str], dict]:
    case = Case.from_dict({"collateral": collateral, "loan": loan or {}, **app})
    r = check_case(case)
    violated = {f.rule for f in r.findings if f.status == "violated"}
    missing = {f.rule for f in r.findings if f.status == "missing_fact"}
    return violated, missing, r.values


def test_lowest_norm_wins_when_a_regular_house_is_partly_let():
    violated, _, v = check({"type": "regular_house", "market_value": 400000, "valuation": "valuation_report",
                            "partly_let": True}, {"amount": 350000, "term_years": 30}, conditions="plus")
    assert v["maxLoan"] == 340000  # 85% (letting) beats 100% (regular house)
    assert "R_MaxLoan" in violated


def test_letting_needs_a_valuation_report_even_for_a_regular_house():
    violated, _, _ = check({"type": "regular_house", "market_value": 400000, "valuation": "desktop",
                            "partly_let": True}, {"amount": 300000, "term_years": 30}, conditions="plus")
    assert "R_ValuationMethod" in violated  # allowed for 'regular house', not for 'partly let'


def test_letting_is_not_possible_for_a_houseboat():
    violated, _, _ = check({"type": "houseboat", "market_value": 200000, "valuation": "emci", "partly_let": True})
    assert "R_LettingType" in violated


def test_home_with_shop_has_a_separate_norm_for_the_business_part():
    _, _, v = check({"type": "shop_house", "market_value": 300000, "business_part_value": 100000,
                     "valuation": "valuation_report"}, {"amount": 370000, "term_years": 30})
    assert v["maxLoan"] == 380000  # 100% of the dwelling + 80% of the shop


def test_business_dwelling_inherits_norm_and_interest_only_ban_from_its_parent_class():
    violated, _, v = check({"type": "business_dwelling_mixed_use", "market_value": 500000,
                            "valuation": "business_valuation"},
                           {"amount": 420000, "term_years": 30, "parts": [{"type": "interest_only", "amount": 50000}]})
    assert v["maxLoan"] == 400000  # the 80% norm is defined on the parent 'BusinessDwelling'
    assert {"R_MaxLoan", "R_InterestOnlyType"} <= violated


def test_agricultural_farmhouse_above_3_hectares():
    violated, _, _ = check({"type": "farmhouse_agricultural", "market_value": 600000, "valuation": "lav",
                            "area_hectares": 4})
    assert "R_FarmArea" in violated


def test_generic_report_for_agricultural_farmhouse_is_a_missing_fact_not_a_violation():
    violated, missing, _ = check({"type": "farmhouse_agricultural", "market_value": 600000,
                                  "valuation": "valuation_report", "area_hectares": 2})
    assert "R_ValuationMethod" in missing and "R_ValuationMethod" not in violated


def test_mobile_home_only_with_nhg():
    violated, _, _ = check({"type": "mobile_home", "market_value": 150000, "valuation": "valuation_report"},
                           {"amount": 140000, "term_years": 30}, nhg=False)
    assert "R_RequiresNHG" in violated
    violated, missing, _ = check({"type": "mobile_home", "market_value": 150000, "valuation": "valuation_report"},
                                 {"amount": 140000, "term_years": 30})
    assert "R_RequiresNHG" in missing


def test_garage_box_term_conditions_and_own_home():
    violated, missing, _ = check({"type": "standalone_garage", "market_value": 30000, "valuation": "nrvt"},
                                 {"amount": 25000, "term_years": 25}, conditions="basis")
    assert {"R_TypeMaxTerm", "R_RequiredConditions"} <= violated  # max 20 years, Plus only
    assert "R_OwnHomeAtRabobank" in missing


def test_construction_costs_only_for_suitable_new_builds():
    violated, _, _ = check({"type": "regular_house", "market_value": 400000, "valuation": "construction_costs",
                            "new_build": "self_build"}, {"amount": 380000, "term_years": 30})
    assert "R_ConstructionCosts" in violated  # self-build needs a valuation report
    violated, _, _ = check({"type": "regular_house", "market_value": 400000, "valuation": "construction_costs",
                            "new_build": "project"}, {"amount": 380000, "term_years": 30})
    assert "R_ConstructionCosts" not in violated
    violated, _, _ = check({"type": "regular_house", "market_value": 400000, "valuation": "construction_costs"},
                           {"amount": 380000, "term_years": 30})
    assert "R_ConstructionCosts" in violated  # not a new build


def test_desktop_valuation_excluded_by_other_dimensions():
    for extra in ({"legal_right": "erfpacht"}, {"new_build": "project"}, {"market_value": 1200000}):
        collateral = {"type": "regular_house", "market_value": 400000, "valuation": "desktop_plus", **extra}
        violated, _, _ = check(collateral, {"amount": 300000, "term_years": 30})
        assert "R_DesktopConditions" in violated, extra
    violated, _, _ = check({"type": "regular_house", "market_value": 400000, "valuation": "desktop_plus",
                            "legal_right": "opstal_utility"}, {"amount": 300000, "term_years": 30})
    assert "R_DesktopConditions" not in violated  # opstal for a utility is the exception


def test_erfpacht_review_unless_approved_municipal_conditions():
    _, missing, _ = check({"type": "apartment", "market_value": 300000, "valuation": "valuation_report",
                           "legal_right": "erfpacht"})
    assert "R_ErfpachtReview" in missing
    _, missing, _ = check({"type": "apartment", "market_value": 300000, "valuation": "valuation_report",
                           "legal_right": "erfpacht", "erfpacht_approved_municipal": True})
    assert "R_ErfpachtReview" not in missing


def test_every_building_type_has_a_section_and_an_ltv_norm():
    g = ontology_graph()
    normed = set(g.objects(None, RABO.forCollateral))
    for key, cls in COLLATERAL_TYPES.items():
        ancestors = set(g.transitive_objects(cls, RDFS.subClassOf))  # includes the class itself
        sections = {str(s) for a in ancestors for s in g.objects(a, RABO.definedIn)}
        assert sections and sections <= SECTIONS, f"{key}: section {sections}"
        assert ancestors & normed, f"{key}: no LTV norm on the class or a parent"


def test_what_if_valuation_report_keeps_the_other_norms():
    # A partly let house valued with a desktop valuation: a full report would allow 100% for the house,
    # but the 85% letting norm still applies, so the what-if maximum is 85%, not 100%.
    _, _, v = check({"type": "regular_house", "market_value": 400000, "valuation": "desktop_plus",
                     "partly_let": True}, {"amount": 330000, "term_years": 30}, conditions="plus")
    assert v["maxLoanWithValuationReport"] == 340000
