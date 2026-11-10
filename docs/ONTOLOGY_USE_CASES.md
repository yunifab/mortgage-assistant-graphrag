# Use cases: where an ontology + rules beats vector search and the document graph

> **Goal of this document:** show with concrete, *tested* examples where an ontology with business rules
> (FIBO + RDFox) makes a difference compared with what we have now (vector RAG and the document graph).
> All cases are made up, but every rule comes from the Rabobank policy (section numbers given).
>
> The "observed" columns are **real outputs** of our current system (5 Nov 2026, `gpt-oss-120b`):
> vector search with 10 passages, and GraphRAG with 5 + 5 passages.
> Script: `evaluation/use_cases/run_use_cases.py`; raw output: `evaluation/use_cases/results*.jsonl`.

---

## 1. The short answer

**When a question is about one topic, today's system is already good.** If all the rules are in one section
(houseboat, interest-only, energy 106%, diplomat clause), the LLM finds them and even gets the
arithmetic right. An ontology adds little there.

**The ontology wins when the advisor asks "is this whole application OK?"**
Then the system must check **every rule that applies**, not only the ones that look like the question.

| What goes wrong today | Seen in | Why it happens | How ontology + rules fix it |
|---|---|---|---|
| **A rule is never checked** | UC7 (age 17 missed), UC9 (RRR ignored) | The LLM only sees the 5–10 passages that *look like* the question. A rule that isn't retrieved isn't checked. | Every rule that applies to the case is always evaluated, whatever the wording of the question. |
| **A rule is applied to the wrong thing** | UC7 (the family-loan rule used against the mortgage) | Text has no explicit *scope*. "Aflossingsvrij lenen is niet toegestaan" appears in many sections, each about a different thing. | Each rule is attached to a **class** (`FamilyLoan`, `Houseboat`, `RecreationHome`), so it only fires for that class. |
| **A different answer for the same case** | UC2, UC9 (yes ↔ no, depending on the mode) | The answer depends on which passages were retrieved, and on the LLM. | Same facts, same verdict, every time. |
| **"No" when it should be "only via Explain"** | UC9 | The LLM only says yes or no. | Rules can give three outcomes: ✅ OK · ❌ violated · 🔍 possible via Explain. |
| **Missing facts are assumed** | UC9 (houseboat lifetime, shore connection unknown) | The LLM fills the gaps or ignores them. | A rule that needs a missing fact reports **"unknown: ask for X"**. |
| **No proof** | all | The LLM gives reasons, but they can be wrong (UC7). | RDFox can **explain** each conclusion (which facts + which rule), linked to the section. |

---

## 2. Results of the 9 test cases

✅ correct · ⚠️ partly correct · ❌ wrong

| Case | Type | Vector (10) | GraphRAG (5 + 5) | Ontology + rules (expected) |
|---|---|---|---|---|
| UC1 Houseboat, 4 violations | one topic | ✅ | ✅ | ✅ |
| UC2 "Hidden" interest-only | one topic + definition | ✅ | ❌ says "complies" | ✅ |
| UC3 Desktop valuation 90% vs 100% | one topic | ✅ | ✅ | ✅ |
| UC4 Energy measures 106% | arithmetic | ✅ €325k | ✅ €325k | ✅ |
| UC5 Explain combination | logic | ✅ | ✅ | ✅ |
| UC6 Diplomat clause, UK, 6 months | one topic | ✅ | ✅ | ✅ |
| **UC7 Full check: age, debtors** | **full check** | ⚠️ missed age 17 + **false** violation | ❌ missed age 17 + **2 false** violations | ✅ |
| UC8 Full check: holiday chalet | full check | ✅ | ✅ | ✅ |
| **UC9 Full check: woonark + RRR 18** | **full check** | ⚠️ "reject" (should be: Explain route) | ❌ "**accept**" (RRR ignored) | ✅ 🔍 Explain + missing facts |

