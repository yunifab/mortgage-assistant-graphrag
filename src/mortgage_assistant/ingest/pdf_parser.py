"""Turn the Rabobank policy PDF into a list of Sections.

How it works (in plain words):
1. Read every text line with its font size and position (PyMuPDF).
2. Throw away what is not content: the navigation bar at the top, the footer,
   cover pages and table-of-contents pages.
3. Recognise headings by font size:
     24 pt  'Hoofdstuk 2 | Aanvrager' / 'Bijlage 2 | Definitielijst'  -> chapter
     12 pt  '2.1 Algemeen'                                            -> section
     10 pt  '2.4.1 EVA en SFH'                                         -> sub-section
    8.5 pt  '1.4.1.1 Hoogte OverbruggingsHypotheek' (only if numbered) -> sub-sub-section
   The level comes from the number itself (count the dots), not from the size.
4. Everything else is body text and goes into the current section.

This parser is written for this one document's layout. Another PDF needs its own rules.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from mortgage_assistant.models import Section

# Layout constants for this PDF (landscape A4: 842 x 595 pt)
NAV_BAR_BOTTOM = 62  # the repeated navigation bar sits above this y
FOOTER_TOP = 555  # the footer ('Acceptatiebeleid Rabobank') sits below this y
FOOTNOTE_TOP = 500  # footnotes are small text below this y
COLUMN_STARTS_X = (290, 550)  # body pages have up to three columns; columns 2 and 3 start after these x
SUPERSCRIPT_MAX = 6.1  # lines this small are footnotes
SUPERSCRIPT_RATIO = 0.7  # a span much smaller than its line is a footnote marker ('EU-land6')

EXPLAIN_ICON_SIZE = (9, 13)  # the 🔍 'see Explain' icon is an ~11x11 pt image
EXPLAIN_LEGEND_PAGES = {6, 42}  # intro pages that only explain what the icon means

HEADING_SIZES = (12.0, 10.0, 8.5)
CHAPTER_SIZE = 24.0

NUMBER_ONLY = re.compile(r"^(\d+(?:\.\d+)+)$")
NUMBER_AND_TITLE = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
CHAPTER_HEADING = re.compile(r"^(Hoofdstuk|Bijlage)\s+(\d+)\s*\|\s*(.+)$")


def part_for_page(page_no: int) -> tuple[str, str]:
    """(part name, short code used in section ids) for a physical page number."""
    if page_no <= 3:
        return "Versiebeheer", "VB"
    if page_no <= 39:
        return "Acceptatiebeleid", "AB"
    if page_no <= 60:
        return "Beheerbeleid", "BB"
    return "Bijlagen", "BIJ"


# Pages laid out as full-width tables (read row by row instead of column by column)
def is_table_page(page_no: int) -> bool:
    return page_no <= 3 or page_no >= 62


@dataclass
class Line:
    text: str
    size: float  # font size of the main (largest) span
    x: float
    y: float
    page: int
    section_id: str | None = None  # filled in while parsing: which section the line went to


def _column(x: float) -> int:
    return sum(x > start for start in COLUMN_STARTS_X)


def _same(a: float, b: float, tol: float = 0.3) -> bool:
    return abs(a - b) <= tol


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _page_lines(page: pymupdf.Page) -> tuple[list[Line], list[str]]:
    """Content lines of one page in reading order, plus the page's footnotes."""
    page_no = page.number + 1
    blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]

    if is_table_page(page_no):
        # Tables: top-to-bottom, then left-to-right, so a row stays together
        blocks.sort(key=lambda b: (round(b["bbox"][1]), b["bbox"][0]))
    else:
        # Columns: the whole left column first, then the middle one, then the right one
        blocks.sort(key=lambda b: (_column(b["bbox"][0]), b["bbox"][1], b["bbox"][0]))

    lines: list[Line] = []
    footnotes: list[str] = []
    for block in blocks:
        for raw in block["lines"]:
            spans = [s for s in raw["spans"] if s["text"].strip()]
            if not spans:
                continue
            x0, y0 = raw["bbox"][0], raw["bbox"][1]
            if y0 < NAV_BAR_BOTTOM or y0 > FOOTER_TOP:
                continue
            main_size = max(s["size"] for s in spans)
            if main_size <= SUPERSCRIPT_MAX:
                if y0 > FOOTNOTE_TOP:
                    footnotes.append(_clean(" ".join(s["text"] for s in spans)))
                continue
            # Drop footnote markers inside normal text ('EU-land6' -> 'EU-land')
            text = _clean("".join(s["text"] for s in spans if s["size"] > SUPERSCRIPT_RATIO * main_size))
            if text:
                lines.append(Line(text, round(main_size, 1), x0, y0, page_no))
    return lines, footnotes


