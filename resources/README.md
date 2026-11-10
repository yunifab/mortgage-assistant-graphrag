# Resources — FIBO Mortgage KG Exploration

Source material for the toy project **"Mortgage Case Checker for Advisors"**:
a FIBO-based knowledge graph of Dutch/EU mortgage rules (in Neo4j) that grounds an LLM
assistant helping a mortgage advisor check a case.

All files were downloaded on **2026-11-01**. They are public documents, kept here only
for internal exploration. **Don't redistribute them, and check for newer versions before relying on any rule.**

---

## 1. Downloaded PDFs (`pdfs/`)

| # | Local file | Layer | Lang | What it is / why it's useful | Source |
|---|---|---|---|---|---|
| 0 | [`rabobank_mortgage.pdf`](pdfs/rabobank_mortgage.pdf) | Bank (underwriting) | NL | **Rabobank Acceptatie- en Beheerbeleid**, 14 September 2026 (95 pages). The bank's **underwriting rules** for advisors and intermediaries: max term, interest-only limits, LTV 100%/106%, applicant rules, income, debts (BKR), collateral and valuation, exceptions ("Explain"), a definitions list and a document checklist with validity periods. **Candidate main document** (added 2026-11-03). | Provided by the user |
| 1 | [`abnamro_home_mortgage_conditions_2026-04_EN.pdf`](pdfs/abnamro_home_mortgage_conditions_2026-04_EN.pdf) | Bank | EN | ABN AMRO Home Mortgage Conditions, April 2026. A real Dutch bank's mortgage terms: loan components, mortgage right, borrower obligations, early repayment, default. Main **text source** for the RAG part. | Third-party mirror ([zelfhypotheekafsluiten.nl](https://www.zelfhypotheekafsluiten.nl/Uploads/geldverstrekkers/2026/09/abn-amro-hypotheek-voorwaarden-home-mortgage-conditions-engels-april-2026.pdf)). The official copy is linked from the [ABN AMRO documents page](https://abnamro.nl/en/personal/mortgages/buying-a-house/documenten/documents-mortgage.html), but that page's links load through JavaScript. |
| 2 | [`abnamro_mortgage_offer_explained_2023-06_EN.pdf`](pdfs/abnamro_mortgage_offer_explained_2023-06_EN.pdf) | Bank | EN | English guide to a Dutch mortgage offer ("hypotheekofferte"), June 2023. Explains each part of an offer, so it's good for **advisor vocabulary** and the fields of a "case". | Third-party mirror ([zelfhypotheekafsluiten.nl](https://www.zelfhypotheekafsluiten.nl/Uploads/geldverstrekkers/2026/09/abn-amro-hypotheek-uitleg-offerte-mortgage-offer-explained-engels-1-juni-2023.pdf)) |
| 3 | [`eba_gl_2020_06_loan_origination_monitoring_EN.pdf`](pdfs/eba_gl_2020_06_loan_origination_monitoring_EN.pdf) | EU regulation | EN | EBA Guidelines on Loan Origination and Monitoring (EBA/GL/2020/06, issued 29 May 2020, applies from 30 June 2021). What every EU bank must check when granting a loan: creditworthiness, affordability, collateral valuation. **Regulation layer.** | [EBA](https://www.eba.europa.eu/regulation-and-policy/credit-risk/guidelines-on-loan-origination-and-monitoring) |
| 4 | [`nhg_voorwaarden_en_normen_2026_NL.pdf`](pdfs/nhg_voorwaarden_en_normen_2026_NL.pdf) | Dutch rules | NL | NHG "Voorwaarden en Normen 2026-1" (96 pages), the Dutch National Mortgage Guarantee rules. The **numeric rules** (limits, conditions). Dutch only, so translate the sections you need with an LLM and check them by hand. | [nhg.nl](https://www.nhg.nl/media/gtaickpv/vn-nhg-2026.pdf) |
| 5 | [`nhg_changes_2025_2026_NL.pdf`](pdfs/nhg_changes_2025_2026_NL.pdf) | Dutch rules | NL | NHG list of changes from 2025-1 to 2026-1 (2 pages). Good for the **"what changed between versions?"** use case. | [nhg.nl](https://www.nhg.nl/media/54sbsuq1/wijzigingenoverzicht-vn-2025-2026.pdf) |
| 6 | [`fanniemae_eligibility_matrix_2026-04.pdf`](pdfs/fanniemae_eligibility_matrix_2026-04.pdf) | Reference (US) | EN | Fannie Mae Eligibility Matrix, April 2026. US, but a very clean **example of policy rules as tables** (LTV/CLTV, credit score, reserves, DTI by property type and loan purpose). Useful as a pattern for structuring our own toy policy. | [Fannie Mae](https://singlefamily.fanniemae.com/media/20786/display) |

---

## 2. Other useful links (not downloaded)

| Link | Why it's useful |
|---|---|
| [ABN AMRO: documents for a mortgage](https://abnamro.nl/en/personal/mortgages/buying-a-house/documenten/documents-mortgage.html) | Official page for ABN AMRO's mortgage documents (check here for the newest version of #1). |
| [ABN AMRO: execution-only terms](https://www-pr3.abnamro.nl/en/personal/mortgages/applying-for-mortgage/execution-only/terms-and-conditions.html) | Terms for taking out a mortgage without advice. Shows how "advised" and "non-advised" differ. |
| [ABN AMRO: Sustainable Home Mortgage](https://www.abnamro.nl/en/personal/mortgages/sustainable-living/sustainable-home-mortgage.html) | Energy-saving / green mortgage product. Links to FIBO `GreenLoans`. |
| [NHG addendum V&N 2026 (NL)](https://nhg.nl/media/tcbb2wnj/nhg-addendum-vn-2026-nl.pdf) | Addendum to the 2026 NHG rules. |
| [Newrez conforming profile](https://www.newrezcorrespondent.com/media/1563117/conforming_profile.pdf) | Example of a lender "overlay" (stricter rules on top of Fannie Mae). Pattern for "bank rule vs. base rule". |
| [Hypotheker: Loan-to-Value explained (NL)](https://www.hypotheker.nl/begrippenlijst/hypotheek-afsluiten/loan-to-value/) | Plain explanation of the Dutch LTV rule. |
| [S&P: primer on the Dutch RMBS market](https://www.spglobal.com/ratings/en/research/articles/240603-a-primer-on-the-dutch-rmbs-market-13030804) | English background on how Dutch mortgages work (LTV, NHG, interest-only history). |
| [Open Risk Manual: EBA LOM Guidelines](https://www.openriskmanual.org/wiki/EBA_Guidelines_on_Loan_Origination_and_Monitoring) | Short English summary of the EBA guidelines. |
| [Internetconsultatie: LTV exception (NL)](https://internetconsultatie.nl/uitzonderingltv/document/5754) | Dutch consultation on exceptions to the 100% LTV rule for home improvements. |

---

## 3. Candidate facts for the toy policy (⚠️ verify before use)

These come from secondary sources found while brainstorming. **Check each one against
the NHG PDF (#4) or official Dutch law before encoding it as a rule.**

| Rule | Value | Source to check |
|---|---|---|
| Max loan-to-value (LTV) | 100% of the home's market value | Dutch mortgage regulation; Hypotheker |
| LTV with energy-saving measures | up to 106% | Hypotheker; NHG V&N |
| NHG loan limit 2026 | ~€470,000 (~€498,200 incl. energy-saving measures); one limit for all housing types from 2026 | NHG V&N 2026 (#4) |
| Max loan based on income (LTI) | Set by yearly Nibud income tables, using a stressed interest rate | Nibud / Dutch regulation |
| NHG 2026: floating homes | Now eligible under the renewed housing definition | NHG changes (#5) |

---

## 4. Related local material

- FIBO clone: [`../fibo`](../fibo). Most relevant: `LOAN/RealEstateLoans/` (Mortgages, MortgageOrigination, ConstructionLoans) and `LOAN/LoansGeneral/` (LoanApplications, Loans).
- Inspiration project: `C:\Users\20244647\Desktop\experimentation\treat-almende` (HeLiFit ontology + WHO-guideline KG + RDFox rules → LLM context).
