"""Question -> retrieval -> LLM answer with citations.

    1. retrieve: find policy passages (the strategy depends on `mode`, see retrievers.py)
    2. build context: put the passages in the prompt, each with a citation label
    3. generate: the LLM answers using only that context

Only step 1 differs between RAG and GraphRAG. Steps 2 and 3 (and the prompt) are identical,
so any difference in the evaluation comes from retrieval.

Mode 'ontology' adds the rule engine: if the question describes a concrete case, the facts are
extracted, checked by RDFox, and the LLM only explains the findings (rules/answer.py).
A general question is answered like GraphRAG, with ontology synonyms added to the query.
"""

import time
from dataclasses import asdict, dataclass, field

from neo4j import Driver

from mortgage_assistant import llm
from mortgage_assistant.config import settings
from mortgage_assistant.embeddings import embed_query
from mortgage_assistant.rag.retrievers import AVAILABLE_MODES, RetrievedChunk


@dataclass
class RAGAnswer:
    question: str
    answer: str
    chunks: list[RetrievedChunk]
    mode: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: dict = field(default_factory=dict)
    case: dict | None = None  # ontology mode: the case facts that were checked
    check: dict | None = None  # ontology mode: verdict, findings, computed values
    notes: list[str] = field(default_factory=list)  # e.g. query expansion, dropped extraction values

    def to_dict(self) -> dict:
        return asdict(self)


def _system_prompt() -> str:
    return (settings.prompts_dir / "rag_answer_system.md").read_text(encoding="utf-8")


def retrieve(driver: Driver, question: str, k: int, mode: str = "vector") -> list[RetrievedChunk]:
    if mode not in AVAILABLE_MODES:
        raise ValueError(f"Retrieval mode '{mode}' is not available yet (choose from {list(AVAILABLE_MODES)})")
    if mode == "ontology":
        from mortgage_assistant.rules.concepts import expand_query

        question, _ = expand_query(question)
    return AVAILABLE_MODES[mode](driver, embed_query(question), k)


def build_context(chunks: list[RetrievedChunk]) -> str:
    blocks = [f"[{c.citation}] {c.heading_path}\n{c.text}" for c in chunks]
    return "\n\n---\n\n".join(blocks)


def answer(driver: Driver, question: str, k: int | None = None, model: str | None = None,
           mode: str = "vector", case=None) -> RAGAnswer:
    """`case`: ontology mode only - structured facts (from the form); if None they are extracted from the text."""
    k = k or settings.top_k
    if mode == "ontology":
        checked = _answer_with_rules(driver, question, model, case, k)
        if checked:
            return checked
    t0 = time.perf_counter()
    chunks = retrieve(driver, question, k, mode)
    t1 = time.perf_counter()

    user_msg = f"Policy passages:\n\n{build_context(chunks)}\n\n=====\n\nQuestion: {question}"
    result = llm.chat(_system_prompt(), user_msg, model=model)
    t2 = time.perf_counter()

    return RAGAnswer(
        question=question,
        answer=result.text,
        chunks=chunks,
        mode=mode,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_s={"retrieval": round(t1 - t0, 3), "generation": round(t2 - t1, 3)},
        notes=_expansion_note(question) if mode == "ontology" else [],
    )


def _expansion_note(question: str) -> list[str]:
    from mortgage_assistant.rules.concepts import expand_query

    _, added = expand_query(question)
    return [f"query expanded with ontology terms: {', '.join(added)}"] if added else []


def _answer_with_rules(driver: Driver, question: str, model: str | None, case, k: int = 5) -> RAGAnswer | None:
    """Ontology mode for a concrete case. Returns None if the text does not describe a case."""
    from mortgage_assistant.rules import rdfox
    from mortgage_assistant.rules.answer import explain
    from mortgage_assistant.rules.engine import check_case
    from mortgage_assistant.rules.extract import extract_case

    t0 = time.perf_counter()
    notes = []
    if case is None:
        case, _, dropped = extract_case(question, model=model)
        if case is None:
            return None
        notes.append("case facts extracted from the question by the LLM (check them)")
        if dropped:
            notes.append("ignored unknown values: " + ", ".join(dropped))
    if not rdfox.is_available():
        raise RuntimeError("RDFox is not running. Start it (see docs/RDFOX_SETUP.md) to use the ontology mode.")
    t1 = time.perf_counter()
    result = check_case(case)
    t2 = time.perf_counter()
    # Hybrid: the findings are authoritative, but the question may ask more than the rules cover,
    # so GraphRAG passages (with ontology synonyms) are given as well
    extra = retrieve(driver, question, k, "ontology")
    llm_result, passages = explain(driver, question, result, model=model, extra_passages=extra)
    t3 = time.perf_counter()
    return RAGAnswer(
        question=question, answer=llm_result.text, chunks=passages, mode="ontology", model=llm_result.model,
        prompt_tokens=llm_result.prompt_tokens, completion_tokens=llm_result.completion_tokens,
        latency_s={"extraction": round(t1 - t0, 3), "rules": round(t2 - t1, 3), "generation": round(t3 - t2, 3)},
        case=case.to_dict(), check=result.to_dict(), notes=notes,
    )
