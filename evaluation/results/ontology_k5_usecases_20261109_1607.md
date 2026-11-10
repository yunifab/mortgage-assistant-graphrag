# Evaluation: ontology_k5_usecases_20261109_1607

- System: **Vector + graph + ontology/rules (FIBO, RDFox)** (k=5) · answer model `openai/gpt-oss-120b` · judge `qwen/qwen3.8-27b` · embeddings `text-embedding-3-large`
- Ground truth: `qa_usecases_*.json` · questions: 144 · date 2026-11-09 16:17

| Lang | Category | n | Answer correctness | Evidence recall | All evidence found | Avg passages | Avg tokens in | Avg latency (s) |
|---|---|---|---|---|---|---|---|---|
| en | single-hop | 34 | 0.91 | 0.88 | 0.85 | 10.6 | 4440 | 3.4 |
| en | two-hop | 15 | 1.00 | 0.97 | 0.87 | 10.9 | 5063 | 3.8 |
| en | multi-hop | 11 | 0.86 | 0.86 | 0.64 | 14.5 | 6526 | 4.9 |
| en | comparison-aggregation | 3 | 0.67 | 0.92 | 0.67 | 10.0 | 3907 | 2.7 |
| en | unanswerable | 9 | 0.61 | 1.00 | 1.00 | 10.6 | 3845 | 2.6 |
| en | **ALL** | 72 | 0.88 | 0.91 | 0.82 | 11.2 | 4792 | 3.6 |
| nl | single-hop | 34 | 0.87 | 0.94 | 0.91 | 10.5 | 4462 | 3.7 |
| nl | two-hop | 15 | 0.93 | 0.97 | 0.87 | 10.7 | 5000 | 4.6 |
| nl | multi-hop | 11 | 0.55 | 0.89 | 0.64 | 14.6 | 6483 | 5.5 |
| nl | comparison-aggregation | 3 | 0.83 | 0.96 | 0.67 | 10.0 | 3830 | 2.6 |
| nl | unanswerable | 9 | 0.78 | 1.00 | 1.00 | 10.9 | 4071 | 2.9 |
| nl | **ALL** | 72 | 0.82 | 0.94 | 0.85 | 11.2 | 4808 | 4.0 |

**How to read this**
- *Answer correctness*: LLM judge, 1 = correct, 0.5 = partial, 0 = incorrect (average).
- *Evidence recall*: share of the gold evidence passages that retrieval found (no LLM involved).
- *All evidence found*: share of questions where retrieval found **every** gold passage.
- *unanswerable*: the policy has no answer or the question lacks facts; correct = the system says so (and names what is missing). No gold evidence, so the retrieval columns are empty (nan).
