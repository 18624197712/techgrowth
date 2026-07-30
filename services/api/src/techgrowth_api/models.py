import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    totp_secret_enc: Mapped[str] = mapped_column(Text)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    recovery_hashes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24), default="preauth")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class LoginAttemptRecord(Base):
    __tablename__ = "login_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), index=True)
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    successful: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkillProfileRecord(Base):
    __tablename__ = "skill_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(24), default="discovering")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkillEvidenceRecord(Base):
    __tablename__ = "skill_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skill_profiles.id", ondelete="CASCADE"))
    submission_id: Mapped[str] = mapped_column(String(36), index=True)
    accepted: Mapped[bool] = mapped_column(Boolean)
    repo_linked: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CurriculumStateRecord(Base):
    __tablename__ = "curriculum_state"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    active_track_key: Mapped[str] = mapped_column(String(40), default="java")
    algorithm_days_per_week: Mapped[int] = mapped_column(Integer, default=2)
    catalog_version: Mapped[str] = mapped_column(String(24), default="v2")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RadarItemRecord(Base):
    __tablename__ = "radar_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(120))
    topic: Mapped[str] = mapped_column(String(120), index=True)
    credibility: Mapped[float] = mapped_column(Float, default=0.8)
    relevance: Mapped[float] = mapped_column(Float, default=0.8)
    relevance_reason: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON().with_variant(Vector(1536), "postgresql"), nullable=True
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningTaskRecord(Base):
    __tablename__ = "learning_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(180))
    topic: Mapped[str] = mapped_column(String(120), index=True)
    skill_name: Mapped[str] = mapped_column(String(120), index=True)
    expected_minutes: Mapped[int] = mapped_column(Integer)
    objective: Mapped[str] = mapped_column(Text)
    curriculum_version: Mapped[str] = mapped_column(String(24), default="legacy")
    track_key: Mapped[str] = mapped_column(String(40), default="legacy")
    stage_key: Mapped[str] = mapped_column(String(40), default="legacy")
    node_key: Mapped[str] = mapped_column(String(120), default="legacy", index=True)
    prerequisites: Mapped[list[str]] = mapped_column(JSON, default=list)
    instructions: Mapped[list[str]] = mapped_column(JSON)
    source_ids: Mapped[list[str]] = mapped_column(JSON)
    submission_kinds: Mapped[list[str]] = mapped_column(JSON)
    deliverables: Mapped[list[str]] = mapped_column(JSON, default=list)
    acceptance_checks: Mapped[list[dict]] = mapped_column(JSON, default=list)
    rubric: Mapped[list[dict]] = mapped_column(JSON)
    remediation_hint: Mapped[str] = mapped_column(Text, default="")
    task_kind: Mapped[str] = mapped_column(String(24), default="coding")
    learning_objectives: Mapped[list[str]] = mapped_column(JSON, default=list)
    theory_brief: Mapped[str] = mapped_column(Text, default="")
    problem_statement: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[list[str]] = mapped_column(JSON, default=list)
    starter_context: Mapped[str] = mapped_column(Text, default="")
    hints: Mapped[list[str]] = mapped_column(JSON, default=list)
    revealed_hint_level: Mapped[int] = mapped_column(Integer, default=0)
    solution_outline: Mapped[str] = mapped_column(Text, default="")
    solution_revealed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaces_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    regeneration_reason: Mapped[str] = mapped_column(Text, default="")
    regeneration_key: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(24), default="ready")
    is_remediation: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubmissionRecord(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="CASCADE"))
    summary: Mapped[str] = mapped_column(Text)
    artifact_kind: Mapped[str] = mapped_column(String(40))
    artifact_reference: Mapped[str] = mapped_column(Text)
    self_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewRecord(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"))
    passed: Mapped[bool] = mapped_column(Boolean)
    overall_score: Mapped[float] = mapped_column(Float)
    criterion_scores: Mapped[list[dict]] = mapped_column(JSON)
    feedback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WeeklyReviewRecord(Base):
    __tablename__ = "weekly_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    summary: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    next_focus: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PairingCodeRecord(Base):
    __tablename__ = "pairing_codes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectorDeviceRecord(Base):
    __tablename__ = "connector_devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    public_key: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConnectorNonceRecord(Base):
    __tablename__ = "connector_nonces"
    nonce: Mapped[str] = mapped_column(String(120), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncJobRecord(Base):
    __tablename__ = "sync_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(ForeignKey("connector_devices.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UploadArtifactRecord(Base):
    __tablename__ = "upload_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("sync_jobs.id"), index=True)
    relative_path: Mapped[str] = mapped_column(Text)
    encrypted_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationPreferenceRecord(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel: Mapped[str] = mapped_column(String(24))
    event: Mapped[str] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    destination_enc: Mapped[str] = mapped_column(Text, default="")


class PushSubscriptionRecord(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subscription_enc: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationDeliveryRecord(Base):
    __tablename__ = "notification_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event: Mapped[str] = mapped_column(String(40), index=True)
    channel: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(24))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    references: Mapped[list[str]] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentActionRecord(Base):
    __tablename__ = "agent_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSettingRecord(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_enc: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RepositoryRecord(Base):
    __tablename__ = "repositories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(24), default="connector")
    provider_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    external_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    canonical_remote: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    local_fingerprint: Mapped[str] = mapped_column(String(300), default="")
    match_status: Mapped[str] = mapped_column(String(24), default="unmatched", index=True)
    name: Mapped[str] = mapped_column(String(200))
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    languages: Mapped[dict] = mapped_column(JSON, default=dict)
    last_commit: Mapped[str] = mapped_column(String(80), default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
