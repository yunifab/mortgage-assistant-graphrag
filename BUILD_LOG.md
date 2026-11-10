# Build Log

A step-by-step diary of how we build the Mortgage Advisor Assistant, in plain language.
For each step: **what** we did, **why**, **how to try it yourself**, and **what we learned**.

See [`PLAN.md`](PLAN.md) for the overall plan.

---

## Step 0: Brainstorm and collect resources (2026-11-01) ✅

**What we did**
- Cloned FIBO (the financial industry ontology) into `fibo/`.
- Looked at the treat-almende project for the pattern: ontology + rules (RDFox) + LLM chat (Gradio).
- Collected public mortgage documents into `resources/pdfs/` (ABN AMRO conditions in English,
  EBA guidelines, NHG rules, Fannie Mae matrix). See `resources/README.md`.
- Decided the scope: an assistant for **advisors** asking questions about the **bank's own documents**,
  plus a **rule checker**.

**Why**
- Plain RAG only finds similar text. Our edge is the **graph** (connected articles, FIBO concepts)
  and the **rule checker** (exact calculations).

**What we learned**
- The ABN AMRO PDF is full of cross-references ("please also read article 5.6") and has a
  precedence rule (article 3.3). That's exactly where plain vector search falls short and a graph helps.

---

## Step 0b: Switch the main document to Rabobank (2026-11-03) ✅

**What we did**
- Compared the new Rabobank PDF with the ABN AMRO PDF and switched the main document to Rabobank.
  Updated `PLAN.md`.

**Why**
- ABN AMRO's PDF is a **customer contract** ("what did I agree to?").
  Rabobank's PDF is the bank's **underwriting policy for advisors** ("can this application be accepted?").
  That matches our user (the advisor) and our differentiator (the rule checker).
- It's full of concrete rules (30-year max term, interest-only ≤ 30% / €150,000, LTV 100% / 106%,
  age ≥ 18, residence permit table…) we can take as-is.
- It has graph structure built in: exceptions (🔍 → chapter "Explain"), a definitions list,
  a document checklist, NHG precedence, and a version history.

**What we learned**
- Choose the document by **who it's written for**. A policy for advisors is a better fit than a contract for customers.
- The PDF is in Dutch while we work in English. FIBO's English concept names with Dutch synonyms
  can be the **bridge** between the two languages.
- Watch out: the layout (multiple columns, repeated navigation bar, doubled bold letters, tables)
  makes text extraction harder, so Phase 1 needs care.

---

## Step 0c: Build the ground-truth question set (2026-11-04) ✅

**What we did**
- Followed the instructions in [`docs/QA_PROMPT.md`](docs/QA_PROMPT.md) and wrote **40 test questions** about the
  Rabobank policy, **10 per category**:

  | Category | Ids | What it tests |
  |---|---|---|
  | Single-hop | S01–S10 | Answer is in **one** passage (e.g. max term 30 years) |
  | Two-hop | T01–T10 | Needs facts from **two** separate sections |
  | Multi-hop (3+) | M01–M10 | Needs a **chain** of 3+ facts across the document |
  | Comparison / aggregation | C01–C10 | Combine or contrast info from **several** places |

- Saved two versions with the **same ids and same evidence**:
  - `evaluation/ground_truth/qa_rabobank_en.json`: questions, answers and reasoning in English
  - `evaluation/ground_truth/qa_rabobank_nl.json`: the same, in Dutch
- Each question has: `category`, `question`, `answer`, `evidence` (exact Dutch quotes + page + section
  for each hop) and `hop_reasoning` (why each piece is needed).
- Checked automatically that **all 136 quotes** really appear in the PDF on the cited page (0 misses).

**Why**
- To compare RAG vs. GraphRAG fairly, we need questions with a **known correct answer** and the
  **known correct locations** ("gold sections"). Then we can measure not only *"is the answer right?"*
  but also *"did retrieval find all the needed sections?"* (context recall).
- Single-hop questions are the **control group**: plain RAG should already do well there.
  The two-hop, multi-hop and comparison questions are where we **expect the graph to help**.
- English and Dutch versions let us test whether retrieval also works when the question
  language differs from the document language.

**How to try it yourself**
- Open a JSON file, pick a question, and look up the quoted text on the given page of
  `resources/pdfs/rabobank_mortgage.pdf`.
- Quick count check:
  ```bash
  python -c "import json,collections; d=json.load(open('evaluation/ground_truth/qa_rabobank_en.json',encoding='utf-8')); print(collections.Counter(q['category'] for q in d['questions']))"
  ```

**Choices and notes**
- Page numbers are **physical PDF pages** (1–95), not the numbers printed on the page.
- Quotes are lightly cleaned: € and × restored (the text extraction dropped them),
  words split by hyphenation joined, table rows written as "row label value".
- Questions are **paraphrased** (not copied from the PDF), so vector search can't just match words.
- Some questions contain deliberate **traps**, e.g. C06 (two different energy tables in one section)
  and T01 (the 106% rule does not apply to holiday homes).
- **Left out:** the residence-permit table (2.3) and the BKR tables (2.4.3, 4.1). Their layout came out
  scrambled in the extracted text, so the row/value mapping wasn't reliable.

