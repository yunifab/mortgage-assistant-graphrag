"""The facts of one mortgage application, and their conversion to RDF (layer 4 of the ontology design).

A case is plain JSON (easy to fill from a form or to extract with an LLM). Every field is optional:
a rule that needs a missing fact reports "missing fact" instead of guessing.

Example (UC9):
    {"applicants": [], "rrr": 18,
     "collateral": {"type": "houseboat", "market_value": 200000, "valuation": "emci",
                    "in_ship_register": true, "mooring_from_government": true},
     "loan": {"amount": 170000, "term_years": 20}}
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal

from rdflib import RDF, RDFS, Graph, Literal, Namespace
from rdflib.namespace import XSD

RABO = Namespace("https://linq.example.org/ontology/rabo-mortgage#")
CASE = Namespace("https://linq.example.org/case/")

# Allowed values (form choices / LLM extraction targets) -> ontology terms
# Building type (taxonomy dimension 1). 'rental_home' is kept for older cases: a regular house that is partly let.
COLLATERAL_TYPES = {
    "regular_house": RABO.RegularHouse, "apartment": RABO.Apartment,
    "shop_house": RABO.ShopHouse, "practice_house": RABO.PracticeHouse,
    "farmhouse_residential": RABO.FarmhouseResidential, "farmhouse_agricultural": RABO.FarmhouseAgricultural,
    "business_dwelling_private": RABO.BusinessDwellingPrivate,
    "business_dwelling_mixed_use": RABO.BusinessDwellingMixedUse,
    "mobile_home": RABO.MobileHome, "recreation_home": RABO.RecreationHome,
    "water_home": RABO.WaterHome, "houseboat": RABO.Houseboat,
    "standalone_garage": RABO.StandaloneGarage, "other_commercial_property": RABO.OtherCommercialProperty,
    "rental_home": RABO.RegularHouse,
}
# Construction (dimension 3) and legal right (dimension 4)
NEW_BUILD_KINDS = {
    "project": RABO.ProjectBuild, "transformation": RABO.TransformationBuild, "turnkey": RABO.TurnkeyBuild,
    "self_build": RABO.SelfBuild, "cpo": RABO.CPOBuild, "demolition": RABO.DemolitionRebuild,
}
LEGAL_RIGHTS = {"erfpacht": RABO.ErfpachtCollateral, "opstal": RABO.OpstalCollateral,
                "opstal_utility": RABO.OpstalUtilityCollateral}
VALUATIONS = {
    "desktop": RABO.DesktopTaxatie, "desktop_plus": RABO.DesktopTaxatiePlus,
    "valuation_report": RABO.ValuationReport, "emci": RABO.EMCIValuationReport, "nrvt": RABO.NRVTValuationReport,
    "lav": RABO.LAVValuationReport, "business_valuation": RABO.BusinessPropertyValuation,
    "construction_costs": RABO.ConstructionCostsValuation,
}
LOAN_PART_TYPES = {
    "interest_only": RABO.InterestOnlyPart, "annuity": RABO.AnnuityPart, "linear": RABO.LinearPart,
    "savings": RABO.SavingsPart,
}
CHANNELS = {"rabobank_advisor": RABO.RabobankAdvisor, "intermediair": RABO.Intermediair}
CONDITIONS = {"basis": RABO.Basis, "plus": RABO.Plus}
ZONINGS = {"residential": RABO.ZoningResidential, "recreation": RABO.ZoningRecreation,
           "recreation_and_residential": RABO.ZoningRecreationAndResidential}
EXPLAIN_TYPES = {
    "maatwerk_niet_annuitair": RABO.MaatwerkNietAnnuitair, "maatwerk_vermogen": RABO.MaatwerkVermogen,
    "exception_applicant": RABO.ApplicantException, "exception_income": RABO.IncomeException,
    "exception_collateral": RABO.CollateralException, "exception_documents": RABO.DocumentException,
}


@dataclass
class Applicant:
    name: str | None = None
    age: int | None = None


@dataclass
class LoanPart:
    type: str  # one of LOAN_PART_TYPES
    amount: float
    pledged: bool | None = None  # only for 'savings': is the build-up product pledged?


@dataclass
class Collateral:
    type: str | None = None  # one of COLLATERAL_TYPES
    market_value: float | None = None
    valuation: str | None = None  # one of VALUATIONS
    mooring_value: float | None = None  # houseboat: value of the mooring (ligplaats)
    expected_lifetime_years: int | None = None  # houseboat: from the valuation report
    in_ship_register: bool | None = None
    shore_connection: bool | None = None
    mooring_from_government: bool | None = None  # permit/lease from a government body, or owned
    zoning: str | None = None  # one of ZONINGS
    permanent_living: bool | None = None
    seller_is_permanent_resident_and_rabo_client: bool | None = None
    partly_let: bool | None = None  # dimension 2 (use): (partly) let out with permission
    new_build: str | None = None  # dimension 3: one of NEW_BUILD_KINDS ('project', 'self_build', ...)
    legal_right: str | None = None  # dimension 4: 'erfpacht' | 'opstal' | 'opstal_utility'
    erfpacht_approved_municipal: bool | None = None  # approved municipal conditions (Bijlage 1)
    business_part_value: float | None = None  # home with shop/practice: value of the business part
    area_hectares: float | None = None  # farmhouse: total area of dwelling + buildings + land
    business_use: bool | None = None


@dataclass
class Loan:
    amount: float | None = None
    ltv: float | None = None  # loan as a share of the market value, e.g. 0.85 (when no amount is given)
    term_years: int | None = None
    parts: list[LoanPart] = field(default_factory=list)


@dataclass
class EnergyInvestment:
    cost: float | None = None
    value_after_renovation: float | None = None
    only_energy_measures: bool | None = True


@dataclass
class DiplomatRequest:
    country: str | None = None  # ISO code, e.g. 'GB', 'DE'
    planned_years: float | None = None
    keeps_dutch_employer: bool | None = None
    returns_to_home: bool | None = None
    previous_diplomat_letting: bool | None = None
    months_lived_since_return: int | None = None


@dataclass
class Case:
    applicants: list[Applicant] = field(default_factory=list)
    channel: str | None = None
    conditions: str | None = None
    rrr: int | None = None
    nhg: bool | None = None  # application with Nationale Hypotheek Garantie
    own_home_financed_by_rabobank: bool | None = None
    collateral: Collateral | None = None
    loan: Loan | None = None
    energy: EnergyInvestment | None = None
    explain_requests: list[str] = field(default_factory=list)
    diplomat: DiplomatRequest | None = None

    # ---------------------------------------------------------------- JSON
    @classmethod
    def from_dict(cls, d: dict) -> "Case":
        def sub(klass, value):
            return klass(**{k: v for k, v in value.items() if k in klass.__dataclass_fields__}) if value else None

        loan = sub(Loan, {k: v for k, v in (d.get("loan") or {}).items() if k != "parts"})
        if d.get("loan"):
            loan = loan or Loan()
            loan.parts = [sub(LoanPart, p) for p in d["loan"].get("parts", []) if p]
        return cls(
            applicants=[sub(Applicant, a) or Applicant() for a in d.get("applicants", [])],
            channel=d.get("channel"), conditions=d.get("conditions"), rrr=d.get("rrr"),
            nhg=d.get("nhg"), own_home_financed_by_rabobank=d.get("own_home_financed_by_rabobank"),
            collateral=sub(Collateral, d.get("collateral")), loan=loan,
            energy=sub(EnergyInvestment, d.get("energy")),
            explain_requests=list(d.get("explain_requests", [])),
            diplomat=sub(DiplomatRequest, d.get("diplomat")),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    # ---------------------------------------------------------------- RDF
    def to_rdf(self, case_id: str = "case") -> Graph:
        g = Graph()
        g.bind("rabo", RABO), g.bind("case", CASE)
        app = CASE[case_id]
        g.add((app, RDF.type, RABO.MortgageApplication))

        def add(s, p, value, choices=None):
            if value is None:
                return
            if choices is not None:
                if value not in choices:
                    raise ValueError(f"unknown value {value!r} for {p} (choose from {sorted(choices)})")
                g.add((s, p, choices[value]))
            elif isinstance(value, bool):
                g.add((s, p, Literal(value)))
            elif isinstance(value, (int, float)):
                g.add((s, p, Literal(Decimal(str(value)), datatype=XSD.decimal)))
            else:
                g.add((s, p, Literal(value)))

        add(app, RABO.channel, self.channel, CHANNELS)
        add(app, RABO.conditions, self.conditions, CONDITIONS)
        add(app, RABO.rrr, self.rrr)
        add(app, RABO.nhg, self.nhg)
        add(app, RABO.ownHomeFinancedByRabobank, self.own_home_financed_by_rabobank)
        for i, a in enumerate(self.applicants, start=1):
            p = CASE[f"{case_id}_applicant{i}"]
            g.add((app, RABO.hasApplicant, p)), g.add((p, RDF.type, RABO.Applicant))
            g.add((p, RDFS.label, Literal(a.name or f"applicant {i}")))
            add(p, RABO.age, a.age)
        if c := self.collateral:
            node = CASE[f"{case_id}_collateral"]
            g.add((app, RABO.hasCollateral, node))
            if c.type:
                add(node, RDF.type, c.type, COLLATERAL_TYPES)
            else:
                g.add((node, RDF.type, RABO.Collateral))
            add(node, RABO.marketValue, c.market_value)
            if c.valuation:
                v = CASE[f"{case_id}_valuation"]
                g.add((node, RABO.valuedBy, v))
                add(v, RDF.type, c.valuation, VALUATIONS)
            add(node, RABO.mooringValue, c.mooring_value)
            add(node, RABO.expectedLifetimeYears, c.expected_lifetime_years)
            add(node, RABO.inShipRegister, c.in_ship_register)
            add(node, RABO.shoreConnection, c.shore_connection)
            add(node, RABO.mooringFromGovernment, c.mooring_from_government)
            add(node, RABO.zoning, c.zoning, ZONINGS)
            add(node, RABO.permanentLiving, c.permanent_living)
            add(node, RABO.sellerIsPermanentResidentAndRaboClient, c.seller_is_permanent_resident_and_rabo_client)
            if c.partly_let or c.type == "rental_home":
                g.add((node, RDF.type, RABO.PartlyLetHome))
            if c.new_build:
                add(node, RDF.type, c.new_build, NEW_BUILD_KINDS)
            if c.legal_right:
                add(node, RDF.type, c.legal_right, LEGAL_RIGHTS)
            add(node, RABO.erfpachtApprovedMunicipal, c.erfpacht_approved_municipal)
            add(node, RABO.businessPartValue, c.business_part_value)
            add(node, RABO.areaHectares, c.area_hectares)
            add(node, RABO.businessUse, c.business_use)
        if loan := self.loan:
            add(app, RABO.requestedAmount, loan.amount)
            add(app, RABO.requestedLTV, loan.ltv)
            add(app, RABO.termYears, loan.term_years)
            for i, part in enumerate(loan.parts, start=1):
                lp = CASE[f"{case_id}_part{i}"]
                g.add((app, RABO.hasLoanPart, lp))
                add(lp, RDF.type, part.type, LOAN_PART_TYPES)
                add(lp, RABO.amount, part.amount)
                add(lp, RABO.pledged, part.pledged)
        if e := self.energy:
            node = CASE[f"{case_id}_energy"]
            g.add((app, RABO.hasEnergyInvestment, node))
            add(node, RABO.cost, e.cost)
            add(node, RABO.valueAfterRenovation, e.value_after_renovation)
            add(node, RABO.onlyEnergyMeasures, e.only_energy_measures)
        for i, kind in enumerate(self.explain_requests, start=1):
            x = CASE[f"{case_id}_explain{i}"]
            g.add((app, RABO.hasExplainRequest, x))
            add(x, RDF.type, kind, EXPLAIN_TYPES)
        if d := self.diplomat:
            node = CASE[f"{case_id}_diplomat"]
            g.add((app, RABO.hasDiplomatRequest, node))
            add(node, RABO.country, d.country.upper() if d.country else None)
            add(node, RABO.plannedYears, d.planned_years)
            add(node, RABO.keepsDutchEmployer, d.keeps_dutch_employer)
            add(node, RABO.returnsToHome, d.returns_to_home)
            add(node, RABO.previousDiplomatLetting, d.previous_diplomat_letting)
            add(node, RABO.monthsLivedSinceReturn, d.months_lived_since_return)
        return g