**Score:** vector 7 ✅ / 2 ⚠️; GraphRAG 6 ✅ / 3 ❌. Every failure is in a case that combines
rules from **different chapters** or depends on a **definition**.

> Honest caveat: 9 cases is a demo, not a measurement. The next step (section 5) is a proper case test set.

---

## 2b. Control experiment: does giving the LLM the WHOLE policy fix it? (no)

The failures above could be "just retrieval": the right rule wasn't among the passages. So we tested
the strongest LLM-only alternative: put **the whole policy (~62k tokens)** in the prompt, with and without a
checklist ("check every rule that applies: applicants, loan, collateral, Explain…").
Each case was run **3 times** and graded by a judge model against `evaluation/use_cases/expected.json`
(required findings + forbidden false claims). Report: `evaluation/use_cases/control_20261105_1638.md`.

**Fully correct** = right verdict **and** every required finding **and** no false claim.

| Set-up | Fully correct | Cases fully correct in all 3 runs | False claims per answer | Tokens per question |
|---|---|---|---|---|
| Vector, 10 passages | 70% | 5 / 9 | 0.33 | ~3,500 |
| GraphRAG, 5 + 5 | 67% | 6 / 9 | 1.30 | ~3,500 |
| **Whole policy** | 70% | 4 / 9 | 0.41 | ~62,000 |
| **Whole policy + checklist** | 59% | 2 / 9 | 0.41 | ~62,000 |

| Set-up | UC1 | UC2 | UC3 | UC4 | UC5 | UC6 | UC7 | UC8 | UC9 |
|---|---|---|---|---|---|---|---|---|---|
| Vector, 10 | 0/3 | 3/3 | 3/3 | 2/3 | 3/3 | 3/3 | 0/3 | 3/3 | 2/3 |
| GraphRAG | 3/3 | 0/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0/3 | 3/3 | 0/3 |
| Whole policy | 0/3 | 2/3 | 3/3 | 1/3 | 3/3 | 3/3 | 2/3 | 3/3 | 2/3 |
| Whole policy + checklist | 0/3 | 3/3 | 3/3 | 2/3 | 2/3 | 1/3 | 2/3 | 1/3 | 2/3 |

**What this shows**
- **The whole policy in context does not solve it.** It fixes some retrieval misses: it found the age-17 rule
  in UC7 and the RRR/Explain route in UC9 more often. But it **creates new errors**:
  - UC4: it gave a maximum of €288,000 by applying the desktop-valuation 90% rule that doesn't apply.
  - UC1: it dropped the term rules.
  - It's also **less consistent**: only 4/9 cases right in every run.
- **A checklist made it worse** (59%, 2/9 consistent, and 2 empty answers on the long prompt).
- **No LLM set-up is above ~70% fully correct**, and every one of them changes its answer between identical runs.
  The problem isn't only *finding* the rule. The LLM is also not reliable at *applying all of them, every time*.
- Using the whole policy costs ~18× more tokens per question.

**Conclusion:** this is the evidence for ontology + rules. A rule engine checks every encoded rule, the same way, every
time. The LLM then only has to *explain* findings it's given, not *find and apply* them.

**Caveats (keep them in the pitch)**
- 9 cases × 3 runs is small. The judge model was spot-checked by hand (UC1, UC4, UC7) and was right.
- The rules are designed **from these same cases**, so they'd score well on them by construction.
  **The fair test of the ontology is a NEW set of cases** written after the rules (a held-out set).
- One answer model (`gpt-oss-120b`). A stronger model may score higher, but consistency is the real issue.

---

## 2c. Result: ontology + rules, built and measured (5 Nov 2026)

The ontology + rules are now built (see [`ontology/README.md`](../ontology/README.md)). Same cases, same judge, same strict
score (**fully correct** = right verdict + every required finding + no false claim), 3 runs per case.

**UC1–UC9** (these were used to *design* the rules, so this result is flattering)

