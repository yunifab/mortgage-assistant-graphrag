"""Write the document graph into Neo4j, on top of the existing (:Chunk) nodes.

Nodes
  (:Part)        Versiebeheer, Acceptatiebeleid, Beheerbeleid, Bijlagen
  (:Section)     every numbered section (id, number, title, level, pages, explain_icon)
  (:Definition)  every term of Bijlage 2, with its own embedding
  (:Chunk)       already there (from build_index.py): text + embedding + vector index

Relationships
  (Chunk)-[:PART_OF]->(Section)-[:PART_OF]->(Section | Part)    structure
  (Chunk)-[:NEXT]->(Chunk), (Section)-[:NEXT]->(Section)        reading order
  (Section)-[:REFERS_TO]->(Section)                             'zie paragraaf 5.5.8'
  (Section)-[:HAS_EXCEPTION]->(Section in chapter 6 Explain)    🔍 icon / 'zie Explain'
  (Section)-[:USES_TERM]->(Definition), (Section)-[:DEFINES]->(Definition)
  (Section)-[:REQUIRES_DOCUMENTS]->(Section in Bijlage 3)

The :Chunk nodes and the vector index are not changed, so the RAG baseline keeps working.
"""

from neo4j import Driver

from mortgage_assistant.config import settings
from mortgage_assistant.graph.links import EXPLAIN_CHAPTER, Link
from mortgage_assistant.models import Chunk, Definition, Section

EXCEPTION_TARGETS_PER_SECTION = 2


def _q(driver: Driver, cypher: str, **params):
    return driver.execute_query(cypher, params, database_=settings.neo4j_database).records


def reset_graph(driver: Driver) -> None:
    """Remove the graph layer only. :Chunk nodes and their embeddings stay."""
    _q(driver, "MATCH (:Chunk)-[r]-() DELETE r")
    for label in ("Section", "Definition", "Part"):
        _q(driver, f"MATCH (n:{label}) DETACH DELETE n")


def create_constraints(driver: Driver) -> None:
    for label in ("Section", "Definition", "Part"):
        key = "name" if label == "Part" else "id"
        _q(driver, f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
                   f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")


def write_structure(driver: Driver, sections: list[Section], chunks: list[Chunk]) -> None:
    rows = [{k: v for k, v in s.to_dict().items() if k != "text"} for s in sections]
    _q(driver, """
        UNWIND $rows AS row
        MERGE (p:Part {name: row.part})
        CREATE (s:Section {id: row.id, part: row.part, chapter: row.chapter, number: row.number,
                           title: row.title, level: row.level, pages: row.pages,
                           explain_icon: row.explain_icon})
    """, rows=rows)
    # Section hierarchy: child -> parent section, top-level -> part
    _q(driver, """
        UNWIND $rows AS row
        MATCH (s:Section {id: row.id})
        OPTIONAL MATCH (parent:Section {id: row.parent_id})
        MATCH (p:Part {name: row.part})
        FOREACH (_ IN CASE WHEN parent IS NULL THEN [1] ELSE [] END | MERGE (s)-[:PART_OF]->(p))
        FOREACH (_ IN CASE WHEN parent IS NOT NULL THEN [1] ELSE [] END | MERGE (s)-[:PART_OF]->(parent))
    """, rows=rows)
    # Reading order of sections
    pairs = [{"a": a.id, "b": b.id} for a, b in zip(sections, sections[1:])]
    _q(driver, """
        UNWIND $pairs AS p
        MATCH (a:Section {id: p.a}), (b:Section {id: p.b}) MERGE (a)-[:NEXT]->(b)
    """, pairs=pairs)
    # Chunks belong to their section, and follow each other within it
    _q(driver, """
        MATCH (c:Chunk) MATCH (s:Section {id: c.section_id}) MERGE (c)-[:PART_OF]->(s)
    """)
    chunk_pairs = [{"a": a.id, "b": b.id} for a, b in zip(chunks, chunks[1:]) if a.section_id == b.section_id]
    _q(driver, """
        UNWIND $pairs AS p
        MATCH (a:Chunk {id: p.a}), (b:Chunk {id: p.b}) MERGE (a)-[:NEXT]->(b)
    """, pairs=chunk_pairs)


def write_definitions(driver: Driver, definitions: list[Definition], embeddings: list[list[float]]) -> None:
    rows = [d.to_dict() | {"embedding": e} for d, e in zip(definitions, embeddings)]
    _q(driver, """
        UNWIND $rows AS row
        CREATE (d:Definition {id: row.id, term: row.term, text: row.text, page: row.page,
                              embedding: row.embedding})
        WITH d
        MATCH (s:Section {id: 'BIJ-B2'}) MERGE (s)-[:DEFINES]->(d)
    """, rows=rows)


def write_links(driver: Driver, links: list[Link]) -> None:
    by_type: dict[str, list[dict]] = {}
    for link in links:
        if link.type != "HAS_EXCEPTION":
            by_type.setdefault(link.type, []).append(
                {"source": link.source, "target": link.target, "evidence": link.evidence})
    for rel_type, rows in by_type.items():
        target_label = "Definition" if rel_type == "USES_TERM" else "Section"
        _q(driver, f"""
            UNWIND $rows AS row
            MATCH (a:Section {{id: row.source}}), (b:{target_label} {{id: row.target}})
            MERGE (a)-[r:{rel_type}]->(b) SET r.evidence = row.evidence
        """, rows=rows)


def write_exceptions(driver: Driver, links: list[Link]) -> int:
    """HAS_EXCEPTION: the rule-based step only says THAT an exception may exist.
    WHICH Explain section is chosen by meaning: the Explain sections whose chunks are most similar
    to the source section's chunks (top 2)."""
    rows = [{"source": l.source, "evidence": l.evidence} for l in links if l.type == "HAS_EXCEPTION"]
    records = _q(driver, """
        UNWIND $rows AS row
        MATCH (s:Section {id: row.source})
        CALL (s, row) {
            MATCH (sc:Chunk)-[:PART_OF]->(s)
            MATCH (ec:Chunk)-[:PART_OF]->(e:Section)
            WHERE e.id STARTS WITH $explain + '.' AND e.level >= 3
            WITH e, max(vector.similarity.cosine(sc.embedding, ec.embedding)) AS sim
            ORDER BY sim DESC LIMIT $n
            MERGE (s)-[r:HAS_EXCEPTION]->(e)
            SET r.evidence = row.evidence, r.similarity = sim
            RETURN count(*) AS made
        }
        RETURN sum(made) AS total
    """, rows=rows, explain=EXPLAIN_CHAPTER, n=EXCEPTION_TARGETS_PER_SECTION)
    return records[0]["total"]


def graph_stats(driver: Driver) -> dict:
    nodes = _q(driver, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label")
    rels = _q(driver, "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type")
    return {"nodes": {r["label"]: r["n"] for r in nodes}, "relationships": {r["type"]: r["n"] for r in rels}}
