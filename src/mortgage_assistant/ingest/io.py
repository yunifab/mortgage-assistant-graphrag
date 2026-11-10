"""Read and write the processed sections/chunks (JSON Lines: one JSON object per line)."""

import json
from pathlib import Path

from mortgage_assistant.config import settings
from mortgage_assistant.models import Chunk, Definition, Section


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_chunks(path: Path | None = None) -> list[Chunk]:
    path = path or settings.processed_dir / "chunks.jsonl"
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    # heading_path is derived from the other fields, so it is not a constructor argument
    return [Chunk(**{k: v for k, v in r.items() if k != "heading_path"}) for r in rows]


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_sections(path: Path | None = None) -> list[Section]:
    return [Section(**r) for r in _read_jsonl(path or settings.processed_dir / "sections.jsonl")]


def load_definitions(path: Path | None = None) -> list[Definition]:
    rows = _read_jsonl(path or settings.processed_dir / "definitions.jsonl")
    return [Definition(**{k: v for k, v in r.items() if k != "id"}) for r in rows]
