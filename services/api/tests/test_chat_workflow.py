import pytest

from techgrowth_api.chat_workflow import (
    ChatIntentDecision,
    ChatWorkflowService,
)
from techgrowth_api.services.chat_context import ChatContextService
from techgrowth_api.tools import ToolRegistry


class FakeModel:
    def __init__(self, decision: ChatIntentDecision) -> None:
        self.decision = decision
        self.prompts: list[str] = []

    async def structured(self, system_prompt, user_prompt, output_model):
        self.prompts.append(user_prompt)
        return self.decision

    async def complete(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        return "基于当前证据，这是具体建议。"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent",
    [
        "technical_qa",
        "task_coaching",
        "submission_improvement",
        "growth_planning",
        "radar_to_task",
    ],
)
async def test_chat_workflow_routes_five_supported_intents(client, intent: str) -> None:
    model = FakeModel(ChatIntentDecision(intent=intent, confidence=0.9))
    workflow = ChatWorkflowService(
        model, ChatContextService(client.app.state.database.session_factory)
    )

    result = await workflow.run("请帮助我", {"view": "today"})

    assert result.intent == intent
    assert result.answer == "基于当前证据，这是具体建议。"


@pytest.mark.asyncio
async def test_chat_workflow_falls_back_to_technical_qa_on_low_confidence(client) -> None:
    model = FakeModel(ChatIntentDecision(intent="growth_planning", confidence=0.2))
    workflow = ChatWorkflowService(
        model, ChatContextService(client.app.state.database.session_factory)
    )

    result = await workflow.run("不确定的问题", {})

    assert result.intent == "technical_qa"
    assert result.needs_action is False


@pytest.mark.asyncio
async def test_only_radar_intent_can_propose_a_write_action(client) -> None:
    model = FakeModel(
        ChatIntentDecision(intent="radar_to_task", confidence=0.95, needs_action=True)
    )
    workflow = ChatWorkflowService(
        model, ChatContextService(client.app.state.database.session_factory)
    )

    result = await workflow.run("把这个雷达条目转成任务", {"radar_item_id": "radar-1"})

    assert result.action == {
        "action_type": "create_task_from_radar",
        "radar_item_id": "radar-1",
    }


class NativeToolModel(FakeModel):
    def __init__(self):
        super().__init__(ChatIntentDecision(intent="growth_planning", confidence=0.95))
        self.round = 0

    async def complete_with_tools(self, system_prompt, user_prompt, tools, messages=None):
        from techgrowth_api.integrations.model_client import ModelToolCall, ToolCompletion

        self.round += 1
        if self.round == 1:
            return ToolCompletion(
                content=None,
                tool_calls=[ModelToolCall("call-1", "get_active_curriculum", {})],
            )
        return ToolCompletion(content="你当前的主路线是 Java。", tool_calls=[])


@pytest.mark.asyncio
async def test_chat_workflow_executes_read_tools_before_answering(client) -> None:
    workflow = ChatWorkflowService(
        NativeToolModel(),
        ChatContextService(client.app.state.database.session_factory),
        ToolRegistry.from_services(client.app.state.services),
        session_id="session-1",
    )

    result = await workflow.run("我现在学哪条路线？", {"view": "curriculum"})

    assert result.answer == "你当前的主路线是 Java。"
    assert [event["type"] for event in result.tool_events] == ["tool_call", "tool_result"]
    assert result.tool_events[1]["result"]["active_track_key"] == "java"
