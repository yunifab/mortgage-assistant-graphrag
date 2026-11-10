"""Free text -> case facts (JSON) with the LLM. The rule engine then does the checking.

This is the only place where the LLM touches the facts. To keep it honest:
- the prompt says: only facts that are explicitly stated, no guessing;
- the output is validated against the allowed values; invalid values are dropped (and reported);
- the extracted facts are shown to the advisor, so a wrong extraction is visible and can be corrected.
"""

import json
import re

from mortgage_assistant import llm
from mortgage_assistant.config import settings
from mortgage_assistant.rules.case import (CHANNELS, COLLATERAL_TYPES, CONDITIONS, EXPLAIN_TYPES, LEGAL_RIGHTS,
                                           LOAN_PART_TYPES, NEW_BUILD_KINDS, VALUATIONS, ZONINGS, Case)
from mortgage_assistant.rules.concepts import allowed_values_text


def _prompt() -> str:
    text = (settings.prompts_dir / "case_extraction_system.md").read_text(encoding="utf-8")
    return text.replace("{allowed_values}", allowed_values_text())


def _clean(d: dict) -> tuple[dict, list[str]]:
    """Drop values that are not allowed, so the rule engine never sees an unknown term."""
    dropped = []

    def keep(container: dict, key: str, choices: dict):
        if key in container and container[key] not in choices:
            dropped.append(f"{key}={container[key]!r}")
            container.pop(key)

    keep(d, "channel", CHANNELS), keep(d, "conditions", CONDITIONS)
    if c := d.get("collateral"):
        keep(c, "type", COLLATERAL_TYPES), keep(c, "valuation", VALUATIONS), keep(c, "zoning", ZONINGS)
        keep(c, "new_build", NEW_BUILD_KINDS), keep(c, "legal_right", LEGAL_RIGHTS)
    if loan := d.get("loan"):
        parts = []
        for p in loan.get("parts", []) or []:
            if p.get("type") in LOAN_PART_TYPES and isinstance(p.get("amount"), (int, float)):
                parts.append(p)
            else:
                dropped.append(f"loan part {p}")
        loan["parts"] = parts
    if (e := d.get("energy")) and "value_before_renovation" in e:
        # the value before renovation is the market value of the collateral (policy 1.3)
        before = e.pop("value_before_renovation")
        d.setdefault("collateral", {}).setdefault("market_value", before)
        if d["collateral"]["market_value"] == e.get("value_after_renovation"):
            d["collateral"]["market_value"] = before
    if reqs := d.get("explain_requests"):
        d["explain_requests"] = [r for r in reqs if r in EXPLAIN_TYPES]
        dropped += [f"explain={r!r}" for r in reqs if r not in EXPLAIN_TYPES]
    return d, dropped


# Words that must appear in the text before we accept an extracted valuation type (grounding check)
VALUATION_EVIDENCE = {
    "desktop": ["desktop", "calcasa"], "desktop_plus": ["desktop", "calcasa"],
    "valuation_report": ["valuation report", "taxatierapport", "nwwi", "full valuation", "validated"],
    "emci": ["e.m.c.i", "emci"], "nrvt": ["nrvt"], "lav": ["lav", "plausibili"],
    "business_valuation": ["business valuation", "bedrijfsmatig", "rabobank bedrijven", "business property"],
    "construction_costs": ["construction cost", "stichtingskosten", "aanneemsom", "contract sum", "building costs"],
}


def _ground(d: dict, text: str) -> list[str]:
    """Drop extracted facts that the text does not support. Returns notes about what was dropped."""
    notes, low = [], text.lower()
    c = d.get("collateral") or {}
    v = c.get("valuation")
    if v and not any(w in low for w in VALUATION_EVIDENCE.get(v, [])):
        c.pop("valuation")
        notes.append(f"valuation={v!r} (not stated in the text)")
    return notes


def has_facts(d: dict) -> bool:
    return any(d.get(k) for k in ("applicants", "collateral", "loan", "energy", "explain_requests", "diplomat", "rrr"))


def extract_case(text: str, model: str | None = None) -> tuple[Case | None, dict, list[str]]:
    """(case or None if the text is not a case, the raw extracted JSON, dropped values)."""
    raw = llm.chat(_prompt(), text, model=model, temperature=0.0).text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        data = {}
    data, dropped = _clean(data)
    dropped += _ground(data, text)
    if not has_facts(data):
        return None, data, dropped
    return Case.from_dict(data), data, dropped
