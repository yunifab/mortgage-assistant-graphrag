<!--
Note: this prompt was written on 2026-11-18, after the set in evaluation/ground_truth/qa_usecases_full.json
(2026-11-08) was built. That set was made in a working session without a saved prompt; this file writes
down the method it followed (BUILD_LOG.md, Step 14) so the set can be extended or rebuilt the same way.
Inputs to attach: the policy PDF, docs/USE_CASES.md (or the cards for the new use cases),
evaluation/use_cases/cases.json, ontology/RULES.md, and the rule-engine output for each structured case.
-->

You are helping me build a ground-truth evaluation set for a mortgage advisor assistant. The assistant answers questions about the Rabobank Acceptatie- en Beheerbeleid (the attached PDF). We compare three approaches on it: vector RAG, GraphRAG and ontology + rules.

I will give you:
- the policy PDF
- a set of use cases. Each has: the client's situation, the trap (what makes it easy to get wrong), the correct answer, the policy sections, and the rules it touches
- the structured facts of each use case (JSON, the format of cases.json)
- the rule list (rule id, what it checks, policy section)
- the rule-engine output for each structured case (verdict and findings)

Generate 8 questions per use case. Every question must be different from the original use case, so we test whether an approach understands the rule and not only the one example.

Question types (use each one at least once across the whole set; per use case, always include one case_check and one unanswerable):
1. case_check: the use case reworded as a client's application. Ask whether it is acceptable.
2. single_rule: one rule from the use case on its own, as a general question.
3. boundary: change the facts so a limit is met exactly (for example the loan equals the maximum). The correct answer must not call it "too high".
4. one_fact_change: the same case with one fact changed, so the verdict or the set of findings changes. Say "same ..." and repeat all facts, so the question stands alone.
5. calculation: ask for an amount (usually a maximum loan) that needs a small calculation from the policy.
6. fact_lookup: a fact the policy states directly (who values, which document, which term).
7. list_compare: list or compare all cases where something applies, collected from several places.
8. unanswerable: the policy does not contain the answer (for example interest rates), or the question misses a fact needed to decide. The correct answer says so and names what is missing; it does not guess.

Rules:
- Paraphrase. Do not reuse phrases from the document in the question.
- Do not write questions answerable from general knowledge.
- Keep the trap of the use case where it fits, so a shallow answer is wrong or incomplete.
- Every answer is written from the policy text, with verbatim Dutch quotes as evidence and the physical PDF page (1-95), not the printed page label.
- For questions with a structured case, run (or use) the rule-engine output and compare it with your answer from the text. If they disagree, do not pick one: flag the question and explain the difference.
- Amounts in the answer show the calculation (for example "€315,000: 90% of €300,000 plus 90% of €50,000").
- Write each question, answer and hop_reasoning in English and in Dutch. The evidence quotes stay Dutch and are shared.
- For unanswerable questions, evidence may be empty.

Map each question to a category for the RAG team:
- single-hop: one passage answers it
- two-hop: needs two separate sections
- multi-hop: needs three or more facts from different places (most full case checks)
- comparison-aggregation: combines or contrasts information from several places
- unanswerable

For each question return:
- id: "<use case>-<two digits>", for example "UC1-01"
- derived_from: the use case id
- type: one of the 8 types above
- category: one of the 5 categories above
- expected_verdict: reject | accept | explain | amount | unanswerable, or null for a fact question without a verdict
- expected_findings: for questions with a structured case, the rule-engine problems only (a list of {rule, status, source} with status violated, needs_explain or missing_fact; an empty list means no problems). null otherwise
- related_rules: the rule ids the question is about
- case: the structured facts (same format as cases.json) when the rule engine can check the question; leave it out otherwise
- question_en, answer_en, hop_reasoning_en
- question_nl, answer_nl, hop_reasoning_nl
- evidence: a list of {page, section, quote}
- review_status: "draft"

hop_reasoning is one or two sentences: why each piece of evidence is needed, and for multi-hop why no single passage suffices.

Output as JSON: {"metadata": {...}, "questions": [...]}. In metadata, state the source document, the date, that the status is DRAFT (to be reviewed by a mortgage expert), and that these are design cases: the rules were built from these use cases, so the set favours the ontology approach and must be reported separately from held-out cases.