def _explain_icons(page: pymupdf.Page) -> list[tuple[float, float]]:
    """(right edge x, vertical centre y) of every 🔍 icon on the page."""
    icons = []
    for info in page.get_image_info():
        x0, y0, x1, y1 = info["bbox"]
        lo, hi = EXPLAIN_ICON_SIZE
        if lo <= x1 - x0 <= hi and lo <= y1 - y0 <= hi:
            icons.append((x1, (y0 + y1) / 2))
    return icons


def _line_next_to(icon: tuple[float, float], lines: list[Line]) -> Line | None:
    """The text line just to the right of an icon, on the same height."""
    x_right, y_mid = icon
    near = [ln for ln in lines if 0 <= ln.x - x_right <= 40 and abs(ln.y + 4 - y_mid) <= 10]
    return min(near, key=lambda ln: abs(ln.y + 4 - y_mid), default=None)


def _is_skipped_page(lines: list[Line]) -> bool:
    """Cover pages and table-of-contents pages contain no policy rules."""
    for ln in lines:
        if ln.size >= 25.5:  # big cover titles, 'Inhoudsopgave', 'Documentenlijst' TOC
            return True
        if "nhoudsopgave" in ln.text:
            return True
        # Chapter TOC pages list numbered entries in 11 pt
        if _same(ln.size, 11.0) and (NUMBER_ONLY.match(ln.text) or NUMBER_AND_TITLE.match(ln.text)
                                     or ln.text.startswith("Bijlage ")):
            return True
    return False


class _Builder:
    """Collects lines into sections while walking through the document."""

    def __init__(self) -> None:
        self.sections: list[Section] = []
        self.by_id: dict[str, Section] = {}
        self.current: Section | None = None
        self.chapter = ""
        self.chapter_id: str | None = None
        self.heading_open = False  # True while a heading title may continue on the next line
        self.heading_size = 0.0
        self.doclist_counter = 0  # Bijlage 3 has unnumbered sub-headings; we number them

    # -- creating sections -------------------------------------------------
    def _new(self, page: int, number: str, title: str, level: int, parent: str | None) -> Section:
        part, code = part_for_page(page)
        sid = f"{code}-{number}" if number else f"{code}-{_slug(title)}"
        if sid in self.by_id:  # same heading repeated on a following page: keep filling it
            self.current = self.by_id[sid]
            return self.current
        sec = Section(id=sid, part=part, chapter=self.chapter, number=number, title=title,
                      level=level, parent_id=parent)
        self.sections.append(sec)
        self.by_id[sid] = sec
        self.current = sec
        return sec

    def _parent_of(self, page: int, number: str) -> str | None:
        _, code = part_for_page(page)
        parts = number.split(".")
        while len(parts) > 1:
            parts = parts[:-1]
            pid = f"{code}-{'.'.join(parts)}"
            if pid in self.by_id:
                return pid
        return self.chapter_id

    def start_chapter(self, ln: Line) -> None:
        m = CHAPTER_HEADING.match(ln.text)
        if m:
            kind, num, title = m.groups()
            self.chapter = f"{kind} {num} | {title}"
            number = num if kind == "Hoofdstuk" else f"B{num}"
            self._new(ln.page, number, self.chapter, 1, None)
            self.chapter_id = self.current.id
        else:  # part intro, e.g. 'Acceptatiebeleid Rabobank' or 'Versiebeheer'
            self.chapter = ln.text
            self._new(ln.page, "", ln.text, 1, None)
            self.chapter_id = self.current.id
        self.heading_open = False
        self.doclist_counter = 0

    def start_section(self, ln: Line, number: str, title: str) -> None:
        level = number.count(".") + 1
        self._new(ln.page, number, title, level, self._parent_of(ln.page, number))
        ln.section_id = self.current.id
        self.heading_open = True
        self.heading_size = ln.size

    def start_doclist_heading(self, ln: Line) -> None:
        """Bijlage 3 (Documentenlijst) uses unnumbered headings like 'Hoofdstuk 3 - Inkomen'."""
        if self.current and self.current.title == ln.text:
            return  # repeated on the next page
        self.doclist_counter += 1
        number = f"B3.{self.doclist_counter}"
        self._new(ln.page, number, ln.text, 2, self.chapter_id)
        self.heading_open = False

    # -- adding text ---------------------------------------------------------
    def add_text(self, ln: Line) -> None:
        self.heading_open = False
        ln.section_id = self.current.id if self.current else None
        if self.current is None:
            return
        sec = self.current
        if ln.page not in sec.pages:
            sec.pages.append(ln.page)
        if ln.text == "-":  # a bullet: the item text follows on the next line
            sec.text += "\n- "
        elif sec.text.endswith("- ") or not sec.text:
            sec.text += ln.text
        else:
            sec.text += "\n" + ln.text

    def add_title_part(self, ln: Line) -> None:
        ln.section_id = self.current.id
        self.current.title = _clean(f"{self.current.title} {ln.text}")

    def add_footnotes(self, page: int, notes: list[str]) -> None:
        """Attach a page's footnotes to every section that has text on that page."""
        if not notes:
            return
        block = "\nVoetnoten: " + " | ".join(notes)
        for sec in self.sections:
            if page in sec.pages:
                sec.text += block


