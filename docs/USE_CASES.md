# Use cases UC1–UC9: what each one tests

One card per use case: the client's situation, the trap, the correct answer and how each approach did.
These cases were used to **design** the ontology rules; the fair test is the held-out set HO1–HO8
(`evaluation/use_cases/holdout.json`). Background and the experiments: [`ONTOLOGY_USE_CASES.md`](ONTOLOGY_USE_CASES.md).

**Where the cases live**
- Question text: `evaluation/use_cases/run_use_cases.py` · structured facts: `evaluation/use_cases/cases.json`
- Expected outcome (required findings, forbidden claims): `evaluation/use_cases/expected.json`
- Question set derived from them (8 per case, EN + NL): `evaluation/ground_truth/qa_usecases_full.json`
  (master) → `qa_usecases_en.json` / `qa_usecases_nl.json` (RAG-team format)

**Results:** fully correct in how many of 3 runs (5 Nov 2026, `gpt-oss-120b`, strict score: right verdict +
every required finding + no false claim).
Vector = vector search with 10 passages · GraphRAG = 5 vector + 5 graph passages · Whole = the whole policy in the prompt ·
Onto form / text = ontology + rules with the facts from the form / extracted from the question text.

| Case | Topic | Verdict | Vector | GraphRAG | Whole | Onto form | Onto text |
|---|---|---|---|---|---|---|---|
| UC1 | Houseboat, 4 violations | reject | 0/3 | 3/3 | 0/3 | 3/3 | 3/3 |
| UC2 | Hidden interest-only | reject | 3/3 | 0/3 | 2/3 | 3/3 | 3/3 |
| UC3 | Desktop valuation 90% vs 100% | reject | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| UC4 | Energy measures, 106% | €325,000 | 2/3 | 3/3 | 1/3 | 3/3 | 0/3 |
| UC5 | Explain combination | reject | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| UC6 | Diplomat clause, UK | reject | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| UC7 | Full check, son aged 17 | reject | 0/3 | 0/3 | 2/3 | 3/3 | 3/3 |
| UC8 | Full check, holiday chalet | reject | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| UC9 | Full check, woonark + RRR 18 | Explain | 2/3 | 0/3 | 2/3 | 3/3 | 3/3 |

---

## UC1 · Houseboat with four violations
**Situation:** a houseboat (boat €300,000, mooring €50,000, lifetime 25 years) with a loan of €320,000, of which
€80,000 interest-only, over 30 years.
**The trap:** four separate limits in one section; an answer that finds two or three of them looks right but is incomplete.
**Correct answer:** reject. Maximum €315,000 (90% + 90%), no interest-only, boat term ≤ 25 years (lifetime), mooring term 20 years.
**Sections:** AB 5.5.12.
**Rules:** `R_MaxLoan`, `R_InterestOnlyType`, `R_HouseboatLifetime`, `R_MooringTerm`.

## UC2 · Interest-only hidden in a savings mortgage
**Situation:** house €600,000; €100,000 interest-only plus a €200,000 savings mortgage whose savings product is **not pledged**.
**The trap:** the obvious reading counts €100,000 interest-only (fine). But an unpledged savings product makes the whole
€200,000 count as interest-only, which gives €300,000, above the €150,000 cap.
**Correct answer:** reject.
**Sections:** AB 1.1.3 (two paragraphs: the cap and "verkapt aflossingsvrij").
**Rules:** `R_InterestOnlyCounts`, `R_InterestOnlyCap`.

## UC3 · Desktop valuation: 90% vs 100%
**Situation:** detached house €400,000 from a Calcasa desktop valuation; the client needs €380,000.
**The trap:** a house can be financed up to 100%, but only with a valuation report; with a desktop it is 90%.
**Correct answer:** reject at €360,000 maximum; with an NWWI-validated report the maximum is €400,000, so the advisor can order one.
**Sections:** AB 5.5.2, 5.4.
**Rules:** `R_MaxLoan`, `R_DesktopConditions`.

