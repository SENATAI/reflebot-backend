"""
Репозиторий для работы с привязками преподавателей к лекциям.
"""

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import TeacherLection
from ..schemas import (
    TeacherLectionCreateSchema,
    TeacherLectionReadSchema,
    TeacherLectionUpdateSchema,
)


class TeacherLectionRepositoryProtocol(
    BaseRepositoryProtocol[
        TeacherLection,
        TeacherLectionReadSchema,
        TeacherLectionCreateSchema,
        TeacherLectionUpdateSchema,
    ]
):
    """Протокол репозитория привязок преподавателей к лекциям."""
    pass


class TeacherLectionRepository(
    BaseRepositoryImpl[
        TeacherLection,
        TeacherLectionReadSchema,
        TeacherLectionCreateSchema,
        TeacherLectionUpdateSchema,
    ],
    TeacherLectionRepositoryProtocol,
):
    """Репозиторий для работы с привязками преподавателей к лекциям."""
    pass
