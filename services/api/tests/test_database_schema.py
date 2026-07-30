from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.sql.sqltypes import JSON

from techgrowth_api.models import RadarItemRecord


def test_radar_embedding_uses_pgvector_with_sqlite_json_fallback() -> None:
    column_type = RadarItemRecord.__table__.c.embedding.type

    assert isinstance(column_type.dialect_impl(postgresql.dialect()), Vector)
    assert isinstance(column_type.dialect_impl(sqlite.dialect()), JSON)

