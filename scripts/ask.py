"""Ask the RAG baseline one question from the command line.

Run:  uv run python scripts/ask.py "What is the maximum loan term?"
"""

import sys

from mortgage_assistant import rag, store


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('usage: uv run python scripts/ask.py "your question"')
    question = " ".join(sys.argv[1:])
    with store.get_driver() as driver:
        result = rag.answer(driver, question)

    print(f"\nQ: {question}\n\nA: {result.answer}\n")
    print("Retrieved chunks:")
    for c in result.chunks:
        print(f"  {c.score:.3f}  [{c.citation}]  {c.section_title}")
    print(f"\nmodel {result.model} | tokens in/out {result.prompt_tokens}/{result.completion_tokens} "
          f"| latency {result.latency_s}")


if __name__ == "__main__":
    main()
