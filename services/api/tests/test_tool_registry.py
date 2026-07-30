import pytest

from techgrowth_api.tools import ToolContext, ToolRegistry, UnknownToolError

EXPECTED_TOOLS = {
    "get_active_curriculum",
    "get_skill_gaps",
    "get_today_task",
    "get_radar_digest",
    "get_repository_metrics",
    "get_growth_evidence",
    "regenerate_today_task",
    "switch_primary_track",
    "set_algorithm_frequency",
    "create_task_from_radar",
    "request_repository_sync",
}


def test_registry_exposes_only_approved_tools(client) -> None:
    registry = ToolRegistry.from_services(client.app.state.services)

    assert set(registry.names) == EXPECTED_TOOLS
    definitions = registry.openai_definitions()
    assert {item["function"]["name"] for item in definitions} == EXPECTED_TOOLS
    assert all(item["type"] == "function" for item in definitions)


@pytest.mark.asyncio
async def test_read_tool_executes_without_confirmation(client) -> None:
    registry = ToolRegistry.from_services(client.app.state.services)

    result = await registry.invoke(
        "get_active_curriculum", {}, ToolContext(session_id="session", page_context={})
    )

    assert result.kind == "result"
    assert result.result["active_track_key"] == "java"
    assert result.action is None


@pytest.mark.asyncio
async def test_write_tool_returns_validated_confirmation_proposal(client) -> None:
    registry = ToolRegistry.from_services(client.app.state.services)

    result = await registry.invoke(
        "switch_primary_track",
        {"track_key": "go", "api_key": "must-not-survive"},
        ToolContext(session_id="session", page_context={}),
    )

    assert result.kind == "proposal"
    assert result.action == {
        "action_type": "switch_primary_track",
        "arguments": {"track_key": "go"},
    }
    assert client.app.state.services.curriculum.state().active_track_key == "java"


@pytest.mark.asyncio
async def test_registry_rejects_unknown_tool(client) -> None:
    registry = ToolRegistry.from_services(client.app.state.services)

    with pytest.raises(UnknownToolError):
        await registry.invoke("read_server_files", {"path": "/etc"}, ToolContext("session", {}))
