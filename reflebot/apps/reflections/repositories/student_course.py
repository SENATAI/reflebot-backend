"""
Репозиторий для работы с привязками студентов к курсам.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import StudentCourse
from ..schemas import (
    StudentCourseCreateSchema,
    StudentCourseReadSchema,
    StudentCourseUpdateSchema,
)


class StudentCourseRepositoryProtocol(
    BaseRepositoryProtocol[
        StudentCourse,
        StudentCourseReadSchema,
        StudentCourseCreateSchema,
        StudentCourseUpdateSchema,
    ]
):
    """Протокол репозитория привязок студентов к курсам."""

    async def exists_by_student_and_course(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить наличие привязки студента к курсу."""
        ...


class StudentCourseRepository(
    BaseRepositoryImpl[
        StudentCourse,
        StudentCourseReadSchema,
        StudentCourseCreateSchema,
        StudentCourseUpdateSchema,
    ],
    StudentCourseRepositoryProtocol,
):
    """Репозиторий для работы с привязками студентов к курсам."""

    async def exists_by_student_and_course(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить наличие привязки студента к курсу."""
        async with self.session as s:
            stmt = sa.select(sa.exists().where(
                self.model_type.student_id == student_id,
                self.model_type.course_session_id == course_id,
            ))
            return bool((await s.execute(stmt)).scalar_one())

    async def bulk_create(
        self,
        create_objects: list[StudentCourseCreateSchema],
    ) -> list[StudentCourseReadSchema]:
        """Создать привязки студент-курс, пропуская уже существующие пары."""
        if len(create_objects) == 0:
            return []

        async with self.session as s, s.begin():
            stmt = (
                insert(self.model_type)
                .values(
                    [
                        {
                            **obj.model_dump(exclude_none=True, exclude={"id"}),
                            "id": uuid.uuid4(),
                        }
                        for obj in create_objects
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=["student_id", "course_session_id"],
                )
                .returning(self.model_type)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [
                self.read_schema_type.model_validate(model, from_attributes=True)
                for model in models
            ]
