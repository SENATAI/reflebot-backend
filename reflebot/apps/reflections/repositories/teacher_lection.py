"""
Репозиторий для работы с привязками преподавателей к лекциям.
"""

import uuid

from sqlalchemy.dialects.postgresql import insert

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

    async def bulk_create(
        self,
        create_objects: list[TeacherLectionCreateSchema],
    ) -> list[TeacherLectionReadSchema]:
        """Создать привязки преподаватель-лекция, пропуская уже существующие пары."""
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
                    index_elements=["teacher_id", "lection_session_id"],
                )
                .returning(self.model_type)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [
                self.read_schema_type.model_validate(model, from_attributes=True)
                for model in models
            ]
