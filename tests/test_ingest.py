"""Checks on the parsed policy. Run: uv run pytest"""

import re

import pytest

from mortgage_assistant.config import settings
from mortgage_assistant.ingest import chunk_sections, parse_pdf
from mortgage_assistant.ingest.chunker import _split_text


@pytest.fixture(scope="module")
def sections():
    return parse_pdf(settings.pdf_path)


def test_known_sections_found_with_title_and_page(sections):
    by_id = {s.id: s for s in sections}
    assert by_id["AB-1.1"].title == "Algemene regels"
    assert by_id["AB-5.5.12"].title == "Woonboot met vaste ligplaats"
    assert 31 in by_id["AB-5.5.12"].pages
    assert by_id["BB-4.1.1"].title == "Verhuur op basis van de diplomatenclausule"
    assert by_id["BIJ-B2"].title.startswith("Bijlage 2")


def test_sections_are_in_document_order(sections):
    numbers = [s.number for s in sections if s.id.startswith("AB-") and s.number[:1].isdigit()]
    as_tuples = [tuple(int(p) for p in n.split(".")) for n in numbers]
    assert as_tuples == sorted(as_tuples)


def test_every_section_has_a_parent_in_the_same_part(sections):
    ids = {s.id for s in sections}
    for s in sections:
        if s.level > 1:
            assert s.parent_id in ids, s.id


def test_no_navigation_bar_or_footnote_markers_in_titles(sections):
    for s in sections:
        assert "Documentenlijst 6. Explain" not in s.text
        # a footnote marker glued to the last word, like 'Aflossingsvrij lenen31' or '(IBL)9'
        assert not re.search(r"[a-z)]\d+$", s.title), s.title


def test_known_rule_text_is_present(sections):
    text = {s.id: s.text for s in sections}
    assert "De looptijd van een lening is maximaal 30 jaar." in text["AB-1.1"]
    assert "minimaal 18 jaar" in text["AB-2.1"]


def test_chunks_stay_within_size_and_section(sections):
    chunks = chunk_sections(sections, max_chars=1500, overlap=200)
    assert all(len(c.text) <= 1500 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)
    assert all(c.section_id in {s.id for s in sections} for c in chunks)


def test_split_text_overlaps():
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(60))
    pieces = _split_text(text, max_chars=500, overlap=100)
    assert len(pieces) > 1
    assert all(len(p) <= 600 for p in pieces)
    # the start of each next piece repeats the end of the previous one
    assert pieces[1][:20] in pieces[0]
