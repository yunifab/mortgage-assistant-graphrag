"""Check one case against the policy rules with RDFox.

    case (JSON) -> RDF facts -> RDFox (+ FIBO slice + rabo ontology + Datalog rules)
                -> findings (violated / needs Explain / missing fact / checked OK) + computed values
                -> verdict

The LLM is NOT involved here: the findings are exact and the same every time.
"""

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDFS, SKOS

from mortgage_assistant.config import PROJECT_ROOT
from mortgage_assistant.rules import rdfox
from mortgage_assistant.rules.case import CASE, RABO, Case

ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
STATUS_ORDER = {"violated": 0, "needs_explain": 1, "missing_fact": 2, "ok": 3}
STATUS_ICON = {"violated": "❌", "needs_explain": "🔍", "missing_fact": "❓", "ok": "✅"}


@dataclass
class Finding:
    rule: str  # e.g. 'R_MinAge'
    status: str  # violated | needs_explain | missing_fact | ok
    label: str  # what the rule says (English)
    source: str  # policy section id, e.g. 'AB-2.1' (also the Neo4j :Section id)
    detail: str = ""  # the facts of THIS case, e.g. 'son: age 17'
    explain_source: str | None = None

    @property
    def icon(self) -> str:
        return STATUS_ICON[self.status]


@dataclass
class CheckResult:
    verdict: str  # reject | explain | incomplete | accept
    findings: list[Finding]
    values: dict = field(default_factory=dict)  # computed amounts: max loan, interest-only total, ...

    def by_status(self, status: str) -> list[Finding]:
        return [f for f in self.findings if f.status == status]

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "findings": [asdict(f) for f in self.findings], "values": self.values}


# ------------------------------------------------------------------------------------- ontology files
ONTOLOGY_FILES = ("fibo_slice.ttl", "rabo_mortgage.ttl", "taxonomy_collateral.ttl")


@lru_cache(maxsize=1)
def _ontology_texts() -> tuple[list[str], str]:
    turtle = [(ONTOLOGY_DIR / name).read_text(encoding="utf-8") for name in ONTOLOGY_FILES]
    rules = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ONTOLOGY_DIR / "rules").glob("*.dlog")))
    return turtle, rules


@lru_cache(maxsize=1)
def ontology_graph() -> Graph:
    """Our ontology (rabo terms + collateral taxonomy) as one rdflib graph, for labels, rules and limits."""
    g = Graph()
    for name in ONTOLOGY_FILES[1:]:
        g.parse(ONTOLOGY_DIR / name, format="turtle")
    return g


@lru_cache(maxsize=1)
def rule_metadata() -> dict[str, dict]:
    """Rule id -> label, source section, explain section (read from the ontology)."""
    g = ontology_graph()
    meta = {}
    for rule in g.subjects(predicate=RABO.source):
        if (rule, None, RABO.Rule) not in g:
            continue
        rid = str(rule).split("#")[-1]
        meta[rid] = {
            "label": str(g.value(rule, RDFS.label) or rid),
            "source": str(g.value(rule, RABO.source)),
            "explain_source": str(g.value(rule, RABO.explainSource)) if g.value(rule, RABO.explainSource) else None,
            "definition_nl": str(g.value(rule, SKOS.definition) or ""),
        }
    return meta


def rule_count() -> int:
    return len(rule_metadata())


# ------------------------------------------------------------------------------------- the check
QUERY_FINDINGS = """
PREFIX rabo: <https://linq.example.org/ontology/rabo-mortgage#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?s ?status ?rule ?label WHERE {
  VALUES ?status { rabo:violates rabo:needsExplain rabo:missingFact rabo:checked }
  ?s ?status ?rule .
  OPTIONAL { ?s rdfs:label ?label }
}"""

QUERY_VALUES = """
PREFIX rabo: <https://linq.example.org/ontology/rabo-mortgage#>
SELECT ?p ?v WHERE {
  VALUES ?p { rabo:maxLoan rabo:baseMaxLoan rabo:energyMaxLoan rabo:loanAmount rabo:interestOnlyTotal
              rabo:interestOnlyCap rabo:numberOfDebtors rabo:maxLoanWithValuationReport
              rabo:energyRuleNotApplicable }
  <%s> ?p ?v .
}"""

QUERY_COLLATERAL = """
PREFIX rabo: <https://linq.example.org/ontology/rabo-mortgage#>
SELECT ?ltv ?mltv WHERE { <%s> rabo:hasCollateral ?c . OPTIONAL { ?c rabo:effectiveLTV ?ltv } OPTIONAL { ?c rabo:mooringMaxLTV ?mltv } }"""

