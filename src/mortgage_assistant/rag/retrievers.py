"""Retrieval strategies. The rest of the pipeline (prompt, LLM) is the same for all of them.

  vector  plain RAG: the k chunks most similar to the question
  graph   GraphRAG with the document graph:
            1. start with the same k vector chunks ('seeds')
            2. from each seed's section, follow the graph one step:
                 REFERS_TO, HAS_EXCEPTION, REQUIRES_DOCUMENTS -> chunks of the target section
                 PART_OF (parent section)                   -> general rules that also apply
                 sub-sections (child sections)              -> the specific rules under a general one
                 USES_TERM                                  -> the definition of a term
            3. rank everything found by similarity to the question; keep the best `expand_k`
          So the graph decides WHAT is a candidate, similarity decides WHICH candidates are used.
"""

from dataclasses import dataclass

from neo4j import Driver

from mortgage_assistant import store
from mortgage_assistant.config import settings


@dataclass
class RetrievedChunk:
    id: str
    text: str
    section_id: str
    section_number: str
    section_title: str
    part: str
    pages: list[int]
    heading_path: str
    score: float
    source: str = "vector"  # 'vector' or 'graph'
    via: str = ""  # for graph chunks: the link that was followed, e.g. 'HAS_EXCEPTION from AB-3.2'

    @property
    def citation(self) -> str:
        where = f"{self.part} {self.section_number}".strip()
        pages = ", ".join(str(p) for p in self.pages)
        return f"{where}, p.{pages}"


def vector_retrieve(driver: Driver, query_embedding: list[float], k: int) -> list[RetrievedChunk]:
    return [RetrievedChunk(**h) for h in store.vector_search(driver, query_embedding, k)]


GRAPH_EXPANSION = """
MATCH (seed:Chunk)-[:PART_OF]->(s:Section) WHERE seed.id IN $seed_ids
CALL (s) {
    MATCH (s)-[r:REFERS_TO|HAS_EXCEPTION|REQUIRES_DOCUMENTS]->(t:Section)<-[:PART_OF]-(c:Chunk)
    RETURN c AS node, type(r) AS rel, t.id AS target
  UNION
    MATCH (s)-[:PART_OF]->(t:Section)<-[:PART_OF]-(c:Chunk)
    RETURN c AS node, 'PARENT' AS rel, t.id AS target
  UNION
    MATCH (c:Chunk)-[:PART_OF]->(t:Section)-[:PART_OF]->(s)
    RETURN c AS node, 'CHILD' AS rel, t.id AS target
  UNION
    MATCH (s)-[:USES_TERM]->(d:Definition)
    RETURN d AS node, 'USES_TERM' AS rel, d.id AS target
}
WITH node, rel, s.id AS from_section, vector.similarity.cosine(node.embedding, $embedding) AS score
WHERE NOT node.id IN $seed_ids
WITH node, max(score) AS score, collect(rel + ' from ' + from_section)[0] AS via
ORDER BY score DESC LIMIT $expand_k
RETURN node.id AS id,
       CASE WHEN node:Definition THEN node.term + ': ' + node.text ELSE node.text END AS text,
       CASE WHEN node:Definition THEN 'BIJ-B2' ELSE node.section_id END AS section_id,
       CASE WHEN node:Definition THEN 'B2' ELSE node.section_number END AS section_number,
       CASE WHEN node:Definition THEN 'Definitie: ' + node.term ELSE node.section_title END AS section_title,
       CASE WHEN node:Definition THEN 'Bijlagen' ELSE node.part END AS part,
       CASE WHEN node:Definition THEN [node.page] ELSE node.pages END AS pages,
       CASE WHEN node:Definition THEN 'Bijlagen > Bijlage 2 | Definitielijst > ' + node.term
            ELSE node.heading_path END AS heading_path,
       score, via
"""


def graph_retrieve(driver: Driver, query_embedding: list[float], k: int,
                   expand_k: int | None = None) -> list[RetrievedChunk]:
    seeds = vector_retrieve(driver, query_embedding, k)
    records = driver.execute_query(
        GRAPH_EXPANSION,
        {"seed_ids": [c.id for c in seeds], "embedding": query_embedding, "expand_k": expand_k or k},
        database_=settings.neo4j_database,
    ).records
    expanded = [RetrievedChunk(**r.data(), source="graph") for r in records]
    return seeds + expanded


# Shown in the UI and accepted by scripts/run_eval.py --mode
RETRIEVAL_MODES = {
    "vector": "Vector search (RAG)",
    "graph": "Vector + document graph (GraphRAG)",
    "ontology": "Vector + graph + ontology/rules (FIBO, RDFox)",
}
# 'ontology' retrieval = graph retrieval on a query expanded with ontology synonyms (see pipeline.retrieve);
# for a concrete case the pipeline uses the rule engine instead (see rules/answer.py)
AVAILABLE_MODES = {"vector": vector_retrieve, "graph": graph_retrieve, "ontology": graph_retrieve}
