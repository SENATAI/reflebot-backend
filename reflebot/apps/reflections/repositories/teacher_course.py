"""
Репозиторий для работы с привязками преподавателей к курсам.
"""

import uuid

import sqlalchemy as sa

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

    async def exists_by_teacher_and_course(
        self,
        teacher_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить наличие привязки преподавателя к курсу."""
        ...

    async def get_teacher_ids_by_course(self, course_id: uuid.UUID) -> list[uuid.UUID]:
        """Получить идентификаторы всех преподавателей курса."""
        ...


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

    async def exists_by_teacher_and_course(
        self,
        teacher_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить наличие привязки преподавателя к курсу."""
        async with self.session as s:
            stmt = sa.select(
                sa.exists().where(
                    self.model_type.teacher_id == teacher_id,
                    self.model_type.course_session_id == course_id,
                )
            )
            return bool((await s.execute(stmt)).scalar_one())

    async def get_teacher_ids_by_course(self, course_id: uuid.UUID) -> list[uuid.UUID]:
        """Получить идентификаторы преподавателей, привязанных к курсу."""
        async with self.session as s:
            stmt = sa.select(self.model_type.teacher_id).where(
                self.model_type.course_session_id == course_id,
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())
