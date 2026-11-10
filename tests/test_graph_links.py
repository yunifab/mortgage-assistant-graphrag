"""Checks on the rule-based links of the document graph. Run: uv run pytest"""

import pytest

from mortgage_assistant.config import settings
from mortgage_assistant.graph.links import find_links
from mortgage_assistant.ingest import parse_pdf
from mortgage_assistant.ingest.definitions import parse_definitions


@pytest.fixture(scope="module")
def parsed():
    sections = parse_pdf(settings.pdf_path)
    definitions = parse_definitions(settings.pdf_path)
    links = {(l.source, l.type, l.target) for l in find_links(sections, definitions)}
    return sections, definitions, links


def test_definitions_are_split_into_terms(parsed):
    _, definitions, _ = parsed
    terms = {d.term for d in definitions}
    assert len(definitions) == 28
    assert {"AOW-leeftijd", "Marktwaarde", "Niet-actieve materiële onderneming (VPB)"} <= terms
    assert not any(t.startswith("Bijlage") for t in terms)


def test_numbered_references(parsed):
    _, _, links = parsed
    assert ("AB-5.5.7", "REFERS_TO", "AB-5.5.8") in links  # 'Zie dan paragraaf 5.5.8'
    assert ("AB-3.1.3", "REFERS_TO", "AB-3.1.1") in links  # '(3.1.1)'
    assert ("BB-3.1", "REFERS_TO", "BB-2.4.2") in links  # stays inside the Beheerbeleid


def test_cross_part_and_named_references(parsed):
    _, _, links = parsed
    assert ("AB-6.1.1.2", "REFERS_TO", "BB-3") in links  # 'Beheerbeleid, hoofdstuk 3'
    assert ("AB-1.1.3", "REFERS_TO", "BIJ-B2") in links  # 'Zie definitielijst'
    assert ("AB-5.2.1", "REFERS_TO", "BIJ-B1") in links  # 'goedgekeurde erfpachtvoorwaarden'
    assert ("BB-2.4.1", "REFERS_TO", "BB-3") in links  # 'hoofdstuk Life events'


def test_explain_icon_creates_exception_link(parsed):
    sections, _, links = parsed
    assert next(s for s in sections if s.id == "AB-2.4.2").explain_icon
    assert ("AB-2.4.2", "HAS_EXCEPTION", "AB-6") in links


def test_term_usage_respects_word_boundaries(parsed):
    sections, _, links = parsed
    # AB-6.1.1 is about the NIET-annuïtaire test; it must not count as using 'Annuïtaire I/L-toets'
    text = next(s for s in sections if s.id == "AB-6.1.1").text.lower()
    assert "niet-annuïtaire i/l-toets" in text
    uses_annuitair = ("AB-6.1.1", "USES_TERM", "DEF-annuïtaire-i-l-toets") in links
    plain_mentions = text.replace("niet-annuïtaire i/l-toets", "").count("annuïtaire i/l-toets")
    assert uses_annuitair == (plain_mentions > 0)


def test_document_requirements_follow_the_chapter(parsed):
    _, _, links = parsed
    targets = {t for s, r, t in links if s == "AB-3.1.1" and r == "REQUIRES_DOCUMENTS"}
    assert len(targets) == 1