**Still to do**
- ⚠️ All answers are a **DRAFT**. A colleague or mortgage expert must review them before we use them.
- Double-check items that involve interpretation: T02 (desktop valuation "Plus"),
  M08 (link to section 5.5.15), C01/C04 ("complete" lists cover only the pages read).
- Merge with the team's existing RAG test set (story EV-1).

**What we learned**
- Writing good multi-hop questions is hard: you must make sure **no single paragraph** can answer it.
- Checking quotes automatically is worth it. It catches small copy mistakes that would make the
  ground truth (and every metric built on it) wrong.
- Messy PDF tables are a risk for **both** the ground truth and the KG. Flag them early.

---

## Step 1: Set up the repo (2026-11-05) ✅

**What we did**
- Turned the folder into a proper Python project, using the same tools as treat-almende:
  **uv** (package manager), **Python 3.13**, a `pyproject.toml` with all dependencies.
- Created a clear folder layout (see [`README.md`](README.md)):
  - `src/mortgage_assistant/`: the code, as one Python package
  - `scripts/`: the commands you run, one per step
  - `app/`: the Gradio chat UI
  - `prompts/`: the LLM prompts as plain text files
  - `evaluation/`: ground truth and results
  - `data/processed/`: generated output
  - `docs/`: meeting notes
  - `tests/`: unit tests
- Moved the meeting notes and `QA_PROMPT.md` into `docs/` and the ground truth into `evaluation/ground_truth/`.
- Added `.gitignore` (keeps `.env` with your keys out of git, and the 800 MB `fibo/` clone)
  and `.env.example` (a template without secrets).
- All settings live in one file: `src/mortgage_assistant/config.py`.

**Why**
- **One package plus small scripts** means each step can be run and tested on its own.
  Later, GraphRAG reuses the same parts and only swaps the retrieval.
- **Prompts in text files** are easy to read, review and change without touching code.
- **Secrets only in `.env`**, never in code or git.

**How to try it yourself**
```bash
uv sync --group dev     # installs everything into .venv
uv run pytest           # runs the unit tests (7 tests)
```

**What we learned**
- **Groq no longer offers the Llama models** we had planned, so our key can't use them.
  We now use `openai/gpt-oss-120b` to write answers and `qwen/qwen3.8-27b` as the judge.
  Lesson: list the available models first (`client.models.list()`) instead of assuming.

---

## Step 2: Parse the PDF into sections and chunks (2026-11-05) ✅

**What we did**
- Wrote a parser (`src/mortgage_assistant/ingest/pdf_parser.py`, using **PyMuPDF**) that splits the
  policy into its real sections, each with its **number, title, part and pages**.
  Example: `AB-5.5.12 | Woonboot met vaste ligplaats | Acceptatiebeleid | p.31`.
- Wrote a chunker (`ingest/chunker.py`) that makes **one chunk per section**. Only long sections
  are split (max 1,500 characters, 200 overlap), so a chunk **never mixes two sections**.
- Result: **183 sections, 261 chunks** (median 842 characters).
  - Acceptatiebeleid: 141 chunks
  - Beheerbeleid: 61 chunks
  - Appendices: 55 chunks
  - Version history: 4 chunks

