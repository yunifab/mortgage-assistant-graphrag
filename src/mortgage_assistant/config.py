"""Central settings, read once from the environment (.env).

Keeping every setting in one place makes it easy to see what the RAG baseline
uses, and to keep RAG and GraphRAG identical except for retrieval.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    # Paths
    pdf_path: Path = PROJECT_ROOT / "resources" / "pdfs" / "rabobank_mortgage.pdf"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    ground_truth_dir: Path = PROJECT_ROOT / "evaluation" / "ground_truth"
    results_dir: Path = PROJECT_ROOT / "evaluation" / "results"

    # Chunking
    chunk_max_chars: int = 1500
    chunk_overlap_chars: int = 200

    # Embeddings: "openai" (API) or "local" (sentence-transformers model on this laptop)
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "openai"))
    embedding_model: str = field(default_factory=lambda: os.getenv(
        "EMBEDDING_MODEL",
        "text-embedding-3-large" if os.getenv("EMBEDDING_PROVIDER", "openai") == "openai" else "BAAI/bge-m3"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # LLM (Groq)
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-oss-120b"))
    llm_temperature: float = 0.0
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))

    # Retrieval
    top_k: int = 5

    # Neo4j
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    neo4j_database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))
    vector_index_name: str = "chunk_embedding"


settings = Settings()
