"""Export the use-case question set to the RAG team's format (one file per language).

The master file evaluation/ground_truth/qa_usecases_full.json has everything (both languages, rule-engine
fields, the structured cases). The RAG team gets the same fields as qa_rabobank_en.json / qa_rabobank_nl.json:
id, category, question, answer, evidence, hop_reasoning. Edit the master file, then run this script.

Run:  uv run python scripts/export_usecase_qa.py
"""

import json
from pathlib import Path

GT = Path(__file__).resolve().parents[1] / "evaluation" / "ground_truth"
MASTER = GT / "qa_usecases_full.json"
CATEGORIES = ["single-hop", "two-hop", "multi-hop", "comparison-aggregation", "unanswerable"]

META = {
    "en": {
        "language": "en",
        "paired_file": "qa_usecases_nl.json (same ids, Dutch question/answer/hop_reasoning)",
        "status": "DRAFT: answers must be reviewed by a person (ideally a mortgage expert) before use",
        "about": "72 questions derived from 9 use cases (ids UC1-01 ... UC9-08, 8 per use case). Many describe a client's "
                 "application and ask whether it is acceptable; the use cases are explained in docs/USE_CASES.md.",
        "unanswerable": "Category 'unanswerable': the policy does not contain the answer, or the question lacks facts "
                        "needed to decide. A correct answer says so (and names what is missing) instead of guessing.",
        "page_numbering": "page = physical PDF page (1-95), not the printed page label",
        "quote_normalization": "Quotes are copied from the PDF text. Line-break hyphenation and whitespace were joined.",
    },
    "nl": {
        "language": "nl",
        "paired_file": "qa_usecases_en.json (zelfde ids, Engelse vraag/antwoord/hop_reasoning)",
        "status": "CONCEPT: antwoorden moeten door een persoon (bij voorkeur een hypotheekexpert) worden gecontroleerd voor gebruik",
        "about": "72 vragen afgeleid van 9 use cases (ids UC1-01 ... UC9-08, 8 per use case). Veel vragen beschrijven een "
                 "aanvraag en vragen of die acceptabel is; de use cases staan uitgelegd in docs/USE_CASES.md.",
        "unanswerable": "Categorie 'unanswerable': het beleid bevat het antwoord niet, of de vraag mist feiten die nodig "
                        "zijn om te beslissen. Een goed antwoord zegt dat (en noemt wat ontbreekt) in plaats van te gokken.",
        "page_numbering": "page = fysieke PDF-pagina (1-95), niet het gedrukte paginanummer",
        "quote_normalization": "Citaten zijn overgenomen uit de PDF-tekst. Afbrekingen en witruimte zijn samengevoegd.",
    },
}


def export(master: dict, lang: str) -> dict:
    m = master["metadata"]
    metadata = {"source_document": m["source_document"], **META[lang], "created": m["created"],
                "categories": CATEGORIES}
    questions = [{"id": q["id"], "category": q["category"], "question": q[f"question_{lang}"],
                  "answer": q[f"answer_{lang}"], "evidence": q["evidence"], "hop_reasoning": q[f"hop_reasoning_{lang}"]}
                 for q in master["questions"]]
    return {"metadata": metadata, "questions": questions}


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    for lang in ("en", "nl"):
        path = GT / f"qa_usecases_{lang}.json"
        path.write_text(json.dumps(export(master, lang), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"written {path.name}: {len(master['questions'])} questions")


if __name__ == "__main__":
    main()
