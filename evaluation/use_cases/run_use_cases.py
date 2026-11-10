"""Run the ontology use cases through the current RAG / GraphRAG, to see where they fail.

Run:  uv run python evaluation/use_cases/run_use_cases.py
Writes evaluation/use_cases/results.jsonl (answers + retrieved sections per mode).
"""

import json
from pathlib import Path

from mortgage_assistant import rag, store

CASES = {
    "UC1": "Client wants to buy a houseboat (woonboot) with a fixed mooring rented from the municipality. "
           "Valuation: boat €300,000, mooring €50,000; expected lifetime of the boat per the valuation report is 25 years. "
           "They want a €320,000 loan, of which €80,000 interest-only, with a 30-year term. Is this application acceptable? "
           "List every rule that is violated.",
    "UC2": "Regular house, market value €600,000 from a validated valuation report. Loan €450,000: €100,000 interest-only "
           "(aflossingsvrij) plus €200,000 savings mortgage (opbouwproduct) whose savings product is NOT pledged, and "
           "€150,000 annuity. Does this meet the interest-only limit?",
    "UC3": "Detached house, market value €400,000 according to a Rabobank Desktop Taxatie from Calcasa. "
           "The client needs a €380,000 mortgage. Is that within the maximum loan-to-value, and if not, what could the advisor do?",
    "UC4": "Client owns a regular house (main residence) worth €300,000 before renovation and €320,000 after. "
           "They only invest in energy-saving measures costing €25,000. What is the maximum mortgage?",
    "UC5": "The client wants tailor-made financing using assets (maatwerk door inzet van vermogen) and also needs an "
           "exception for his income as a professional football player. Is this combination allowed?",
    "UC6": "Client works abroad for 2 years in the United Kingdom, stays employed by his Dutch employer, and wants to rent "
           "out his house under the diplomat clause. He already did this once and moved back 6 months ago. Can he?",
    # Full application checks: the problem is NOT the topic of the question
    "UC7": "Please check this application. Applicants: a father (45) and his son (17), plus a family friend as third "
           "debtor; submitted by a Rabobank advisor (not via the Intermediair), standard (Basis) conditions. "
           "Regular terraced house, market value €350,000 from a validated valuation report. Loan €340,000 of which "
           "€60,000 interest-only, term 30 years. RRR 12, energy label B. Is everything in order?",
    "UC8": "Please check this application. The client buys a chalet on a holiday park (zoning: recreation only), "
           "market value €200,000 from an NRVT valuation report. Loan €180,000 of which €50,000 interest-only, term "
           "25 years. The client will sell his apartment and live in the chalet permanently. The seller is not a "
           "Rabobank client. Is everything in order?",
    "UC9": "Please check this application. The client buys a woonark with a fixed mooring owned by the municipality "
           "(rented), registered in the ship register, valued by an E.M.C.I. valuer. Loan 85% of the value, fully "
           "repaid in 20 years. The client's Rabo Risk Rating is R18. Can the application be accepted?",
}


ONLY = set(__import__("sys").argv[1:])  # optional: run only some cases, e.g. UC7 UC8


def main() -> None:
    out = Path(__file__).with_name("results.jsonl" if not ONLY else "results_" + "_".join(sorted(ONLY)) + ".jsonl")
    with store.get_driver() as driver, open(out, "w", encoding="utf-8") as f:
        for cid, question in CASES.items():
            if ONLY and cid not in ONLY:
                continue
            for mode, k in (("vector", 10), ("graph", 5)):
                r = rag.answer(driver, question, k=k, mode=mode)
                row = {"case": cid, "mode": f"{mode}_k{k}", "question": question, "answer": r.answer,
                       "sections": [c.citation for c in r.chunks]}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"\n===== {cid} {mode} k={k}\n{r.answer}\n-- sections: {sorted(set(row['sections']))}")


if __name__ == "__main__":
    main()
