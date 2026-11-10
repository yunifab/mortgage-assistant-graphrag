"""The LLM call (Groq). Kept in one small function so the provider is easy to swap."""

import re
from dataclasses import dataclass
from functools import lru_cache

from groq import Groq

from mortgage_assistant.config import settings


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


@lru_cache(maxsize=1)
def _client() -> Groq:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env (see .env.example).")
    return Groq(api_key=settings.groq_api_key, max_retries=5)


def chat(system: str, user: str, model: str | None = None, temperature: float | None = None) -> LLMResult:
    response = _client().chat.completions.create(
        model=model or settings.llm_model,
        temperature=settings.llm_temperature if temperature is None else temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    usage = response.usage
    text = response.choices[0].message.content or ""
    # Reasoning models (e.g. Qwen) may put their thinking in <think> tags: keep only the answer
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return LLMResult(
        text=text,
        model=response.model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )
