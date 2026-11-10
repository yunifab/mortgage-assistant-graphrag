"""Gradio chat UI for the mortgage advisor assistant.

Run:  uv run python app/gradio_app.py      then open http://127.0.0.1:7860
For the ontology mode and the 'Check a case' tab, RDFox must be running (docs/RDFOX_SETUP.md).

Retrieval modes (choose in the Chat tab):
  - Vector search (RAG)                          the baseline
  - Vector + document graph (GraphRAG)           also follows references, exceptions, definitions
  - Vector + graph + ontology/rules (FIBO, RDFox) a described case is checked by the rule engine;
                                                 general questions use GraphRAG + ontology synonyms

Each question is answered on its own (no chat memory yet), so the evaluation and the UI behave
the same. The 'Sources' panel shows which passages were used, which graph link led to them, and
in ontology mode the rule findings and the extracted case facts.
"""

import atexit
import json

import gradio as gr

from mortgage_assistant import rag, store
from mortgage_assistant.config import settings
from mortgage_assistant.rules import rdfox
from mortgage_assistant.rules.case import (COLLATERAL_TYPES, EXPLAIN_TYPES, LEGAL_RIGHTS, NEW_BUILD_KINDS, VALUATIONS,
                                           Applicant, Case, Collateral, DiplomatRequest, EnergyInvestment, Loan,
                                           LoanPart)
from mortgage_assistant.rules.engine import STATUS_ICON, rule_count

MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]  # on Groq, Nov 2026
MODE_BY_LABEL = {label: key for key, label in rag.RETRIEVAL_MODES.items()}
DEFAULT_MODE_LABEL = rag.RETRIEVAL_MODES["graph"]

EXAMPLES = [
    "What is the maximum term of a mortgage loan?",
    "Can a houseboat be used as collateral, and what are the conditions?",
    "Check this application: one applicant (40), Rabobank advisor, Basis conditions, RRR 3. The client buys a house "
    "that will be partly let out (with permission), valued at EUR 400,000 by a validated NWWI valuation report. "
    "Loan EUR 360,000 annuity, term 30 years. Is it OK?",
    "Mag een aanvrager met een tijdelijke verblijfsvergunning debiteur zijn?",
]
EMPTY_SOURCES = "*The passages used for the answer appear here.*"
VERDICT_BADGE = {
    "reject": "## ❌ Not acceptable\nAt least one policy rule is violated.",
    "explain": "## 🔍 Only via Explain\nNot possible under the standard rules; possibly via the Explain route.",
    "incomplete": "## ❓ Incomplete\nNo violation found, but facts are missing.",
    "accept": "## ✅ Acceptable\nAll rules that were checked are met.",
}
UNKNOWN = "unknown"

driver = store.get_driver()
atexit.register(driver.close)


# ----------------------------------------------------------------------------------- rendering
def _findings_markdown(check: dict) -> str:
    rows = ["| | Rule | Section | This case |", "|---|---|---|---|"]
    for f in check["findings"]:
        rows.append(f"| {STATUS_ICON[f['status']]} | {f['label']} | {f['source']} | {f['detail']} |")
    values = check.get("values", {})
    extra = []
    for key, name in (("maxLoan", "Maximum loan"), ("interestOnlyTotal", "Interest-only total"),
                      ("interestOnlyCap", "Interest-only cap"), ("maxLoanWithValuationReport",
                                                                  "Maximum with a full valuation report")):
        if key in values:
            extra.append(f"**{name}:** EUR {values[key]:,.0f}")
    return "\n".join(rows) + ("\n\n" + " · ".join(extra) if extra else "")


