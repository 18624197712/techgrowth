from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.sql.sqltypes import JSON

from techgrowth_api.models import (
    AgentActionRecord,
    AgentRunRecord,
    LearningTaskRecord,
    RadarItemRecord,
)


def test_radar_embedding_uses_pgvector_with_sqlite_json_fallback() -> None:
    column_type = RadarItemRecord.__table__.c.embedding.type

    assert isinstance(column_type.dialect_impl(postgresql.dialect()), Vector)
    assert isinstance(column_type.dialect_impl(sqlite.dialect()), JSON)


def test_curriculum_and_agent_tables_expose_required_columns() -> None:
    task_columns = set(LearningTaskRecord.__table__.c.keys())
    assert {
        "curriculum_version",
        "track_key",
        "stage_key",
        "node_key",
        "prerequisites",
        "deliverables",
        "acceptance_checks",
        "remediation_hint",
        "generation_source",
    } <= task_columns
    assert {"session_id", "action_type", "payload", "status", "expires_at"} <= set(
        AgentActionRecord.__table__.c.keys()
    )
    assert "details" in AgentRunRecord.__table__.c
