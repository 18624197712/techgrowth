from sqlalchemy import select

from ..models import SkillEvidenceRecord, SkillProfileRecord, WeeklyReviewRecord


class WeeklyService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def generate(self) -> WeeklyReviewRecord:
        with self.session_factory() as db:
            evidence = db.scalars(
                select(SkillEvidenceRecord)
                .order_by(SkillEvidenceRecord.created_at.desc())
                .limit(20)
            ).all()
            skills = db.scalars(select(SkillProfileRecord)).all()
            names = [skill.name for skill in skills]
            review = WeeklyReviewRecord(
                summary=(
                    f"本周记录了 {len(evidence)} 条有效证据，覆盖 {len(skills)} 项技能。"
                    if evidence
                    else "本周还没有通过审阅的成长证据。"
                ),
                evidence_ids=[item.id for item in evidence],
                next_focus=names[:3] or ["完成首次 AI Agent 实战任务"],
            )
            db.add(review)
            db.commit()
            return review
