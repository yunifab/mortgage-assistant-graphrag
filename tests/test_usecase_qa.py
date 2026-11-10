"""Checks of the use-case question set (evaluation/ground_truth/qa_usecases_*.json).

Static checks always run: ids, the RAG-format files are up to date with the master, every quote is in the policy
text on the given page, every rule id exists. The engine checks need RDFox and are skipped otherwise: for every
question with a structured case, the rule engine must still give the expected verdict (or amount) and findings.
Run: uv run pytest tests/test_usecase_qa.py
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

from mortgage_assistant.rules import rdfox
from mortgage_assistant.rules.case import Case
from mortgage_assistant.rules.engine import check_case, rule_metadata

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "evaluation" / "ground_truth"
MASTER = json.loads((GT / "qa_usecases_full.json").read_text(encoding="utf-8"))
QUESTIONS = MASTER["questions"]
CASE_QUESTIONS = [q for q in QUESTIONS if q["case"]]


def _norm(text: str) -> str:
    """Compare quotes without whitespace, case, hyphenation, quote marks and bullet marks."""
    return re.sub(r"[\s\-‘’'\"“”•·]", "", text.lower().replace("­", ""))


def _page_texts() -> dict[int, str]:
    pages: dict[int, str] = {}
    for line in open(ROOT / "data" / "processed" / "sections.jsonl", encoding="utf-8"):
        section = json.loads(line)
        for p in section["pages"]:
            pages[p] = pages.get(p, "") + _norm(section.get("text", ""))
    return pages


def test_ids_eight_per_use_case():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids)) == 72
    assert Counter(q["derived_from"] for q in QUESTIONS) == {f"UC{i}": 8 for i in range(1, 10)}
    assert all(q["id"].startswith(q["derived_from"] + "-") for q in QUESTIONS)


def test_rag_files_are_up_to_date_with_the_master():
    sys.path.insert(0, str(ROOT / "scripts"))
    from export_usecase_qa import export

    for lang in ("en", "nl"):
        on_disk = json.loads((GT / f"qa_usecases_{lang}.json").read_text(encoding="utf-8"))
        assert on_disk == export(MASTER, lang), f"run scripts/export_usecase_qa.py ({lang} is out of date)"
        assert set(on_disk["questions"][0]) == {"id", "category", "question", "answer", "evidence", "hop_reasoning"}


def test_every_quote_is_in_the_policy_on_the_given_page():
    pages = _page_texts()
    missing = [(q["id"], e["page"], e["quote"][:60]) for q in QUESTIONS for e in q["evidence"]
               if _norm(e["quote"]) not in pages.get(e["page"], "")]
    assert not missing


def test_answerable_questions_have_evidence_and_known_rules():
    rules = set(rule_metadata())
    for q in QUESTIONS:
        assert set(q["related_rules"]) <= rules, q["id"]
        if q["category"] != "unanswerable":
            assert q["evidence"], q["id"]


@pytest.mark.skipif(not rdfox.is_available(), reason="RDFox is not running (docs/RDFOX_SETUP.md)")
@pytest.mark.parametrize("q", CASE_QUESTIONS, ids=[q["id"] for q in CASE_QUESTIONS])
def test_rule_engine_still_gives_the_expected_outcome(q):
    r = check_case(Case.from_dict(q["case"]))
    if q["expected_verdict"] == "amount":
        assert r.values.get("maxLoan") == q["expected_amount"]
    else:
        assert r.verdict == q["expected_verdict"]
    found = sorted((f.rule, f.status) for f in r.findings if f.status != "ok")
    assert found == sorted((f["rule"], f["status"]) for f in q["expected_findings"])
