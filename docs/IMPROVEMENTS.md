# Potential improvements

A to-do list of the gaps we found while reviewing the ontology, the rules and the results (Nov 2026).
Each item says **what is wrong**, **why it matters** and **what to do**. Tick an item when it is done, and log
the work in `BUILD_LOG.md`.

Priority: **H** = do first (correctness or understanding), **M** = useful, **L** = nice to have.

---

## 1. Ontology structure (T-Box)

| # | Prio | What is wrong | What to do |
|---|---|---|---|
| 1.1 | H | **Properties are not declared.** The rules and `rules/case.py` use 83 properties (`hasApplicant`, `hasCollateral`, `hasLoanPart`, `marketValue`, `termYears`, ...), but none is declared in the `.ttl` files. A reader cannot see how the classes connect. | Add a *properties* section to `rabo_mortgage.ttl`: `owl:ObjectProperty` / `owl:DatatypeProperty` with `rdfs:domain`, `rdfs:range`, labels (EN + NL). |
| 1.2 | H | **No definitions on our classes.** The 18 `skos:definition`s are on rules and outcomes; the 65 `rabo:` classes have none. A definition is not inherited from the FIBO parent. | Add `skos:definition` (EN + NL) to every class: "parent + what is different". Add a test that fails when a class has no definition. |
| 1.3 | M | **Custom annotations are not declared:** `rabo:definedIn`, `rabo:relatedFiboConcept`, `rabo:source`. | Declare them as `owl:AnnotationProperty` with a label and comment. |
| 1.4 | M | **`definedIn` is missing on 11 real policy terms:** `DesktopTaxatie`, `DesktopTaxatiePlus`, `ValuationReport`, `EMCIValuationReport`, `NRVTValuationReport`, `LAVValuationReport`, `ShopHouse`, `PracticeHouse`, `AnnuityPart`, `LinearPart`, `BusinessPropertyValuation`. (Grouping classes like `DwellingOnWater` have no single section; that is fine.) | Add the sections. |
| 1.5 | M | **`definedIn` is a string, not a link.** `"AB-5.5.12"` is plain text in the T-Box; the real link to the section only exists in the Neo4j copy. | Make each section a resource (e.g. `rabo:Section_AB-5.5.12`) and point to it. |
| 1.6 | M | **No source quote on classes.** You cannot check a class against the PDF without opening it. | Add `rabo:sourceQuote` (verbatim Dutch text) and a test that the quote appears in the section named in `definedIn` (same check as the QA quotes). |
| 1.7 | L | **FIBO alignment is loose.** The FIBO slice copies only classes, not FIBO's relationships. We use `rabo:requestedAmount` and a plain number for `rabo:marketValue`, while the slice already has `fibo-loanapplications:hasRequestedAmount` and FIBO models `MarketValue` as a class (an amount). | Where FIBO has a matching property, add `rdfs:subPropertyOf` to it. Decide whether amounts stay plain numbers (simple) or follow FIBO (interoperable). |

## 2. Rules: correctness

| # | Prio | What is wrong | What to do |
|---|---|---|---|
| 2.1 | H | **Rules are not reviewed by an expert.** Our own interpretations are not marked. | One card per rule in `ontology/RULES.md`: section + quote, what the rule does, **our own choices**, the boundary test. Review with a mortgage expert or the PO. |
| 2.2 | H | **Some rules have no quote** in `RULES.md` (e.g. `R_ConstructionCosts`). | Add the Dutch policy text for every rule. |
| 2.3 | H | **One term for the whole loan.** The policy gives the houseboat and the mooring separate loan parts with their own terms; the case model has one `termYears`, so any term above 20 years is flagged for the mooring. | Term per loan part in `rules/case.py`, and update `R_HouseboatLifetime`, `R_MooringTerm`. (Changes the case model: decide first.) |
| 2.4 | M | **Mooring permit is simplified.** One true/false (`mooringFromGovernment`) stands for "permit or lease from a government body, **or** owned". | Two facts: the legal basis (permit / lease / owned) and who granted it. |
| 2.5 | M | **RRR: the "outside 1-20 → violated" line is our own choice**, not policy text; the "onterechte Default rating" is not modelled; the situations for Explain are in *Kapitaalmodel Hypotheken*, which we do not have. | Mark it as an input check; note the gaps on the rule card. |
| 2.6 | M | **Energy rule assumes the energy measures are the only works.** UC4-05 (energy + kitchen) failed: the engine used the wrong base. | Add a "value without the energy measures" fact; decide what to do when the valuation method is not given (assume the 100% norm, or ask). |
| 2.7 | L | **Tests do not cover every boundary.** | One pass / one violated / one missing-fact test per rule. |

