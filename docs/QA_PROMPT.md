You are helping me build a ground-truth evaluation set for comparing vector search against GraphRAG. I will give you a PDF. Generate questions in four categories:

1. Single-hop: answerable from one passage. 
2. Two-hop: needs facts from two different sections or pages.
3. Multi-hop (3+): needs a chain of three or more facts across the document.
4. Comparison or aggregation: needs combining or contrasting information from several places.

Generate 10 questions per category.

Rules:
- Paraphrase. Do not reuse phrases from the document in the question.
- For two-hop and multi-hop, the evidence must come from clearly separate locations. If one paragraph could answer it, discard it.
- Do not write questions answerable from general knowledge.
- Vary entity types and question forms.

For each question return:
- category
- question
- answer
- evidence: exact quotes with page or section for each hop
- hop_reasoning: one or two sentences explaining why each piece of evidence is needed and why no single passage suffices

Output as JSON.