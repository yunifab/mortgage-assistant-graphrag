"""Control experiment: does giving the LLM the WHOLE policy fix the case-check failures?

Set-ups (same answer model and system prompt for all):
  vector_k10        vector search, 10 passages
  graph_k5          GraphRAG, 5 vector + 5 graph passages
  full              the whole policy (~62k tokens) in the prompt
  full_checklist    the whole policy + a generic checklist of what to check
  ontology_text     ontology + rules: the LLM extracts the case facts from the text, RDFox checks, LLM explains
  ontology_form     ontology + rules with the correct facts (as from the 'Check a case' form)

Each case is run N times (default 3) to measure consistency, and graded by an LLM judge against the
expected outcome (required findings, forbidden claims, verdict).

Case sets:
  use_cases   UC1-UC9 (texts in run_use_cases.py, expected.json, facts in cases.json); used to DESIGN the rules
  holdout     HO1-HO8 (holdout.json): written after the rules, the fairer test

Run:  uv run python evaluation/use_cases/run_control.py                       (UC1-UC9, all set-ups, 3 runs)
      uv run python evaluation/use_cases/run_control.py --set holdout
      uv run python evaluation/use_cases/run_control.py --runs 1 --setups full --cases UC7
"""

import argparse
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from mortgage_assistant import llm, rag, store
from mortgage_assistant.config import settings
from mortgage_assistant.evaluation import JUDGE_MODEL
from mortgage_assistant.ingest.io import load_sections

HERE = Path(__file__).parent
SETUPS = ["vector_k10", "graph_k5", "full", "full_checklist", "ontology_text", "ontology_form"]
CHECKLIST = (
    "\n\nBefore you answer, check systematically EVERY rule in the policy that applies to this case, not only the "
    "topic of the question. Go through: the applicants (age, number of debtors, submission channel and Basis/Plus "
    "conditions, residence, risk rating, BKR), the income, the loan (term, interest-only limits and what counts as "
    "interest-only, maximum loan-to-value for this collateral type and valuation method), the conditions for this "
    "type of collateral, and whether Explain (maatwerk or an exception) is possible. For each item say: OK, "
    "violated, only possible via Explain, or unknown (fact missing). Only report rules that really apply to this case."
)


def full_policy_context() -> str:
    sections = [s for s in load_sections() if s.text]
    return "\n\n---\n\n".join(f"[{s.part} {s.number}, p.{', '.join(map(str, s.pages))}] {s.title}\n{s.text}"
                              for s in sections)


def run_setup(setup: str, question: str, driver, policy: str, facts: dict | None = None) -> str:
    if setup == "ontology_text":
        return rag.answer(driver, question, mode="ontology").answer
    if setup == "ontology_form":
        from mortgage_assistant.rules.case import Case

        return rag.answer(driver, question, mode="ontology", case=Case.from_dict(facts)).answer
    if setup == "vector_k10":
        return rag.answer(driver, question, k=10, mode="vector").answer
    if setup == "graph_k5":
        return rag.answer(driver, question, k=5, mode="graph").answer
    system = (settings.prompts_dir / "rag_answer_system.md").read_text(encoding="utf-8")
    q = question + (CHECKLIST if setup == "full_checklist" else "")
    return llm.chat(system, f"Policy passages:\n\n{policy}\n\n=====\n\nQuestion: {q}").text


def judge(case_q: str, exp: dict, answer: str) -> dict:
    system = (settings.prompts_dir / "judge_case.md").read_text(encoding="utf-8")
    user = (f"CASE:\n{case_q}\n\nEXPECTED VERDICT: {exp['verdict']}\n\nREQUIRED FINDINGS:\n"
            + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(exp["required"]))
            + "\n\nFORBIDDEN CLAIMS:\n"
            + ("\n".join(f"{i + 1}. {f}" for i, f in enumerate(exp["forbidden"])) or "(none)")
            + (f"\n\nNOTE FOR THE GRADER:\n{exp['note']}" if exp.get("note") else "")
            + f"\n\nSYSTEM ANSWER:\n{answer}")
    raw = llm.chat(system, user, model=JUDGE_MODEL, temperature=0.0).text
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        v = json.loads(m.group(0))
        req = [bool(x) for x in v.get("required_found", [])][: len(exp["required"])]
        forb = [bool(x) for x in v.get("forbidden_made", [])][: len(exp["forbidden"])]
        return {"verdict_correct": bool(v.get("verdict_correct")), "required_found": req,
                "forbidden_made": forb, "other_false_claims": v.get("other_false_claims", []),
                "reason": v.get("reason", "")}
    except (AttributeError, ValueError, TypeError):
        return {"verdict_correct": False, "required_found": [], "forbidden_made": [],
                "other_false_claims": [], "reason": "judge_error: " + raw[:200]}


