"""
Репозиторий для логов действий студентов.
"""

from typing import Protocol

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import StudentHistoryLog
from ..schemas import (
    StudentHistoryLogCreateSchema,
    StudentHistoryLogReadSchema,
    StudentHistoryLogUpdateSchema,
)


class StudentHistoryLogRepositoryProtocol(
    BaseRepositoryProtocol[
        StudentHistoryLog,
        StudentHistoryLogReadSchema,
        StudentHistoryLogCreateSchema,
        StudentHistoryLogUpdateSchema,
    ],
    Protocol,
):
    """Протокол репозитория логов действий студентов."""


class StudentHistoryLogRepository(
    BaseRepositoryImpl[
        StudentHistoryLog,
        StudentHistoryLogReadSchema,
        StudentHistoryLogCreateSchema,
        StudentHistoryLogUpdateSchema,
    ],
    StudentHistoryLogRepositoryProtocol,
):
    """Репозиторий логов действий студентов."""

