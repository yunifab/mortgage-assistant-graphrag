# Mortgage Advisor Assistant: Project Plan

> **Goal:** a chat assistant that helps a **mortgage advisor** find correct, complete answers
> in the bank's mortgage policy quickly, and **check a case against the rules**.
> Every answer comes with sources (section numbers).

> **Main document:** Rabobank *Acceptatie- en Beheerbeleid* (Acceptance and Management Policy),
> 14 September 2026, 95 pages, in Dutch (`resources/pdfs/rabobank_mortgage.pdf`).
> These are the bank's own underwriting rules, written for advisors. The advisor asks in **English**;
> the assistant answers in English and cites the Dutch sections.

Status: 🟡 planning · Last updated: 2026-11-03

---

## 1. Why this is better than "just RAG"

| | Plain RAG (vector search) | Our assistant |
|---|---|---|
| Finds the most similar text chunk | ✅ | ✅ |
| Follows "see definition list" / "see chapter Explain" | ❌ | ✅ **document graph** |
| Knows a rule has an exception (🔍 → chapter 6 "Explain") | ❌ | ✅ **document graph** |
| Knows "if Rabobank is stricter than NHG, Rabobank wins" | ❌ | ✅ **document graph** |
| Links Dutch text to English questions, and across documents (NHG, EBA) | ⚠️ | ✅ **FIBO concept graph** |
| Calculates "is LTV 103% allowed?" | ❌ (LLMs guess at maths) | ✅ **rule checker** |

**The idea in one line:** *vector search finds the text, the graph finds what's connected,
FIBO keeps the graph tidy, and the rule checker does the maths.*

---

## 2. The big picture

```
                        ┌──────────────── Gradio chat ────────────────┐
                        │   advisor asks a question / enters a case   │
                        └──────────────────────┬──────────────────────┘
                                               │
                                       LLM assistant (agent)
                         ┌─────────────────────┼─────────────────────┐
                         ▼                     ▼                     ▼
                 ① Vector search        ② Graph expansion       ③ Rule checker
                 (find best article)    (cross-refs, overrides, (LTV, NHG limit…)
                                         glossary, FIBO concepts)
                         └────────── Neo4j ────┘                  RDFox + FIBO
                                               ▲                     ▲
                                               │                     │
             PDFs ─► parse into chapters/sections ─► chunks + links  FIBO slice + rules
             (Rabobank policy, later NHG + EBA)
```

| Component | Tool | Why |
|---|---|---|
| Chat interface | **Gradio** | Same as treat-almende |
| Text + document graph + vectors | **Neo4j** | Team standard; has a built-in vector index |
| Ontology + rule reasoning | **RDFox** + FIBO | Real rule engine (Datalog); same pattern as treat-almende |
| LLM | your LLM API | Answers, concept tagging, tool calling |

---

## 3. The phases (step by step)

Each phase ends with something you can **see and try**.

### Phase 0: Setup
- Project folder, git, Python environment (uv), `.env` for keys
- Check that Neo4j, RDFox and the LLM API are reachable
- ✅ *Done when:* a small script says "Neo4j OK, RDFox OK, LLM OK"

### Phase 1: Read the PDF properly *(the hardest "boring" step)*
- The Rabobank PDF has a messy layout: 2–3 columns, a navigation bar repeated on every page,
  doubled letters in bold headings ("AAcccceeppttaattiiee"), many tables, footnotes
- Use a better PDF tool than plain text extraction, and remove the noise
- Split it into its **3 parts**: Acceptatiebeleid (acceptance rules), Beheerbeleid (management rules),
  Bijlagen (appendices: definitions list, document checklist)
- Then into **part → chapter → section** (e.g. 1.1.3), keeping tables and footnotes
- ✅ *Done when:* we can print any section by number, e.g. "1.1.3 Aflossingsvrij lenen", cleanly

### Phase 2: Plain RAG baseline + Gradio chat
- Turn sections into chunks with embeddings (a model that handles **Dutch + English**)
  and store them in Neo4j's vector index
- First Gradio chat: English question → vector search → English answer with section numbers
- ✅ *Done when:* you can chat with the PDF. This is our **baseline to beat**