| Set-up | Fully correct | Cases right in all 3 runs |
|---|---|---|
| Best LLM-only (vector 10 / whole policy) | 70% | 5/9 / 4/9 |
| GraphRAG | 67% | 6/9 |
| **Ontology + rules, facts from the form** | **100%** | **9/9** |
| **Ontology + rules, facts extracted from the text** | **89%** | 8/9 |

**HO1–HO8, held-out cases** (written *after* the rules, the fairer test)

| Set-up | Fully correct | Cases right in all 3 runs |
|---|---|---|
| Vector, 10 passages | 25% | 1/8 |
| GraphRAG | 33% | 2/8 |
| Whole policy (~62k tokens) | 33% | 2/8 |
| Whole policy + checklist | 42% | 3/8 |
| **Ontology + rules, facts from the form** | **92%** | 7/8 |
| **Ontology + rules, facts extracted from the text** | **100%** | 8/8 |

Files: `evaluation/use_cases/control_20261105_1803.md`, `holdout_20261105_1722.md` (LLM-only set-ups), `holdout_20261105_1807.md` (ontology).

**Honest notes**
- The **first** held-out run gave the ontology 75% (text) and 88% (form). We fixed two problems that run revealed:
  - the explanation LLM misread ✅ checks as problems (HO1). Fix: separate PROBLEMS / PASSED blocks in the prompt.
  - the extraction missed "partly let out" → rental home (HO2). Fix: more synonyms in the ontology.

  So HO1 and HO2 are **no longer fully held-out**. A truly blind test needs new cases from a colleague or expert.
- **No error came from the rule engine.** Every remaining failure is in the LLM parts: extracting facts from
  free text, or writing the explanation. The form (exact facts) removes the extraction risk.
- **Open issue, UC4 (free text):** the text doesn't say how the house was valued. The engine therefore gives two
  exact scenarios (€325,000 with a valuation report, €270,000 with a desktop valuation) instead of one amount.
  We think that's the right behaviour, but the answer doesn't yet mention the 106% check.
- **Ordinary policy questions** (the 40-question set): the first version *hurt*, because 15/80 questions were
  treated as a case and lost the policy text (0.61). The **hybrid** version (rule findings + GraphRAG passages)
  scores 0.75 (EN) / 0.71 (NL), on par with the other modes.

---

## 3. The cases in detail

### UC7: Full check with a hidden age problem ⭐ (best demo case)

**Case:** Father (45) + son (**17**) + a family friend as **3rd debtor**. Submitted by a **Rabobank advisor**
(not the Intermediair), **Basis** conditions. Regular terraced house, market value €350,000 from a valuation report.
Loan €340,000, of which €60,000 interest-only, 30 years. RRR 12, energy label B.

**Expected (from the policy):**

| Rule | Section | Verdict |
|---|---|---|
| Applicant is at least 18 | AB 2.1 | ❌ the son is 17 |
| 3–5 debtors only via the Intermediair **and** with Plus conditions | AB 2.2 | ❌ Rabobank advisor, Basis |
| LTV ≤ 100% (valuation report, regular house) | AB 1.3, 5.5.2 | ✅ 97% |
| Interest-only ≤ 30% of market value **and** ≤ €150,000 | AB 1.1.3 | ✅ €60k ≤ €105k |
| Term ≤ 30 years | AB 1.1 | ✅ |
| RRR 1–16 | AB 2.4.2 | ✅ |

**Observed:**
- **Vector:** found the debtor rule ✅, **missed the age** ❌, and said "interest-only is not allowed",
  citing **4.3.1 Leen-schenkconstructie**. That rule is about *family loans*, not about this mortgage. ❌ false reason.
- **GraphRAG:** missed the debtor rule, **missed the age** ("not addressed in the passages"), and made up
  **two** violations from the family-loan section (interest-only ban, 50% limit). ❌

**Why the ontology wins:**
- The age rule is attached to `Applicant`. It runs for every applicant, whether or not "age" is in the question.
- The family-loan rules are attached to `FamilyLoan`. This case has no family loan, so they can't fire.

