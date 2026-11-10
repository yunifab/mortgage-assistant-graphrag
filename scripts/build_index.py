"""Step 2: embed the chunks and load them into Neo4j with a vector index.

Run:  uv run python scripts/build_index.py
Needs: data/processed/chunks.jsonl (from scripts/parse_pdf.py) and a running Neo4j.
Re-running is safe: it deletes our :Chunk nodes first and rebuilds them.
"""

import time

from mortgage_assistant.config import settings
from mortgage_assistant.embeddings import embed_texts
from mortgage_assistant.ingest.io import load_chunks
from mortgage_assistant import store


def main() -> None:
    chunks = load_chunks()
    print(f"embedding {len(chunks)} chunks with {settings.embedding_provider}:{settings.embedding_model} ...")
    t0 = time.perf_counter()
    embeddings = embed_texts([c.text_for_embedding for c in chunks])
    dimension = len(embeddings[0])
    print(f"  done in {time.perf_counter() - t0:.0f}s (dimension {dimension})")

    with store.get_driver() as driver:
        store.reset_chunks(driver)
        store.create_schema(driver, dimension)
        store.write_chunks(driver, chunks, embeddings)
        print(f"Neo4j now holds {store.count_chunks(driver)} :Chunk nodes "
              f"(index '{settings.vector_index_name}', database '{settings.neo4j_database}')")


if __name__ == "__main__":
    main()
