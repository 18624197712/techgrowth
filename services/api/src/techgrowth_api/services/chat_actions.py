from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..models import AgentActionRecord


class ChatActionError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ChatActionService:
    def __init__(self, session_factory, daily_tasks, growth, radar) -> None:
        self.session_factory = session_factory
        self.daily_tasks = daily_tasks
        self.growth = growth
        self.radar = radar

    def create(self, session_id: str, action: dict) -> dict:
        if action.get("action_type") != "create_task_from_radar":
            raise ChatActionError("不支持的导师操作", 400)
        radar_id = str(action.get("radar_item_id", ""))
        radar = self.radar.get(radar_id)
        if radar is None:
            raise ChatActionError("技术雷达条目不存在", 404)
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        with self.session_factory() as db:
            item = AgentActionRecord(
                session_id=session_id,
                action_type="create_task_from_radar",
                payload={"radar_item_id": radar_id},
                status="pending",
                expires_at=expires_at,
            )
            db.add(item)
            db.commit()
            return {
                "id": item.id,
                "summary": f"基于“{radar.title}”创建课程兼容任务",
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
                task = self.growth.get_task(str(item.payload.get("result_task_id", "")))
                if task is None:
                    raise ChatActionError("已执行操作的结果不存在", 409)
                return task
            if item.status != "pending":
                raise ChatActionError("导师操作已取消或正在执行", 409)
            expires_at = (
                item.expires_at if item.expires_at.tzinfo else item.expires_at.replace(tzinfo=UTC)
            )
            if expires_at <= datetime.now(UTC):
                item.status = "expired"
                db.commit()
                raise ChatActionError("导师操作已过期", 410)
            radar_item_id = str(item.payload["radar_item_id"])
            item.status = "executing"
            db.commit()
        try:
            task = await self.daily_tasks.generate_from_radar(radar_item_id)
        except (ValueError, LookupError) as exc:
            with self.session_factory() as db:
                item = db.get(AgentActionRecord, action_id)
                item.status = "pending"
                db.commit()
            raise ChatActionError(str(exc), 409) from exc
        with self.session_factory() as db:
            item = db.get(AgentActionRecord, action_id)
            item.payload = {**item.payload, "result_task_id": task.id}
            item.status = "executed"
            db.commit()
        return task

    def cancel(self, action_id: str, session_id: str) -> dict:
        with self.session_factory() as db:
            item = db.get(AgentActionRecord, action_id)
            if item is None or item.session_id != session_id:
                raise ChatActionError("导师操作不存在", 404)
            if item.status == "pending":
                item.status = "cancelled"
                db.commit()
            return {"id": item.id, "status": item.status}