**Rule sketch (RDFox Datalog, for illustration):**
```prolog
# Each rule produces a finding with its source section
[?app, :violates, :R_MinAge] :-
    [?app, :hasApplicant, ?p], [?p, :age, ?age], FILTER(?age < 18) .

[?app, :violates, :R_DebtorCount] :-
    [?app, :numberOfDebtors, ?n], FILTER(?n >= 3),
    NOT [?app, :submittedVia, :Intermediair] .

[?app, :violates, :R_DebtorCount] :-
    [?app, :numberOfDebtors, ?n], FILTER(?n >= 3),
    NOT [?app, :conditions, :Plus] .

[:R_MinAge, :source, "AB-2.1"] .        # the link to the Neo4j section and the PDF
[:R_DebtorCount, :source, "AB-2.2"] .
```

---

### UC9: Woonark + risk rating R18: "accept", "reject" or "Explain"?

**Case:** A **woonark** with a fixed mooring rented from the municipality, registered in the ship register,
valued by an E.M.C.I. valuer. Loan 85% of value, fully repaid in 20 years. **RRR R18.**

**Expected:**

| Rule | Section | Verdict |
|---|---|---|
| A woonark counts as a houseboat (*"woonboot, woonschip of woonark"*) | AB 5.5.12 | class: `Houseboat` |
| LTV ≤ 90% of the boat + 90% of the mooring | AB 5.5.12 | ✅ 85% |
| No interest-only | AB 5.5.12 | ✅ |
| Boat loan repaid within the expected lifetime (max 30 years), mooring in 20 years | AB 5.5.12 | ❓ **lifetime unknown**: ask for the valuation report |
| Shore connection (walaansluiting) | AB 5.5.12 | ❓ unknown |
| RRR 1–16 accepted; R17–R20 possible in specific situations | AB 2.4.2 → AB 6.2.1.1 | 🔍 **only via Explain** |

**Observed:**
- **Vector:** "cannot be accepted". The direction is right, but it's presented as a rejection, not as an Explain route. ⚠️
- **GraphRAG:** "**Yes, can be accepted**". It ignored the R18 rating because the RRR section wasn't retrieved. ❌

**Why the ontology wins:**
- The verdict doesn't depend on retrieval.
- There are **three outcomes** (🔍 Explain is not ❌).
- **Missing facts** are reported instead of assumed.

---

### UC2: Interest-only that's hidden in a savings mortgage

**Case:** Market value €600,000. Loan: €100,000 interest-only + €200,000 savings mortgage whose savings product is
**not pledged** + €150,000 annuity.

**Expected:** AB 1.1.3 says that if the savings product is not pledged, **the whole loan part counts as interest-only**
(*verkapt aflossingsvrij*). Interest-only = €100k + €200k = **€300k**, which is more than €150k. ❌

**Observed:** vector ✅ (€300k, violation). GraphRAG ❌: "€100k complies".

**Why the ontology wins:** the definition becomes a **classification rule**:
`LoanPart with SavingsProduct and NOT pledged ⇒ InterestOnlyPart`. Then the cap rule adds up all `InterestOnlyPart`s.
The definition is applied every time, not only when the LLM happens to read it.

---

### UC1, UC3, UC4, UC5, UC6, UC8: no difference today

| Case | What the LLM got right |
|---|---|
| UC1 Houseboat: €350k value, €320k loan, €80k interest-only, 30 years, lifetime 25 | max €315k; no interest-only; term ≤ lifetime; mooring in 20 years (4/4 violations) |
| UC3 Desktop valuation €400k, loan €380k | 90% = €360k ❌; suggests a valuation report (100%) |
| UC4 Energy measures | 100% × €300k + €25k = €325k ≤ 106% × €320k |
| UC5 Assets maatwerk + footballer income exception | not allowed (AB 6.1 "combinatie van Explain") |
| UC6 Diplomat clause to the UK, back for 6 months | UK excluded; must have lived there ≥ 1 year again (BB 4.1.1) |
| UC8 Holiday chalet, permanent living | no interest-only; permanent living not allowed (the exception needs a Rabobank-client seller) |

