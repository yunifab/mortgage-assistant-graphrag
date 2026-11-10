# Evaluation: vector_k5_usecases_20261109_1552

- System: **Vector search (RAG)** (k=5) · answer model `openai/gpt-oss-120b` · judge `qwen/qwen3.8-27b` · embeddings `text-embedding-3-large`
- Ground truth: `qa_usecases_*.json` · questions: 144 · date 2026-11-09 15:59

| Lang | Category | n | Answer correctness | Evidence recall | All evidence found | Avg passages | Avg tokens in | Avg latency (s) |
|---|---|---|---|---|---|---|---|---|
| en | single-hop | 34 | 0.88 | 0.75 | 0.74 | 5.0 | 1951 | 2.1 |
| en | two-hop | 15 | 0.80 | 0.71 | 0.47 | 5.0 | 1901 | 2.4 |
| en | multi-hop | 11 | 0.41 | 0.52 | 0.36 | 5.0 | 2068 | 3.3 |
| en | comparison-aggregation | 3 | 0.67 | 0.96 | 0.67 | 5.0 | 1845 | 3.0 |
| en | unanswerable | 9 | 0.72 | 0.50 | 0.50 | 5.0 | 1660 | 1.6 |
| en | **ALL** | 72 | 0.76 | 0.70 | 0.60 | 5.0 | 1917 | 2.3 |
| nl | single-hop | 34 | 1.00 | 0.97 | 0.94 | 5.0 | 1939 | 1.8 |
| nl | two-hop | 15 | 0.77 | 0.73 | 0.53 | 5.0 | 1891 | 2.6 |
| nl | multi-hop | 11 | 0.50 | 0.45 | 0.27 | 5.0 | 2072 | 4.1 |
| nl | comparison-aggregation | 3 | 0.83 | 0.96 | 0.67 | 5.0 | 1848 | 3.1 |
| nl | unanswerable | 9 | 0.67 | 0.75 | 0.75 | 5.0 | 1769 | 1.5 |
| nl | **ALL** | 72 | 0.83 | 0.82 | 0.72 | 5.0 | 1924 | 2.3 |

**How to read this**
- *Answer correctness*: LLM judge, 1 = correct, 0.5 = partial, 0 = incorrect (average).
- *Evidence recall*: share of the gold evidence passages that retrieval found (no LLM involved).
- *All evidence found*: share of questions where retrieval found **every** gold passage.
- *unanswerable*: the policy has no answer or the question lacks facts; correct = the system says so (and names what is missing). No gold evidence, so the retrieval columns are empty (nan).