### Phase 3: Document graph
- Add links in Neo4j:
  - `PART_OF`: section → chapter → part
  - `REFERS_TO`: "see chapter Onderpand", "see definition list", footnotes
  - `HAS_EXCEPTION`: rules marked 🔍 → their exception in chapter 6 "Explain"
  - `DEFINES`: definitions list (Appendix 2) → the sections that use the term
  - `REQUIRES_DOCUMENT`: topic → required documents and validity (Appendix 3)
  - `CHANGED_IN`: version history (what changed per section, per month)
- ✅ *Done when:* we can see the graph in Neo4j Browser and ask "what does section 1.1.3 connect to?"

### Phase 4: FIBO concept layer
- Pick a **small FIBO slice** (mortgage, loan, collateral, LTV, borrower, income, guarantee…) and add
  our own concepts where FIBO has gaps (e.g. NHG, interest-only loan part, BKR registration)
- Each concept gets an **English name (FIBO) + Dutch synonyms** (e.g. interest-only ↔ *aflossingsvrij*,
  collateral ↔ *onderpand*). This makes FIBO the **bridge between Dutch text and English questions**
- LLM tags each section with the concepts it covers, choosing **only from our FIBO list**
- ✅ *Done when:* "show all sections about interest-only loans" works through concepts

### Phase 5: GraphRAG assistant
- Retrieval = vector search **+ graph expansion** (references, exceptions, definitions, concepts)
- Answer shows which sections were used and why
- ✅ *Done when:* the assistant gives complete answers where plain RAG missed something

### Phase 6: Evaluation, round 1
- Write 30–50 advisor questions with correct answers (by type: definition, reference,
  exception, required documents, what changed)
- Score plain RAG against GraphRAG
- ✅ *Done when:* we have a results table showing where the graph helps

### Phase 7: More documents, linked through FIBO
- Add key **NHG** sections (Rabobank section 1.1.2 says: NHG rules apply too, but stricter Rabobank
  rules win) and the **EBA Guidelines** (English)
- They connect to the **same FIBO concepts**, so we can do cross-document questions
- ✅ *Done when:* "for an NHG mortgage, which rule applies, Rabobank's or NHG's?" works

### Phase 8: Rule checker
- Take ~10–15 rules **straight from the Rabobank policy**, each with its section number, e.g.:
  - max term 30 years (1.1)
  - interest-only ≤ 30% of market value and ≤ €150,000 (1.1.3)
  - max loan 100% of market value, 106% with energy-saving measures (1.3)
  - applicant ≥ 18 years (2.1); 1–2 borrowers, 3–5 only via intermediary with Plus conditions (2.2)
  - residence permit type → allowed? income counted? (2.3)
  - test interest rate: fixed > 10 years → current rate, else AFM rate (1.2)
- Rules run in **RDFox** (Datalog) on top of FIBO, like the WHO rules in treat-almende
- The advisor gives case facts in the chat → the assistant calls the rule checker as a **tool**
  → ✅/❌ per rule + the reason + the source section + any 🔍 exception that might apply
- ✅ *Done when:* "client: 2 borrowers, market value €X, loan €Y, interest-only €Z" gives a
  correct, explained verdict

### Phase 9: Final evaluation + demo
- Rerun the evaluation, including rule questions
- Write up the results for the KG team
- ✅ *Done when:* demo plus write-up are ready

### Out of scope (for now)
- Processing client documents (payslips, valuation reports)
- Comparing banks (the ABN AMRO conditions could come back later for this)
- Real customer data. **We only use public documents and made-up cases.**

---

## 4. How we work together

- We build **one phase at a time**. Before each phase I explain *what* we build and *why*;
  after it I show you the result and what you can try.
- Every step is written down in [`BUILD_LOG.md`](BUILD_LOG.md) in plain language, so you can learn from it
  and explain it to your team.
- You review and decide at the end of every phase before we move on.

## 5. Resources

- Source documents: [`resources/README.md`](resources/README.md)
- FIBO: [`fibo/`](fibo) (EDM Council clone, untouched)
- Inspiration: `treat-almende` (HeLiFit + RDFox rules + Gradio)