**Lesson for the team:** don't pitch the ontology as "better at answering policy questions".
On single-topic questions a strong LLM with retrieval is already good. Pitch it for **complete,
consistent and explainable case checks**.

---

## 4. More use cases worth building (not tested yet)

| # | Use case | Why rules are needed |
|---|---|---|
| UC10 | **"How much can this client borrow at most?"** Take the minimum of all limits: collateral type × valuation method (5.5.x), energy 106% (1.3), interest-only cap (1.1.3), residual debt 115% (1.3) | A small optimisation across many sections. An LLM tends to apply only the first limit it finds. |
| UC11 | **What-if:** "What changes if he gets a valuation report instead of a desktop valuation?" or "…without the interest-only part?" | Change one fact and re-run all rules. That's cheap and exact with RDFox (incremental reasoning). |
| UC12 | **Policy dates:** the rules for "from 1 Jan 2030" (1.1.3) and the version history (Versiebeheer) | Rules can have a validity period. "Which rules applied on the offer date?" |
| UC13 | **Documents per case:** which documents are needed for *this* case (Bijlage 3), and are they still valid (e.g. a salary slip is valid for 3 months)? | Combines the case facts with the checklist and the dates. |
| UC14 | **Explain combinations:** maatwerk + exceptions (6.1 "wat mag wel / niet") | Pure logic over typed items (`Maatwerk`, `IncomeException`). Easy to get wrong when there are 3+ items. |

---

## 5. How we measure it (proposal)

- **Case test set:** 20–30 cases like UC7 and UC9, each with the **expected verdict per rule**
  (✅ / ❌ / 🔍 / ❓) and the section.
- **Compare:** vector RAG vs GraphRAG vs ontology + rules (the LLM then only writes the explanation).
- **Metrics:**
  - **Violation recall:** of the real problems, how many were found?
  - **False violations:** how many made-up problems? (UC7 shows this matters.)
  - **Verdict accuracy:** accept / reject / Explain, overall.
  - **Consistency:** run each case 3 times; is the verdict the same?
  - Explainability: is every finding linked to a section? (yes/no)

---

## 6. Proposed first slice (small, for one sprint)

1. **About 15 rules**, covering UC1, UC2, UC7, UC9:
   - age (2.1), debtors and channel (2.2), RRR (2.4.2)
   - term (1.1), interest-only cap + savings mortgage counted as interest-only (1.1.3), LTV 100% (1.3)
   - collateral types: regular house (5.5.2), houseboat (5.5.12), holiday home (5.5.13)
   - Explain combinations (6.1)
2. **A small ontology:** `Application`, `Applicant`, `LoanPart` (interest-only, annuity, with savings product),
   `Collateral` and its subclasses, `Valuation` (desktop / valuation report / E.M.C.I.).
   Reuse FIBO terms where they fit (loan, borrower, collateral), plus our own `rabo:` terms.
3. **RDFox** runs the rules. Each finding gets `:source "AB-x.y"`, which links to the Neo4j section.
   The LLM then writes the explanation from the findings + the cited sections.
4. **UI:** a "Check a case" tab with a form, so no free-text extraction errors at first.

---

## 7. ⚠️ RDFox licence: check before using it at the bank

The RDFox in `treat-almende/RDFox-win64-x86_64-7.5b/` works (version 7.5b), but the licence says:

> *"licensed for **Academic use** to [a TU Eindhoven researcher] of Eindhoven University of Technology until 20-Mar-2027"*

An academic licence normally **doesn't allow commercial use**, and it's in another person's name.
**Before** using it for bank work, even locally:
- ask the team or the PO whether the bank has (or can get) an **RDFox evaluation or commercial licence**
  (Oxford Semantic offers free evaluation licences); or
- prototype the rules with an open-source option first (e.g. SHACL rules with pySHACL, or plain Python),
  keeping the rules in the same Datalog-like structure so they can move to RDFox later.
