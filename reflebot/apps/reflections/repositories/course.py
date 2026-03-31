"""
Репозиторий для работы с курсами.
"""

from sqlalchemy import select

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import CourseSession
from ..schemas import CourseSessionCreateSchema, CourseSessionReadSchema, CourseSessionUpdateSchema


class CourseSessionRepositoryProtocol(
    BaseRepositoryProtocol[CourseSession, CourseSessionReadSchema, CourseSessionCreateSchema, CourseSessionUpdateSchema]
):
    """Протокол репозитория курсов."""

    async def get_by_join_code(self, join_code: str) -> CourseSessionReadSchema:
        """Получить курс по коду."""
        ...

    async def get_by_join_code_or_none(self, join_code: str) -> CourseSessionReadSchema | None:
        """Получить курс по коду или None."""
        ...


class CourseSessionRepository(
    BaseRepositoryImpl[CourseSession, CourseSessionReadSchema, CourseSessionCreateSchema, CourseSessionUpdateSchema],
    CourseSessionRepositoryProtocol,
):
    """Репозиторий для работы с курсами."""

    async def get_by_join_code(self, join_code: str) -> CourseSessionReadSchema:
        """Получить курс по коду."""
        async with self.session as s:
            statement = select(self.model_type).where(self.model_type.join_code == join_code)
            model = (await s.execute(statement)).scalar_one_or_none()
            if model is None:
                raise ModelFieldNotFoundException(self.model_type, "join_code", join_code)
            return self.read_schema_type.model_validate(model, from_attributes=True)

    async def get_by_join_code_or_none(self, join_code: str) -> CourseSessionReadSchema | None:
        """Получить курс по коду или None."""
        try:
            return await self.get_by_join_code(join_code)
        except ModelFieldNotFoundException:
            return None
    pass