def _sources_markdown(result: rag.RAGAnswer) -> str:
    lines = []
    if result.check:
        lines += [VERDICT_BADGE[result.check["verdict"]].replace("## ", "### "), "",
                  "**Rule engine findings (RDFox)**", "", _findings_markdown(result.check), ""]
    for note in result.notes:
        lines.append(f"ℹ️ *{note}*  ")
    if result.case:
        facts = {k: v for k, v in result.case.items() if v not in (None, [], {})}
        lines += ["", "<details><summary>Case facts used</summary>\n\n```json\n"
                  + json.dumps(facts, indent=1, ensure_ascii=False, default=str) + "\n```\n</details>\n"]
    n_graph = sum(c.source == "graph" for c in result.chunks)
    lines.append(f"**{len(result.chunks)} passages** · mode `{result.mode}`"
                 + ("" if result.check else f" · {len(result.chunks) - n_graph} vector, {n_graph} graph") + "\n")
    for i, c in enumerate(result.chunks, start=1):
        badge = {"vector": "🔎 vector", "graph": f"🕸️ graph · *{c.via}*", "rules": "📐 cited by a rule"}[c.source]
        preview = c.text[:300].replace("\n", " ")
        score = "" if c.source == "rules" else f" · similarity {c.score:.3f}"
        lines.append(f"**{i}. [{c.citation}]** {c.section_title}  \n{badge}{score}  \n> {preview}…\n")
    timing = " · ".join(f"{k} {v}s" for k, v in result.latency_s.items())
    lines.append(f"---\n*model `{result.model}` · tokens in/out {result.prompt_tokens}/{result.completion_tokens}"
                 f" · {timing}*")
    return "\n".join(lines)


def _run(message: str, mode_label: str, top_k: int, model: str, case: Case | None = None) -> tuple[str, str]:
    mode = MODE_BY_LABEL[mode_label]
    try:
        result = rag.answer(driver, message, k=int(top_k), model=model, mode=mode, case=case)
        return result.answer, _sources_markdown(result)
    except Exception as e:  # show the problem in the UI instead of crashing
        return f"⚠️ Error: {e}", ""


def respond(message: str, history: list[dict], mode_label: str, top_k: int, model: str):
    if not message.strip():
        return history, gr.update(), ""
    reply, sources = _run(message, mode_label, top_k, model)
    history = history + [{"role": "user", "content": message},
                         {"role": "assistant", "content": reply}]
    return history, sources or EMPTY_SOURCES, ""


def compare(message: str, top_k: int, model: str):
    if not message.strip():
        return [""] * 6
    out = []
    for key in ("vector", "graph", "ontology"):
        out += list(_run(message, rag.RETRIEVAL_MODES[key], top_k, model))
    return out


# ----------------------------------------------------------------------------------- the case form
def _num(x):
    return None if x in (None, "") or (isinstance(x, (int, float)) and x == 0) else x


def _bool(x):
    return {"yes": True, "no": False}.get(x)


def _choice(x):
    return None if x in (None, "", UNKNOWN) else x


def build_case(ages, channel, conditions, rrr, ctype, value, valuation, mooring_value, lifetime, ship_register,
               shore, mooring_gov, zoning, permanent, seller_rabo, amount, term, io_amount, savings_amount,
               savings_pledged, energy_cost, value_after, explain, dipl_country, dipl_years, dipl_prev,
               dipl_months, partly_let, new_build, legal_right, erfpacht_ok, business_value, area, business_use,
               nhg, own_home) -> Case:
    applicants = []
    for i, part in enumerate([p.strip() for p in (ages or "").split(",") if p.strip()], start=1):
        applicants.append(Applicant(name=f"applicant {i}", age=int(part) if part.isdigit() else None))
    collateral = None
    if _choice(ctype):
        collateral = Collateral(type=ctype, market_value=_num(value), valuation=_choice(valuation),
                                mooring_value=_num(mooring_value), expected_lifetime_years=_num(lifetime),
                                in_ship_register=_bool(ship_register), shore_connection=_bool(shore),
                                mooring_from_government=_bool(mooring_gov), zoning=_choice(zoning),
                                permanent_living=_bool(permanent),
                                seller_is_permanent_resident_and_rabo_client=_bool(seller_rabo),
                                partly_let=_bool(partly_let), new_build=_choice(new_build),
                                legal_right=_choice(legal_right), erfpacht_approved_municipal=_bool(erfpacht_ok),
                                business_part_value=_num(business_value), area_hectares=_num(area),
                                business_use=_bool(business_use))
    loan = None
    if _num(amount) or _num(term) or _num(io_amount) or _num(savings_amount):
        parts = []
        if _num(io_amount):
            parts.append(LoanPart("interest_only", io_amount))
        if _num(savings_amount):
            parts.append(LoanPart("savings", savings_amount, pledged=_bool(savings_pledged)))
        loan = Loan(amount=_num(amount), term_years=_num(term), parts=parts)
    energy = EnergyInvestment(energy_cost, value_after, True) if _num(energy_cost) and _num(value_after) else None
    diplomat = None
    if dipl_country:
        diplomat = DiplomatRequest(country=dipl_country, planned_years=_num(dipl_years), keeps_dutch_employer=True,
                                   returns_to_home=True, previous_diplomat_letting=_bool(dipl_prev),
                                   months_lived_since_return=_num(dipl_months))
    return Case(applicants=applicants, channel=_choice(channel), conditions=_choice(conditions), rrr=_num(rrr),
                nhg=_bool(nhg), own_home_financed_by_rabobank=_bool(own_home), collateral=collateral, loan=loan, energy=energy, explain_requests=list(explain or []),
                diplomat=diplomat)


