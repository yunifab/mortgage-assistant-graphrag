"""The concept layer: English/Dutch labels and synonyms from the ontology.

Used for two things:
1. Case extraction: the LLM gets the allowed values together with the words that mean them
   (e.g. houseboat = woonboot, woonark, woonschip).
2. Retrieval: a question that uses a synonym ('houseboat', 'woonark') is expanded with the
   policy's own Dutch term ('woonboot met vaste ligplaats') before the vector search.
"""

import re
from functools import lru_cache

from rdflib import Graph
from rdflib.namespace import SKOS

from mortgage_assistant.rules.case import (CHANNELS, COLLATERAL_TYPES, CONDITIONS, EXPLAIN_TYPES, LEGAL_RIGHTS,
                                           LOAN_PART_TYPES, NEW_BUILD_KINDS, VALUATIONS, ZONINGS)
from mortgage_assistant.rules.engine import ontology_graph


def _graph() -> Graph:
    return ontology_graph()


def labels(term) -> dict[str, list[str]]:
    """{'en': [...], 'nl': [...]} with preferred labels first, then synonyms."""
    g = _graph()
    out: dict[str, list[str]] = {"en": [], "nl": []}
    for prop in (SKOS.prefLabel, SKOS.altLabel):
        for lit in g.objects(term, prop):
            lang = lit.language if lit.language in out else "en"
            if str(lit) not in out[lang]:
                out[lang].append(str(lit))
    return out


def allowed_values_text() -> str:
    """The enumerated fields of the case schema, each value with its English/Dutch words."""
    types = {k: v for k, v in COLLATERAL_TYPES.items() if k != "rental_home"}  # letting is collateral.partly_let
    groups = [("collateral type", types), ("new build kind", NEW_BUILD_KINDS), ("legal right", LEGAL_RIGHTS),
              ("valuation type", VALUATIONS),
              ("loan part type", LOAN_PART_TYPES), ("explain type", EXPLAIN_TYPES),
              ("channel", CHANNELS), ("conditions", CONDITIONS), ("zoning", ZONINGS)]
    lines = []
    for name, choices in groups:
        lines.append(f"{name}:")
        for key, term in choices.items():
            words = labels(term)
            lines.append(f'  "{key}": ' + "; ".join(words["en"] + words["nl"]))
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _synonym_index() -> list[tuple[re.Pattern, str]]:
    """(pattern for any label, the Dutch policy term to add) for every concept with a Dutch label."""
    g = _graph()
    index = []
    for term in set(g.subjects(SKOS.prefLabel, None)):
        words = labels(term)
        if not words["nl"]:
            continue
        policy_term = words["nl"][0]
        for w in words["en"] + words["nl"][1:]:
            if len(w) >= 4:
                index.append((re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)", re.IGNORECASE), policy_term))
    return index


def expand_query(question: str) -> tuple[str, list[str]]:
    """Add the policy's Dutch terms for concepts mentioned in the question (returns the new query + added terms)."""
    added = []
    for pattern, policy_term in _synonym_index():
        if pattern.search(question) and policy_term not in added and policy_term.lower() not in question.lower():
            added.append(policy_term)
    return (f"{question}\n({'; '.join(added)})" if added else question), added
