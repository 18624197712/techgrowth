from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..models import AgentActionRecord, LearningTaskRecord
from ..schemas import SyncJobRequest
from ..tools import (
    AlgorithmFrequencyArguments,
    RadarTaskArguments,
    RegenerateTaskArguments,
    RepositorySyncArguments,
    SwitchTrackArguments,
)


class ChatActionError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ChatActionService:
    ARGUMENT_MODELS = {
        "regenerate_today_task": RegenerateTaskArguments,
        "switch_primary_track": SwitchTrackArguments,
        "set_algorithm_frequency": AlgorithmFrequencyArguments,
        "create_task_from_radar": RadarTaskArguments,
        "request_repository_sync": RepositorySyncArguments,
    }

    def __init__(
        self, session_factory, daily_tasks, growth, radar, curriculum=None, connector=None
    ) -> None:
        self.session_factory = session_factory
        self.daily_tasks = daily_tasks
        self.growth = growth
        self.radar = radar
        self.curriculum = curriculum
        self.connector = connector

    def create(self, session_id: str, action: dict) -> dict:
        action_type = str(action.get("action_type", ""))
        model = self.ARGUMENT_MODELS.get(action_type)
        if model is None:
            raise ChatActionError("不支持的导师操作", 400)
        raw_arguments = action.get("arguments") or {
            key: value for key, value in action.items() if key != "action_type"
        }
        try:
            arguments = model.model_validate(raw_arguments).model_dump(mode="json")
        except ValueError as exc:
            raise ChatActionError("导师操作参数无效", 422) from exc
        summary = self._summary(action_type, arguments)
        if action_type == "create_task_from_radar":
            radar = self.radar.get(str(arguments["radar_item_id"]))
            if radar is None:
                raise ChatActionError("技术雷达条目不存在", 404)
            summary = f"基于“{radar.title}”创建课程兼容任务"
        if action_type == "regenerate_today_task":
            task = self.growth.today_task()
            if task is None:
                raise ChatActionError("今日任务不存在", 404)
            arguments["task_id"] = task.id
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        with self.session_factory() as db:
            item = AgentActionRecord(
                session_id=session_id,
                action_type=action_type,
                payload={"arguments": arguments},
                status="pending",
                expires_at=expires_at,
            )
            db.add(item)
            db.commit()
            return {
                "id": item.id,
                "action_type": action_type,
                "summary": summary,
                "expires_at": item.expires_at.isoformat(),
            }

    async def confirm(self, action_id: str, session_id: str):
        with self.session_factory() as db:
            item = db.scalar(
                select(AgentActionRecord).where(AgentActionRecord.id == action_id).with_for_update()
            )
            if item is None or item.session_id != session_id:
                raise ChatActionError("导师操作不存在", 404)
            if item.status == "executed":
                if item.payload.get("result_task_id"):
                    task = self.growth.get_task(str(item.payload["result_task_id"]))
                    if task is None:
                        raise ChatActionError("已执行操作的结果不存在", 409)
                    return task
                return item.payload.get("result", {})
            if item.status != "pending":
                raise ChatActionError("导师操作已取消或正在执行", 409)
            expires_at = (
                item.expires_at if item.expires_at.tzinfo else item.expires_at.replace(tzinfo=UTC)
            )
            if expires_at <= datetime.now(UTC):
                item.status = "expired"
                db.commit()
                raise ChatActionError("导师操作已过期", 410)
            action_type = item.action_type
            arguments = dict(item.payload.get("arguments", {}))
            item.status = "executing"
            db.commit()
        try:
            result = await self._execute(action_id, action_type, arguments)
        except (ValueError, LookupError) as exc:
            with self.session_factory() as db:
                item = db.get(AgentActionRecord, action_id)
                item.status = "pending"
                db.commit()
            raise ChatActionError(str(exc), 409) from exc
        with self.session_factory() as db:
            item = db.get(AgentActionRecord, action_id)
            if isinstance(result, LearningTaskRecord):
                item.payload = {**item.payload, "result_task_id": result.id}
            else:
                item.payload = {**item.payload, "result": result}
            item.status = "executed"
            db.commit()
        return result

    async def _execute(self, action_id: str, action_type: str, arguments: dict):
        if action_type == "create_task_from_radar":
            return await self.daily_tasks.generate_from_radar(arguments["radar_item_id"])
        if action_type == "regenerate_today_task":
            return await self.daily_tasks.regenerate(
                arguments["task_id"], arguments["reason"], f"chat-{action_id}"
            )
        if action_type == "switch_primary_track":
            self.curriculum.switch_track(arguments["track_key"])
            return self.curriculum.payload()
        if action_type == "set_algorithm_frequency":
            self.curriculum.set_algorithm_frequency(arguments["days_per_week"])
            return self.curriculum.payload()
        if action_type == "request_repository_sync":
            repository = next(
                (
                    item
                    for item in self.connector.list_repositories()
                    if item.id == arguments["repository_id"]
                ),
                None,
            )
            if repository is None:
                raise LookupError("Repository not found")
            job = self.connector.queue_job(
                repository.device_id,
                SyncJobRequest(
                    kind="repository_metadata",
                    payload={"repository_id": repository.id},
                    idempotency_key=f"chat-sync-{action_id}",
                ),
            )
            return {"job_id": job.id, "status": job.status}
        raise ValueError("不支持的导师操作")

    @staticmethod
    def _summary(action_type: str, arguments: dict) -> str:
        if action_type == "switch_primary_track":
            return f"将主路线切换为 {arguments['track_key']}，保留其他路线进度"
        if action_type == "set_algorithm_frequency":
            return f"将算法任务频率设为每周 {arguments['days_per_week']} 天"
        if action_type == "regenerate_today_task":
            return f"重新生成今日任务：{arguments['reason']}"
        if action_type == "request_repository_sync":
            return "请求连接器同步指定仓库"
        return "创建课程兼容的雷达任务"

    def cancel(self, action_id: str, session_id: str) -> dict:
        with self.session_factory() as db:
            item = db.get(AgentActionRecord, action_id)
            if item is None or item.session_id != session_id:
                raise ChatActionError("导师操作不存在", 404)
            if item.status == "pending":
                item.status = "cancelled"
                db.commit()
            return {"id": item.id, "status": item.status}