def fully_correct(r: dict) -> bool:
    """Strict: right verdict AND every required finding AND no false claim."""
    return (r["verdict_correct"] and bool(r["required_found"]) and all(r["required_found"])
            and not any(r["forbidden_made"]) and not r["other_false_claims"])


def summarize(rows: list[dict]) -> str:
    by = defaultdict(list)
    for r in rows:
        by[r["setup"]].append(r)
    lines = ["| Set-up | **Fully correct** | Verdict correct | Required findings found | False claims per answer "
             "| Cases fully correct in every run | Empty answers | Approx. tokens in |",
             "|---|---|---|---|---|---|---|---|"]
    for setup in SETUPS:
        rs = by.get(setup)
        if not rs:
            continue
        verdict = sum(r["verdict_correct"] for r in rs) / len(rs)
        req = [x for r in rs for x in r["required_found"]]
        false = sum(sum(r["forbidden_made"]) + len(r["other_false_claims"]) for r in rs) / len(rs)
        per_case = defaultdict(list)
        for r in rs:
            per_case[r["case"]].append(fully_correct(r))
        always = sum(all(v) for v in per_case.values())
        strict = sum(map(fully_correct, rs)) / len(rs)
        empty = sum(not r["answer"].strip() for r in rs)
        lines.append(f"| {setup} | **{strict:.0%}** | {verdict:.2f} | {sum(req) / max(len(req), 1):.2f} | "
                     f"{false:.2f} | {always}/{len(per_case)} | {empty} | "
                     f"{sum(r['tokens_in'] for r in rs) / len(rs):,.0f} |")
    lines.append("\n**Per case: fully correct in how many runs**\n")
    cases = sorted({r["case"] for r in rows}, key=lambda c: int(c[2:]))
    lines.append("| Set-up | " + " | ".join(cases) + " |")
    lines.append("|---|" + "---|" * len(cases))
    for setup in SETUPS:
        rs = by.get(setup)
        if not rs:
            continue
        cells = []
        for c in cases:
            cr = [r for r in rs if r["case"] == c]
            cells.append(f"{sum(map(fully_correct, cr))}/{len(cr)}" if cr else "")
        lines.append(f"| {setup} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def load_case_set(name: str) -> tuple[dict, dict, dict]:
    """(question per case, expected per case, structured facts per case)."""
    if name == "holdout":
        data = json.loads((HERE / "holdout.json").read_text(encoding="utf-8"))["cases"]
        return ({c: d["question"] for c, d in data.items()}, {c: d["expected"] for c, d in data.items()},
                {c: d["facts"] for c, d in data.items()})
    from run_use_cases import CASES  # same case texts as the earlier run

    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))["cases"]
    facts = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
    return CASES, expected, facts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--set", choices=["use_cases", "holdout"], default="use_cases")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--setups", nargs="+", choices=SETUPS, default=SETUPS)
    p.add_argument("--cases", nargs="+", default=None, help="e.g. --cases UC7 UC9")
    args = p.parse_args()
    CASES, expected, facts = load_case_set(args.set)
    cases = args.cases or list(CASES)
    policy = full_policy_context()
    prefix = "control" if args.set == "use_cases" else "holdout"
    out = HERE / f"{prefix}_{datetime.now():%Y%m%d_%H%M}.jsonl"

    rows = []
    with store.get_driver() as driver, open(out, "w", encoding="utf-8") as f:
        for setup in args.setups:
            for cid in cases:
                for run in range(1, args.runs + 1):
                    t0 = time.perf_counter()
                    try:
                        answer = run_setup(setup, CASES[cid], driver, policy, facts.get(cid))
                    except Exception as e:  # record the failure instead of stopping the whole run
                        answer = f"ERROR: {e}"
                    verdict = judge(CASES[cid], expected[cid], answer)
                    row = {"setup": setup, "case": cid, "run": run, "answer": answer, **verdict,
                           "tokens_in": 62000 if setup.startswith("full") else 3500 if setup[:5] in ("vecto", "graph") else 2500,
                           "latency_s": round(time.perf_counter() - t0, 1)}
                    rows.append(row)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"{setup:15} {cid} run{run} verdict={'OK ' if row['verdict_correct'] else 'BAD'} "
                          f"req={sum(row['required_found'])}/{len(expected[cid]['required'])} "
                          f"false={sum(row['forbidden_made']) + len(row['other_false_claims'])} "
                          f"({row['latency_s']}s)", flush=True)
    summary = summarize(rows)
    title = "Control experiment (UC1-UC9)" if args.set == "use_cases" else "Held-out test (HO1-HO8)"
    out.with_suffix(".md").write_text(f"# {title} ({datetime.now():%Y-%m-%d %H:%M})\n\n"
                                      f"answer model `{settings.llm_model}` · judge `{JUDGE_MODEL}` · "
                                      f"{args.runs} runs per case\n\n{summary}", encoding="utf-8")
    print("\n" + summary)


if __name__ == "__main__":
    main()