**How the parser recognises the structure** (it uses the PDF's font sizes)

| Font size | Meaning | Example |
|---|---|---|
| 24 pt | Chapter | `Hoofdstuk 2 \| Aanvrager` |
| 12 pt | Section | `2.1 Algemeen` |
| 10 pt | Sub-section | `2.4.1 EVA en SFH` |
| 8.5 pt + 4-part number | Sub-sub-section | `1.4.1.1 Hoogte OverbruggingsHypotheek` |

What it throws away:
- the navigation bar repeated at the top of every page
- the footer
- cover pages and table-of-contents pages
- footnote markers glued to words (`EU-land6` → `EU-land`)

The footnote text itself is kept and attached to the section.

**Why**
- **Section numbers are the key to everything that comes next.**
  - RAG needs them for **citations** ("see 5.5.12, p.31").
  - The evaluation needs them to check whether we found the **gold sections**.
  - GraphRAG needs them to draw **links** ("see 6.2", exceptions, definitions).
- The section ids include the part (`AB-`, `BB-`, `BIJ-`) because the same number, e.g. `1.1`,
  exists in both the Acceptatiebeleid and the Beheerbeleid.
- Each chunk also gets its **heading path** in front of it when embedded (e.g.
  `Acceptatiebeleid > Hoofdstuk 5 … > 5.5.12 Woonboot…`). Then even a short chunk like
  "Maximaal 80%…" still says what it's about.

**How to try it yourself**
```bash
uv run python scripts/parse_pdf.py
```
Then open `data/processed/sections_preview.md` to read every parsed section next to the PDF.

**How we checked it**
- Sections come out in the right order (1.1, 1.1.1, …, 6.2.1.4) and every section has a parent (unit tests).
- **135 of the 136 ground-truth quotes are found word-for-word in a chunk, on the right page.**
  The one miss is a table row that the ground truth had rewritten, which is expected.

**What we learned**
- **Look at the PDF's layout before writing a parser.** The first version assumed two columns,
  but these landscape pages have **three**. Sections then came out in the wrong order
  (e.g. `1.4.1.1` before `1.4`), and the ordering test caught it.
- Font size is a cheap and reliable way to find headings, but it's specific to this document.
  Another bank's PDF would need its own rules.
- **Known limits (fine for a baseline):** tables are read row by row as plain text, so complex tables
  (e.g. the residence-permit table in 2.3) lose their column structure. The 🔍 "see Explain"
  icons are images, so they're not in the text yet. They're a good candidate for GraphRAG links later.

---

## Step 3: Embed the chunks and store them in Neo4j (2026-11-05) ✅

**What we did**
- Wrote `embeddings.py` with two interchangeable providers, chosen with `EMBEDDING_PROVIDER` in `.env`:
  - `openai` (default): **`text-embedding-3-large`** through the OpenAI API, 3,072 dimensions
  - `local`: **BGE-M3** on your laptop
  Both are multilingual, so an English question can find a Dutch passage.
- Wrote `store.py`, which saves the chunks as `(:Chunk)` nodes in Neo4j with a **vector index**,
  plus `vector_search()`. It only deletes our own `:Chunk` nodes, never anything else.
- Wrote `scripts/build_index.py`, which embeds all chunks and loads them in one command.

**Why Neo4j for plain RAG?**
- Neo4j has a built-in vector index, so RAG and GraphRAG use the **same database and the same chunks**.
  GraphRAG only adds relationships on top, and that keeps the comparison fair.

**Why OpenAI embeddings instead of BGE-M3?**
- The plan was local BGE-M3, but the C: drive had only ~0.8 GB free and the model needs ~2.3 GB
  (`There is not enough space on the disk. (os error 112)`). OpenAI needs no download, the policy is
  public, and the cost is tiny: the whole policy is about 0.1M tokens, which is about $0.01.
- You can switch back with `EMBEDDING_PROVIDER=local` in `.env` once there's disk space.
- ⚠️ The index and the questions must use the **same** model. After switching, rebuild the index.

**How to try it yourself**
```bash
uv run python scripts/build_index.py
```
Output: `261 :Chunk nodes`, embedded in about 18 seconds.

In Neo4j Browser (http://localhost:7474) you can look at the result:
```cypher
MATCH (c:Chunk) RETURN c.id, c.heading_path, c.pages LIMIT 10
```

**What we learned**
- Make heavy dependencies **swappable** (one setting, same interface). A blocker like a full disk
  then becomes a one-line change instead of a rewrite.

---

## Step 4: RAG pipeline, chat UI and evaluation script (2026-11-05) ✅

**What we did**
- `rag/pipeline.py` has three small steps:
  1. **retrieve:** embed the question and get the top-5 chunks from Neo4j
  2. **build context:** each chunk gets a citation label like `[Acceptatiebeleid 5.5.12, p.31]`
  3. **generate:** Groq answers **only** from those chunks
- `prompts/rag_answer_system.md` holds the rules for the LLM:
  - only use the passages
  - say so if the answer isn't there
  - cite every fact
  - answer in the question's language
- `app/gradio_app.py` is the chat UI, in the same style as treat-almende:
  - **Chat** tab with a **Sources** panel that shows exactly which passages were used
  - **Settings** tab to choose the model and top-k
  - **About** tab
- `scripts/run_eval.py` runs all 40 questions in **English and Dutch** and scores:
  - **Answer correctness:** an LLM judge compares the answer with our reference answer
    (1 = correct, 0.5 = partial, 0 = wrong). The judge is a *different* model (Qwen), so the
    answer model doesn't grade its own work. The judge prompt is in `prompts/judge_correctness.md`.
  - **Evidence recall:** did retrieval find the gold passages? This needs **no LLM**: each evidence quote
    is matched to the chunk that contains it.
  - Latency and tokens per question.

  It writes a summary table per category and language to `evaluation/results/`.

**Why**
- **GraphRAG will only replace step 1 (retrieve).** Steps 2 and 3 and the prompt stay identical, so any
  difference in the scores comes from the graph.
- Measuring **retrieval separately from the answer** tells us *where* things go wrong:
  - not found → a retrieval problem (where the graph should help)
  - found but answered wrongly → an LLM or prompt problem

**Checked**
- Groq works with both models.
- The judge gives 1.0 to a correct answer and 0.0 to a wrong one.
- The Gradio app starts and responds on http://127.0.0.1:7860.

**How to run it**
```bash
uv run python scripts/ask.py "What is the maximum loan term?"   # one question
uv run python app/gradio_app.py                                   # chat UI on http://127.0.0.1:7860
uv run python scripts/run_eval.py --lang en --limit 5             # quick test
uv run python scripts/run_eval.py                                 # full baseline (80 runs)
```

---

## Step 5: First baseline result (2026-11-05) ✅

**What we did**
- Ran all 40 questions in English and Dutch through the RAG baseline (80 runs, about 4 minutes, 0 judge errors).
- The full table is in `evaluation/results/rag_baseline_20261105_1424.md`.
- Settings: top-5 vector search, `gpt-oss-120b` for answers, `qwen3.8-27b` as judge, `text-embedding-3-large`.

**Result: the baseline to beat**

| Category | Correct (EN) | Correct (NL) | Evidence recall | All evidence found |
|---|---|---|---|---|
| Single-hop | 0.90 | 0.85 | 0.90 | 0.90 |
| Two-hop | 0.80 | 0.75 | 0.81 | 0.50 |
| Multi-hop | 0.65 | 0.50 | ~0.55 | **0.00** |
| Comparison | 0.50 | 0.50 | ~0.61 | 0.30 |
| **All** | **0.71** | **0.65** | 0.72 | 0.42 |

**What it tells us**
- **The harder the question, the worse plain RAG does.** It handles single-hop well, but for
  multi-hop it **never** found all the gold passages (0 of 10 questions).
  That's exactly the gap GraphRAG should close, and now we have a number for it.
- **Answer quality follows retrieval.** When the passages are missing, the answer is partial
  or wrong. So retrieval is the bottleneck, not the LLM.
- **Dutch questions score slightly lower** (0.65 vs 0.71), even though the document is Dutch.
- **Typical failures:**
  - Wrong or missing section, e.g. "houseboat" didn't find *5.5.12 Woonboot*.
    The answer then confidently says "not allowed".
  - Lists spread over the document (C01, C04) come back incomplete.
  - A rule found without its exception (M08 says interest-only is allowed, but in that case it isn't).

**Caveats**
- The ground-truth answers are still a **draft** (not reviewed by an expert).
- The judge is an LLM, so expect some noise. Read a few verdicts in the `.jsonl` file yourself.
- This is one run. Small differences (±0.05) can be chance.

**What we learned**
- Measure **retrieval and answer separately**. "Evidence recall" shows the cause, not just the symptom.
- A good baseline is honest and simple. We didn't tune it, so a GraphRAG gain will be real.

**Next:** GraphRAG step 1, the **document graph** (sections, `PART_OF`, references, Explain exceptions,
definitions) on the same `:Chunk` nodes. Then run the same evaluation and compare.

---

## Step 6: Git repo + document graph in Neo4j (2026-11-05) ✅

**What we did**
- `git init` and a first commit of the RAG baseline (`05eeeb0`).
  `.env`, `.venv` and the `fibo/` clone are ignored.
- Extended the parser:
  - It detects the **🔍 icon** ("an exception is possible, see Explain"). The icon is a small image,
    so we look for the 11×11 pt image and the text line right next to it. It's found in **14 sections**.
  - `ingest/definitions.py` splits **Bijlage 2 (Definitielijst)** into **28 separate terms**.
    The table has fixed columns, so the x-position of a line tells us whether it's a term or a description.
- `graph/links.py` finds links with **simple rules, no LLM**. Each link keeps the text that triggered it
  (`evidence`), so you can check every link:

  | Link | Rule | Count | Example |
  |---|---|---|---|
  | `REFERS_TO` | "(3.1.1)", "paragraaf 5.5.8", "zie definitielijst", "hoofdstuk Life events" | 57 | `AB-5.5.7 → AB-5.5.8` |
  | `HAS_EXCEPTION` | 🔍 icon or "zie hoofdstuk Explain" | 34 | `AB-2.4.2 RRR → AB-6.2.1.1 Aanvrager` |
  | `USES_TERM` | the section uses a term from the definitions list | 118 | `… → Definitie: AOW-leeftijd` |
  | `REQUIRES_DOCUMENTS` | the document checklist part for the section's chapter | 148 | `AB-3.x → Documentenlijst Hoofdstuk 3` |
  | `PART_OF` / `NEXT` | the structure and reading order | 444 / 275 | `chunk → 5.5.12 → 5.5 → chapter 5` |

- **Which Explain section?** The rule (icon) only says *that* an exception exists. *Which* Explain section
  it points to is decided by **similarity**: the 2 Explain sections whose text is most like the section.
  The results make sense, e.g. income sections point to *6.2.1.2 Inkomen*, and the document rules point to *6.2.1.4 Documentenlijst*.
- `graph/loader.py` and `scripts/build_graph.py` write it all to Neo4j **on top of the existing chunks**.
  The vector index is not touched, so RAG keeps working.
- **GraphRAG retriever** (`rag/retrievers.py`):
  1. Take the same 5 vector passages ("seeds").
  2. Follow the graph one step from each seed's section: references, exceptions, parent/child sections,
     definitions, document checklist.
  3. Rank what we found by similarity to the question and add the best 5.

  The graph decides *what is a candidate*; similarity decides *which ones are used*.
- **UI:**
  - a **Retrieval mode** choice:
    - *Vector (RAG)*
    - *Vector + document graph (GraphRAG)*
    - *Vector + graph + ontology*, shown as "coming later"
  - a **🔀 Compare** tab with RAG and GraphRAG side by side
  - the Sources panel shows for each passage whether it came from 🔎 vector or 🕸️ graph, and via which link
- 13 unit tests, including tests for the link rules.

**How to try it yourself**
```bash
uv run python scripts/parse_pdf.py     # now also writes definitions.jsonl
uv run python scripts/build_graph.py   # builds the graph (safe to re-run)
uv run python app/gradio_app.py        # choose the mode in the Chat tab
```
In Neo4j Browser (http://localhost:7474):
```cypher
// every exception link, with the reason
MATCH (s:Section)-[r:HAS_EXCEPTION]->(e:Section) RETURN s.id, s.title, e.title, r.evidence
// the neighbourhood of the houseboat section
MATCH p=(:Section {id:'AB-5.5.12'})-[*1..2]-() RETURN p LIMIT 50
```

**What we learned**
- **The houseboat case:** vector search found *5.5 Onderpanden* but not *5.5.12 Woonboot*.
  The `CHILD` link (general section → its sub-sections) fixed it. A graph can repair a missed hop.
- A rule says *that* there is a link, similarity says *which* target. Combining both is cheap and explainable.
- **A word-boundary bug:** "annuïtaire I/L-toets" also matched inside "**niet-**annuïtaire I/L-toets".
  Small rule details matter, and a test now guards it.

---

## Step 7: GraphRAG vs RAG, with a fair control (2026-11-05) ✅

**What we did**
- Ran the 80 questions (40 EN + 40 NL) in three set-ups:
  - **Vector, 5 passages** (run twice, to see how much it varies between runs)
  - **GraphRAG, 5 + 5 passages**
  - **Vector, 10 passages**: the **control**. GraphRAG gives the LLM 10 passages, so we must check
    whether the gain comes from the *graph* or just from *more text*.
- Result files are in `evaluation/results/` (`vector_k5_…`, `graph_k5_…`, `vector_k10_…`).

**Results (all 40 questions per language)**

| Set-up | Correct EN | Correct NL | Evidence recall EN / NL | All evidence found | Tokens in |
|---|---|---|---|---|---|
| Vector, 5 | 0.71 | 0.65 | 0.72 / 0.71 | 0.42 | ~1,900 |
| GraphRAG, 5 + 5 | 0.72 | 0.75 | 0.79 / 0.78 | 0.50 | ~3,600 |
| **Vector, 10** | **0.75** | **0.75** | **0.87 / 0.89** | **0.62** | ~3,400 |

**What it tells us (honest conclusion)**
- GraphRAG beats the 5-passage baseline. But **plain vector search with 10 passages beats GraphRAG**,
  at the same context size and with fewer tokens.
- So **this first version of the graph mostly helps by adding more text**. Its extra passages are,
  on average, worse than vector search's passages 6–10.
- The two vector-5 runs had identical totals (0.71 / 0.65), so overall scores are stable between runs.
  Per category they move by ±0.05–0.15, so don't read too much into small category differences.

**Why the graph didn't win yet (my best guesses, to verify)**
- `REQUIRES_DOCUMENTS` links every section to a long checklist part. Those chunks often look similar
  to the question, so they **push out** better passages.
- The graph **replaces** vector passages 6–10 instead of adding to them. Passages 6–10 are often good.
- Many multi-hop questions need links the document graph doesn't have yet: concepts across chapters,
  e.g. "senior" → AOW, Explain senior solutions, interest-only rules.

**Next experiments**
1. **Vector 10 + a few graph extras.** The graph only adds what vector search missed.
2. Use `REQUIRES_DOCUMENTS` **only for document questions**, or give graph links weights.
3. Per-question analysis: for which questions did the graph find a gold passage that vector search missed (and the reverse)?
4. **Concept layer** (KG-3): Dutch/English concepts and FIBO, for links across chapters.

**What we learned**
- **Always run a control with the same context size.** Without it we'd have reported
  "GraphRAG +10 points (NL)", which would have been a wrong conclusion.
- A negative result is still a result. It tells the team *where* the graph must improve.
- Keep an eye on your machine: the full disk (0 bytes free) broke a run halfway. Freeing ~11 GB of old
  Hugging Face models fixed it.

---

## Step 8: Use cases for the ontology + rules (2026-11-05) ✅

**What we did**
- Wrote 9 made-up client cases (UC1–UC9), each based on real policy rules, and **ran them through the
  current system** (vector k=10 and GraphRAG) instead of guessing how it would do.
  Script: `evaluation/use_cases/run_use_cases.py`.
- Wrote everything down in [`docs/ONTOLOGY_USE_CASES.md`](docs/ONTOLOGY_USE_CASES.md): results, rule sketches
  in Datalog, more use cases, how to measure, and a first sprint slice.
- Checked the RDFox in treat-almende: version 7.5b works. The licence is an **academic licence in
  someone else's name**, so we need to check before using it for bank work.

**What we found**
- **Single-topic cases** (houseboat, energy 106%, diplomat clause…): today's system is already good,
  including the arithmetic. An ontology adds little here.
- **Full application checks** are where it fails:
  - **UC7:** both modes missed that an applicant is **17**, and cited a *family-loan* rule as if it applied
    to the mortgage (false violations).
  - **UC9:** GraphRAG said "**accept**" while the risk rating R18 needs the **Explain** route. The RRR
    section simply wasn't retrieved.
  - **UC2:** GraphRAG missed that a savings mortgage with an unpledged savings product counts as interest-only.

**Why rules help there**
- **Every** rule that applies is checked, not just the ones that look like the question.
- Rules have a **scope** (the class they apply to).
- They give **three outcomes** (OK / violated / via Explain) and report **missing facts**.
- They're **consistent** and can **explain** each finding.

**What we learned**
- **Test before you claim.** We expected the LLM to fail on arithmetic, but it didn't. It failed on
  *completeness* and *scope*. That changes the pitch: "complete, consistent, explainable case checks",
  not "better answers".
- Check licences before you reuse tools from another project.

---

## Step 9: RDFox running locally (2026-11-05) ✅

**What we did**
- Agreed: the academic RDFox licence may be used **for prototyping only**.
- Started RDFox 7.5b as a server and tested it end to end over REST: create a datastore, load Turtle,
  load a Datalog rule, query with SPARQL, delete. The age rule from UC7 flagged only the 17-year-old.
- Wrote the steps in [`docs/RDFOX_SETUP.md`](docs/RDFOX_SETUP.md) and added the `RDFOX_*` settings to `.env.example`.

**How to try it yourself**
```powershell
cd RDFox-win64-x86_64-7.5b
.\RDFox.exe -persistence off -server-directory "" -role admin -password admin daemon
```

**What we learned**
- Without `-server-directory ""` RDFox refuses to start (*"directory appears to be uninitialized"*).
  With persistence off it doesn't need a folder.
- With curl, send Turtle/Datalog with `--data-raw`: `--data '@prefix…'` is read as a file name.

---

## Step 10: Control: does the whole policy in the prompt fix case checks? (2026-11-05) ✅

**What we did**
- Before building the ontology, we tested the strongest LLM-only alternative: the **whole policy (~62k tokens)**
  in the prompt, with and without a checklist. We compared it with vector (10 passages) and GraphRAG.
- 9 cases × 4 set-ups × **3 runs** each, graded by a judge model against `evaluation/use_cases/expected.json`
  (the expected verdict, the required findings and the **false claims** an answer must not make).
- Added a **strict score**: *fully correct* = right verdict + every required finding + no false claim.
  "Verdict correct" alone was too generous: UC7 said "reject" for the wrong reasons.
- Script: `evaluation/use_cases/run_control.py`; report: `evaluation/use_cases/control_20261105_1638.md`.

**Result**

| Set-up | Fully correct | Cases right in all 3 runs |
|---|---|---|
| Vector, 10 | 70% | 5/9 |
| GraphRAG | 67% | 6/9 |
| Whole policy | 70% | 4/9 |
| Whole policy + checklist | 59% | 2/9 |

- The whole policy fixes some misses (age 17, RRR) but creates new errors (a wrong maximum in UC4, dropped
  term rules in UC1). It's **less consistent** and costs ~18× more tokens.
- **No LLM-only set-up is reliable**: at most ~70% fully correct, and answers change between identical runs.
- So the bottleneck is **reliably applying every rule**, not only finding it. That's what a rule engine does.

**What we learned**
- **Grade strictly.** A right verdict with wrong reasons is not a right answer, especially in a bank.
- **Run each case more than once.** One run hides inconsistency, and consistency matters most for case checks.
- **A held-out test is needed.** Our rules will be designed from these 9 cases, so the real test of the
  ontology is a new set of cases written afterwards.

---

## Step 11: Feature 3: ontology + business rules (FIBO + RDFox) (2026-11-05) ✅

**What we built** (details in [`ontology/README.md`](ontology/README.md))

| Layer | File | What |
|---|---|---|
| 1. FIBO slice | `ontology/fibo_slice.ttl` | 17 FIBO terms, **extracted** from the local FIBO clone by `scripts/extract_fibo_slice.py` |
| 2. Our ontology | `ontology/rabo_mortgage.ttl` | 38 classes built on FIBO (e.g. `rabo:Houseboat ⊂ fibo:Collateral`), NL/EN labels + synonyms, the **limits as data** (LTV norms per collateral × valuation, interest-only allowed yes/no), 27 rules with their source section |
| 3. Rules | `ontology/rules/*.dlog` | Datalog for RDFox: applicant, loan, collateral, Explain, diplomat clause |
| 4. Case facts | `src/mortgage_assistant/rules/case.py` | JSON → RDF |

- **Four outcomes** per rule: ❌ violated · 🔍 only via Explain · ❓ missing fact · ✅ OK.
  Exact **computed values** come from the rules too (maximum loan, interest-only total, what-if with a valuation report).
- **Engine** (`rules/engine.py`): a temporary RDFox datastore per check. It takes about 0.3 s and is the same every time.
- **LLM only at the edges:**
  - `extract.py` turns free text into facts. A grounding check drops facts that aren't in the text.
  - `answer.py` explains the findings. The prompt forbids adding findings or doing its own maths, and gives problems and passed checks separately.
- **Bridge to the document graph:** each rule's `rabo:source` = a Neo4j `:Section` id. The explanation fetches and cites that section.
  `scripts/build_ontology_graph.py` also loads concepts, FIBO terms and rules into Neo4j (`(:Rule)-[:SOURCE]->(:Section)`).
- **UI:**
  - a new **✅ Check a case** tab (form → verdict + findings table + explanation)
  - the ontology mode in Chat (case → rules; question → GraphRAG + ontology synonyms)
  - a 3-column Compare tab
- **Review table:** `ontology/RULES.md` (generated). **Tests:** `tests/test_rules.py` (each case is a test); 34 tests in total.
- **Held-out set:** `evaluation/use_cases/holdout.json` (HO1–HO8, written after the rules).

**Results** (strict "fully correct", 3 runs per case)

| | LLM-only (best) | GraphRAG | Ontology (form) | Ontology (text) |
|---|---|---|---|---|
| UC1–UC9 (design cases) | 70% | 67% | **100%** | **89%** |
| HO1–HO8 (held-out) | 42% | 33% | **92%** | **100%** |
| 40 policy questions (EN / NL) | 0.75 / 0.75 | 0.72 / 0.75 | n/a | **0.75 / 0.71** (hybrid) |

**What went wrong on the way (and the fixes)**
- **Ordinary questions got worse at first (0.61):** 15/80 general questions were treated as a "case" and answered
  from rule findings only. Fix: the **hybrid** answer (findings + GraphRAG passages) brought it back to 0.75 / 0.71.
- **The explanation LLM read ✅ as ❌** (e.g. "interest-only allowed for this collateral ✅" became "not allowed for apartments").
  Fix: problems and passed checks in separate blocks, and rule labels worded as the condition that must hold.
- **Extraction guessed facts** (the text said "valuation: €300,000", the LLM wrote "valuation report"). Fix: a grounding
  check in code. A generic "valuation report" for a houseboat is now ❓ ("must be by an E.M.C.I. valuer"), not ❌.
- **A crash** when energy facts were incomplete. Fix: optional fields plus a ❓ rule.
- **Our own reference answer for UC4 was too strict:** the policy makes the norm depend on the valuation method, which
  the case doesn't give. The engine now gives exact scenarios (€325k / €270k), and the reference is updated (with a note).
- A Datalog **negation loop** (a rule saying "not violated" about the fact it derives itself). Fix: a helper fact.

**What we learned**
- **Rules make case checks reliable; the LLM parts are where the errors are.** On the held-out cases every remaining
  error came from extraction or explanation, never from the rule engine.
- **Keep limits as data, not code** (LTV norms, interest-only per type). One LTV rule then serves every collateral type,
  and adding a type means adding a row.
- **Hybrid beats either alone:** rules for what's encoded, retrieval for everything else.
- **Every fix needs a re-measure,** and a fix that a test case revealed makes that case no longer "held-out".

**Open points**
- A mortgage expert should review `ontology/RULES.md` and the expected outcomes. We also need a **blind** case set written by someone else.
- Not encoded yet: income/I-L test, BKR, residence permits, NHG, most of the Beheerbeleid.
- Make the routing explicit (question / case / both) and visible, instead of implicit in the extraction step.
- RDFox runs on an academic licence for prototyping only.

---

## Step 12: A collateral taxonomy in four dimensions (2026-11-05) ✅ (draft for review)

**What we did**
- Read all of chapter 5 (5.2, 5.4, 5.5.1–5.5.15) and modelled the property types as a **taxonomy** in
  [`ontology/taxonomy_collateral.ttl`](ontology/taxonomy_collateral.ttl): 16 building types (was 6) plus valuation types.
  The readable tree is in [`ontology/TAXONOMY.md`](ontology/TAXONOMY.md), generated from the ontology.
- **Four independent dimensions.** One property is in one class per dimension:

  | Dimension | Classes (examples) | Policy |
  |---|---|---|
  | building type | regular house, apartment, home with shop/practice, farmhouse (residential / agricultural ≤ 3 ha), business dwelling (private / mixed), mobile home, recreation home, water home, houseboat, garage box, other business property | 5.5.2–5.5.14 |
  | use | partly let | 5.5.15 |
  | construction | new build: project, transformation, turnkey, self-build, CPO, demolition | 5.5.1 |
  | legal right | erfpacht, opstal (for utilities) | 5.2 |

- **The limits are data on the classes.** Examples: LTV norms; allowed valuation; interest-only yes/no; letting yes/no; Plus only;
  NHG only; maximum term; maximum hectares.
- **The rules use the taxonomy** (`rules/35_taxonomy.dlog`, 9 new rules, 36 in total):
  - limits on a **parent** class apply to every sub-class (e.g. the 80% norm and "no interest-only" on *business dwelling*)
  - when several LTV norms apply, the **lowest wins** (a regular house at 100% that is partly let → 85%)
  - the valuation method must be allowed for **every** class (a partly let house can't use a desktop valuation)
  - the 5.4 exclusions for a desktop valuation across dimensions (new build, erfpacht/opstal, value > €1M, loan > 90%)
- The case form, the LLM extraction and Neo4j know the new fields and types (65 concepts, 36 rules in Neo4j).
- **13 new tests** (`tests/test_taxonomy.py`), 47 tests in total, all passing. All 17 earlier cases give the same verdict.

**What we learned**
- **"Rental home" was not a building type but a use.** Splitting the dimensions removed that confusion,
  and the "lowest norm wins" rule then followed naturally.
- **A new rule found a real issue in an old case:** UC3 (desktop valuation, a loan of 95% of the value) now also
  reports that a desktop valuation isn't allowed above 90% (5.4). That's correct, and the old version missed it.
- **Reusing one predicate name for two meanings breaks Datalog:** `maxLTV` was both the norm and the computed
  limit, which created a loop through the MIN aggregate. RDFox refused the rules with a clear message. Fix: a separate `effectiveLTV`.

**To review (it's a draft)**
- Check every class and limit in `ontology/TAXONOMY.md` against chapter 5.
- Simplifications:
  - the 80% of the "privately used part" (5.5.8): enter that part's value as the market value
  - the 85% "in verhuurde staat" (5.5.15): uses the market value given
  - "delivered in the current or previous calendar year" (5.4): treated as "new build"

---

## Step 13: Ontology slides for the product owner, and a what-if fix (2026-11-08) ✅

**What we did**
- Five diagram slides in the deck ([`docs/presentation/mortgage_assistant.pptx`](docs/presentation/mortgage_assistant.pptx)),
  in the visual style of the Almende/TREAT deck:
  - the foundational ontology (FIBO terms + our `rabo:` terms, in 4 families)
  - the collateral taxonomy tree
  - T-Box / A-Box reasoning, with real RDFox output
  - policy text → data + rule + link
  - case → RDF triples → findings
- **Fix:** the what-if "with a full valuation report" now keeps the other norms that apply. A partly let house stays at
  85% (€340,000), it does not jump to 100%. Regression test added (48 tests).

**What we learned**
- Drawing the real engine output for a slide found the bug: checking the output by eye is a useful test.

---

## Step 14: A question set from the use cases, for us and the RAG team (2026-11-08) ✅ (draft for review)

**What we did**
- **72 questions** from UC1–UC9 (8 per use case), in English and Dutch. Each use case gets variants:
  the case reworded, one rule alone, a boundary value, one fact changed, a calculation, a fact lookup, a list/compare,
  and one **unanswerable** question (facts missing, or not in the policy).
- **Two formats, one source:**
  - [`evaluation/ground_truth/qa_usecases_full.json`](evaluation/ground_truth/qa_usecases_full.json) is the master
    (for us): question type, `derived_from`, expected verdict, the rule-engine findings, the structured case, both languages.
  - `qa_usecases_en.json` / `qa_usecases_nl.json` are for the RAG team, in the same format as `qa_rabobank_*.json`,
    plus the category `unanswerable`. They are generated by `scripts/export_usecase_qa.py`; never edit them by hand.
- **How the answers were made:** for the 38 questions with a structured case, the rule engine proposed the verdict and
  findings, and every one agreed with the answer written from the policy text. Every answer has verbatim quotes.
- **Checks** (`tests/test_usecase_qa.py`, 90 tests in total, all passing):
  - every quote is in the policy text on the given page
  - the RAG files match the master
  - with RDFox running, the engine still gives each expected verdict and findings
- **Explanation of the use cases:** [`docs/USE_CASES.md`](docs/USE_CASES.md) (one card per case: situation, trap,
  correct answer, results), and a new table slide "Nine test cases, each with a trap" in the deck.

**What we learned**
- **Unanswerable questions are worth adding.** A good assistant says "I can't decide, I need X" instead of guessing;
  the old set never tested that.
- **The rule engine is a good answer-checker, but not an independent one.** It proposed the expected answers, so a
  person still has to review them (the status is draft).

**Watch out**
- These are **design cases**: the rules were built from UC1–UC9, so this set favours the ontology approach.
  Report it separately from the held-out cases (HO1–HO8).
- `scripts/run_eval.py` reads only `qa_rabobank_*.json` for now; running the approaches on this set is a next step.

---

## Step 15: The three approaches on the use-case question set (2026-11-09) ✅ (one run)

**What we did**
- `scripts/run_eval.py --gt usecases` runs the 72 use-case questions (EN + NL = 144 answers) per approach.
  The summary table has a new category `unanswerable` (no gold evidence → the retrieval columns are empty).
- The judge prompt (`prompts/judge_correctness.md`) got one exception: when the reference says the policy has no
  answer or facts are missing, a system answer that says so is correct, and a definite answer is wrong.
  The old question set has no such references, so its scores are not affected.
- **One run per approach**, not three (to save time). Small differences are noise.

**Results** (answer correctness, judge `qwen3.8-27b`, answers `gpt-oss-120b`; files `evaluation/results/*_usecases_20261109_*.md`)

| Question type | n | Vector (k=5) | GraphRAG | Ontology |
|---|---|---|---|---|
| case_check (full application) | 18 | 0.47 | 0.61 | **0.92** |
| boundary | 18 | 0.83 | 0.89 | 0.92 |
| one_fact_change | 38 | 0.83 | 0.82 | 0.83 |
| single_rule | 22 | 0.89 | 0.80 | 0.89 |
| calculation | 12 | **1.00** | **1.00** | 0.79 |
| fact_lookup | 12 | 0.92 | 0.88 | 0.96 |
| list_compare | 6 | 0.75 | 0.75 | 0.75 |
| unanswerable | 18 | 0.69 | 0.75 | 0.69 |
| **All** | 144 | 0.80 | 0.81 | **0.85** |

**What we learned**
- **The ontology wins where the use cases said it would: full application checks** (0.92 vs 0.47 / 0.61), e.g. UC7
  (the hidden age problem): 0.75 vs 0.41 / 0.47. On plain lookups and single rules all three are about equal.
- **Most ontology misses come from reading the question, not from the rules:**
  - The Dutch phrase "gevalideerd rapport" was extracted correctly but then **dropped by the grounding check** in
    `rules/extract.py` (`VALUATION_EVIDENCE` has "validated" but not "gevalideerd"), so the engine said "valuation
    method missing" (UC2-03, UC7-04, UC7-05 in Dutch). A one-line fix.
  - UC2-03 (NL): the extractor read "IS verpand" (pledged) as not pledged.
- **Calculations are worse with the ontology** (0.79): UC4-05 has a kitchen renovation next to the energy measures,
  and the case model has only one "value after renovation", so the engine computed the wrong base. The RAG answers
  did the arithmetic from the text correctly.
- **Unanswerable questions are hard for all three** (~0.7): the systems still tend to give a definite answer
  (e.g. UC8-08: "permanent living is not allowed" while the zoning was not given).

**Watch out**
- These are design cases (they favour the ontology), and it is one run; report them separately from HO1–HO8.

---

<!-- Next steps will be added below as we build. -->
