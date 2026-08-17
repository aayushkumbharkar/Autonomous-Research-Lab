"""
Groq API Helper utilities with automatic multi-model fallback and rate-limit resilience.
"""

from groq import Groq
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("groq_helpers")

# ONLY active, supported, non-deprecated Groq production models
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "llama-3.2-3b-preview",
    "llama-3.2-1b-preview",
    "qwen-2.5-coder-32b",
]


def call_groq_with_fallback(
    messages: list[dict],
    preferred_model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    Calls Groq API chat completions trying preferred_model first (openai/gpt-oss-20b),
    falling back seamlessly to active non-deprecated models if a 429 TPD rate limit is encountered.
    """
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)

    primary = preferred_model or settings.groq_model
    candidate_models = [primary] + [m for m in FALLBACK_MODELS if m != primary]

    last_exception = None
    for model_id in candidate_models:
        try:
            logger.info("groq_api_call", model=model_id)
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
        except Exception as e:
            err_str = str(e)
            logger.warning("groq_model_failed_trying_fallback", model=model_id, error=err_str[:150])
            last_exception = e

    logger.error("all_groq_fallback_models_failed", last_error=str(last_exception))
    raise last_exception if last_exception else RuntimeError("Failed to obtain Groq LLM response")
