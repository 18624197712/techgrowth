from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select

from ..domain.curriculum import CURRICULUM, CurriculumNode
from ..models import CurriculumStateRecord, LearningTaskRecord

PRIMARY_TRACK_KEYS = ("java", "python_ai", "go", "node_ts")
STAGE_KEYS = ("foundation", "practice", "production", "architecture")
STAGE_LABELS = {
    "foundation": "初级",
    "practice": "中级",
    "production": "高级",
    "architecture": "架构师",
}


@dataclass(frozen=True, slots=True)
class CurriculumState:
    active_track_key: str
    target_stage: str
    algorithm_days_per_week: int
    catalog_version: str


@dataclass(frozen=True, slots=True)
class TrackProgress:
    track_key: str
    label: str
    completed_nodes: int
    total_nodes: int
    current_stage: str


class CurriculumService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def state(self) -> CurriculumState:
        with self.session_factory() as db:
            record = db.scalar(select(CurriculumStateRecord).limit(1))
            if record is None:
                record = CurriculumStateRecord()
                db.add(record)
                db.commit()
            return self._state(record)

    def switch_track(self, track_key: str) -> CurriculumState:
        if track_key not in PRIMARY_TRACK_KEYS:
            raise ValueError("主路线必须是 Java、Python/AI、Go 或 Node.js/TypeScript")
        with self.session_factory() as db:
            record = self._record(db)
            record.active_track_key = track_key
            record.updated_at = datetime.now(UTC)
            db.commit()
            return self._state(record)

    def set_algorithm_frequency(self, days_per_week: int) -> CurriculumState:
        if not 0 <= days_per_week <= 7:
            raise ValueError("算法任务频率必须在每周 0 到 7 天之间")
        with self.session_factory() as db:
            record = self._record(db)
            record.algorithm_days_per_week = days_per_week
            record.updated_at = datetime.now(UTC)
            db.commit()
            return self._state(record)

    def set_target_stage(self, stage_key: str) -> CurriculumState:
        if stage_key not in STAGE_KEYS:
            raise ValueError("课程难度必须是初级、中级、高级或架构师")
        with self.session_factory() as db:
            record = self._record(db)
            record.target_stage = stage_key
            record.updated_at = datetime.now(UTC)
            db.commit()
            return self._state(record)

    def progress(self) -> list[TrackProgress]:
        with self.session_factory() as db:
            completed = set(
                db.scalars(
                    select(LearningTaskRecord.node_key).where(LearningTaskRecord.status == "passed")
                ).all()
            )
        result = []
        for track in CURRICULUM.tracks:
            count = sum(node.key in completed for node in track.nodes)
            current = next(
                (node for node in track.nodes if node.key not in completed), track.nodes[-1]
            )
            result.append(
                TrackProgress(track.key, track.label, count, len(track.nodes), current.stage_key)
            )
        return result

    def next_node(self, on_date: date) -> CurriculumNode:
        state = self.state()
        track_key = (
            "algorithms"
            if self._algorithm_day(on_date, state.algorithm_days_per_week)
            else state.active_track_key
        )
        with self.session_factory() as db:
            tasks = list(
                db.scalars(select(LearningTaskRecord).order_by(LearningTaskRecord.created_at)).all()
            )
        remediation = next(
            (
                task
                for task in reversed(tasks)
                if task.status == "remediation"
                and task.node_key != "legacy"
                and task.track_key == track_key
                and task.stage_key == state.target_stage
            ),
            None,
        )
        if remediation is not None:
            try:
                return CURRICULUM.node(remediation.node_key)
            except StopIteration:
                pass
        completed = {task.node_key for task in tasks if task.status == "passed"}
        stage_nodes = [
            node
            for node in CURRICULUM.track(track_key).nodes
            if node.stage_key == state.target_stage
        ]
        stage_node_keys = {node.key for node in stage_nodes}
        for node in stage_nodes:
            required_in_stage = {key for key in node.prerequisites if key in stage_node_keys}
            if node.key not in completed and required_in_stage <= completed:
                return node
        raise ValueError("当前路线所选难度的课程节点已全部完成，请选择下一难度")

    def payload(self) -> dict:
        state = self.state()
        progress = {item.track_key: item for item in self.progress()}
        completed = self._completed_nodes()
        return {
            **asdict(state),
            "tracks": [
                {
                    "key": track.key,
                    "label": track.label,
                    "kind": "secondary" if track.key == "algorithms" else "primary",
                    "completed_nodes": progress[track.key].completed_nodes,
                    "total_nodes": progress[track.key].total_nodes,
                    "current_stage": progress[track.key].current_stage,
                    "stages": [
                        {
                            "key": stage_key,
                            "label": STAGE_LABELS[stage_key],
                            "nodes": [
                                {
                                    "key": node.key,
                                    "order": node.order,
                                    "title": node.title,
                                    "completed": node.key in completed,
                                }
                                for node in track.nodes
                                if node.stage_key == stage_key
                            ],
                        }
                        for stage_key in STAGE_KEYS
                    ],
                }
                for track in CURRICULUM.tracks
            ],
        }

    @staticmethod
    def _algorithm_day(on_date: date, days_per_week: int) -> bool:
        if days_per_week == 0:
            return False
        scheduled = {round(index * 7 / days_per_week) % 7 for index in range(days_per_week)}
        return on_date.weekday() in scheduled

    @staticmethod
    def _state(record: CurriculumStateRecord) -> CurriculumState:
        return CurriculumState(
            record.active_track_key,
            record.target_stage,
            record.algorithm_days_per_week,
            record.catalog_version,
        )

    def _completed_nodes(self) -> set[str]:
        with self.session_factory() as db:
            return set(
                db.scalars(
                    select(LearningTaskRecord.node_key).where(
                        LearningTaskRecord.status == "passed"
                    )
                ).all()
            )

    @staticmethod
    def _record(db) -> CurriculumStateRecord:
        record = db.scalar(select(CurriculumStateRecord).limit(1))
        if record is None:
            record = CurriculumStateRecord()
            db.add(record)
            db.flush()
        return record
