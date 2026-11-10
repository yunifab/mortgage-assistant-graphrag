"""Step 6: build the document graph in Neo4j (on top of the chunks from build_index.py).

Run:  uv run python scripts/build_graph.py
Needs: data/processed/*.jsonl (parse_pdf.py) and the :Chunk nodes in Neo4j (build_index.py).
Re-running is safe: it removes the graph layer and rebuilds it. Chunks are not touched.
"""

import collections

from mortgage_assistant import store
from mortgage_assistant.embeddings import embed_texts
from mortgage_assistant.graph import loader
from mortgage_assistant.graph.links import find_links
from mortgage_assistant.ingest.io import load_chunks, load_definitions, load_sections


def main() -> None:
    sections, chunks, definitions = load_sections(), load_chunks(), load_definitions()
    links = find_links(sections, definitions)
    print(f"links found by rules: {dict(collections.Counter(l.type for l in links))}")

    with store.get_driver() as driver:
        if store.count_chunks(driver) != len(chunks):
            raise SystemExit("Neo4j chunks differ from chunks.jsonl: run scripts/build_index.py first.")
        loader.reset_graph(driver)
        loader.create_constraints(driver)
        loader.write_structure(driver, sections, chunks)
        def_embeddings = embed_texts([f"{d.term}: {d.text}" for d in definitions])
        loader.write_definitions(driver, definitions, def_embeddings)
        loader.write_links(driver, links)
        n_exc = loader.write_exceptions(driver, links)
        print(f"HAS_EXCEPTION links to Explain sections: {n_exc}")
        stats = loader.graph_stats(driver)
    print(f"nodes:         {stats['nodes']}")
    print(f"relationships: {stats['relationships']}")


if __name__ == "__main__":
    main()
