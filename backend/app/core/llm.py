"""LLM gateway — unified interface to multiple providers via LiteLLM.

Features:
- Provider routing: OpenAI, Anthropic Claude, DeepSeek
- Model fallback chain (primary → secondary)
- Token counting via tiktoken
- Token-bucket rate limiter
- Structured error handling with retries
- SSE-formatted streaming helper
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

import tiktoken
from litellm import acompletion, completion

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base exception for LLM gateway errors."""


class RateLimitExceeded(LLMError):
    """Token-bucket rate limit hit."""


class AllProvidersFailed(LLMError):
    """All provider attempts (primary + fallback) exhausted."""


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    KUAPAO = "kuaPao"
    MINIMAX = "miniMax"
    DASHSCOPE = "dashscope"


# ---------------------------------------------------------------------------
# Token bucket rate limiter
# ---------------------------------------------------------------------------

@dataclass
class TokenBucket:
    """Thread-safe token bucket for rate limiting.

    capacity: max tokens in bucket
    fill_rate: tokens added per second
    """

    capacity: float = 60.0
    fill_rate: float = 1.0  # tokens / second
    tokens: float | None = None  # None → start full
    last_fill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if self.tokens is None:
            self.tokens = self.capacity

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_fill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        self.last_fill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate-limited."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def acquire(self, tokens: float = 1.0) -> None:
        """Block until tokens become available."""
        while not self.consume(tokens):
            self._refill()
            wait = max(0.0, (tokens - self.tokens) / self.fill_rate)
            await asyncio.sleep(min(wait, 1.0))


# Singleton bucket — configured from settings
_rate_bucket = TokenBucket(
    capacity=float(settings.RATE_LIMIT_REQUESTS),
    fill_rate=float(settings.RATE_LIMIT_REQUESTS) / float(settings.RATE_LIMIT_WINDOW_SECONDS),
)


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

# Default encoding for token estimation
_token_encoder = tiktoken.get_encoding("cl100k_base")

