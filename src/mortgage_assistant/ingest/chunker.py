"""Split sections into chunks.

Rule: one chunk per section. Only a section longer than `max_chars` is split,
at line breaks, with some overlap so a sentence near the cut is in both pieces.
Because a chunk never crosses a section border, every chunk has exactly one
section number. That makes citations easy now and graph links possible later.
"""

from mortgage_assistant.models import Chunk, Section


def _split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for line in text.split("\n"):
        if current and len(current) + 1 + len(line) > max_chars:
            pieces.append(current)
            # Start the next piece with the tail of this one (cut at a word boundary)
            tail = current[-overlap:]
            current = tail[tail.find(" ") + 1:] if " " in tail else tail
        current = f"{current}\n{line}" if current else line
    if current:
        pieces.append(current)
    return pieces


def chunk_sections(sections: list[Section], max_chars: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for sec in sections:
        if not sec.text:
            continue  # heading-only section (its text lives in its sub-sections)
        for i, piece in enumerate(_split_text(sec.text, max_chars, overlap), start=1):
            chunks.append(Chunk(
                id=f"{sec.id}#{i}",
                section_id=sec.id,
                part=sec.part,
                chapter=sec.chapter,
                section_number=sec.number,
                section_title=sec.title,
                pages=sec.pages,
                text=piece,
            ))
    return chunks
