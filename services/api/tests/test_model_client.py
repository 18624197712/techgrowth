import json

import httpx
import pytest
from pydantic import BaseModel

from techgrowth_api.config import Settings
from techgrowth_api.integrations.model_client import ModelClient, TokenBudgetExceeded


class Answer(BaseModel):
    title: str
    source_ids: list[str]


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
