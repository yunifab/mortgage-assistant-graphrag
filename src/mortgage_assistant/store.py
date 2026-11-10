"""Neo4j as the vector store.

For the RAG baseline we only store (:Chunk) nodes with their text, metadata and
embedding, plus a vector index. No relationships yet: that is exactly what
GraphRAG will add later, in the same database, on top of the same chunks.
"""

from neo4j import Driver, GraphDatabase

from mortgage_assistant.config import settings
from mortgage_assistant.models import Chunk


def get_driver() -> Driver:
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    driver.verify_connectivity()
    return driver


def _query(driver: Driver, cypher: str, **params):
    return driver.execute_query(cypher, params, database_=settings.neo4j_database).records


def reset_chunks(driver: Driver) -> None:
    """Delete only our own :Chunk nodes and the vector index (nothing else in the database)."""
    _query(driver, f"DROP INDEX {settings.vector_index_name} IF EXISTS")
    _query(driver, "MATCH (c:Chunk) CALL (c) { DETACH DELETE c } IN TRANSACTIONS OF 500 ROWS")


def create_schema(driver: Driver, dimension: int) -> None:
    _query(driver, "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
    _query(driver, f"""
        CREATE VECTOR INDEX {settings.vector_index_name} IF NOT EXISTS
        FOR (c:Chunk) ON c.embedding
        OPTIONS {{indexConfig: {{`vector.dimensions`: $dim, `vector.similarity_function`: 'cosine'}}}}
    """, dim=dimension)
    _query(driver, "CALL db.awaitIndexes(300)")


def write_chunks(driver: Driver, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    rows = [c.to_dict() | {"heading_path": c.heading_path, "embedding": e} for c, e in zip(chunks, embeddings)]
    _query(driver, """
        UNWIND $rows AS row
        MERGE (c:Chunk {id: row.id})
        SET c.text = row.text,
            c.section_id = row.section_id,
            c.section_number = row.section_number,
            c.section_title = row.section_title,
            c.part = row.part,
            c.chapter = row.chapter,
            c.pages = row.pages,
            c.heading_path = row.heading_path
        WITH c, row
        CALL db.create.setNodeVectorProperty(c, 'embedding', row.embedding)
    """, rows=rows)


def vector_search(driver: Driver, query_embedding: list[float], k: int) -> list[dict]:
    """The k chunks most similar to the question, best first."""
    records = _query(driver, f"""
        CALL db.index.vector.queryNodes('{settings.vector_index_name}', $k, $embedding)
        YIELD node, score
        RETURN node.id AS id, node.text AS text, node.section_id AS section_id,
               node.section_number AS section_number, node.section_title AS section_title,
               node.part AS part, node.pages AS pages, node.heading_path AS heading_path, score
        ORDER BY score DESC
    """, k=k, embedding=query_embedding)
    return [r.data() for r in records]


def count_chunks(driver: Driver) -> int:
    return _query(driver, "MATCH (c:Chunk) RETURN count(c) AS n")[0]["n"]
