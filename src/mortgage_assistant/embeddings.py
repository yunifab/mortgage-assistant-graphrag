"""Text -> vectors. Two interchangeable providers, chosen with EMBEDDING_PROVIDER in .env:

- "openai" (default): text-embedding-3-large via the OpenAI API. Multilingual,
  nothing to download, costs about $0.13 per million tokens (the whole policy is ~0.1M).
- "local": a sentence-transformers model on this laptop, e.g. BGE-M3 (~2.3 GB download).

Both give normalised vectors (length 1), so cosine similarity is just a dot product.
Important: the index and the questions must use the SAME model. After switching,
rebuild the index with scripts/build_index.py.
"""

from functools import lru_cache

from mortgage_assistant.config import settings

OPENAI_BATCH = 64  # texts per API request
LOCAL_MAX_TOKENS = 1024  # our chunks are <= 1500 characters, well below this


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env (see .env.example).")
    return OpenAI(api_key=settings.openai_api_key, max_retries=5)


@lru_cache(maxsize=1)
def _local_model():
    from sentence_transformers import SentenceTransformer  # heavy import, only when used

    model = SentenceTransformer(settings.embedding_model)
    model.max_seq_length = LOCAL_MAX_TOKENS
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "openai":
        vectors: list[list[float]] = []
        for i in range(0, len(texts), OPENAI_BATCH):
            response = _openai_client().embeddings.create(model=settings.embedding_model,
                                                          input=texts[i:i + OPENAI_BATCH])
            vectors += [d.embedding for d in response.data]  # OpenAI vectors are already normalised
        return vectors
    if settings.embedding_provider == "local":
        return _local_model().encode(texts, batch_size=16, normalize_embeddings=True,
                                     show_progress_bar=len(texts) > 16).tolist()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER '{settings.embedding_provider}' (use 'openai' or 'local')")


def embed_query(question: str) -> list[float]:
    return embed_texts([question])[0]
