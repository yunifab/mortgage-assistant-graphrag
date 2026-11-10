"""Step 4: run the ground-truth questions through the RAG baseline and score them.

Run:  uv run python scripts/run_eval.py                       # RAG baseline, English + Dutch
      uv run python scripts/run_eval.py --mode graph          # GraphRAG (document graph)
      uv run python scripts/run_eval.py --mode vector --k 10  # control: same context size as graph
      uv run python scripts/run_eval.py --lang en --limit 5   # quick test
      uv run python scripts/run_eval.py --gt usecases --mode ontology  # the use-case set (qa_usecases_*.json)

Writes to evaluation/results/:
  <run>.jsonl   one line per question: answer, retrieved chunks, scores
  <run>.md      summary table per category and language (this is the baseline to beat)
"""

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime

from mortgage_assistant import rag, store
from mortgage_assistant.config import settings
from mortgage_assistant.evaluation import JUDGE_MODEL, judge_answer, retrieval_scores
from mortgage_assistant.ingest.io import load_chunks
from mortgage_assistant.rag import AVAILABLE_MODES, RETRIEVAL_MODES

CATEGORIES = ["single-hop", "two-hop", "multi-hop", "comparison-aggregation", "unanswerable"]
GROUND_TRUTH = {"rabobank": "qa_rabobank", "usecases": "qa_usecases"}


def load_questions(gt: str, lang: str) -> list[dict]:
    path = settings.ground_truth_dir / f"{GROUND_TRUTH[gt]}_{lang}.json"
    return json.loads(path.read_text(encoding="utf-8"))["questions"]


def summarize(rows: list[dict], run_name: str, args) -> str:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["lang"], r["category"])].append(r)
        groups[(r["lang"], "ALL")].append(r)

    def avg(items, key):
        values = [i[key] for i in items if i[key] is not None]  # None: no gold evidence (unanswerable)
        return sum(values) / len(values) if values else float("nan")

    lines = [
        f"# Evaluation: {run_name}",
        "",
        f"- System: **{RETRIEVAL_MODES[args.mode]}** (k={args.k}) · answer model `{settings.llm_model}` "
        f"· judge `{JUDGE_MODEL}` · embeddings `{settings.embedding_model}`",
        f"- Ground truth: `{GROUND_TRUTH[args.gt]}_*.json` · questions: {len(rows)} · date {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "| Lang | Category | n | Answer correctness | Evidence recall | All evidence found "
        "| Avg passages | Avg tokens in | Avg latency (s) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for lang in sorted({r["lang"] for r in rows}):
        for cat in CATEGORIES + ["ALL"]:
            items = groups.get((lang, cat))
            if not items:
                continue
            name = f"**{cat}**" if cat == "ALL" else cat
            lines.append(
                f"| {lang} | {name} | {len(items)} | {avg(items, 'correctness'):.2f} | "
                f"{avg(items, 'evidence_recall'):.2f} | {avg(items, 'all_evidence'):.2f} | "
                f"{avg(items, 'n_passages'):.1f} | {avg(items, 'tokens_in'):.0f} | "
                f"{avg(items, 'latency_total'):.1f} |")
    lines += [
        "",
        "**How to read this**",
        "- *Answer correctness*: LLM judge, 1 = correct, 0.5 = partial, 0 = incorrect (average).",
        "- *Evidence recall*: share of the gold evidence passages that retrieval found (no LLM involved).",
        "- *All evidence found*: share of questions where retrieval found **every** gold passage.",
        "- *unanswerable*: the policy has no answer or the question lacks facts; correct = the system says so "
        "(and names what is missing). No gold evidence, so the retrieval columns are empty (nan).",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["en", "nl", "both"], default="both")
    parser.add_argument("--limit", type=int, default=None, help="only the first N questions per language")
    parser.add_argument("--k", type=int, default=settings.top_k)
    parser.add_argument("--mode", choices=list(AVAILABLE_MODES), default="vector")
    parser.add_argument("--gt", choices=list(GROUND_TRUTH), default="rabobank", help="question set")
    parser.add_argument("--name", default=None, help="run name (default: <mode>_k<k>)")
    args = parser.parse_args()

    langs = ["en", "nl"] if args.lang == "both" else [args.lang]
    chunks = load_chunks()
    run_name = f"{args.name or f'{args.mode}_k{args.k}' + ('' if args.gt == 'rabobank' else f'_{args.gt}')}_{datetime.now():%Y%m%d_%H%M}"
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = settings.results_dir / f"{run_name}.jsonl"

    rows = []
    with store.get_driver() as driver, open(out_jsonl, "w", encoding="utf-8") as f:
        for lang in langs:
            questions = load_questions(args.gt, lang)[: args.limit]
            for q in questions:
                t0 = time.perf_counter()
                result = rag.answer(driver, q["question"], k=args.k, mode=args.mode)
                latency = time.perf_counter() - t0
                if q["evidence"]:
                    scores = retrieval_scores(q["evidence"], result.chunks, chunks)
                else:
                    scores = {"evidence_found": [], "evidence_recall": None, "all_evidence": None}
                verdict = judge_answer(q["question"], q["answer"], result.answer)
                row = {
                    "id": q["id"], "lang": lang, "category": q["category"],
                    "question": q["question"], "reference": q["answer"], "answer": result.answer,
                    "mode": args.mode,
                    "retrieved": [{"id": c.id, "citation": c.citation, "score": round(c.score, 4),
                                   "source": c.source, "via": c.via} for c in result.chunks],
                    "n_passages": len(result.chunks),
                    **scores,
                    "correctness": verdict["score"], "judge_label": verdict["label"],
                    "judge_reason": verdict["reason"],
                    "latency_total": round(latency, 2),
                    "tokens_in": result.prompt_tokens, "tokens_out": result.completion_tokens,
                }
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(f"{lang} {q['id']:4} correct={verdict['score']:.1f} "
                      f"recall={scores['evidence_recall'] if scores['evidence_recall'] is None else round(scores['evidence_recall'], 2)} ({latency:.1f}s)")

    summary = summarize(rows, run_name, args)
    (settings.results_dir / f"{run_name}.md").write_text(summary, encoding="utf-8")
    print("\n" + summary)
    print(f"details: {out_jsonl}")


if __name__ == "__main__":
    main()
