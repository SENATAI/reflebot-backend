"""
Сервис для логирования действий студента.
"""

import uuid
from typing import Protocol

from ..repositories.student_history_log import StudentHistoryLogRepositoryProtocol
from ..schemas import StudentHistoryLogCreateSchema, StudentHistoryLogReadSchema


class StudentHistoryLogServiceProtocol(Protocol):
    """Протокол сервиса логов действий студента."""

    async def log_action(
        self,
        student_id: uuid.UUID,
        action: str,
    ) -> StudentHistoryLogReadSchema:
        """Записать действие студента в историю."""
        ...


class StudentHistoryLogService(StudentHistoryLogServiceProtocol):
    """Сервис логирования действий студента."""

    def __init__(self, repository: StudentHistoryLogRepositoryProtocol):
        self.repository = repository

    async def log_action(
        self,
        student_id: uuid.UUID,
        action: str,
    ) -> StudentHistoryLogReadSchema:
        """Записать действие студента в историю."""
        return await self.repository.create(
            StudentHistoryLogCreateSchema(
                student_id=student_id,
                action=action,
            ),
        )

