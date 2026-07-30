import json

import httpx
import pytest
from pydantic import BaseModel

from techgrowth_api.config import Settings
from techgrowth_api.integrations.model_client import (
    ModelClient,
    ModelClientError,
    TokenBudgetExceeded,
)


class Answer(BaseModel):
    title: str
    source_ids: list[str]


@pytest.mark.asyncio
async def test_chat_and_embedding_requests_use_independent_providers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"title":"Task","source_ids":["s1"]}'}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}], "usage": {"total_tokens": 1}},
        )

    settings = Settings(
        chat_base_url="https://chat.example/v1",
        chat_api_key="chat-secret",
        chat_model="chat-model",
        embedding_base_url="https://embed.example/v1",
        embedding_api_key="embed-secret",
        embedding_model="embed-model",
    )
    client = ModelClient(settings, transport=httpx.MockTransport(handler))

    await client.structured("system", "user", Answer)
    await client.embedding("text")

    assert str(requests[0].url) == "https://chat.example/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer chat-secret"
    assert str(requests[1].url) == "https://embed.example/v1/embeddings"
    assert requests[1].headers["authorization"] == "Bearer embed-secret"


@pytest.mark.asyncio
async def test_missing_chat_configuration_only_blocks_chat() -> None:
    settings = Settings(
        embedding_base_url="https://embed.example/v1",
        embedding_api_key="embed-secret",
        embedding_model="embed-model",
    )
    client = ModelClient(settings)

    assert client.embedding_configured is True
    with pytest.raises(ModelClientError, match="Chat model provider"):
        await client.structured("system", "user", Answer)


@pytest.mark.asyncio
async def test_missing_embedding_configuration_only_blocks_embedding() -> None:
    settings = Settings(
        chat_base_url="https://chat.example/v1",
        chat_api_key="chat-secret",
        chat_model="chat-model",
    )
    client = ModelClient(settings)

    assert client.configured is True
    with pytest.raises(ModelClientError, match="Embedding model provider"):
        await client.embedding("text")


@pytest.mark.asyncio
async def test_natural_completion_uses_chat_provider() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "这是模型生成的真实回答"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5},
            },
        )

    client = ModelClient(
        Settings(
            chat_base_url="https://chat.example/v1",
            chat_api_key="chat-secret",
            chat_model="chat-model",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = await client.complete("system", "user")

    assert result == "这是模型生成的真实回答"
    assert str(requests[0].url) == "https://chat.example/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer chat-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_code"),
    [(401, "provider_auth"), (403, "provider_auth"), (429, "provider_rate_limited")],
)
async def test_natural_completion_normalizes_provider_errors(
    status_code: int, error_code: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "do not expose this"})

    client = ModelClient(
        Settings(
            chat_base_url="https://chat.example/v1",
            chat_api_key="chat-secret",
            chat_model="chat-model",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ModelClientError) as error:
        await client.complete("system", "user")

    assert error.value.code == error_code
    assert "do not expose this" not in str(error.value)


@pytest.mark.asyncio
async def test_structured_output_retries_invalid_json() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = "not json" if calls == 1 else json.dumps({"title": "Task", "source_ids": ["s1"]})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    settings = Settings(
        openai_base_url="https://model.example/v1",
        openai_api_key="secret",
        chat_model="agent-model",
        max_agent_tokens=100,
    )
    client = ModelClient(settings, transport=httpx.MockTransport(handler))

    result = await client.structured("system", "user", Answer)

    assert result.title == "Task"
    assert calls == 2


@pytest.mark.asyncio
async def test_structured_output_rejects_token_budget_overrun() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"title":"Task","source_ids":["s1"]}'}}],
                "usage": {"prompt_tokens": 90, "completion_tokens": 20},
            },
        )

    settings = Settings(
        openai_base_url="https://model.example/v1",
        openai_api_key="secret",
        chat_model="agent-model",
        max_agent_tokens=100,
    )
    client = ModelClient(settings, transport=httpx.MockTransport(handler))

    with pytest.raises(TokenBudgetExceeded):
        await client.structured("system", "user", Answer)


@pytest.mark.asyncio
async def test_structured_output_enforces_cumulative_daily_budget() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"title":"Task","source_ids":["s1"]}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    settings = Settings(
        openai_base_url="https://model.example/v1",
        openai_api_key="secret",
        chat_model="agent-model",
        max_agent_tokens=100,
        max_daily_tokens=25,
    )
    client = ModelClient(settings, transport=httpx.MockTransport(handler))

    await client.structured("system", "first", Answer)
    with pytest.raises(TokenBudgetExceeded, match="daily"):
        await client.structured("system", "second", Answer)