def _section_heading(ln: Line) -> tuple[str, str] | None:
    """(number, title) if the line is a numbered heading, else None. Title may be '' (on the next line)."""
    if not any(_same(ln.size, s) for s in HEADING_SIZES):
        return None
    if m := NUMBER_ONLY.match(ln.text):
        number, title = m.group(1), ""
    elif m := NUMBER_AND_TITLE.match(ln.text):
        number, title = m.group(1), m.group(2)
    else:
        return None
    # 8.5 pt is also used for table headers, so only accept 4-level numbers like 1.4.1.1
    if _same(ln.size, 8.5) and number.count(".") < 3:
        return None
    return number, title


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_pdf(pdf_path: Path) -> list[Section]:
    """Parse the policy PDF into sections (empty heading-only sections included)."""
    doc = pymupdf.open(pdf_path)
    b = _Builder()

    for page in doc:
        page_no = page.number + 1
        lines, footnotes = _page_lines(page)
        if not lines or _is_skipped_page(lines):
            continue
        in_doclist = b.chapter.startswith("Bijlage 3")

        for ln in lines:
            if _same(ln.size, CHAPTER_SIZE):
                if b.chapter != ln.text:  # a chapter heading can repeat on its next page
                    b.start_chapter(ln)
                continue

            heading = _section_heading(ln)
            if heading:
                b.start_section(ln, *heading)
            elif b.heading_open and _same(ln.size, b.heading_size) and ln.text != "-":
                b.add_title_part(ln)
            elif in_doclist and (_same(ln.size, 11.0) or _same(ln.size, 12.0)):
                b.start_doclist_heading(ln)
            else:
                b.add_text(ln)
            in_doclist = b.chapter.startswith("Bijlage 3")

        b.add_footnotes(page_no, footnotes)

        if page_no not in EXPLAIN_LEGEND_PAGES:
            for icon in _explain_icons(page):
                ln = _line_next_to(icon, lines)
                if ln and ln.section_id:
                    sec = b.by_id[ln.section_id]
                    sec.explain_icon = True
                    if ln.text not in sec.explain_icon_lines:
                        sec.explain_icon_lines.append(ln.text)

    for sec in b.sections:
        sec.text = sec.text.strip()
    return b.sections
