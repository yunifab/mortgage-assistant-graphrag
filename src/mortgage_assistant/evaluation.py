"""Scoring helpers for comparing RAG and GraphRAG on the ground-truth set.

Two kinds of scores:
- Retrieval (no LLM, exact): did we retrieve the passages that hold the evidence?
  Each evidence quote is mapped to the chunk(s) that contain it ('gold chunks').
- Answer correctness (LLM judge): does the answer state the same facts as the reference?
"""

import json
import re

from mortgage_assistant import llm
from mortgage_assistant.config import settings
from mortgage_assistant.models import Chunk

JUDGE_MODEL = "qwen/qwen3.8-27b"  # another model family than the answer model, to avoid self-grading


def _norm(text: str) -> str:
    """Compare text on letters and digits only (ignores line breaks, €, punctuation)."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def gold_chunk_ids(evidence: dict, chunks: list[Chunk]) -> set[str]:
    """The chunks that contain an evidence quote (on the cited page)."""
    quote = _norm(evidence["quote"])
    on_page = [c for c in chunks if evidence["page"] in c.pages]
    for needle in (quote, quote[:60]):  # the prefix catches quotes cut by a chunk border
        hits = {c.id for c in on_page if needle in _norm(c.text)}
        if hits:
            return hits
    # Fallback (e.g. rewritten table rows): chunks of the cited section on the cited page
    number = evidence["section"].split()[0]
    return {c.id for c in on_page if c.section_number == number}


def _evidence_found(evidence: dict, retrieved: list, chunks: list[Chunk]) -> bool:
    """Found if a gold chunk was retrieved, or the quote is in another retrieved item
    (e.g. a Definition node that holds the same text as part of a definitions chunk)."""
    if gold_chunk_ids(evidence, chunks) & {r.id for r in retrieved}:
        return True
    quote = _norm(evidence["quote"])[:60]
    return any(quote in _norm(r.text) and evidence["page"] in r.pages for r in retrieved)


def retrieval_scores(evidence: list[dict], retrieved: list, chunks: list[Chunk]) -> dict:
    """evidence_recall: share of evidence pieces found. all_evidence: 1 if every piece was found."""
    found = [_evidence_found(e, retrieved, chunks) for e in evidence]
    recall = sum(found) / len(found) if found else 0.0
    return {"evidence_found": found, "evidence_recall": recall, "all_evidence": float(all(found))}


def judge_answer(question: str, reference: str, system_answer: str) -> dict:
    system = (settings.prompts_dir / "judge_correctness.md").read_text(encoding="utf-8")
    user = f"QUESTION:\n{question}\n\nREFERENCE ANSWER:\n{reference}\n\nSYSTEM ANSWER:\n{system_answer}"
    raw = llm.chat(system, user, model=JUDGE_MODEL, temperature=0.0).text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        verdict = json.loads(match.group(0)) if match else {}
        return {"score": float(verdict["score"]), "label": verdict.get("label", ""),
                "reason": verdict.get("reason", "")}
    except (KeyError, ValueError, TypeError):
        return {"score": 0.0, "label": "judge_error", "reason": raw[:300]}
