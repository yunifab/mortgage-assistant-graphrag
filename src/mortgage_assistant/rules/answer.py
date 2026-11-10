"""Ontology mode: case facts -> rule engine -> findings + policy text from Neo4j -> LLM explanation.

The bridge between the two graphs: each finding has a source section id (e.g. 'AB-5.5.12'),
which is the :Section id in the Neo4j document graph. We fetch that section's text from Neo4j
so the explanation can quote the policy, and cite exactly the sections the rules come from.
"""

from neo4j import Driver

from mortgage_assistant import llm
from mortgage_assistant.config import settings
from mortgage_assistant.rag.retrievers import RetrievedChunk
from mortgage_assistant.rules.engine import CheckResult, _eur

VERDICT_TEXT = {
    "reject": "NOT acceptable: at least one policy rule is violated",
    "explain": "NOT acceptable under the standard rules; possibly acceptable via the Explain route",
    "incomplete": "no violation found, but facts are missing to complete the check",
    "accept": "acceptable on all rules that were checked",
}
MAX_SECTION_CHARS = 2500


def section_passages(driver: Driver, section_ids: list[str]) -> list[RetrievedChunk]:
    """The text of each cited section, from the Neo4j document graph."""
    records = driver.execute_query("""
        UNWIND $ids AS sid
        MATCH (s:Section {id: sid})
        OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(s)
        WITH s, c ORDER BY c.id
        WITH s, collect(c.text) AS texts, collect(c.heading_path)[0] AS path
        RETURN s.id AS id, s.part AS part, s.number AS number, s.title AS title, s.pages AS pages,
               reduce(t = '', x IN texts | t + x + '\n') AS text, path
    """, {"ids": section_ids}, database_=settings.neo4j_database).records
    out = []
    for r in records:
        out.append(RetrievedChunk(id=r["id"], text=(r["text"] or "")[:MAX_SECTION_CHARS], section_id=r["id"],
                                  section_number=r["number"], section_title=r["title"], part=r["part"],
                                  pages=r["pages"] or [], heading_path=r["path"] or r["title"], score=1.0,
                                  source="rules", via="cited by rule"))
    return out


def findings_text(result: CheckResult, citations: dict[str, str] | None = None) -> str:
    citations = citations or {}
    lines = [f"VERDICT: {VERDICT_TEXT[result.verdict]}", ""]
    # Problems and passed checks in separate blocks, so a passed check is never read as a problem
    problems = [f for f in result.findings if f.status != "ok"]
    passed = [f for f in result.findings if f.status == "ok"]
    lines.append("PROBLEMS (report all of these, and nothing else as a problem):")
    for f in problems:
        cite = citations.get(f.source, f.source)
        extra = f" (Explain: [{citations.get(f.explain_source, f.explain_source)}])" if f.explain_source else ""
        lines.append(f"{f.icon} [{cite}] {f.label}: {f.detail}{extra}")
    if not problems:
        lines.append("(none)")
    lines += ["", "PASSED CHECKS (these rules are MET; they are not problems):"]
    for f in passed:
        lines.append(f"✅ [{citations.get(f.source, f.source)}] {f.label}: {f.detail}")
    if result.values:
        v = result.values
        computed = []
        for key, name in (("maxLoan", "maximum loan"), ("loanAmount", "requested loan"),
                          ("interestOnlyTotal", "interest-only total"), ("interestOnlyCap", "interest-only cap"),
                          ("maxLoanWithValuationReport", "maximum loan with a full valuation report")):
            if key in v:
                computed.append(f"{name}: {_eur(v[key])}")
        for method, amount in v.get("maxLoanByValuation", {}).items():
            computed.append(f"maximum loan if valued with {method.replace('_', ' ')}: {_eur(amount)}")
        if computed:
            lines += ["", "COMPUTED VALUES: " + "; ".join(computed)]
    return "\n".join(lines)


DUTCH_WORDS = {"de", "het", "een", "en", "van", "is", "mag", "wordt", "niet", "met", "voor", "aanvraag", "klant",
               "wil", "hij", "zij", "deze", "kan", "zijn", "op", "bij", "ook", "wat", "hoeveel"}


def _looks_dutch(text: str) -> bool:
    words = [w.strip(".,?!:;()").lower() for w in text.split()]
    return sum(w in DUTCH_WORDS for w in words) >= max(2, len(words) // 12)


def explain(driver: Driver, question: str, result: CheckResult, model: str | None = None,
            extra_passages: list[RetrievedChunk] | None = None):
    """extra_passages: GraphRAG passages for the parts of the question the rules do not cover."""
    sources = []
    for f in result.findings:
        for s in (f.source, f.explain_source):
            if s and s not in sources:
                sources.append(s)
    passages = section_passages(driver, sources)
    citations = {p.section_id: p.citation for p in passages}
    policy = "\n\n---\n\n".join(f"[{p.citation}] {p.heading_path}\n{p.text}" for p in passages)
    system = (settings.prompts_dir / "ontology_answer_system.md").read_text(encoding="utf-8")
    language = "Dutch" if _looks_dutch(question) else "English"
    cited_ids = {p.section_id for p in passages}
    extra = [c for c in (extra_passages or []) if c.section_id not in cited_ids]
    other = "\n\n---\n\n".join(f"[{c.citation}] {c.heading_path}\n{c.text}" for c in extra) or "(none)"
    user = (f"ANSWER LANGUAGE: {language}\n\nQUESTION:\n{question}\n\n"
            f"RULE ENGINE FINDINGS:\n{findings_text(result, citations)}\n\n"
            f"POLICY TEXT OF THE CITED SECTIONS:\n{policy}\n\n"
            f"OTHER RELEVANT POLICY PASSAGES (search results; use them only for parts of the question the findings "
            f"do not cover):\n{other}")
    return llm.chat(system, user, model=model), passages + extra
