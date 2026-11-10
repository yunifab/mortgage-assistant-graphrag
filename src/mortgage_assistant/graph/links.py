"""Find the links between parts of the policy, with simple rules (no LLM).

Link types (all point FROM the section where the link is written):

  REFERS_TO           an explicit reference in the text
                      '(3.1.1)', 'zie paragraaf 5.5.8', 'zie definitielijst',
                      'hoofdstuk Onderpand en waardebepaling', 'Beheerbeleid, hoofdstuk 3'
  HAS_EXCEPTION       the section shows the 🔍 icon or says 'zie hoofdstuk Explain':
                      an exception or tailor-made solution may exist in chapter 6.
                      (WHICH Explain section is decided later, by similarity, in the loader.)
  USES_TERM           the section uses a term from the definitions list (Bijlage 2)
  REQUIRES_DOCUMENTS  the part of the document checklist (Bijlage 3) for the section's chapter

Every link keeps an 'evidence' string (the text that triggered it), so each link can be checked.
"""

import re
from dataclasses import dataclass

from mortgage_assistant.models import Definition, Section

EXPLAIN_CHAPTER = "AB-6"
NAMED_TARGETS = [  # (pattern, target section id)
    (r"definitielijst", "BIJ-B2"),
    (r"documentenlijst", "BIJ-B3"),
    (r"goedgekeurde erfpachtvoorwaarden", "BIJ-B1"),
]
# Terms that appear almost everywhere: linking them adds noise, not information
MAX_SECTIONS_PER_TERM = 25


@dataclass(frozen=True)
class Link:
    source: str  # section id
    type: str
    target: str  # section id or definition id
    evidence: str


def _snippet(text: str, start: int, end: int, pad: int = 40) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - pad):end + pad]).strip()


def _part_code(section_id: str) -> str:
    return section_id.split("-", 1)[0]


def _target_part(source: Section, text: str, pos: int) -> str:
    """Which part a reference points to: its own part, unless the text names the other one."""
    window = text[max(0, pos - 40):pos + 60].lower()
    code = _part_code(source.id)
    if code != "AB" and "acceptatiebeleid" in window:
        return "AB"
    if code != "BB" and "beheerbeleid" in window:
        return "BB"
    return code if code in ("AB", "BB") else "AB"


def numbered_references(sections: list[Section]) -> list[Link]:
    """'(3.1.1)', 'paragraaf 5.5.8', 'hoofdstuk 4', 'Beheerbeleid, hoofdstuk 3' -> REFERS_TO."""
    ids = {s.id for s in sections}
    links = []
    for s in sections:
        if s.part == "Versiebeheer":
            continue  # the version history lists changed sections; that is not a reference
        for m in re.finditer(r"(?<![\d.,€])(\d+\.\d+(?:\.\d+){0,2})(?![\d,]|\.\d)", s.text):
            target = f"{_target_part(s, s.text, m.start())}-{m.group(1)}"
            if target in ids and target != s.id:
                links.append(Link(s.id, "REFERS_TO", target, _snippet(s.text, m.start(), m.end())))
        for m in re.finditer(r"(?i)hoofdstuk\s+(\d)\b", s.text):
            target = f"{_target_part(s, s.text, m.start())}-{m.group(1)}"
            if target in ids and target != s.id and not s.id.startswith(target + "."):
                links.append(Link(s.id, "REFERS_TO", target, _snippet(s.text, m.start(), m.end())))
    return links


def named_references(sections: list[Section]) -> list[Link]:
    """References by name: appendices and chapter titles ('hoofdstuk Life events')."""
    chapters = {s.title.split("|", 1)[1].strip().lower(): s.id
                for s in sections if s.level == 1 and "|" in s.title and s.id[:2] in ("AB", "BB")}
    links = []
    for s in sections:
        if s.part == "Versiebeheer":
            continue
        for pattern, target in NAMED_TARGETS:
            for m in re.finditer(pattern, s.text, re.IGNORECASE):
                if target != s.id and not s.id.startswith(target):
                    links.append(Link(s.id, "REFERS_TO", target, _snippet(s.text, m.start(), m.end())))
        for title, target in chapters.items():
            for m in re.finditer(r"hoofdstuk\s+" + re.escape(title), s.text, re.IGNORECASE):
                if target != s.id and not s.id.startswith(target + "."):
                    links.append(Link(s.id, "REFERS_TO", target, _snippet(s.text, m.start(), m.end())))
    return links


def exception_sources(sections: list[Section]) -> list[Link]:
    """Sections with the 🔍 icon or an explicit 'Explain' mention. Target filled in by the loader."""
    links = []
    for s in sections:
        if s.id == EXPLAIN_CHAPTER or s.id.startswith(EXPLAIN_CHAPTER + ".") or s.part == "Versiebeheer":
            continue
        if s.explain_icon:
            links.append(Link(s.id, "HAS_EXCEPTION", EXPLAIN_CHAPTER,
                              "🔍 icon next to: " + " / ".join(s.explain_icon_lines)))
        elif m := re.search(r"explain", s.text, re.IGNORECASE):
            links.append(Link(s.id, "HAS_EXCEPTION", EXPLAIN_CHAPTER, _snippet(s.text, m.start(), m.end())))
    return links


def _term_pattern(term: str) -> re.Pattern:
    """'Aflossingsvrij lenen (producten)' -> matches 'aflossingsvrij lenen' as whole words."""
    core = re.sub(r"\s*\(.*?\)\s*", " ", term).strip()
    # (?<![\w-]) so 'annuïtaire I/L-toets' does not match inside 'niet-annuïtaire I/L-toets'
    return re.compile(r"(?<![\w-])" + re.escape(core) + r"(?![\w-])", re.IGNORECASE)


def term_usage(sections: list[Section], definitions: list[Definition]) -> list[Link]:
    links = []
    for d in definitions:
        pattern = _term_pattern(d.term)
        hits = []
        for s in sections:
            if s.id == "BIJ-B2" or s.part == "Versiebeheer":
                continue
            if m := pattern.search(s.text):
                hits.append(Link(s.id, "USES_TERM", d.id, _snippet(s.text, m.start(), m.end())))
        if len(hits) <= MAX_SECTIONS_PER_TERM:
            links += hits
    return links


def document_requirements(sections: list[Section]) -> list[Link]:
    """Bijlage 3 is ordered per chapter ('Hoofdstuk 3 - Inkomen'), plus one part for the Beheerbeleid."""
    doclists = {}
    for s in sections:
        if s.id.startswith("BIJ-B3."):
            if m := re.match(r"Hoofdstuk (\d)", s.title):
                doclists[f"AB-{m.group(1)}"] = s.id
            elif s.title.strip() == "Beheerbeleid":
                doclists["BB"] = s.id
    links = []
    for s in sections:
        if not s.text or s.level < 2:
            continue
        code = _part_code(s.id)
        chapter = f"AB-{s.number.split('.')[0]}" if code == "AB" else "BB"
        if code in ("AB", "BB") and chapter in doclists:
            links.append(Link(s.id, "REQUIRES_DOCUMENTS", doclists[chapter], f"document list for {s.chapter}"))
    return links


def find_links(sections: list[Section], definitions: list[Definition]) -> list[Link]:
    links = (numbered_references(sections) + named_references(sections) + exception_sources(sections)
             + term_usage(sections, definitions) + document_requirements(sections))
    # one link per (source, type, target), keep the first piece of evidence
    unique: dict[tuple, Link] = {}
    for link in links:
        unique.setdefault((link.source, link.type, link.target), link)
    return list(unique.values())