def check_form(language, model, *fields):
    case = build_case(*fields)
    question = ("Controleer deze hypotheekaanvraag tegen het beleid." if language == "Nederlands"
                else "Please check this mortgage application against the policy.")
    try:
        result = rag.answer(driver, question, model=model, mode="ontology", case=case)
    except Exception as e:
        return f"⚠️ Error: {e}", "", "", ""
    facts = json.dumps({k: v for k, v in case.to_dict().items() if v not in (None, [], {})}, indent=1,
                       ensure_ascii=False)
    return (VERDICT_BADGE[result.check["verdict"]], _findings_markdown(result.check), result.answer,
            f"```json\n{facts}\n```")


# ----------------------------------------------------------------------------------- layout
def create_demo() -> gr.Blocks:
    yn = ["unknown", "yes", "no"]
    with gr.Blocks(title="Mortgage Advisor Assistant") as demo:
        gr.Markdown("# 🏠 Mortgage Advisor Assistant\n"
                    "Ask questions about the **Rabobank Acceptatie- en Beheerbeleid** (14 Sep 2026), or check a "
                    "case against the policy rules. Answers in English or Dutch, with citations.")

        with gr.Tabs():
            with gr.Tab("💬 Chat"):
                mode = gr.Radio(list(rag.RETRIEVAL_MODES.values()), value=DEFAULT_MODE_LABEL,
                                label="Retrieval mode")
                with gr.Row():
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(label="Chat", height=500)
                        msg = gr.Textbox(placeholder="Ask about the policy or describe a case… / "
                                                     "Stel een vraag of beschrijf een casus…", show_label=False)
                        with gr.Row():
                            send = gr.Button("Send", variant="primary")
                            clear = gr.Button("Clear")
                        gr.Examples(EXAMPLES, inputs=msg)
                    with gr.Column(scale=2):
                        gr.Markdown("### 📄 Sources")
                        sources = gr.Markdown(EMPTY_SOURCES)

            with gr.Tab("✅ Check a case"):
                gr.Markdown("Fill in what you know; leave the rest empty or *unknown*. The **rule engine (RDFox)** "
                            "checks every encoded rule and reports ❌ violated · 🔍 only via Explain · ❓ missing "
                            "fact · ✅ OK. The LLM only writes the explanation.")
                with gr.Row():
                    with gr.Column():
                        with gr.Accordion("Applicants", open=True):
                            ages = gr.Textbox(label="Ages of all applicants/debtors, comma separated", value="45, 17")
                            channel = gr.Dropdown([UNKNOWN, "rabobank_advisor", "intermediair"], value="rabobank_advisor",
                                                  label="Channel")
                            conditions = gr.Dropdown([UNKNOWN, "basis", "plus"], value="basis", label="Conditions")
                            rrr = gr.Number(label="Rabo Risk Rating (RRR)", value=12, precision=0)
                        with gr.Accordion("Collateral", open=True):
                            ctype = gr.Dropdown([UNKNOWN] + list(COLLATERAL_TYPES), value="regular_house", label="Type")
                            value = gr.Number(label="Market value (EUR)", value=350000)
                            valuation = gr.Dropdown([UNKNOWN] + list(VALUATIONS), value="valuation_report",
                                                    label="Valuation")
                            with gr.Accordion("Houseboat / recreation home details", open=False):
                                mooring_value = gr.Number(label="Mooring value (EUR)")
                                lifetime = gr.Number(label="Expected lifetime of the boat (years)", precision=0)
                                ship_register = gr.Radio(yn, value="unknown", label="In the ship register?")
                                shore = gr.Radio(yn, value="unknown", label="Shore connection?")
                                mooring_gov = gr.Radio(yn, value="unknown", label="Mooring permit/lease from government?")
                                zoning = gr.Dropdown([UNKNOWN, "residential", "recreation",
                                                      "recreation_and_residential"], value=UNKNOWN, label="Zoning")
                                permanent = gr.Radio(yn, value="unknown", label="Client will live there permanently?")
                                seller_rabo = gr.Radio(yn, value="unknown",
                                                       label="Seller lives there permanently and is a Rabobank client?")
                            with gr.Accordion("Use, construction, legal right, other", open=False):
                                partly_let = gr.Radio(yn, value="unknown", label="(Partly) let out?")
                                new_build = gr.Dropdown([UNKNOWN] + list(NEW_BUILD_KINDS), value=UNKNOWN,
                                                        label="New build (kind)")
                                legal_right = gr.Dropdown([UNKNOWN] + list(LEGAL_RIGHTS), value=UNKNOWN,
                                                          label="Legal right (erfpacht / opstal)")
                                erfpacht_ok = gr.Radio(yn, value="unknown",
                                                       label="Approved municipal erfpacht conditions (Bijlage 1)?")
                                business_value = gr.Number(label="Home with shop/practice: value of the business part (EUR)")
                                area = gr.Number(label="Farmhouse: total area (hectares)")
                                business_use = gr.Radio(yn, value="unknown", label="Business use?")
                                nhg = gr.Radio(yn, value="unknown", label="With NHG?")
                                own_home = gr.Radio(yn, value="unknown",
                                                    label="Applicant owns a home financed by Rabobank?")
                    with gr.Column():
                        with gr.Accordion("Loan", open=True):
                            amount = gr.Number(label="Loan amount (EUR)", value=340000)
                            term = gr.Number(label="Term (years)", value=30, precision=0)
                            io_amount = gr.Number(label="of which interest-only (EUR)", value=60000)
                            savings_amount = gr.Number(label="of which with a build-up product / savings (EUR)")
                            savings_pledged = gr.Radio(yn, value="unknown", label="Build-up product pledged?")
                        with gr.Accordion("Energy-saving measures", open=False):
                            energy_cost = gr.Number(label="Costs of energy-saving measures (EUR)")
                            value_after = gr.Number(label="Market value after renovation (EUR)")
                        with gr.Accordion("Explain / letting", open=False):
                            explain = gr.CheckboxGroup(list(EXPLAIN_TYPES), label="Requested maatwerk / exceptions")
                            dipl_country = gr.Textbox(label="Diplomat clause: country (ISO code, e.g. DE, GB)")
                            dipl_years = gr.Number(label="Diplomat clause: planned years abroad")
                            dipl_prev = gr.Radio(yn, value="unknown", label="Used the diplomat clause before?")
                            dipl_months = gr.Number(label="Months lived in the home since returning", precision=0)
                        language = gr.Radio(["English", "Nederlands"], value="English", label="Answer language")
                        check_btn = gr.Button("Check against the policy", variant="primary")
                verdict = gr.Markdown()
                findings = gr.Markdown()
                with gr.Row():
                    with gr.Column(scale=3):
                        explanation = gr.Markdown()
                    with gr.Column(scale=2):
                        with gr.Accordion("Case facts sent to the rule engine", open=False):
                            facts_md = gr.Markdown()

            with gr.Tab("🔀 Compare"):
                gr.Markdown("Ask one question and see **RAG**, **GraphRAG** and **ontology + rules** side by side.")
                cmp_msg = gr.Textbox(placeholder="Question or case…", show_label=False)
                cmp_btn = gr.Button("Compare", variant="primary")
                gr.Examples(EXAMPLES, inputs=cmp_msg)
                with gr.Row():
                    cmp_out = []
                    for title in ("🔎 Vector search (RAG)", "🕸️ Document graph (GraphRAG)", "📐 Ontology + rules"):
                        with gr.Column():
                            gr.Markdown(f"### {title}")
                            answer_md = gr.Markdown()
                            with gr.Accordion("Sources", open=False):
                                src_md = gr.Markdown()
                            cmp_out += [answer_md, src_md]

            with gr.Tab("⚙️ Settings"):
                model = gr.Dropdown(MODELS, value=settings.llm_model, label="LLM (Groq)")
                top_k = gr.Slider(1, 15, value=settings.top_k, step=1,
                                  label="Vector passages (top-k). GraphRAG adds up to the same number from the graph.")
                gr.Markdown(f"Embeddings: `{settings.embedding_provider}:{settings.embedding_model}` · "
                            f"Neo4j database: `{settings.neo4j_database}`  \n{rag_stats()}  \n"
                            f"Rule engine: RDFox at `{rdfox.ENDPOINT}` · "
                            f"{'🟢 running' if rdfox.is_available() else '🔴 not running (see docs/RDFOX_SETUP.md)'}"
                            f" · {rule_count()} rules in the ontology")

            with gr.Tab("ℹ️ About"):
                gr.Markdown(
                    "**Vector search (RAG)**: the question becomes a vector; Neo4j finds the most similar policy "
                    "passages; the LLM answers only from those passages and cites them.\n\n"
                    "**Vector + document graph (GraphRAG)**: same start, then the graph is followed one step: "
                    "`REFERS_TO`, `HAS_EXCEPTION` (🔍 → Explain), `PARENT`/`CHILD`, `USES_TERM` (definitions), "
                    "`REQUIRES_DOCUMENTS`.\n\n"
                    "**Vector + graph + ontology/rules**: the policy rules are encoded as an ontology (built on "
                    "**FIBO**) with **Datalog rules** in **RDFox**. A described case is turned into facts, every "
                    "rule is checked exactly (❌ / 🔍 / ❓ / ✅), and the LLM only explains the findings, citing the "
                    "sections the rules come from (fetched from the Neo4j document graph). General questions are "
                    "answered with GraphRAG plus the ontology's Dutch/English synonyms.\n\n"
                    "⚠️ Prototype for internal experimentation. Only the encoded rules are checked; always check "
                    "the cited policy text.")

        inputs = [msg, chatbot, mode, top_k, model]
        outputs = [chatbot, sources, msg]
        send.click(respond, inputs, outputs)
        msg.submit(respond, inputs, outputs)
        clear.click(lambda: ([], EMPTY_SOURCES), None, [chatbot, sources])
        cmp_btn.click(compare, [cmp_msg, top_k, model], cmp_out)
        cmp_msg.submit(compare, [cmp_msg, top_k, model], cmp_out)
        form = [ages, channel, conditions, rrr, ctype, value, valuation, mooring_value, lifetime, ship_register,
                shore, mooring_gov, zoning, permanent, seller_rabo, amount, term, io_amount, savings_amount,
                savings_pledged, energy_cost, value_after, explain, dipl_country, dipl_years, dipl_prev, dipl_months,
                partly_let, new_build, legal_right, erfpacht_ok, business_value, area, business_use, nhg, own_home]
        check_btn.click(check_form, [language, model] + form, [verdict, findings, explanation, facts_md])
    return demo


def rag_stats() -> str:
    records = driver.execute_query(
        "MATCH (n) WHERE n:Chunk OR n:Section OR n:Definition RETURN labels(n)[0] AS l, count(*) AS n",
        database_=settings.neo4j_database).records
    counts = {r["l"]: r["n"] for r in records}
    return " · ".join(f"{label}s: **{counts.get(label, 0)}**" for label in ("Chunk", "Section", "Definition"))


if __name__ == "__main__":
    create_demo().launch(theme=gr.themes.Soft(primary_hue="teal"))
