# Evaluation: graph_k5_usecases_20261109_1559

- System: **Vector + document graph (GraphRAG)** (k=5) · answer model `openai/gpt-oss-120b` · judge `qwen/qwen3.8-27b` · embeddings `text-embedding-3-large`
- Ground truth: `qa_usecases_*.json` · questions: 144 · date 2026-11-09 16:07

| Lang | Category | n | Answer correctness | Evidence recall | All evidence found | Avg passages | Avg tokens in | Avg latency (s) |
|---|---|---|---|---|---|---|---|---|
| en | single-hop | 34 | 0.88 | 0.78 | 0.76 | 10.0 | 3602 | 2.8 |
| en | two-hop | 15 | 0.90 | 0.71 | 0.47 | 10.0 | 3878 | 2.7 |
| en | multi-hop | 11 | 0.55 | 0.52 | 0.36 | 10.0 | 4092 | 5.1 |
| en | comparison-aggregation | 3 | 0.83 | 0.96 | 0.67 | 10.0 | 3958 | 7.9 |
| en | unanswerable | 9 | 0.78 | 0.50 | 0.50 | 10.0 | 3329 | 2.3 |
| en | **ALL** | 72 | 0.82 | 0.71 | 0.61 | 10.0 | 3715 | 3.3 |
| nl | single-hop | 34 | 0.96 | 0.97 | 0.94 | 10.0 | 3726 | 2.2 |
| nl | two-hop | 15 | 0.87 | 0.73 | 0.53 | 10.0 | 3907 | 3.0 |
| nl | multi-hop | 11 | 0.27 | 0.45 | 0.27 | 10.0 | 4079 | 3.7 |
| nl | comparison-aggregation | 3 | 0.67 | 0.96 | 0.67 | 10.0 | 3908 | 3.4 |
| nl | unanswerable | 9 | 0.72 | 0.75 | 0.75 | 10.0 | 3517 | 2.2 |
| nl | **ALL** | 72 | 0.79 | 0.82 | 0.72 | 10.0 | 3799 | 2.6 |

**How to read this**
- *Answer correctness*: LLM judge, 1 = correct, 0.5 = partial, 0 = incorrect (average).
- *Evidence recall*: share of the gold evidence passages that retrieval found (no LLM involved).
- *All evidence found*: share of questions where retrieval found **every** gold passage.
- *unanswerable*: the policy has no answer or the question lacks facts; correct = the system says so (and names what is missing). No gold evidence, so the retrieval columns are empty (nan).
