"""Unified model-id based gateway for business-facing LLM calls."""

from __future__ import annotations

from app.core.llm_policy import is_model_available
from app.core.llm_registry import MODEL_REGISTRY, get_model_info


class LLMGateway:
    """Single integration interface for all chat-capable models."""

    def list_models(self) -> list[dict]:
        return [
            {
                "id": model.id,
                "name": model.name,
                "provider": "model-relay" if model.provider == "kuaPao" else model.provider,
                "model": model.model,
                "description": model.description,
                "available": is_model_available(model.provider, model.model),
            }
            for model in MODEL_REGISTRY
        ]

    def resolve(self, model_id: str | None):
        model = get_model_info(model_id)
        if not model:
            return None
        if not is_model_available(model.provider, model.model):
            return None
        return model

    async def complete(
        self,
        messages: list[dict],
        *,
        model_id: str | None = None,
        tools: list[dict] | None = None,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        from app.core.llm import chat_completion

        model = self.resolve(model_id)
        return await chat_completion(
            messages=messages,
            tools=tools,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            provider=model.provider if model else None,
            model=model.model if model else None,
        )

    def complete_sync(
        self,
        messages: list[dict],
        *,
        model_id: str | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        from app.core.llm import chat_completion_sync

        model = self.resolve(model_id)
        return chat_completion_sync(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            provider=model.provider if model else None,
            model=model.model if model else None,
        )


llm_gateway = LLMGateway()


def get_available_models() -> list[dict]:
    return llm_gateway.list_models()