## 3. Rules: coverage

The rules cover **20 of 183 sections** (11%); the Beheerbeleid only 1 of 56.

| # | Prio | What is missing | What to do |
|---|---|---|---|
| 3.1 | H | **No coverage map.** We do not know how many sections can become rules. | Label every section: *covered / rule-able / partly / text only* (signals: a number, a prohibition, if-then, a list, a required document). An LLM can draft it; a person confirms. |
| 3.2 | M | **5.5.12 Houseboat: 4 of 16 statements missing:** lies in the Netherlands on the water; not a means of transport; only sails for maintenance (these 3 define what a houseboat *is*); steel hull → proof of insurance; increasing with an existing interest-only loan → new loan in max 20 years. | Add the insurance rule and the 20-year rule; decide whether the definition criteria become checks or an assumption. |
| 3.3 | M | **1.1.3 Interest-only: 4 statements missing:** loans at other lenders count toward the cap; an interest-only mortgage always has an end date; a credit mortgage uses the credit limit; when increasing above the cap, the existing amount may stay. | Add as rules (facts needed: third-party interest-only, end date, credit limit, existing amount). |
| 3.4 | M | **Chapters 2-4 (applicant, income, loan)** only cover age, number of debtors and RRR; **income and affordability are not modelled.** | Next areas after the coverage map. |
| 3.5 | L | **Beheerbeleid** (servicing existing mortgages) is almost uncovered. | After the Acceptatiebeleid. |

## 4. Reading facts from the question (extraction)

| # | Prio | What is wrong | What to do |
|---|---|---|---|
| 4.1 | H | **Bug: "gevalideerd rapport" is dropped.** The LLM extracts it correctly, but the grounding check (`VALUATION_EVIDENCE` in `rules/extract.py`) knows "validated" and not "gevalideerd", so the engine says "valuation method missing". Cost 3 Dutch questions in the use-case eval. | Add "gevalideerd" (and similar Dutch words) to the list; add a test with a Dutch question. |
| 4.2 | M | **"IS verpand" read as not pledged** (UC2-03, Dutch). | Add a Dutch example to the extraction prompt; test. |
| 4.3 | M | **Unanswerable questions:** all three approaches still give a firm answer instead of "fact missing" (~0.7). | Prompt: when a needed fact is missing, say so and name it. |

## 5. Neo4j copy of the ontology

| # | Prio | What is wrong | What to do |
|---|---|---|---|
| 5.1 | M | **The copy looks like a word list, not a T-Box.** `build_ontology_graph.py` copies classes, `SUBCLASS_OF` and the links to sections, but not the limits on the classes (`interestOnlyAllowed`, `maxTermYears`, ...), the LTV norms, or the relationships between classes. | Add the limits as node properties, the norms as nodes, and the declared properties (1.1) as schema links, e.g. `(MortgageApplication)-[:HAS_COLLATERAL]->(Collateral)`. Alternative: full RDF import with the neosemantics (n10s) plugin. |

## 6. Data quality (PDF extraction)

| # | Prio | What is wrong | What to do |
|---|---|---|---|
| 6.1 | L | **Margin text in the chunks:** link texts like "InforEuro Valutakoers, Lijst van internationale organisaties" appear inside section 3.1.3. | Filter margin text in `ingest/pdf_parser.py`. |
| 6.2 | L | **Lines in the wrong section:** "Vanaf 1 januari 2030 ..." in 1.1.3, "Er is een bevestigingsbrief van NHG ..." in 2.4.2 (footnotes or side notes). | Detect footnotes / side notes and keep them apart. |

## 7. Evaluation

| # | Prio | What is wrong | What to do |
|---|---|---|---|
| 7.1 | H | **The 72 use-case answers are a draft.** | Human review against the PDF (or an expert sample). |
| 7.2 | M | **Design cases favour the ontology.** | For every new rule, add a question to the **held-out** set too; report design and held-out results separately. |
| 7.3 | M | **One run only** for the use-case comparison. | Rerun the close categories (or 3 runs) before drawing conclusions. |
| 7.4 | L | **Per-question results are not shared** (`*.jsonl` is in `.gitignore`). | Commit a small summary per question, or share the files when the team needs them. |
