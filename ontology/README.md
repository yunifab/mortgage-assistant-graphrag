# Ontology + rules (feature 3)

The policy's **hard rules** as an ontology (built on **FIBO**) and **Datalog rules** that **RDFox** evaluates.
A case is checked against *every* encoded rule, exactly and the same way every time. The LLM only extracts
facts (from free text) and explains the findings.

## The four layers

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 1. fibo_slice.ttl       17 FIBO terms we reuse (LoanApplication, Borrower, Collateral, │
│                         LoanToValueRatio, Appraisal, MarketValue, ...), generated from │
│                         the local FIBO clone by scripts/extract_fibo_slice.py         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ 2. rabo_mortgage.ttl    our terms, built on FIBO (rabo:Houseboat ⊂ fibo:Collateral,    │
│                         rabo:DesktopTaxatie ⊂ fibo:Appraisal, ...), NL/EN labels and   │
│                         synonyms, the policy LIMITS as data (LTV norms, interest-only  │
│                         allowed per collateral type), and the RULES with their source  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ 3. rules/*.dlog         the rule LOGIC in Datalog (RDFox): facts -> findings           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ 4. case facts           one application, as RDF (made from JSON by                     │
│                         src/mortgage_assistant/rules/case.py)                          │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**The bridge to the document graph:** every rule has `rabo:source "AB-5.5.12"`, which is the `:Section` id in Neo4j.
So each finding links to the exact policy text, and the explanation cites it.

## Files

| File | What |
|---|---|
| `fibo_slice.ttl` | generated FIBO slice (do not edit; re-run `scripts/extract_fibo_slice.py`) |
| `rabo_mortgage.ttl` | the Rabobank mortgage ontology: application, applicants, loan parts, Explain, rule list |
| `taxonomy_collateral.ttl` | the **collateral taxonomy** in 4 dimensions (building type, use, construction, legal right), valuation types, LTV norms and other limits per class (DRAFT) |
| `TAXONOMY.md` | generated tree of the taxonomy with the limits per class (`scripts/export_taxonomy.py`) |
| `rules/00_inference.dlog` | class hierarchy, loan amount, passing findings up to the application |
| `rules/10_applicant.dlog` | age (2.1), debtors and channel (2.2), RRR (2.4.2) |
| `rules/20_loan.dlog` | term (1.1), what counts as interest-only + cap (1.1.3), interest-only per collateral, desktop + interest-only (5.4) |
| `rules/30_collateral.dlog` | valuation method (5.4), LTV norms + maximum loan (1.3, 5.5.x), energy 106% (1.3), houseboat (5.5.12), recreation home (5.5.13), letting (5.5.15) |
| `rules/35_taxonomy.dlog` | rules that come with the taxonomy: type max term, letting allowed per type, NHG, own home at Rabobank, farm area, desktop exclusions (5.4), construction costs, erfpacht/opstal review |
| `rules/40_explain_letting.dlog` | Explain route + combinations (6, 6.1), diplomat clause (BB 4.1.1) |
| `RULES.md` | generated review table of all rules (`scripts/export_rules_table.py`) |

## How a check works

```
advisor's text ──LLM extraction──┐
                                 ├──> case facts (JSON) ──> RDF ──> RDFox: FIBO slice + ontology + rules
"Check a case" form ─────────────┘                                     │
                                                                       ▼
                                       findings: ❌ violated · 🔍 only via Explain · ❓ missing fact · ✅ OK
                                       + computed values (maximum loan, interest-only total, ...)
                                                                       │
                     section text from the Neo4j document graph ───────┤
                                                                       ▼
                                                     LLM writes the explanation (may not add or change findings)
```

Code: `src/mortgage_assistant/rules/` (`case.py` facts→RDF, `rdfox.py` REST client, `engine.py` check + findings,
`extract.py` text→facts, `answer.py` explanation, `concepts.py` labels/synonyms).

## Run it

1. Start RDFox (see `docs/RDFOX_SETUP.md`).
2. In the app (`uv run python app/gradio_app.py`), either:
   - use the **✅ Check a case** tab (form), or
   - in **Chat**, choose *Vector + graph + ontology/rules* and describe a case. A general question is
     answered with GraphRAG plus the ontology synonyms (e.g. *houseboat → woonboot met vaste ligplaats*).
3. Tests: `uv run pytest tests/test_rules.py` (each use case and held-out case is a test).
4. Optional, to explore the ontology in Neo4j Browser: `uv run python scripts/build_ontology_graph.py`
   (re-run it after `build_graph.py`, which removes the old links).

## Add or change a rule (checklist)

1. Find the sentence in the policy and its section id (e.g. `AB-5.5.13`).
2. If it's a **limit** (a percentage, an amount, "allowed: yes/no"), put it as **data** in `rabo_mortgage.ttl`
   (e.g. a new `rabo:LTVNorm`), so the existing rules use it. Otherwise write a **rule** in `rules/*.dlog`.
3. Add the rule to `rabo_mortgage.ttl` (`a rabo:Rule ; rabo:source "..." ; rdfs:label "..." ; skos:definition "<policy text>"`).
   Word the label as the condition that must hold, so ✅ always reads as "OK".
4. If the rule needs a new fact, add it to `case.py` (field + RDF) and to `prompts/case_extraction_system.md`.
5. Add a test case to `tests/test_rules.py`, run `scripts/export_rules_table.py`, and have someone check the row
   against the PDF.

## Limits (be honest about these)

- Only the encoded rules (see `RULES.md`) are checked. Income and the affordability test, BKR, residence permits,
  NHG and most of the Beheerbeleid are **not** encoded. Those questions go to GraphRAG.
- Free-text extraction is done by the LLM, so it can make mistakes. The UI shows the facts it used; the form avoids this.
- The rules were written and checked by the assistant. A mortgage expert must review them (`RULES.md`).
- RDFox runs with an academic licence for this prototype only.