QUERY_HIDDEN_IO = """
PREFIX rabo: <https://linq.example.org/ontology/rabo-mortgage#>
SELECT ?amount WHERE { <%s> rabo:hasLoanPart ?p . ?p rabo:hiddenInterestOnly true ; rabo:amount ?amount }"""

QUERY_DESKTOP_EXCLUDED = """
PREFIX rabo: <https://linq.example.org/ontology/rabo-mortgage#>
SELECT DISTINCT ?why WHERE { <%s> rabo:hasCollateral ?c . ?c rabo:desktopExcluded ?why }"""

STATUS_PREDICATE = {"violates": "violated", "needsExplain": "needs_explain", "missingFact": "missing_fact",
                    "checked": "ok"}


def _num(v: str) -> float | int:
    f = float(v)
    return int(f) if f.is_integer() else f


def run_rdfox(case: Case, case_id: str = "case") -> tuple[list[dict], dict]:
    """Raw RDFox output: finding rows and computed values."""
    turtle, rules = _ontology_texts()
    facts = case.to_rdf(case_id).serialize(format="turtle")
    app = str(CASE[case_id])
    with rdfox.temporary_datastore() as ds:
        for text in turtle:
            ds.load_turtle(text)
        ds.load_turtle(facts)
        ds.load_datalog(rules)
        rows = ds.select(QUERY_FINDINGS)
        values = {r["p"].split("#")[-1]: (r["v"] if r["v"] in ("true", "false") else _num(r["v"]))
                  for r in ds.select(QUERY_VALUES % app)}
        for r in ds.select(QUERY_COLLATERAL % app):
            if "ltv" in r:
                values["maxLTV"] = _num(r["ltv"])
            if "mltv" in r:
                values["mooringMaxLTV"] = _num(r["mltv"])
        if "interestOnlyTotal" not in values:
            values.pop("interestOnlyCap", None)  # only relevant when there is interest-only
        reasons = [r["why"] for r in ds.select(QUERY_DESKTOP_EXCLUDED % app)]
        if reasons:
            values["desktopExcluded"] = reasons
        hidden = [_num(r["amount"]) for r in ds.select(QUERY_HIDDEN_IO % app)]
        if hidden:
            values["hiddenInterestOnly"] = sum(hidden)
    return rows, values


def check_case(case: Case) -> CheckResult:
    rows, values = run_rdfox(case)
    # Missing valuation method where the norm depends on it: compute each scenario with the rules too,
    # so the advisor gets exact amounts ("with a valuation report: EUR X") instead of an LLM guess
    if case.collateral and case.collateral.valuation is None and _norms_by_valuation(case.collateral.type):
        scenarios = {}
        for method in ("valuation_report", "desktop_plus"):
            alt = Case.from_dict(case.to_dict())
            alt.collateral.valuation = method
            alt_values = run_rdfox(alt)[1]
            if "maxLoan" in alt_values:
                scenarios[method] = alt_values["maxLoan"]
        if scenarios:
            values["maxLoanByValuation"] = scenarios
    meta = rule_metadata()
    app = str(CASE["case"])

    # (rule, status) -> subjects (an applicant label, the collateral, or the application itself)
    found: dict[tuple[str, str], set[str]] = {}
    for r in rows:
        rule = r["rule"].split("#")[-1]
        status = STATUS_PREDICATE[r["status"].split("#")[-1]]
        subject = "" if r["s"] == app else r.get("label", "collateral" if r["s"].endswith("_collateral") else "")
        found.setdefault((rule, status), set()).add(subject)

    problems = {rule for (rule, status) in found if status != "ok"}
    if ("R_InterestOnlyType", "violated") in found:
        problems.add("R_InterestOnlyCap")  # the cap is irrelevant when interest-only is not allowed at all
    findings = []
    for (rule, status), subjects in found.items():
        if status == "ok" and rule in problems:
            continue  # checked, but it has a problem: report the problem only
        m = meta.get(rule, {"label": rule, "source": "", "explain_source": None})
        findings.append(Finding(rule=rule, status=status, label=m["label"], source=m["source"],
                                detail=_detail(rule, status, case, values, sorted(s for s in subjects if s)),
                                explain_source=m.get("explain_source")))
    findings.sort(key=lambda f: (STATUS_ORDER[f.status], f.source, f.rule))

    if any(f.status == "violated" for f in findings):
        verdict = "reject"
    elif any(f.status == "needs_explain" for f in findings):
        verdict = "explain"
    elif any(f.status == "missing_fact" for f in findings):
        verdict = "incomplete"
    else:
        verdict = "accept"
    return CheckResult(verdict=verdict, findings=findings, values=values)


# ------------------------------------------------------------------------------------- explanations
def _eur(x) -> str:
    return f"EUR {x:,.0f}" if isinstance(x, (int, float)) else str(x)


