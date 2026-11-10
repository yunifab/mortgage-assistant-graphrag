"""Step 13: put the ontology (concepts + rules) into Neo4j, linked to the document graph.

Run:  uv run python scripts/build_ontology_graph.py
Needs: the document graph (scripts/build_graph.py). Safe to re-run.

Adds
  (:Concept {id, label_en, label_nl, synonyms})      every rabo: class (Houseboat, Applicant, ...)
  (:FiboConcept {iri, label, definition})             the reused FIBO terms
  (:Rule {id, label, definition_nl})                  every policy rule
  (:Concept)-[:SUBCLASS_OF]->(:Concept | :FiboConcept)
  (:Concept)-[:DEFINED_IN]->(:Section)                where the policy describes the concept
  (:Rule)-[:SOURCE]->(:Section), (:Rule)-[:EXPLAIN_IN]->(:Section)

This is a simple, readable copy for exploring in Neo4j Browser. The rule engine itself (RDFox)
reads the Turtle and Datalog files directly. (A full RDF import is also possible with the
neosemantics/n10s plugin, which the platform team may prefer.)
"""

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.namespace import OWL, SKOS

from mortgage_assistant import store
from mortgage_assistant.config import settings
from mortgage_assistant.rules.case import RABO
from mortgage_assistant.rules.concepts import labels
from mortgage_assistant.rules.engine import ONTOLOGY_DIR, ontology_graph, rule_metadata


def short(iri) -> str:
    return str(iri).split("#")[-1].split("/")[-1]


def main() -> None:
    g = ontology_graph()
    fibo = Graph().parse(ONTOLOGY_DIR / "fibo_slice.ttl", format="turtle")

    concepts, subclass, defined_in = [], [], []
    for cls in g.subjects(RDF.type, OWL.Class):
        if not str(cls).startswith(str(RABO)):
            continue
        words = labels(cls)
        concepts.append({"id": short(cls), "label_en": (words["en"] or [""])[0], "label_nl": (words["nl"] or [""])[0],
                         "synonyms": words["en"][1:] + words["nl"][1:]})
        for parent in g.objects(cls, RDFS.subClassOf):
            subclass.append({"child": short(cls), "parent": str(parent), "fibo": not str(parent).startswith(str(RABO))})
        for section in g.objects(cls, RABO.definedIn):
            defined_in.append({"concept": short(cls), "section": str(section)})

    fibo_terms = [{"iri": str(t), "label": str(fibo.value(t, RDFS.label) or short(t)),
                   "definition": str(fibo.value(t, SKOS.definition) or "")}
                  for t in set(fibo.subjects(RDFS.isDefinedBy, None)) if isinstance(t, URIRef)]
    rules = [{"id": rid, **m} for rid, m in rule_metadata().items()]

    with store.get_driver() as driver:
        q = lambda cypher, **p: driver.execute_query(cypher, p, database_=settings.neo4j_database)  # noqa: E731
        for label in ("Concept", "FiboConcept", "Rule"):
            q(f"MATCH (n:{label}) DETACH DELETE n")
        q("UNWIND $rows AS r CREATE (:FiboConcept {iri: r.iri, label: r.label, definition: r.definition})", rows=fibo_terms)
        q("UNWIND $rows AS r CREATE (:Concept {id: r.id, label_en: r.label_en, label_nl: r.label_nl, synonyms: r.synonyms})",
          rows=concepts)
        q("""UNWIND $rows AS r MATCH (c:Concept {id: r.child})
             OPTIONAL MATCH (p:Concept {id: split(r.parent, '#')[-1]}) WHERE NOT r.fibo
             OPTIONAL MATCH (f:FiboConcept {iri: r.parent}) WHERE r.fibo
             FOREACH (x IN CASE WHEN p IS NULL THEN [] ELSE [p] END | MERGE (c)-[:SUBCLASS_OF]->(x))
             FOREACH (x IN CASE WHEN f IS NULL THEN [] ELSE [f] END | MERGE (c)-[:SUBCLASS_OF]->(x))""", rows=subclass)
        q("""UNWIND $rows AS r MATCH (c:Concept {id: r.concept}), (s:Section {id: r.section})
             MERGE (c)-[:DEFINED_IN]->(s)""", rows=defined_in)
        q("""UNWIND $rows AS r CREATE (x:Rule {id: r.id, label: r.label, definition_nl: r.definition_nl})
             WITH x, r MATCH (s:Section {id: r.source}) MERGE (x)-[:SOURCE]->(s)""", rows=rules)
        q("""UNWIND $rows AS r MATCH (x:Rule {id: r.id}), (s:Section {id: r.explain_source})
             WHERE r.explain_source IS NOT NULL MERGE (x)-[:EXPLAIN_IN]->(s)""", rows=rules)
        stats = q("""MATCH (n) WHERE n:Concept OR n:FiboConcept OR n:Rule
                     OPTIONAL MATCH (n)-[r]->() RETURN labels(n)[0] AS l, count(DISTINCT n) AS nodes, count(r) AS rels""").records
    for r in stats:
        print(f"{r['l']:12} {r['nodes']:3} nodes, {r['rels']:3} outgoing links")


if __name__ == "__main__":
    main()
