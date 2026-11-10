"""Tests of the ontology + Datalog rules (needs RDFox running; skipped otherwise). Run: uv run pytest

Every use case (UC1-UC9) and held-out case (HO1-HO8) is checked against the expected verdict and
the rules that must (and must not) fire. These tests are the 'unit tests of the policy': if a rule is
changed, they show at once which cases change.
"""

import json
from pathlib import Path

import pytest

from mortgage_assistant.rules import rdfox
from mortgage_assistant.rules.case import Case
from mortgage_assistant.rules.engine import check_case, rule_metadata

HERE = Path(__file__).resolve().parents[1] / "evaluation" / "use_cases"
pytestmark = pytest.mark.skipif(not rdfox.is_available(), reason="RDFox is not running (docs/RDFOX_SETUP.md)")

UC_FACTS = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
HOLDOUT = json.loads((HERE / "holdout.json").read_text(encoding="utf-8"))["cases"]

# (case, expected verdict, rules that must be violated / need Explain, rules that must NOT be violated)
EXPECTATIONS = [
    ("UC1", "reject", {"R_MaxLoan", "R_InterestOnlyType", "R_HouseboatLifetime", "R_MooringTerm"}, set()),
    ("UC2", "reject", {"R_InterestOnlyCap"}, {"R_MaxLoan"}),
    ("UC3", "reject", {"R_MaxLoan"}, set()),
    ("UC4", "accept", set(), {"R_MaxLoan"}),
    ("UC5", "reject", {"R_ExplainCombination"}, set()),
    ("UC6", "reject", {"R_DiplomatCountry", "R_DiplomatRepeat"}, {"R_DiplomatDuration"}),
    ("UC7", "reject", {"R_MinAge", "R_Debtors"}, {"R_InterestOnlyCap", "R_InterestOnlyType", "R_MaxLoan", "R_MaxTerm"}),
    ("UC8", "reject", {"R_InterestOnlyType", "R_RecreationPermanent"}, {"R_MaxLoan"}),
    ("UC9", "explain", {"R_RRR"}, {"R_MaxLoan", "R_MaxTerm"}),
]


def _problems(result) -> set[str]:
    return {f.rule for f in result.findings if f.status in ("violated", "needs_explain")}


@pytest.mark.parametrize("cid,verdict,must,must_not", EXPECTATIONS)
def test_use_cases(cid, verdict, must, must_not):
    result = check_case(Case.from_dict(UC_FACTS[cid]))
    assert result.verdict == verdict
    assert must <= _problems(result), f"missing: {must - _problems(result)}"
    assert not (must_not & _problems(result)), f"false: {must_not & _problems(result)}"


@pytest.mark.parametrize("cid", sorted(HOLDOUT))
def test_holdout_verdicts(cid):
    expected = HOLDOUT[cid]["expected"]["verdict"]
    result = check_case(Case.from_dict(HOLDOUT[cid]["facts"]))
    # 'amount' questions have no violation; the engine then says accept (and gives the amount)
    assert result.verdict == ("accept" if expected == "amount" else expected)


def test_computed_amounts():
    assert check_case(Case.from_dict(UC_FACTS["UC1"])).values["maxLoan"] == 315000  # 90% boat + 90% mooring
    assert check_case(Case.from_dict(UC_FACTS["UC2"])).values["interestOnlyTotal"] == 300000  # incl. unpledged savings
    assert check_case(Case.from_dict(UC_FACTS["UC3"])).values["maxLoanWithValuationReport"] == 400000
    assert check_case(Case.from_dict(UC_FACTS["UC4"])).values["maxLoan"] == 325000  # energy rule
    assert check_case(Case.from_dict(HOLDOUT["HO4"]["facts"])).values["maxLoan"] == 225000  # no 106% at 90% norm


def test_missing_facts_are_reported_not_guessed():
    result = check_case(Case.from_dict(UC_FACTS["UC9"]))
    missing = {f.rule for f in result.findings if f.status == "missing_fact"}
    assert {"R_HouseboatLifetime", "R_HouseboatShore", "R_ValuationKnown"} <= missing


def test_pledged_savings_part_is_not_interest_only():
    facts = json.loads(json.dumps(UC_FACTS["UC2"]))
    facts["loan"]["parts"][1]["pledged"] = True
    result = check_case(Case.from_dict(facts))
    assert result.values["interestOnlyTotal"] == 100000
    assert "R_InterestOnlyCap" not in _problems(result)


def test_every_rule_has_a_source_section_in_the_document_graph():
    sections = {json.loads(line)["id"] for line in
                open(HERE.parents[1] / "data" / "processed" / "sections.jsonl", encoding="utf-8")}
    for rule, meta in rule_metadata().items():
        assert meta["source"] in sections, f"{rule}: unknown section {meta['source']}"