# Provider-specific encodings
_ENCODING_MAP: dict[str, str] = {
    "gpt-4o": "o200k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}


def count_tokens(text: str, model: str | None = None) -> int:
    """Estimate token count for a given text and optional model."""
    encoding_name = _ENCODING_MAP.get(model or "", "cl100k_base")
    try:
        enc = tiktoken.get_encoding(encoding_name)
    except KeyError:
        enc = _token_encoder
    return len(enc.encode(text))


def count_message_tokens(messages: list[dict], model: str | None = None) -> int:
    """Estimate tokens for a list of chat messages."""
    total = 0
    for msg in messages:
        total += count_tokens(str(msg.get("content", "")), model)
        total += count_tokens(str(msg.get("role", "")), model)
        # Each message has ~4 tokens of framing overhead
        total += 4
    total += 2  # conversation framing
    return total


# ---------------------------------------------------------------------------
# Provider API key mapping
# ---------------------------------------------------------------------------

def _get_api_key(provider: str) -> str | None:
    mapping = {
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
        "kuaPao": settings.KUAPAO_API_KEY,
        "miniMax": settings.MINIMAX_API_KEY,
        "dashscope": settings.DASHSCOPE_API_KEY,
    }
    return mapping.get(provider)


def _get_api_base(provider: str) -> str | None:
    """Return custom base URL for providers that use relays/proxies."""
    mapping = {
        "kuaPao": settings.KUAPAO_BASE_URL,
        "miniMax": settings.MINIMAX_BASE_URL,
        "dashscope": settings.DASHSCOPE_BASE_URL,
    }
    return mapping.get(provider) or None


def _model_string(provider: str, model: str) -> str:
    """Build LiteLLM model identifier.

    Custom OpenAI-compatible relays (kuaPao, miniMax) use 'openai/' prefix
    so LiteLLM uses the OpenAI chat-completion protocol.
    """
    if provider in ("kuaPao", "miniMax", "dashscope"):
        return f"openai/{model}"
    return f"{provider}/{model}"


# ---------------------------------------------------------------------------
# Core async completion with fallback & retry
# ---------------------------------------------------------------------------

async def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    stream: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    provider: str | None = None,
    model: str | None = None,
):
    """Async chat completion with fallback chain and rate limiting.

    Args:
        messages: Chat messages list.
        tools: Optional tool definitions for function calling.
        stream: If True, return an async generator.
        temperature: LLM temperature override.
        max_tokens: Max tokens override.
        provider: Override the default provider (e.g. 'kuaPao', 'miniMax').
        model: Override the default model (e.g. 'gpt-5.4', 'miniMax').

    Returns:
        LiteLLM response object (or async generator if stream=True).
    """
    if temperature is None:
        temperature = settings.LLM_TEMPERATURE
    if max_tokens is None:
        max_tokens = settings.LLM_MAX_TOKENS

    # Rate-limit check (token-bucket)
    if not _rate_bucket.consume(1):
        raise RateLimitExceeded(
            f"Rate limit hit ({settings.RATE_LIMIT_REQUESTS} req / "
            f"{settings.RATE_LIMIT_WINDOW_SECONDS}s)"
        )

    # Resolve provider/model: runtime override > settings default
    use_provider = provider or settings.LLM_PROVIDER
    use_model = model or settings.LLM_MODEL

    providers: list[tuple[str, str]] = [
        (use_provider, use_model),
    ]
    fallback = (settings.LLM_FALLBACK_PROVIDER, settings.LLM_FALLBACK_MODEL)
    if fallback != providers[0]:
        providers.append(fallback)

    last_error: Exception | None = None

    for prov, mod in providers:
        api_key = _get_api_key(prov)
        api_base = _get_api_base(prov)
        kwargs: dict = dict(
            model=_model_string(prov, mod),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        if tools:
            kwargs["tools"] = tools
        if stream:
            kwargs["stream"] = True

        kwargs["timeout"] = settings.LLM_REQUEST_TIMEOUT

        for attempt in range(1, settings.LLM_MAX_RETRIES + 1):
            try:
                if stream:
                    return await acompletion(**kwargs)
                else:
                    return await acompletion(**kwargs)
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                # Permanent errors — skip retries, go straight to fallback
                is_permanent = any(kw in err_str for kw in (
                    "arrearage", "overdue", "insufficient_balance",
                    "invalid_api_key", "invalid authentication",
                    "access denied", "account", "billing",
                ))
                if is_permanent:
                    logger.warning(
                        "LLM provider %s/%s permanently unavailable: %s",
                        prov, mod, exc,
                    )
                    break  # skip remaining retries, go to next provider
                logger.warning(
                    "LLM attempt %d/%d for %s/%s failed: %s",
                    attempt, settings.LLM_MAX_RETRIES, prov, mod, exc,
                )
                if attempt < settings.LLM_MAX_RETRIES:
                    await asyncio.sleep(settings.LLM_RETRY_DELAY_SECONDS * attempt)

    raise AllProvidersFailed(
        f"All LLM providers failed. Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Synchronous completion (for non-async contexts)
# ---------------------------------------------------------------------------

def chat_completion_sync(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    provider: str | None = None,
    model: str | None = None,
):
    """Sync chat completion — for scripts / pre-loading prompts."""
    if temperature is None:
        temperature = settings.LLM_TEMPERATURE
    if max_tokens is None:
        max_tokens = settings.LLM_MAX_TOKENS

    if not _rate_bucket.consume(1):
        raise RateLimitExceeded(
            f"Rate limit hit ({settings.RATE_LIMIT_REQUESTS} req / "
            f"{settings.RATE_LIMIT_WINDOW_SECONDS}s)"
        )

    use_provider = provider or settings.LLM_PROVIDER
    use_model = model or settings.LLM_MODEL

    providers: list[tuple[str, str]] = [
        (use_provider, use_model),
    ]
    fallback = (settings.LLM_FALLBACK_PROVIDER, settings.LLM_FALLBACK_MODEL)
    if fallback != providers[0]:
        providers.append(fallback)

    last_error: Exception | None = None

    for prov, mod in providers:
        api_key = _get_api_key(prov)
        api_base = _get_api_base(prov)
        kwargs: dict = dict(
            model=_model_string(prov, mod),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        if tools:
            kwargs["tools"] = tools

        for attempt in range(1, settings.LLM_MAX_RETRIES + 1):
            try:
                return completion(**kwargs)
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                is_permanent = any(kw in err_str for kw in (
                    "arrearage", "overdue", "insufficient_balance",
                    "invalid_api_key", "invalid authentication",
                    "access denied", "account", "billing",
                ))
                if is_permanent:
                    logger.warning(
                        "LLM sync provider %s/%s permanently unavailable: %s",
                        prov, mod, exc,
                    )
                    break
                logger.warning(
                    "LLM sync attempt %d/%d for %s/%s failed: %s",
                    attempt, settings.LLM_MAX_RETRIES, prov, mod, exc,
                )
                time.sleep(settings.LLM_RETRY_DELAY_SECONDS * attempt)

    raise AllProvidersFailed(
        f"All LLM providers failed. Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------

async def stream_sse(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yields SSE-formatted chunks from the LLM streaming response.

    Usage::

        async for chunk in stream_sse(messages):
            yield chunk
    """
    response = await chat_completion(
        messages=messages,
        tools=tools,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
        provider=provider,
        model=model,
    )

    full_content: list[str] = []
    async for part in response:
        delta = part.get("choices", [{}])[0].get("delta", {})
        content = delta.get("content", "")
        if content:
            full_content.append(content)
            yield json.dumps({"type": "content", "content": content})

        # Tool call delta
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            yield json.dumps({"type": "tool_call", "tool_calls": tool_calls})

        # Finish reason
        finish = part.get("choices", [{}])[0].get("finish_reason")
        if finish:
            yield json.dumps({"type": "finish", "reason": finish})

    # Yield final aggregated content for DB persistence convenience
    yield json.dumps({
        "type": "done",
        "full_content": "".join(full_content),
        "token_usage": {
            "model": model or settings.LLM_MODEL,
            "estimated_tokens": count_tokens("".join(full_content), model or settings.LLM_MODEL),
        },
    })


# ---------------------------------------------------------------------------
# Model registry — available models exposed to the frontend
# ---------------------------------------------------------------------------

@dataclass
class ModelInfo:
    id: str          # unique key used in API calls (e.g. "deepseek", "kuaPao")
    name: str        # display name (e.g. "DeepSeek V4 Pro")
    provider: str    # backend provider key
    model: str       # model identifier
    description: str = ""
    available: bool = True


MODEL_REGISTRY: list[ModelInfo] = [
    ModelInfo(
        id="deepseek",
        name="DeepSeek V4 Pro",
        provider="deepseek",
        model=settings.LLM_MODEL if settings.LLM_MODEL != "gpt-4o" else "deepseek-v4-pro",
        description="1M context, 384K output — primary model",
    ),
    ModelInfo(
        id="kuaPao",
        name="KuaPao GPT-5.4",
        provider="kuaPao",
        model=settings.KUAPAO_MODEL,
        description="OpenAI-compatible relay at kuaipao.ai",
        available=bool(settings.KUAPAO_API_KEY),
    ),
    ModelInfo(
        id="miniMax",
        name="MiniMax-M2.7",
        provider="miniMax",
        model=settings.MINIMAX_MODEL,
        description="MiniMax M2.7 via relay",
        available=bool(settings.MINIMAX_API_KEY),
    ),
    ModelInfo(
        id="dashscope",
        name="阿里云千问 (Qwen)",
        provider="dashscope",
        model=settings.DASHSCOPE_MODEL,
        description="阿里云百炼 DashScope — qwen3.7-max 旗舰模型",
        available=bool(settings.DASHSCOPE_API_KEY),
    ),
]


def get_available_models() -> list[dict]:
    """Return the list of models that have API keys configured."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "provider": m.provider,
            "model": m.model,
            "description": m.description,
            "available": m.available,
        }
        for m in MODEL_REGISTRY
    ]
