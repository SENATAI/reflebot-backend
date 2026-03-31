"""
Сервис bounded scan для поиска кандидатов на запрос рефлексии.
"""

from datetime import datetime
from typing import Protocol

import sqlalchemy as sa

from ..enums import NotificationDeliveryType
from ..models import LectionSession, NotificationDelivery, Student, StudentLection
from ..repositories.student_lection import StudentLectionRepositoryProtocol
from ..schemas import ReflectionPromptCandidateSchema


class ReflectionPromptScanServiceProtocol(Protocol):
    """Протокол сервиса поиска due кандидатов."""

    async def find_due_candidates(
        self,
        now: datetime,
        limit: int,
    ) -> list[ReflectionPromptCandidateSchema]:
        """Найти bounded batch кандидатов для создания доставок."""
        ...


class ReflectionPromptScanService(ReflectionPromptScanServiceProtocol):
    """Сервис bounded scan для due запросов рефлексии."""

    def __init__(
        self,
        student_lection_repository: StudentLectionRepositoryProtocol,
        lookback_hours: int = 168,
    ):
        self.student_lection_repository = student_lection_repository
        self.lookback_hours = lookback_hours

    async def find_due_candidates(
        self,
        now: datetime,
        limit: int,
    ) -> list[ReflectionPromptCandidateSchema]:
        """Найти bounded batch кандидатов, исключая уже созданные доставки."""
        delivery_exists = sa.exists(
            sa.select(NotificationDelivery.id).where(
                NotificationDelivery.lection_session_id == StudentLection.lection_session_id,
                NotificationDelivery.student_id == StudentLection.student_id,
                NotificationDelivery.type == NotificationDeliveryType.REFLECTION_PROMPT,
            )
        )

        async with self.student_lection_repository.session as s:
            stmt = (
                sa.select(
                    StudentLection.lection_session_id,
                    StudentLection.student_id,
                    Student.telegram_id,
                    LectionSession.ended_at,
                )
                .join(Student, Student.id == StudentLection.student_id)
                .join(LectionSession, LectionSession.id == StudentLection.lection_session_id)
                .where(
                    LectionSession.ended_at <= now,
                    Student.is_active.is_(True),
                    Student.telegram_id.is_not(None),
                    ~delivery_exists,
                )
                .order_by(LectionSession.ended_at.asc(), StudentLection.student_id.asc())
                .limit(limit)
            )
            rows = (await s.execute(stmt)).all()

        return [
            ReflectionPromptCandidateSchema(
                lection_session_id=row.lection_session_id,
                student_id=row.student_id,
                telegram_id=row.telegram_id,
                scheduled_for=row.ended_at,
            )
            for row in rows
        ]