## UC4 · Energy-saving measures and the 106% cap
**Situation:** house worth €300,000 before and €320,000 after renovation; only €25,000 of energy-saving measures.
**The trap:** a formula plus a cap, and the rule only applies to collateral with a 100% norm (so the valuation method matters).
**Correct answer:** €325,000 (100% before + costs, below 106% × €320,000 = €339,200), given a valuation report.
**Sections:** AB 1.3, 5.5.2.
**Rules:** `R_Energy106`.
**Known issue:** with free text the valuation method is unknown, so the system gives two scenarios; the judge marked that
as not fully correct (0/3).

## UC5 · Combining Explain solutions
**Situation:** maatwerk by using assets plus an income exception for a professional football player.
**The trap:** combinations are allowed in general, but this specific pair is forbidden.
**Correct answer:** reject: "maatwerk door inzet van vermogen" cannot be combined with exceptions that deviate on income.
**Sections:** AB 6.1, 6.2.1.2.
**Rules:** `R_ExplainCombination`.

## UC6 · Diplomat clause to the United Kingdom
**Situation:** working 2 years in the UK for a Dutch employer; used the clause before and moved back 6 months ago.
**The trap:** the UK exclusion is a separate sentence below the list of conditions.
**Correct answer:** reject: the UK is excluded, and a new request needs at least 1 year back in the home.
**Sections:** BB 4.1.1.
**Rules:** `R_DiplomatCountry`, `R_DiplomatRepeat`.

## UC7 · Full check with a hidden age problem ⭐
**Situation:** father (45), son (17) and a family friend; Rabobank advisor, Basis conditions; house €350,000, loan
€340,000 of which €60,000 interest-only.
**The trap:** the question is about a house and a loan, but the problems are about the **applicants**. Retrieval
finds loan passages, so the age rule is never seen. LLM answers also invented false problems.
**Correct answer:** reject: the son is under 18, and 3 debtors need an Intermediair advisor + Plus conditions.
Everything about the loan is fine. The friend's age is unknown.
**Sections:** AB 2.1, 2.2 (plus 1.1, 1.1.3, 5.5.2, 2.4.2 that all pass).
**Rules:** `R_MinAge`, `R_Debtors`.

## UC8 · Full check: holiday chalet
**Situation:** chalet with recreation-only zoning, €200,000; loan €180,000 of which €50,000 interest-only; the client
will live there permanently; the seller is not a Rabobank client.
**The trap:** two problems hidden in the story; the amount is exactly on the 90% boundary (fine).
**Correct answer:** reject: no interest-only for a recreation home; permanent living is not allowed here.
**Sections:** AB 5.5.13.
**Rules:** `R_InterestOnlyType`, `R_RecreationPermanent`.

## UC9 · Full check: woonark with RRR 18
**Situation:** woonark with a municipal mooring, ship register, E.M.C.I. valuation, loan 85%, 20 years; RRR 18.
**The trap:** not "yes" or "no" but **"only via Explain"**; and some facts are missing (lifetime, shore connection).
**Correct answer:** Explain route (RRR above 16); the houseboat rules are otherwise met; ask for the missing facts.
**Sections:** AB 2.4.2, 6.2.1.1, 5.5.12.
**Rules:** `R_RRR` (needs Explain), houseboat rules.

---

## The question set derived from UC1–UC9

72 questions: 8 per use case, in English and Dutch. Each use case gets variants of these types:

| Type | What it tests | Example (UC7) |
|---|---|---|
| `case_check` | the original case, reworded | "Is everything in order?" |
| `single_rule` | one rule on its own | "Can a 17-year-old be a co-applicant?" |
| `boundary` | a value exactly on or just over a limit | the son is 18, but there are still 3 debtors |
| `one_fact_change` | one fact changed, so the verdict or a finding changes | via an Intermediair advisor with Plus |
| `calculation` | an amount | maximum interest-only for €350,000 |
| `fact_lookup` | a plain fact from the policy | — |
| `list_compare` | collect or compare across sections | — |
| `unanswerable` | missing facts, or not in the policy | the friend's age is not given |

**How the answers were made:** for the 38 questions with a structured case, the rule engine proposed the verdict
and findings; every answer was written from the policy text, with verbatim quotes. `tests/test_usecase_qa.py` checks
that every quote is on the given page, that the RAG files match the master, and (with RDFox running) that the
engine still gives the expected outcome. **Status: draft, to be reviewed by a person.**
