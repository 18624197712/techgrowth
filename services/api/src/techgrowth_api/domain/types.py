from enum import StrEnum


class SkillLevel(StrEnum):
    DISCOVERING = "discovering"
    PRACTICING = "practicing"
    APPLIED = "applied"
    PROFICIENT = "proficient"


class TaskStatus(StrEnum):
    READY = "ready"
    SUBMITTED = "submitted"
    PASSED = "passed"
    REMEDIATION = "remediation"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
