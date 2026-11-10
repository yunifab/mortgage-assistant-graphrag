# Mortgage Advisor Assistant (RAG → GraphRAG)

A chat assistant that helps a mortgage **advisor** answer questions about the
**Rabobank Acceptatie- en Beheerbeleid** (the bank's mortgage policy, public PDF).

We build it in stages and measure each one on the same test questions:

1. **RAG baseline** ✅: vector search over the policy + an LLM answer with citations.
2. **GraphRAG** ✅ (document graph): sections, references, exceptions, definitions in Neo4j.
   Next: a concept layer (Dutch/English synonyms, FIBO).
3. **Ontology + rules** ✅: the policy's hard rules as an ontology on **FIBO**, checked by **RDFox** (Datalog).
   A case is checked against every encoded rule; the LLM only explains. See [`ontology/README.md`](ontology/README.md).

- Plan: [`PLAN.md`](PLAN.md)
- Step-by-step diary (what, why, how, what we learned): [`BUILD_LOG.md`](BUILD_LOG.md)

## Repo structure

```
.
├── src/mortgage_assistant/   # the Python package
│   ├── config.py             # settings, read from .env
│   ├── models.py             # data shapes: Section, Chunk, Definition
│   ├── ingest/               # PDF → sections → chunks, definitions list
│   ├── graph/                # document graph: link rules + Neo4j loader
│   ├── evaluation.py         # scoring: evidence recall + LLM judge
│   ├── embeddings.py         # text → vectors (OpenAI, or local BGE-M3)
│   ├── store.py              # Neo4j: save chunks + vector search
│   ├── llm.py                # Groq LLM call
│   ├── rag/                  # retrievers (vector, graph, ontology) + answer pipeline
│   └── rules/                # ontology mode: case facts -> RDFox -> findings -> explanation
├── ontology/                 # FIBO slice, rabo: ontology (Turtle), Datalog rules, RULES.md
├── prompts/                  # LLM prompts as plain text files
├── scripts/                  # command-line entry points (ingest, ask, evaluate)
├── app/                      # Gradio chat UI
├── evaluation/
│   ├── ground_truth/         # 40 test questions (EN + NL)
│   ├── results/              # outputs of evaluation runs
│   └── use_cases/            # case checks: UC1-UC9, held-out HO1-HO8, control experiment
├── data/processed/           # parsed sections and chunks (generated)
├── resources/pdfs/           # source PDFs (public documents)
├── docs/                     # meeting notes, refinement plan, prompts used
└── tests/                    # unit tests
```

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), Python 3.13, a running Neo4j 5.11+, a Groq API key, an OpenAI
API key (embeddings) and, for the ontology mode, RDFox (licence needed).

```bash
uv sync                      # install dependencies into .venv
cp .env.example .env         # then fill in your keys and Neo4j password
```

## Usage

```bash
uv run python scripts/parse_pdf.py      # 1. PDF -> sections, chunks, definitions (data/processed/)
uv run python scripts/build_index.py    # 2. embed chunks -> Neo4j vector index
uv run python scripts/build_graph.py    # 3. document graph in Neo4j
uv run python scripts/build_ontology_graph.py    # 4. (optional) ontology concepts + rules in Neo4j
# RDFox must run for the ontology mode: see docs/RDFOX_SETUP.md
uv run python app/gradio_app.py         # chat UI: http://127.0.0.1:7860
uv run python scripts/run_eval.py --mode graph   # evaluate questions (modes: vector, graph, ontology)
uv run python evaluation/use_cases/run_control.py --set holdout   # evaluate case checks
uv run pytest                           # unit tests
```

See [`BUILD_LOG.md`](BUILD_LOG.md) for what each step does and why.