_ontology_graph = ontology_graph


def _norms_by_valuation(collateral_type: str | None) -> list[tuple[str, float]]:
    """LTV norms that depend on the valuation method, e.g. [('a desktop valuation', 0.9), ('a valuation report', 1.0)]."""
    from mortgage_assistant.rules.case import COLLATERAL_TYPES

    if collateral_type not in COLLATERAL_TYPES:
        return []
    g, out = _ontology_graph(), []
    for norm in g.subjects(RABO.forCollateral, COLLATERAL_TYPES[collateral_type]):
        vtype = g.value(norm, RABO.forValuation)
        if vtype is not None:
            name = {"DesktopValuation": "a desktop valuation", "ValuationReport": "a valuation report"}.get(
                str(vtype).split("#")[-1], str(vtype).split("#")[-1])
            out.append((name, float(g.value(norm, RABO.maxLTV))))
    return sorted(out, key=lambda x: x[1])


def _collateral_desc(c) -> str:
    parts = [c.type or "unknown type"]
    if c.partly_let or c.type == "rental_home":
        parts.append("partly let")
    if c.new_build:
        parts.append(f"new build ({c.new_build})")
    if c.legal_right:
        parts.append(c.legal_right)
    return ", ".join(parts)


def _detail(rule: str, status: str, case: Case, v: dict, subjects: list[str]) -> str:
    """A short, factual sentence about THIS case (numbers come from RDFox, not from the LLM)."""
    c, loan = case.collateral, case.loan
    who = ", ".join(subjects)
    if rule == "R_MinAge":
        if status == "violated":
            ages = {a.name or "": a.age for a in case.applicants}
            return "; ".join(f"{s}: age {ages.get(s, '?')}" for s in subjects) + " (minimum 18)"
        if status == "missing_fact":
            return f"age not given for: {who}"
        return "all applicants are 18 or older"
    if rule == "R_Debtors":
        return (f"{v.get('numberOfDebtors')} debtors, channel {case.channel or 'unknown'}, "
                f"conditions {case.conditions or 'unknown'}")
    if rule == "R_RRR":
        return f"RRR {case.rrr}" if case.rrr is not None else "RRR not given"
    if rule == "R_MaxTerm":
        return f"term {loan.term_years} years (maximum 30)"
    if rule == "R_TermKnown":
        return "the loan term is not given"
    if rule in ("R_InterestOnlyCap", "R_InterestOnlyType", "R_DesktopInterestOnly", "R_InterestOnlyCounts"):
        parts = [f"interest-only total {_eur(v.get('interestOnlyTotal', 0))}"]
        if v.get("hiddenInterestOnly"):
            parts.append(f"of which {_eur(v['hiddenInterestOnly'])} is a loan part with a build-up product "
                         "that is not pledged (counts as interest-only)")
        if rule == "R_InterestOnlyCap" and "interestOnlyCap" in v:
            parts.append(f"cap {_eur(v['interestOnlyCap'])} (lower of 30% of market value and EUR 150,000)")
        if rule == "R_InterestOnlyType" and c:
            parts.append(f"collateral type: {c.type}")
        if rule == "R_DesktopInterestOnly" and c:
            parts.append(f"valuation: {c.valuation}")
        return "; ".join(parts)
    if rule == "R_MaxLoan":
        if loan and loan.ltv is not None and v.get("loanAmount") is None:
            return f"requested {loan.ltv:.0%} of the market value, maximum {v.get('maxLTV', 0):.0%}"
        s = f"requested {_eur(v.get('loanAmount'))}, maximum {_eur(v.get('maxLoan'))}"
        if "maxLTV" in v and c and c.market_value:
            s += f" ({v['maxLTV']:.0%} of {_eur(c.market_value)}"
            if c.mooring_value:
                s += f" + {v.get('mooringMaxLTV', 0):.0%} of mooring {_eur(c.mooring_value)}"
            s += ")"
        if "energyMaxLoan" in v:
            s += " - energy-saving measures rule applied"
        if "maxLoanWithValuationReport" in v:
            s += f"; with a full valuation report the maximum would be {_eur(v['maxLoanWithValuationReport'])}"
        return s
    if rule == "R_Energy106":
        if "energyMaxLoan" in v:
            e = case.energy
            return (f"maximum {_eur(v['energyMaxLoan'])} = lower of {_eur(c.market_value)} + costs {_eur(e.cost)} "
                    f"and 106% of {_eur(e.value_after_renovation)}")
        if v.get("energyRuleNotApplicable") == "true":
            return "not applicable: the 106% rule only applies to collateral with a 100% norm"
        e = case.energy
        missing = [n for n, val in (("costs", e.cost if e else None),
                                    ("value after renovation", e.value_after_renovation if e else None)) if val is None]
        return ("not given: " + ", ".join(missing)) if missing else             "the energy rule needs: only energy-saving measures, costs, value after renovation"
    if rule == "R_ValuationMethod":
        if status == "missing_fact":
            needed = {"houseboat": "an E.M.C.I. certified houseboat valuer", "recreation_home": "an NRVT valuer"}
            return f"a valuation report is mentioned; it must be made by {needed.get(c.type, 'the right valuer')}: not given"
        return f"valuation '{c.valuation}' for collateral type '{c.type}'"
    if rule == "R_ValuationKnown":
        missing = [n for n, val in (("market value", c.market_value), ("valuation method", c.valuation)) if val is None]
        text = "not given: " + ", ".join(missing)
        if c.valuation is None and (norms := _norms_by_valuation(c.type)):
            text += " (for this collateral the maximum is " + ", ".join(
                f"{n:.0%} with {name}" for name, n in norms) + ")"
        if scen := v.get("maxLoanByValuation"):
            names = {"valuation_report": "a validated valuation report", "desktop_plus": "a desktop valuation"}
            text += "; computed maximum loan: " + "; ".join(f"{_eur(m)} with {names[k]}" for k, m in scen.items())
        return text
    if rule == "R_HouseboatLifetime":
        if status == "missing_fact":
            return "expected lifetime of the boat (from the valuation report) not given"
        return f"term {loan.term_years} years, expected lifetime {c.expected_lifetime_years} years"
    if rule == "R_MooringTerm":
        return f"term {loan.term_years} years; the loan on the mooring must be repaid in 20 years"
    if rule == "R_HouseboatRegister":
        return "registered in the ship register: " + ("not given" if c.in_ship_register is None else str(c.in_ship_register))
    if rule == "R_HouseboatShore":
        return "fixed mooring with shore connection: " + ("not given" if c.shore_connection is None else str(c.shore_connection))
    if rule == "R_HouseboatMooringPermit":
        return "mooring permit/lease from a government body: " + (
            "not given" if c.mooring_from_government is None else str(c.mooring_from_government))
    if rule == "R_RecreationPermanent":
        return (f"permanent living: {c.permanent_living}; zoning: {c.zoning or 'not given'}; seller lives there "
                f"permanently and is a Rabobank client: {c.seller_is_permanent_resident_and_rabo_client}")
    if rule == "R_RequiredConditions":
        return f"collateral: {_collateral_desc(c)}; conditions: {case.conditions or 'not given'}"
    if rule == "R_TypeMaxTerm":
        return f"term {loan.term_years} years for collateral type '{c.type}'"
    if rule == "R_LettingType":
        return f"partly let, collateral type '{c.type}'"
    if rule == "R_RequiresNHG":
        return "NHG: " + ("not given" if case.nhg is None else str(case.nhg))
    if rule == "R_OwnHomeAtRabobank":
        return "own home financed by Rabobank: " + (
            "not given" if case.own_home_financed_by_rabobank is None else str(case.own_home_financed_by_rabobank))
    if rule == "R_FarmArea":
        return (f"area: {'not given' if c.area_hectares is None else f'{c.area_hectares} ha'} (maximum 3 ha); "
                f"business use: {c.business_use}")
    if rule == "R_DesktopConditions":
        return "a desktop valuation is not possible with " + " and ".join(v.get("desktopExcluded", ["?"]))
    if rule == "R_ConstructionCosts":
        return f"value from construction costs; new build: {c.new_build or 'no'}"
    if rule == "R_ErfpachtReview":
        return ("approved municipal erfpacht conditions (Bijlage 1)" if c.erfpacht_approved_municipal
                else "erfpacht: a specialist must review the conditions (unless approved municipal conditions, Bijlage 1)")
    if rule == "R_OpstalReview":
        return ("opstal for a utility: no review needed" if c.legal_right == "opstal_utility"
                else "opstal: a specialist must review the right of superficies")
    if rule in ("R_ExplainCombination", "R_ExplainRoute", "R_MaatwerkNoLetting"):
        return "requested: " + ", ".join(case.explain_requests)
    if rule.startswith("R_Diplomat") and case.diplomat:
        d = case.diplomat
        return {"R_DiplomatCountry": f"country {d.country}",
                "R_DiplomatDuration": f"planned {d.planned_years} years (maximum 3)",
                "R_DiplomatRepeat": f"used before: {d.previous_diplomat_letting}; lived in the home again for "
                                    f"{d.months_lived_since_return} months (minimum 12)",
                "R_DiplomatEmployer": f"keeps Dutch employer: {d.keeps_dutch_employer}; returns to the home: "
                                      f"{d.returns_to_home}"}.get(rule, "")
    return who
