"""Stable model registry for all chat-capable LLM integrations."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ModelInfo:
    id: str          # stable model id used by the frontend / business layer
    name: str        # display name
    provider: str    # backend provider key
    model: str       # provider-native model identifier
    description: str = ""
    configured: bool = True


MODEL_REGISTRY: list[ModelInfo] = [
    ModelInfo(
        id="gpt55",
        name="GPT-5.5",
        provider="kuaPao",
        model=settings.KUAPAO_MODEL,
        description="OpenAI-compatible model relay",
        configured=bool(settings.KUAPAO_API_KEY),
    ),
    ModelInfo(
        id="gpt56",
        name="GPT-5.6",
        provider="kuaPao",
        model=settings.KUAPAO_GPT56_MODEL,
        description="OpenAI-compatible model relay — GPT-5.6",
        configured=bool(settings.KUAPAO_API_KEY),
    ),
    ModelInfo(
        id="gpt56-sol",
        name="GPT-5.6 sol",
        provider="kuaPao",
        model=settings.KUAPAO_SOL_MODEL,
        description="OpenAI-compatible model relay — GPT-5.6 sol",
        configured=bool(settings.KUAPAO_API_KEY),
    ),
    ModelInfo(
        id="gpt6-sol",
        name="GPT-6-sol",
        provider="kuaPao",
        model=settings.KUAPAO_GPT6_SOL_MODEL,
        description="OpenAI-compatible model relay — GPT-6-sol",
        configured=bool(settings.KUAPAO_API_KEY),
    ),
    ModelInfo(
        id="deepseek-v4ro",
        name="DeepSeek-v4ro",
        provider="deepseek",
        model=settings.DEEPSEEK_V4RO_MODEL,
        description="DeepSeek reasoning model",
        configured=bool(settings.DEEPSEEK_API_KEY),
    ),
]


def get_model_info(model_id: str | None) -> ModelInfo | None:
    """Resolve a stable model id to its registry entry."""
    if not model_id:
        return None
    aliases = {
        "kuaPao": "gpt55",
        "kuaPao-gpt56": "gpt56",
        "kuaPao-gpt56-sol": "gpt56-sol",
        "gpt-6-sol": "gpt6-sol",
        "DeepSeek-v4ro": "deepseek-v4ro",
    }
    model_id = aliases.get(model_id, model_id)
    for model in MODEL_REGISTRY:
        if model.id == model_id:
            return model
    return None
