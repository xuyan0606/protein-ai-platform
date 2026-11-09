"""Model availability and failover policy for the unified LLM gateway."""

from __future__ import annotations

from app.core.config import settings
from app.core.llm_registry import MODEL_REGISTRY

_runtime_unavailable_models: set[tuple[str, str]] = set()


def is_provider_enabled(provider: str) -> bool:
    disabled = {
        item.strip()
        for item in settings.LLM_DISABLED_PROVIDERS.split(",")
        if item.strip()
    }
    return provider not in disabled


def get_api_key(provider: str) -> str | None:
    mapping = {
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
        "kuaPao": settings.KUAPAO_API_KEY,
        "miniMax": settings.MINIMAX_API_KEY,
        "dashscope": settings.DASHSCOPE_API_KEY,
    }
    return mapping.get(provider)


def get_api_base(provider: str) -> str | None:
    mapping = {
        "kuaPao": settings.KUAPAO_BASE_URL,
        "miniMax": settings.MINIMAX_BASE_URL,
        "dashscope": settings.DASHSCOPE_BASE_URL,
    }
    return mapping.get(provider) or None


def mark_model_unavailable(provider: str, model: str) -> None:
    _runtime_unavailable_models.add((provider, model))


def is_model_available(provider: str, model: str) -> bool:
    return (
        bool(model.strip())
        and is_provider_enabled(provider)
        and bool(get_api_key(provider))
        and (provider, model) not in _runtime_unavailable_models
    )


def candidate_provider_chain(
    provider: str | None,
    model: str | None,
) -> list[tuple[str, str]]:
    """Build requested -> configured fallback -> other available models."""
    use_provider = provider or settings.LLM_PROVIDER
    use_model = model or settings.LLM_MODEL

    requested = (use_provider, use_model)
    fallback = (settings.LLM_FALLBACK_PROVIDER, settings.LLM_FALLBACK_MODEL)

    ordered: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(prov: str, mod: str) -> None:
        item = (prov, mod)
        if item in seen:
            return
        seen.add(item)
        if is_model_available(prov, mod):
            ordered.append(item)

    add(*requested)
    if fallback != requested:
        add(*fallback)

    for info in MODEL_REGISTRY:
        add(info.provider, info.model)

    return ordered


def model_string(provider: str, model: str) -> str:
    """Build the LiteLLM model identifier."""
    if provider in ("kuaPao", "miniMax", "dashscope"):
        return f"openai/{model}"
    return f"{provider}/{model}"
