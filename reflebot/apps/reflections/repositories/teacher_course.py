"""
Репозиторий для работы с привязками преподавателей к курсам.
"""

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import TeacherCourse
from ..schemas import TeacherCourseCreateSchema, TeacherCourseReadSchema, TeacherCourseUpdateSchema


class TeacherCourseRepositoryProtocol(
    BaseRepositoryProtocol[
        TeacherCourse,
        TeacherCourseReadSchema,
        TeacherCourseCreateSchema,
        TeacherCourseUpdateSchema,
    ]
):
    """Протокол репозитория привязок преподавателей к курсам."""
    pass


class TeacherCourseRepository(
    BaseRepositoryImpl[
        TeacherCourse,
        TeacherCourseReadSchema,
        TeacherCourseCreateSchema,
        TeacherCourseUpdateSchema,
    ],
    TeacherCourseRepositoryProtocol,
):
    """Репозиторий для работы с привязками преподавателей к курсам."""
    pass
