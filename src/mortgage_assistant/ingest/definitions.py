"""Parse Bijlage 2 (Definitielijst) into separate Definition entries.

The list is a two-column table, printed twice side by side on a landscape page:
    term column        x ~ 43   (left half)   and x ~ 436 (right half)
    description column x ~ 184  (left half)   and x ~ 577 (right half)
So the x position of a line tells us if it is a term or part of a description.
"""

import re
from pathlib import Path

import pymupdf

from mortgage_assistant.models import Definition

DEFINITION_PAGES = (63, 64)
TERM_X = (43, 436)
TOLERANCE = 15
HEADER_WORDS = {"Definitie", "Omschrijving"}
CONTENT_TOP, CONTENT_BOTTOM = 62, 555


def _is_term_x(x: float) -> bool:
    return any(abs(x - t) <= TOLERANCE for t in TERM_X)


def parse_definitions(pdf_path: Path) -> list[Definition]:
    doc = pymupdf.open(pdf_path)
    definitions: list[Definition] = []
    for page_no in DEFINITION_PAGES:
        page = doc[page_no - 1]
        rows = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                x0, y0 = line["bbox"][0], line["bbox"][1]
                if text and CONTENT_TOP < y0 < CONTENT_BOTTOM and text not in HEADER_WORDS:
                    rows.append((x0 > 400, y0, x0, text))  # left half first, then right half
        rows.sort()

        term_lines: list[str] = []
        desc_lines: list[str] = []
        prev_was_term = False

        def flush() -> None:
            if term_lines and desc_lines:
                desc = " ".join(desc_lines).replace(" - ", "\n- ").replace("- -", "-")
                definitions.append(Definition(" ".join(term_lines), re.sub(r"[ \t]+", " ", desc).strip(),
                                              page_no))

        for _, _, x, text in rows:
            if text.startswith("Bijlage "):  # the page title
                continue
            if _is_term_x(x) and text.startswith("(") and term_lines:
                term_lines.append(text)  # a wrapped term, e.g. 'Niet-actieve materiële onderneming' + '(VPB)'
                continue
            if _is_term_x(x):
                if not prev_was_term:  # a new term starts: save the previous one
                    flush()
                    term_lines, desc_lines = [], []
                term_lines.append(text)
                prev_was_term = True
            else:
                desc_lines.append(text)
                prev_was_term = False
        flush()
    return definitions
